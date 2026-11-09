# graphify-skills

Install this repo as a **single nested tree** (global or project-local). Both layouts must keep the same relative paths so converter lookup works:

| Layout | Path |
|--------|------|
| Global (Claude Code) | `~/.claude/skills/graphifyy-skills/` |
| Project-local | `<repo>/.claude/skills/graphifyy-skills/` |

Scripts live next to each skill file (`ipynb-graphify/ipynb_split.py`, `databricks-graphify/lvdash_split.py`). **Resolve the skills repo root** by probing the install paths above (or `GRAPHIFYY_SKILLS_ROOT`); use `$PSScriptRoot` / `BASH_SOURCE` only when non-empty and pointing at a skill folder. **Set the notebook/dashboard scan path explicitly** (`$ScanTarget` / `SCAN_TARGET`) — do not rely on `$args[0]` or `$1` in ad-hoc agent shells. Fail loudly if converters are missing.

- **graphify** — Base skill (separate PyPI package). Trigger: `/graphify`
- **databricks-graphify** (`…/graphifyy-skills/databricks-graphify/SKILL.md`) — notebooks + Lakeview dashboards, then graphify. Trigger: `/databricks-graphify`
- **ipynb-graphify** (`…/graphifyy-skills/ipynb-graphify/SKILL.md`) — notebooks only. Trigger: `/ipynb-graphify`

When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.
When the user types `/databricks-graphify`, invoke `skill: "databricks-graphify"`.
When the user types `/ipynb-graphify`, invoke `skill: "ipynb-graphify"`.
