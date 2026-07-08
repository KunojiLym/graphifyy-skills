# graphify-skills

Install to `~/.claude/skills/graphifyy-skills/`

- **graphify** — Base skill (separate repo). Trigger: `/graphify`
- **databricks-graphify** (`.claude/skills/graphifyy-skills/databricks-graphify/SKILL.md`) — notebooks + Lakeview dashboards, then graphify. Trigger: `/databricks-graphify`
- **ipynb-graphify** (`.claude/skills/graphifyy-skills/ipynb-graphify/SKILL.md`) — notebooks only. Trigger: `/ipynb-graphify`

When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.
When the user types `/databricks-graphify`, invoke `skill: "databricks-graphify"`.
When the user types `/ipynb-graphify`, invoke `skill: "ipynb-graphify"`.
