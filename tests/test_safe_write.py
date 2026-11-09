from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from lib.safe_write import (
    UnsafeOutputError,
    _fsync_dir_best_effort,
    assert_output_allowed,
    safe_unlink,
    safe_write_text,
)


def test_fsync_dir_best_effort_ignores_einval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError(errno.EINVAL, "fuse")))
    _fsync_dir_best_effort(99)


def test_fsync_dir_best_effort_reraises_eio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError(errno.EIO, "disk")))
    with pytest.raises(OSError) as exc:
        _fsync_dir_best_effort(99)
    assert exc.value.errno == errno.EIO


def test_write_succeeds_when_dir_fsync_einval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nb.ipynb.py"
    real_fsync = os.fsync
    calls: list[int] = []

    def counted_fsync(fd: int) -> None:
        calls.append(fd)
        if len(calls) >= 2:
            raise OSError(errno.EINVAL, "dir fsync rejected")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counted_fsync)
    safe_write_text(target, "ok", allowed_roots=(tmp_path,))
    assert target.read_text(encoding="utf-8") == "ok"
    assert len(calls) >= 2


def test_unlink_succeeds_when_dir_fsync_einval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "drop.ipynb.py"
    target.write_text("x", encoding="utf-8")

    def dir_fsync_einval(fd: int) -> None:
        raise OSError(errno.EINVAL, "dir fsync rejected")

    monkeypatch.setattr(os, "fsync", dir_fsync_einval)
    assert safe_unlink(target, allowed_roots=(tmp_path,)) is True


def test_write_confined_to_root(tmp_path: Path) -> None:
    target = tmp_path / "a" / "file.ipynb.py"
    safe_write_text(target, "hello", allowed_roots=(tmp_path,))
    assert target.read_text(encoding="utf-8") == "hello"


def test_refuses_path_outside_root(tmp_path: Path, tmp_path_factory) -> None:
    other = tmp_path_factory.mktemp("other")
    outside_target = other / "owned.txt"
    with pytest.raises(UnsafeOutputError):
        safe_write_text(outside_target, "nope", allowed_roots=(tmp_path,))


def test_dangling_symlink_to_outside_not_overwritten(tmp_path: Path, tmp_path_factory) -> None:
    victim_dir = tmp_path_factory.mktemp("victim")
    victim = victim_dir / "secret.txt"
    victim.write_text("original", encoding="utf-8")

    link = tmp_path / "trap.ipynb.py"
    link.symlink_to(victim)

    safe_write_text(link, "sidecar", allowed_roots=(tmp_path,))
    assert not link.exists() or link.is_file()
    if link.is_file():
        assert link.read_text(encoding="utf-8") == "sidecar"
    assert victim.read_text(encoding="utf-8") == "original"


def test_legitimate_rerun_overwrites_same_file(tmp_path: Path) -> None:
    target = tmp_path / "nb.ipynb.py"
    safe_write_text(target, "v1", allowed_roots=(tmp_path,))
    safe_write_text(target, "v2", allowed_roots=(tmp_path,))
    assert target.read_text(encoding="utf-8") == "v2"


def test_refuses_dotdot_components(tmp_path: Path) -> None:
    target = tmp_path / "a" / ".." / "b" / "file.ipynb.py"
    with pytest.raises(UnsafeOutputError):
        safe_write_text(target, "nope", allowed_roots=(tmp_path,))


def test_refuses_symlinked_parent_escape(
    tmp_path: Path, tmp_path_factory
) -> None:
    outside = tmp_path_factory.mktemp("outside")
    outdir = tmp_path / "mirror"
    outdir.mkdir()
    nested = outdir / "nested"
    nested.symlink_to(outside, target_is_directory=True)
    target = nested / "side.ipynb.py"
    with pytest.raises(UnsafeOutputError):
        safe_write_text(target, "escape", allowed_roots=(tmp_path,))


