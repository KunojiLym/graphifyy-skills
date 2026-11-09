---
name: databricks-graphify
description: "Build a graphify knowledge graph for Databricks repos: Lakeview .lvdash.json dashboards plus Jupyter notebooks. Use when the user runs /databricks-graphify, or asks to graphify linkedin-on-databricks / databricks-linkedin-analytics with notebooks and dashboards included. Runs ipynb-graphify (notebooks) and lvdash sidecar extraction, then hands off to /graphify."
---

# /databricks-graphify

Databricks pipelines in this workspace live mostly in **notebooks** (`.ipynb`) and **Lakeview
dashboards** (`.lvdash.json`). Stock graphify skips the former and indexes the latter as
inert JSON — neither yields useful graph nodes.

This skill is the **Databricks umbrella**: it runs both converters, then `/graphify`.

| Gap | Converter | Sidecars |
|-----|-----------|----------|
| Notebooks ignored | `../ipynb-graphify/ipynb_split.py` | `*.ipynb.py`, `*.ipynb.md`, `*.ipynb.sql`, … |
| Dashboard queries invisible | `lvdash_split.py` | `*.lvdash.sql`, `*.lvdash.md` |

After conversion, graphify sees SQL AST nodes for `gold.linkedin.*` table references and
AST/semantic nodes for notebook pipeline logic.

## Usage

```
/databricks-graphify                 # convert notebooks + dashboards under cwd, then graphify .
/databricks-graphify <path>          # scoped to a subfolder (e.g. linkedin-on-databricks)
/databricks-graphify <path> --clean  # remove all generated sidecars and stop
/databricks-graphify <path> --outdir <dir>   # mirror sidecars (both converters)
```

Flags not consumed here (`--update`, `--directed`, `--no-viz`, `--mode deep`, …) are
forwarded to `/graphify`.

For **notebooks only**, use `/ipynb-graphify`. For **full workspace** Databricks coverage,
prefer `/databricks-graphify`.

## What You Must Do When Invoked

If the user passed `--clean`, run Steps 2a and 2b with `--clean`, then stop.

Otherwise follow all steps in order.

### Step 1 — Resolve skill paths, target path, and Python

Resolve converter scripts from the **installed skills tree**, not from workspace cwd.
Nested installs keep sibling skills:

```
graphifyy-skills/
  ipynb-graphify/ipynb_split.py
  databricks-graphify/lvdash_split.py   ← this skill
```

**PowerShell:**

```powershell
$DatabricksDir = $PSScriptRoot
$SkillsRoot    = Split-Path $DatabricksDir -Parent
$IpynbScript   = Join-Path $SkillsRoot "ipynb-graphify\ipynb_split.py"
$LvdashScript  = Join-Path $DatabricksDir "lvdash_split.py"
$Target        = $args[0]
if (-not $Target) { $Target = "." }

New-Item -ItemType Directory -Force -Path graphify-out | Out-Null
$PY = "python"
if (Test-Path graphify-out\.graphify_python) {
  $PY = (Get-Content graphify-out\.graphify_python -Raw).Trim()
}
```

**Bash:**

```bash
DATABRICKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_ROOT="$(dirname "$DATABRICKS_DIR")"
IPYNB_SCRIPT="$SKILLS_ROOT/ipynb-graphify/ipynb_split.py"
LVDASH_SCRIPT="$DATABRICKS_DIR/lvdash_split.py"
TARGET="${1:-.}"
PY=python3
if [[ -f graphify-out/.graphify_python ]]; then PY="$(tr -d '\n' < graphify-out/.graphify_python)"; fi
```

Pass `$Target` / `$TARGET` as a quoted argument in every converter invocation (paths with spaces).

### Step 2a — Convert notebooks (ipynb-graphify)

```powershell
& $PY $IpynbScript $Target
# optional: & $PY $IpynbScript $Target --outdir "D:\mirrored sidecars"
```

On `--clean`:

```powershell
& $PY $IpynbScript $Target --clean
```

Report briefly, e.g. `Notebooks: N → M sidecars (X py, Y md, Z sql).`

See `../ipynb-graphify/SKILL.md` for cell-routing details and notebook limitations.

### Step 2b — Convert Lakeview dashboards

```powershell
& $PY $LvdashScript $Target
```

On `--clean`:

```powershell
& $PY $LvdashScript $Target --clean
```

Report briefly, e.g. `Dashboards: N → M sidecars; tables: gold.linkedin.daily_statistics, …`

Each `.lvdash.json` produces:

| Sidecar | Contents |
|---------|----------|
| `<name>.lvdash.sql` | One `-- %% dataset …` block per `datasets[].queryLines` entry |
| `<name>.lvdash.md` | Dashboard title, **Consumes** table list, dataset/page summary |

