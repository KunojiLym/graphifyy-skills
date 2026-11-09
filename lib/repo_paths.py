"""Resolve skill install layout (nested global vs project-local)."""
from __future__ import annotations

from pathlib import Path


def repo_root_from_script(script: Path) -> Path:
    """Repository root: parent of ``ipynb-graphify`` / ``databricks-graphify``."""
    return script.resolve().parent.parent


def ipynb_split_script(repo_root: Path) -> Path:
    return repo_root / "ipynb-graphify" / "ipynb_split.py"


def lvdash_split_script(repo_root: Path) -> Path:
    return repo_root / "databricks-graphify" / "lvdash_split.py"


def skill_install_candidates(cwd: Path | None = None) -> list[Path]:
    """Common install locations for this skills repo (documentation / discovery only)."""
    home = Path.home()
    cwd = cwd or Path.cwd()
    return [
        home / ".claude" / "skills" / "graphifyy-skills",
        cwd / ".claude" / "skills" / "graphifyy-skills",
        cwd / ".cursor" / "skills" / "graphifyy-skills",
    ]
