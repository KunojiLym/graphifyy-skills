from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "ipynb-graphify" / "ipynb_split.py"


def _run(*args: str, cwd: Path | None = None) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def test_converts_minimal_notebook(tmp_path: Path) -> None:
    nb = tmp_path / "sample.ipynb"
    nb.write_text(
        json.dumps(
            {
                "cells": [
                    {"cell_type": "code", "source": ["print('hi')\n"], "metadata": {}},
                    {"cell_type": "markdown", "source": ["# Title\n"], "metadata": {}},
                ],
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )
    summary = _run(str(tmp_path), cwd=tmp_path)
    assert summary["notebooks"] == 1
    assert summary["sidecars_written"] >= 1
    assert (tmp_path / "sample.ipynb.py").is_file()


def test_outdir_mirrors_without_touching_outside(tmp_path: Path, tmp_path_factory) -> None:
    nb_root = tmp_path / "src"
    nb_root.mkdir()
    out_root = tmp_path / "mirrored"
    nb = nb_root / "dash.ipynb"
    nb.write_text(
        json.dumps({"cells": [{"cell_type": "code", "source": "x=1", "metadata": {}}], "nbformat": 4}),
        encoding="utf-8",
    )
    _run(str(nb_root), "--outdir", str(out_root), cwd=tmp_path)
    assert (out_root / "dash.ipynb.py").is_file()
    assert not (nb_root / "dash.ipynb.py").exists()


def test_repo_paths_agree_with_claude_layout() -> None:
    from lib.repo_paths import ipynb_split_script, lvdash_split_script, repo_root_from_script

    root = repo_root_from_script(SCRIPT)
    assert ipynb_split_script(root) == SCRIPT
    assert lvdash_split_script(root).is_file()
