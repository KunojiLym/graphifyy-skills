"""Safe sidecar writes: confine outputs, reject dangling symlinks, atomic replace."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


class UnsafeOutputError(ValueError):
    """Refuse to write when the target path is outside scope or unsafe."""


def _parent_resolved_contained(child: Path, parent_root: Path) -> bool:
    """True when the resolved parent directory is under parent_root."""
    try:
        resolved_parent = child.parent.resolve(strict=False)
        resolved_parent.relative_to(parent_root.resolve())
        return True
    except (ValueError, OSError):
        return False


def assert_output_allowed(path: Path, *, allowed_roots: tuple[Path, ...]) -> Path:
    """Ensure output path parent (resolved) sits under allowed roots; final name stays lexical.

    The last path component is not resolved so a sidecar symlink can be replaced via
    ``os.replace`` without writing through to an external target.
    """
    if ".." in path.parts:
        raise UnsafeOutputError(f"refusing path with '..': {path}")

    absolute = path.absolute()
    for root in allowed_roots:
        if _parent_resolved_contained(absolute, root):
            return path
    try:
        resolved_parent = absolute.parent.resolve(strict=False)
    except OSError as exc:
        resolved_parent = absolute.parent
        parent_note = f" (parent resolve failed: {exc})"
    else:
        parent_note = f" (resolved parent {resolved_parent})"
    raise UnsafeOutputError(
        f"refusing to write outside allowed roots: {path}{parent_note}"
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
    # Re-check after mkdir: a symlinked segment in parent could redirect the tree.
    assert_output_allowed(dest, allowed_roots=allowed_roots)

    if dest.exists() or dest.is_symlink():
        if dest.is_dir():
            raise UnsafeOutputError(f"refusing to overwrite directory: {dest}")
        if dest.is_file() or dest.is_symlink():
            pass  # os.replace below atomically replaces file or symlink
        else:
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
        # Replace file or symlink inode atomically; do not unlink dest before this.
        os.replace(tmp_path, dest)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
