from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from lib.safe_write import safe_unlink

REPO = Path(__file__).resolve().parent.parent
IPYNB = REPO / "ipynb-graphify" / "ipynb_split.py"


def _load_ipynb_split():
    spec = importlib.util.spec_from_file_location("ipynb_split_clean_test", IPYNB)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ipynb_clean_continues_after_safe_unlink_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_ipynb_split()
    (tmp_path / "a.ipynb.py").write_text("1", encoding="utf-8")
    (tmp_path / "b.ipynb.py").write_text("2", encoding="utf-8")

    def flaky(path: Path, *, allowed_roots: tuple[Path, ...]) -> bool:
        if path.name == "b.ipynb.py":
            raise OSError("permission denied")
        return safe_unlink(path, allowed_roots=allowed_roots)

    monkeypatch.setattr(mod, "safe_unlink", flaky)
    removed = mod.clean(tmp_path)
    assert any(p.endswith("a.ipynb.py") for p in removed)
    assert not any(p.endswith("b.ipynb.py") for p in removed)
    assert (tmp_path / "b.ipynb.py").exists()
