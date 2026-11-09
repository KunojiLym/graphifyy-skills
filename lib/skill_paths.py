"""Locate graphifyy-skills install roots (global, project-local, dev checkout)."""
from __future__ import annotations

import os
from pathlib import Path


class SkillInstallNotFoundError(FileNotFoundError):
    """No graphifyy-skills tree with converters was found."""


def skills_root_candidates(*, cwd: Path, home: Path) -> list[Path]:
    """Known layouts (see README / CLAUDE.md). Order: explicit env, dev tree, project, global, Cursor."""
    env = os.environ.get("GRAPHIFYY_SKILLS_ROOT", "").strip()
    roots: list[Path] = []
    if env:
        roots.append(Path(env))
    roots.extend(
        [
            cwd,
            cwd / ".claude" / "skills" / "graphifyy-skills",
            home / ".claude" / "skills" / "graphifyy-skills",
            cwd / ".cursor" / "skills" / "graphifyy-skills",
        ]
    )
    seen: set[str] = set()
    unique: list[Path] = []
    for r in roots:
        key = str(r.resolve()) if r.exists() else str(r)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _looks_like_skills_root(root: Path) -> bool:
    return (
        (root / "ipynb-graphify" / "ipynb_split.py").is_file()
        and (root / "databricks-graphify" / "lvdash_split.py").is_file()
    )


def resolve_skills_root(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    skill_dir_hint: Path | None = None,
) -> Path:
    """Return the skills repo root. ``skill_dir_hint`` is ipynb- or databricks-graphify dir when known."""
    cwd = (cwd or Path.cwd()).resolve()
    home = (home or Path.home()).resolve()

    if skill_dir_hint is not None:
        hint = skill_dir_hint.resolve()
        parent = hint.parent
        if hint.name == "ipynb-graphify" and (hint / "ipynb_split.py").is_file():
            if _looks_like_skills_root(parent):
                return parent
        if hint.name == "databricks-graphify" and (hint / "lvdash_split.py").is_file():
            if _looks_like_skills_root(parent):
                return parent

    for candidate in skills_root_candidates(cwd=cwd, home=home):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if _looks_like_skills_root(resolved):
            return resolved

    msg = (
        "graphifyy-skills not found: install clone to "
        "~/.claude/skills/graphifyy-skills or <repo>/.claude/skills/graphifyy-skills "
        "(or set GRAPHIFYY_SKILLS_ROOT). Expected ipynb-graphify/ipynb_split.py."
    )
    raise SkillInstallNotFoundError(msg)


def repo_root_from_script(script: Path) -> Path:
    """Repository root: parent of ``ipynb-graphify`` / ``databricks-graphify``."""
    return script.resolve().parent.parent


def ipynb_split_script(repo_root: Path) -> Path:
    return repo_root / "ipynb-graphify" / "ipynb_split.py"


def lvdash_split_script(repo_root: Path) -> Path:
    return repo_root / "databricks-graphify" / "lvdash_split.py"


def skill_install_candidates(cwd: Path | None = None) -> list[Path]:
    cwd = cwd or Path.cwd()
    return skills_root_candidates(cwd=cwd, home=Path.home())
