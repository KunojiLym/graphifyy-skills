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
