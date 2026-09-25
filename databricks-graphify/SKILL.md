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

### Step 1 — Resolve paths and Python

```powershell
$ROOT = (Get-Location).Path
$SKILL = Join-Path $ROOT ".claude\skills\databricks-graphify"
$IPYNB_SCRIPT = Join-Path $ROOT ".claude\skills\ipynb-graphify\ipynb_split.py"
$LVDASH_SCRIPT = Join-Path $SKILL "lvdash_split.py"

New-Item -ItemType Directory -Force -Path graphify-out | Out-Null
$PY = "python"
if (Test-Path graphify-out\.graphify_python) {
    $PY = (Get-Content graphify-out\.graphify_python -Raw).Trim()
}
```

Substitute `INPUT_PATH` (default `.`). If `$PSScriptRoot` is available in your host, you
may resolve `$SKILL` from there instead of `$ROOT\.claude\skills\databricks-graphify`.

### Step 2a — Convert notebooks (ipynb-graphify)

```powershell
& $PY $IPYNB_SCRIPT INPUT_PATH [--outdir OUTDIR]
```

On `--clean`:

```powershell
& $PY $IPYNB_SCRIPT INPUT_PATH --clean
```

Report briefly, e.g. `Notebooks: N → M sidecars (X py, Y md, Z sql).`

See `../ipynb-graphify/SKILL.md` for cell-routing details and notebook limitations.

### Step 2b — Convert Lakeview dashboards

```powershell
& $PY $LVDASH_SCRIPT INPUT_PATH [--outdir OUTDIR]
```

On `--clean`:

```powershell
& $PY $LVDASH_SCRIPT INPUT_PATH --clean
```

Report briefly, e.g. `Dashboards: N → M sidecars; tables: gold.linkedin.daily_statistics, …`

Each `.lvdash.json` produces:

| Sidecar | Contents |
|---------|----------|
| `<name>.lvdash.sql` | One `-- %% dataset …` block per `datasets[].queryLines` entry |
| `<name>.lvdash.md` | Dashboard title, **Consumes** table list, dataset/page summary |

If `dashboards` is 0, say so and continue — the path may still have notebooks or docs.

### Step 3 — Run graphify

Invoke the **graphify** skill on the same `INPUT_PATH`, forwarding extra flags.
Use workspace root (`.`) as the graphify working directory when possible so
**Step 5.5 consolidation** (`graphify-out/_consolidate_communities.py`) runs after
labeling — it merges notebook and dashboard sidecar fragments and applies section-root
community names.

If `graphify-out/graph.json` already exists for this scan root, prefer:

```
/graphify INPUT_PATH --update
```

Otherwise run a full `/graphify INPUT_PATH`.

The update picks up new `.ipynb.*` and `.lvdash.*` sidecars via AST (SQL/Python) and
semantic extraction (`.md` sidecars) as appropriate.

### Step 4 — Summarise Databricks-specific graph value

In your final message, call out what the graph should now expose (verify with
`graphify query` if helpful):

- **Daily-use pipeline:** `linkedin_pipeline.ipynb.py` → bronze/silver logic;
  `*.lvdash.sql` → `gold.linkedin.daily_statistics`;
  `refresh_linkedin_view_notebook.ipynb.sql` → `REFRESH MATERIALIZED VIEW`.
- **Public repo:** `*.lvdash.sql` → `fct_daily_profile_statistics` / `fct_daily_post_statistics`;
  `resources/dashboards.yml` bundle resource should connect via shared table nodes.

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

Stock Graphify v8 (0.9.58 as of 2026-09-11) still skips `.ipynb` and has no
Lakeview `.lvdash.json` SQL extractor. 0.9.58 is a fix-heavy release for
nested Python function resolution, namespace/sibling imports, PHP aliased
`use`, and `graphify install` on unwritable config, plus SQL `CREATE INDEX`
nodes and Rust `static`/`const` extraction. Native notebook support is proposed in
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
