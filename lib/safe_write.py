"""Safe sidecar writes: confine outputs, reject dangling symlinks, atomic replace."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


class UnsafeOutputError(ValueError):
    """Refuse to write when the target path is outside scope or unsafe."""


def _is_within(child: Path, parent: Path) -> bool:
    """Containment without following a symlink in the final path component."""
    try:
        child.absolute().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def assert_output_allowed(path: Path, *, allowed_roots: tuple[Path, ...]) -> Path:
    """Ensure the output path sits under an allowed root (symlink location, not target)."""
    absolute = path.absolute()
    for root in allowed_roots:
        if _is_within(absolute, root.resolve()):
            return path
    raise UnsafeOutputError(
        f"refusing to write outside allowed roots: {path} (absolute {absolute})"
    )


def safe_unlink(path: Path, *, allowed_roots: tuple[Path, ...]) -> bool:
    """Remove a generated sidecar only if it is a regular file under an allowed root."""
    if not path.exists() and not path.is_symlink():
        return False
    assert_output_allowed(path, allowed_roots=allowed_roots)
    if path.is_symlink():
        path.unlink()
        return True
    if not path.is_file():
        raise UnsafeOutputError(f"refusing to remove non-file: {path}")
    path.unlink()
    return True


def safe_write_text(path: Path, text: str, *, allowed_roots: tuple[Path, ...]) -> None:
    """Atomically write UTF-8 text; never follow a symlink target outside allowed roots."""
    dest = assert_output_allowed(path, allowed_roots=allowed_roots)
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() or dest.is_symlink():
        if dest.is_symlink():
            # Replace the symlink itself (do not write through to an external target).
            dest.unlink()
        elif dest.is_dir():
            raise UnsafeOutputError(f"refusing to overwrite directory: {dest}")
        elif not dest.is_file():
            raise UnsafeOutputError(f"refusing to overwrite special file: {dest}")

    fd, tmp_name = tempfile.mkstemp(
        prefix=".graphify-sidecar-", suffix=dest.suffix, dir=parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        # Same-directory replace avoids races with concurrent readers.
        os.replace(tmp_path, dest)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
