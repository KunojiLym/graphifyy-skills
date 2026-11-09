"""Backward-compatible re-exports (prefer lib.skill_paths)."""
from __future__ import annotations

from lib.skill_paths import (  # noqa: F401
    SkillInstallNotFoundError,
    ipynb_split_script,
    lvdash_split_script,
    repo_root_from_script,
    resolve_skills_root,
    skill_install_candidates,
    skills_root_candidates,
)