def test_symlink_sidecar_replaced_without_touching_target(
    tmp_path: Path, tmp_path_factory
) -> None:
    victim_dir = tmp_path_factory.mktemp("victim")
    victim = victim_dir / "secret.txt"
    victim.write_text("original", encoding="utf-8")
    link = tmp_path / "nb.ipynb.py"
    link.symlink_to(victim)
    safe_write_text(link, "replaced", allowed_roots=(tmp_path,))
    assert link.is_file() and not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "replaced"
    assert victim.read_text(encoding="utf-8") == "original"


def test_toctou_parent_symlink_swap_does_not_write_outside(
    tmp_path: Path,
    tmp_path_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate swapping a path component for a symlink after the parent dir fd is opened."""
    from lib import safe_write as sw

    if not sw._POSIX_DIR_FD:
        pytest.skip("dir_fd anchoring not available on this platform")

    outside = tmp_path_factory.mktemp("outside")
    victim = outside / "victim.ipynb.py"
    victim.write_text("untouched", encoding="utf-8")

    root = tmp_path / "allowed"
    sub = root / "nested"
    sub.mkdir(parents=True)
    target = sub / "out.ipynb.py"

    trapped = root / ".nested_trapped"

    def _swap() -> None:
        sub.rename(trapped)
        (root / "nested").symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(sw, "_race_test_hook", _swap)
    sw.safe_write_text(target, "safe", allowed_roots=(root,))
    assert victim.read_text(encoding="utf-8") == "untouched"
    assert (trapped / "out.ipynb.py").read_text(encoding="utf-8") == "safe"


def test_toctou_unlink_via_dir_fd_after_parent_swap(
    tmp_path: Path,
    tmp_path_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lib import safe_write as sw

    if not sw._POSIX_DIR_FD:
        pytest.skip("dir_fd anchoring not available on this platform")

    outside = tmp_path_factory.mktemp("outside")
    victim = outside / "must_keep.ipynb.py"
    victim.write_text("keep", encoding="utf-8")

    root = tmp_path / "allowed"
    sub = root / "nested"
    sub.mkdir(parents=True)
    sidecar = sub / "drop.ipynb.py"
    sidecar.write_text("remove me", encoding="utf-8")

    trapped = root / ".nested_trapped"

    def _swap() -> None:
        sub.rename(trapped)
        (root / "nested").symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(sw, "_race_test_hook", _swap)
    assert sw.safe_unlink(sidecar, allowed_roots=(root,))
    assert victim.read_text(encoding="utf-8") == "keep"
    assert not (trapped / "drop.ipynb.py").exists()


def test_no_powershell_home_assignment_in_repo() -> None:
    """Copilot r4513128214: no PowerShell ``$home =`` assignment (read-only ``$HOME``)."""
    import re

    repo = Path(__file__).resolve().parent.parent
    pat = re.compile(r"^\s*\$home\s*=", re.IGNORECASE | re.MULTILINE)
    offenders: list[str] = []
    for path in repo.rglob("*"):
        if path.suffix not in {".ps1", ".md"} or ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if pat.search(text):
            offenders.append(str(path))
    assert not offenders, offenders


def test_clean_continues_after_oserror_on_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = tmp_path / "ok.ipynb.py"
    good.write_text("x", encoding="utf-8")
    bad = tmp_path / "bad.ipynb.py"
    bad.write_text("y", encoding="utf-8")
    from lib import safe_write as sw

    original = sw.safe_unlink

    def flaky_unlink(path: Path, *, allowed_roots: tuple[Path, ...]) -> bool:
        if path.name == "bad.ipynb.py":
            raise OSError("permission denied")
        return original(path, allowed_roots=allowed_roots)

    monkeypatch.setattr(sw, "safe_unlink", flaky_unlink)
    removed = []
    for p in (good, bad):
        try:
            if sw.safe_unlink(p, allowed_roots=(tmp_path,)):
                removed.append(p.name)
        except (ValueError, OSError):
            pass
    assert removed == ["ok.ipynb.py"]
    assert not good.exists()
    assert bad.exists()
