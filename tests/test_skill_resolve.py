from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _symlink_skills_tree(install_dir: Path) -> None:
    install_dir.parent.mkdir(parents=True, exist_ok=True)
    if install_dir.exists() or install_dir.is_symlink():
        install_dir.unlink(missing_ok=True)
    install_dir.symlink_to(REPO, target_is_directory=True)


def test_python_resolve_project_local(tmp_path: Path) -> None:
    from lib.skill_paths import resolve_skills_root

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    install = workspace / ".claude" / "skills" / "graphifyy-skills"
    _symlink_skills_tree(install)
    root = resolve_skills_root(cwd=workspace)
    assert root.resolve() == REPO.resolve()


def test_python_resolve_global_home(tmp_path: Path) -> None:
    from lib.skill_paths import resolve_skills_root

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    install = fake_home / ".claude" / "skills" / "graphifyy-skills"
    _symlink_skills_tree(install)
    workspace = tmp_path / "empty_project"
    workspace.mkdir()
    root = resolve_skills_root(cwd=workspace, home=fake_home)
    assert root.resolve() == REPO.resolve()


def test_python_resolve_dev_checkout_cwd() -> None:
    from lib.skill_paths import resolve_skills_root

    root = resolve_skills_root(cwd=REPO)
    assert root.resolve() == REPO.resolve()


def test_python_missing_install_raises(tmp_path: Path) -> None:
    from lib.skill_paths import SkillInstallNotFoundError, resolve_skills_root

    workspace = tmp_path / "bare"
    workspace.mkdir()
    with pytest.raises(SkillInstallNotFoundError):
        resolve_skills_root(cwd=workspace, home=tmp_path / "nohome")


def _bash_adhoc_convert(workspace: Path, scan_subdir: Path, *, env: dict | None = None) -> dict:
    """Run ad-hoc bash (no script file): resolver + converter, matching SKILL Step 1."""
    resolver_src = (REPO / "lib" / "resolve_skills_root.sh").read_text(encoding="utf-8")
    snippet = f"""
{resolver_src}
unset GRAPHIFYY_SKILLS_ROOT
SCAN_TARGET="{scan_subdir}"
SKILLS_ROOT="$(resolve_graphifyy_skills_root)" || exit 1
SCRIPT="$SKILLS_ROOT/ipynb-graphify/ipynb_split.py"
[[ -f "$SCRIPT" ]] || {{ echo "missing script" >&2; exit 1; }}
python3 "$SCRIPT" "$SCAN_TARGET"
"""
    proc = subprocess.run(
        ["bash", "-c", snippet],
        cwd=workspace,
        capture_output=True,
        text=True,
        env=env or os.environ.copy(),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def test_adhoc_bash_project_local_layout(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    install = workspace / ".claude" / "skills" / "graphifyy-skills"
    _symlink_skills_tree(install)

    nb_dir = workspace / "data sets"
    nb_dir.mkdir()
    nb = nb_dir / "x.ipynb"
    nb.write_text(
        json.dumps(
            {
                "cells": [{"cell_type": "code", "source": "a=1", "metadata": {}}],
                "nbformat": 4,
            }
        ),
        encoding="utf-8",
    )

    summary = _bash_adhoc_convert(workspace, nb_dir)
    assert summary["notebooks"] == 1
    assert (nb_dir / "x.ipynb.py").is_file()


def test_adhoc_bash_global_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    install = fake_home / ".claude" / "skills" / "graphifyy-skills"
    _symlink_skills_tree(install)
    workspace = tmp_path / "proj"
    workspace.mkdir()
    nb = workspace / "n.ipynb"
    nb.write_text(
        json.dumps({"cells": [{"cell_type": "code", "source": "b=2", "metadata": {}}], "nbformat": 4}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(fake_home))
    snippet = (REPO / "lib" / "resolve_skills_root.sh").read_text(encoding="utf-8")
    full = f"""
{snippet}
unset GRAPHIFYY_SKILLS_ROOT
SCAN_TARGET="{workspace}"
SKILLS_ROOT="$(resolve_graphifyy_skills_root)" || exit 1
python3 "$SKILLS_ROOT/ipynb-graphify/ipynb_split.py" "$SCAN_TARGET"
"""
    proc = subprocess.run(["bash", "-c", full], cwd=workspace, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert (workspace / "n.ipynb.py").is_file()


def test_adhoc_bash_missing_install_exits_nonzero(tmp_path: Path) -> None:
    workspace = tmp_path / "lonely"
    workspace.mkdir()
    resolver_src = (REPO / "lib" / "resolve_skills_root.sh").read_text(encoding="utf-8")
    proc = subprocess.run(
        ["bash", "-c", f"{resolver_src}\nresolve_graphifyy_skills_root || exit 42"],
        cwd=workspace,
        env={**os.environ, "HOME": str(tmp_path / "nohome")},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 42
    assert "not found" in (proc.stderr or proc.stdout).lower()


def test_empty_psscriptroot_splits_unreliably() -> None:
    """Documented regression: ad-hoc PowerShell has no $PSScriptRoot (verified on Windows hosts)."""
    if shutil.which("pwsh") or shutil.which("powershell"):
        exe = shutil.which("pwsh") or shutil.which("powershell")
        proc = subprocess.run(
            [exe, "-NoProfile", "-Command", "$PSScriptRoot; if (-not $PSScriptRoot) { exit 0 } else { exit 9 }"],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
    else:
        pytest.skip("PowerShell not installed on this runner")
