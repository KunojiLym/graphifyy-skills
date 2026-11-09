"""Safe sidecar writes: confine outputs, reject dangling symlinks, atomic replace.

On POSIX with ``dir_fd`` support, create/replace/unlink are anchored to validated
directory file descriptors (``O_DIRECTORY`` / ``O_NOFOLLOW`` walk from ``allowed_roots``),
which closes the parent-symlink swap (TOCTOU) race between validation and I/O.

On platforms without ``dir_fd`` (notably Windows), the same path checks run but the
race guarantee is **best-effort** only: containment is re-verified immediately before
each operation.
"""
from __future__ import annotations

import errno
import os
import secrets
import stat
import sys
import tempfile
from pathlib import Path
from typing import Callable

# Tests may set this to simulate a symlink swap after the parent dir fd is opened.
_race_test_hook: Callable[[], None] | None = None


class UnsafeOutputError(ValueError):
    """Refuse to write when the target path is outside scope or unsafe."""


def _posix_dir_fd_enabled() -> bool:
    if sys.platform == "win32":
        return False
    if not hasattr(os, "O_DIRECTORY"):
        return False
    needed = (os.open, os.mkdir, os.unlink, os.stat)
    if not all(fn in os.supports_dir_fd for fn in needed):
        return False
    try:
        import inspect

        sig = inspect.signature(os.replace)
    except (TypeError, ValueError):
        return False
    return "src_dir_fd" in sig.parameters and "dst_dir_fd" in sig.parameters


_POSIX_DIR_FD = _posix_dir_fd_enabled()


def _parent_resolved_contained(child: Path, parent_root: Path) -> bool:
    """True when the resolved parent directory is under parent_root."""
    try:
        resolved_parent = child.parent.resolve(strict=False)
        resolved_parent.relative_to(parent_root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _pick_allowed_root(path: Path, *, allowed_roots: tuple[Path, ...]) -> Path:
    absolute = path.absolute()
    for root in allowed_roots:
        if _parent_resolved_contained(absolute, root):
            return root.resolve()
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


def assert_output_allowed(path: Path, *, allowed_roots: tuple[Path, ...]) -> Path:
    """Ensure output path parent (resolved) sits under allowed roots; final name stays lexical."""
    if ".." in path.parts:
        raise UnsafeOutputError(f"refusing path with '..': {path}")

    _pick_allowed_root(path, allowed_roots=allowed_roots)
    return path


def _open_dir_component(name: str, *, base_fd: int) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return os.open(name, flags, dir_fd=base_fd)


def _mkdir_component(name: str, *, base_fd: int) -> None:
    if hasattr(os, "mkdir") and os.mkdir in os.supports_dir_fd:
        os.mkdir(name, mode=0o755, dir_fd=base_fd)
        return
    raise OSError(errno.ENOTSUP, "mkdir with dir_fd not supported")


def _anchor_parent_dir_fd(path: Path, *, allowed_roots: tuple[Path, ...]) -> tuple[int, str]:
    """Return ``(parent_dir_fd, dest_basename)``. Caller must ``os.close`` the fd."""
    dest = assert_output_allowed(path, allowed_roots=allowed_roots)
    root = _pick_allowed_root(dest, allowed_roots=allowed_roots)
    parent = dest.parent.resolve(strict=False)
    rel_parent = parent.relative_to(root)
    root_flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        root_flags |= os.O_NOFOLLOW
    fd = os.open(root, root_flags)
    try:
        for part in rel_parent.parts:
            if part in (".", ""):
                continue
            try:
                next_fd = _open_dir_component(part, base_fd=fd)
            except FileNotFoundError:
                _mkdir_component(part, base_fd=fd)
                next_fd = _open_dir_component(part, base_fd=fd)
            os.close(fd)
            fd = next_fd
    except OSError as exc:
        os.close(fd)
        raise UnsafeOutputError(f"cannot anchor directory for {path}: {exc}") from exc
    return fd, dest.name


def _write_via_dir_fd(parent_fd: int, dest_name: str, text: str) -> None:
    suffix = Path(dest_name).suffix
    tmp_name = f".graphify-sidecar-{secrets.token_hex(8)}{suffix}"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    tmp_fd = os.open(tmp_name, flags, mode=0o644, dir_fd=parent_fd)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            tmp_fd = -1  # fdopen took ownership
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, dest_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
    except Exception:
        try:
            os.unlink(tmp_name, dir_fd=parent_fd)
        except OSError:
            pass
        raise


def _unlink_via_dir_fd(parent_fd: int, name: str) -> None:
    try:
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return
        raise
    if stat.S_ISDIR(st.st_mode):
        raise UnsafeOutputError(f"refusing to remove directory: {name}")
    os.unlink(name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def safe_unlink(path: Path, *, allowed_roots: tuple[Path, ...]) -> bool:
    """Remove a generated sidecar only if it is a regular file under an allowed root."""
    if not path.exists() and not path.is_symlink():
        return False
    assert_output_allowed(path, allowed_roots=allowed_roots)

    if _POSIX_DIR_FD:
        parent_fd, name = _anchor_parent_dir_fd(path, allowed_roots=allowed_roots)
        try:
            if _race_test_hook:
                _race_test_hook()
            try:
                st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                return False
            if not (stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)):
                raise UnsafeOutputError(f"refusing to remove non-file: {path}")
            _unlink_via_dir_fd(parent_fd, name)
            return True
        finally:
            os.close(parent_fd)

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

    if _POSIX_DIR_FD:
        parent_fd, dest_name = _anchor_parent_dir_fd(dest, allowed_roots=allowed_roots)
        try:
            if _race_test_hook:
                _race_test_hook()
            try:
                st = os.stat(dest_name, dir_fd=parent_fd, follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    raise UnsafeOutputError(f"refusing to overwrite directory: {dest}")
            except FileNotFoundError:
                pass
            _write_via_dir_fd(parent_fd, dest_name, text)
        finally:
            os.close(parent_fd)
        return

    # Fallback (Windows): re-verify immediately before each filesystem call.
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    assert_output_allowed(dest, allowed_roots=allowed_roots)

    if dest.exists() or dest.is_symlink():
        if dest.is_dir():
            raise UnsafeOutputError(f"refusing to overwrite directory: {dest}")
        if not (dest.is_file() or dest.is_symlink()):
            raise UnsafeOutputError(f"refusing to overwrite special file: {dest}")

    assert_output_allowed(dest, allowed_roots=allowed_roots)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".graphify-sidecar-", suffix=dest.suffix, dir=parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        assert_output_allowed(dest, allowed_roots=allowed_roots)
        os.replace(tmp_path, dest)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