If `dashboards` is 0, say so and continue — the path may still have notebooks or docs.

### Step 3 — Run graphify

Invoke the **graphify** skill on the same scan target, forwarding extra flags.

If `graphify-out/graph.json` already exists, prefer **`/graphify <target> --update`**
(graphify 0.9.104 content-only incremental re-extract). Otherwise run a full `/graphify <target>`.

The update picks up new `.ipynb.*` and `.lvdash.*` sidecars via AST (SQL/Python) and semantic
extraction (`.md` sidecars).

**Optional project-local hook:** a workspace may ship `graphify-out/_consolidate_communities.py`
for custom community merging. This is **not** stock Graphify — run only when the user maintains
that script and the base graphify skill documents it; `/databricks-graphify` does not require it.

### Step 4 — Summarise and verify Databricks-specific graph value

Verify claims with graphify 0.9.104 CLI (not invented wrappers):

```bash
graphify query "lakeview dashboard gold tables" --graph graphify-out/graph.json
graphify explain "daily_statistics" --graph graphify-out/graph.json
graphify path "daily_metrics.lvdash.sql" "gold.linkedin.daily_statistics" --graph graphify-out/graph.json
```

In your final message, call out what the graph should expose, citing query/explain output:

- Notebook pipeline logic in `*.ipynb.py` / SQL in `*.ipynb.sql` (**EXTRACTED** AST edges).
- Lakeview dataset SQL in `*.lvdash.sql` → gold tables (**EXTRACTED** via SQL extractor).
- Dashboard `Consumes` lists in `*.lvdash.md` (**regex heuristic** during split — treat as
  advisory until confirmed by `graphify query` or SQL AST nodes).
- Bundle YAML such as `dashboards.yml` (**EXTRACTED** by graphify's YAML/doc extractors when present).

Distinguish **EXTRACTED** (parser/AST) vs **INFERRED** (semantic doc edges). Parallel SQL→table
edges may include `also_seen` provenance in 0.9.104 when the same reference appears in multiple
sidecars.

State limitations honestly (see below).

### Step 5 — Cleanup reminder

Sidecars are build artifacts. Remind the user:

- Re-run `/databricks-graphify <path>` after editing notebooks or dashboards.
- `/databricks-graphify <path> --clean` removes all sidecars from both converters.
- Add to `.gitignore`:

```
*.ipynb.py
*.ipynb.md
*.ipynb.sql
*.ipynb.sh
*.ipynb.scala
*.ipynb.r
*.lvdash.sql
*.lvdash.md
```

## Limitations

- **Sidecar `source_location`**, not original `.ipynb` / `.lvdash.json` path. SQL blocks
  are tagged `-- %% dataset displayName [id]` for manual trace-back.
- **Widget-level logic** (fields, expressions, filters on pages) is not extracted — only
  `datasets[].queryLines` SQL and page display names.
- **No `%run` edges** between notebooks (ipynb-graphify limitation).
- **`dashboards.yml`** is already parsed by graphify as YAML docs; this skill does not
  duplicate it — the new value is linking **Lakeview query SQL** to gold tables.

## Upstream path

Stock Graphify v8 (0.9.104 as of 2026-11-08) still skips `.ipynb` and has no
Lakeview `.lvdash.json` SQL extractor. 0.9.104 (with 0.9.96–0.9.103) adds
weakest-hop path confidence and parallel-edge `also_seen` provenance,
centralises LLM rationale credential redaction, fixes case-distinct
type/function node ids and JVM cross-file import resolution, incremental
content-only `graphify update`, query depth/budget from `.graphifyrc`, broad
call-resolution and cache/watch fixes, and skill runbook scan-root hardening
via `.graphify_root`.
Native notebook support is proposed in
[Graphify-Labs/graphify#1498](https://github.com/Graphify-Labs/graphify/pull/1498)
(open, not merged: `KunojiLym feat/ipynb-notebook-support` → `v8`). Until that
lands, this skill remains the working path. Do not claim native notebook support
is already on v8.

PR 1498 is a weaker native path: one markdown sidecar / docs pass (semantic
extraction, kernel-language fenced code, outputs stripped). It does not split
cells into per-language AST sidecars and does not route Databricks
`%sql`/`%md`/`%sh` magics. This skill stays strictly better even after 1498
lands — per-language AST sidecars + magic routing — and Lakeview coverage
remains unique to `/databricks-graphify`. Keep using this skill for Databricks
workspaces.

Graphify lives at [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify).
Do not open a new PR to `safishamsi/graphify`.
