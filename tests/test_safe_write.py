from __future__ import annotations

from pathlib import Path

import pytest

from lib.safe_write import UnsafeOutputError, assert_output_allowed, safe_unlink, safe_write_text


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
