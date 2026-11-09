from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _symlink_skills_tree(install_dir: Path) -> None:
    install_dir.parent.mkdir(parents=True, exist_ok=True)
    if install_dir.exists() or install_dir.is_symlink():
        install_dir.unlink(missing_ok=True)
    install_dir.symlink_to(REPO, target_is_directory=True)


def _bash_lib_resolver() -> str:
    return (REPO / "lib" / "resolve_skills_root.sh").read_text(encoding="utf-8")


def _pwsh_exe() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell (pwsh) not installed")
    return exe


def test_bash_lib_resolver_workspace_path_with_spaces(tmp_path: Path) -> None:
    workspace = tmp_path / "my workspace"
    workspace.mkdir()
    _symlink_skills_tree(workspace / ".claude" / "skills" / "graphifyy-skills")
    snippet = f"""{_bash_lib_resolver()}
cd {repr(str(workspace))} && resolve_graphifyy_skills_root
"""
    proc = subprocess.run(
        ["bash", "-c", snippet],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path / "nohome")},
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert Path(proc.stdout.strip()).resolve() == REPO.resolve()


def test_bash_lib_graphifiyy_skills_root_prepends_and_falls_back(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _symlink_skills_tree(workspace / ".claude" / "skills" / "graphifyy-skills")
    bogus = tmp_path / "not skills"
    bogus.mkdir()
    snippet = f"""{_bash_lib_resolver()}
export GRAPHIFYY_SKILLS_ROOT={repr(str(bogus))}
cd {repr(str(workspace))} && resolve_graphifyy_skills_root
"""
    proc = subprocess.run(
        ["bash", "-c", snippet],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path / "nohome")},
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert Path(proc.stdout.strip()).resolve() == REPO.resolve()


def test_bash_lib_not_found(tmp_path: Path) -> None:
    workspace = tmp_path / "lonely place"
    workspace.mkdir()
    proc = subprocess.run(
        ["bash", "-c", f"{_bash_lib_resolver()}\nresolve_graphifyy_skills_root || exit 7"],
        cwd=workspace,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path / "nohome")},
    )
    assert proc.returncode == 7
    assert "not found" in (proc.stderr or proc.stdout).lower()


def test_bash_databricks_skill_snippet_defines_resolver(tmp_path: Path) -> None:
    """Ad-hoc: bash block from databricks-graphify/SKILL.md defines resolve_graphifyy_skills_root."""
    skill = (REPO / "databricks-graphify" / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"```bash\n(SCAN_TARGET=.*?)\n```", skill, re.DOTALL)
    assert match, "databricks bash Step 1 block missing"
    block = match.group(1)
    assert "resolve_graphifyy_skills_root()" in block

    workspace = tmp_path / "ws"
    workspace.mkdir()
    _symlink_skills_tree(workspace / ".claude" / "skills" / "graphifyy-skills")
    proc = subprocess.run(
        ["bash", "-c", f"{block}\n test -n \"$SKILLS_ROOT\" && test -f \"$LVDASH_SCRIPT\""],
        cwd=workspace,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path / "nohome")},
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_pwsh_lib_resolve_stop_action(tmp_path: Path) -> None:
    workspace = tmp_path / "my workspace"
    workspace.mkdir()
    _symlink_skills_tree(workspace / ".claude" / "skills" / "graphifyy-skills")
    ps1 = REPO / "lib" / "resolve_skills_root.ps1"
    cmd = (
        f"$ErrorActionPreference = 'Stop'; "
        f"Set-Location -LiteralPath {repr(str(workspace))}; "
        f". {repr(str(ps1))}; "
        f"Resolve-GraphifyySkillsRoot"
    )
    proc = subprocess.run(
        [_pwsh_exe(), "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path / "nohome")},
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert Path(proc.stdout.strip()).resolve() == REPO.resolve()


def test_pwsh_ipynb_skill_snippet_userhome_not_readonly_collision(tmp_path: Path) -> None:
    """Ad-hoc: PowerShell Step 1 block must reach candidate probing (no $HOME assign)."""
    skill = (REPO / "ipynb-graphify" / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"```powershell\n(# Set from.*?)\n```", skill, re.DOTALL)
    assert match, "ipynb powershell Step 1 block missing"
    block = match.group(1)
    assert "$userHome" in block
    assert "$home =" not in block.lower() or "$userhome" in block.lower()

    workspace = tmp_path / "ws"
    workspace.mkdir()
    _symlink_skills_tree(workspace / ".claude" / "skills" / "graphifyy-skills")
    cmd = f"$ErrorActionPreference = 'Stop'; Set-Location -LiteralPath {repr(str(workspace))}; {block}; $SkillsRoot"
    proc = subprocess.run(
        [_pwsh_exe(), "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path / "nohome")},
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert Path(proc.stdout.strip()).resolve() == REPO.resolve()


def test_pwsh_lib_dotsource_psscriptroot_branch(tmp_path: Path) -> None:
    """Dot-sourcing lib/ sets $PSScriptRoot; resolver must not throw on -or Test-Path bug."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _symlink_skills_tree(workspace / ".claude" / "skills" / "graphifyy-skills")
    ps1 = REPO / "lib" / "resolve_skills_root.ps1"
    cmd = (
        f"$ErrorActionPreference = 'Stop'; "
        f"Set-Location -LiteralPath {repr(str(workspace))}; "
        f". {repr(str(ps1))}; "
        f"Resolve-GraphifyySkillsRoot | Out-String"
    )
    proc = subprocess.run(
        [_pwsh_exe(), "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert (REPO / "ipynb-graphify" / "ipynb_split.py").is_file()
