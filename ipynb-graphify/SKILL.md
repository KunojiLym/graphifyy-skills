---
name: ipynb-graphify
description: "Build a graphify knowledge graph that INCLUDES Jupyter / Databricks .ipynb notebooks. Use when the user runs /ipynb-graphify, or asks to graphify a repo whose logic lives in notebooks (e.g. linkedin-on-databricks). Converts each notebook's cells into per-language sidecars (.ipynb.py / .ipynb.md / .ipynb.sql / .ipynb.sh / .ipynb.scala / .ipynb.r) so stock graphify can index them, then runs the normal graphify pipeline."
---

# /ipynb-graphify

Stock graphify silently skips `.ipynb` files — the extension is in neither
`CODE_EXTENSIONS` nor `DOC_EXTENSIONS`, so `classify_file()` returns `None`. This
wrapper closes that gap **without forking graphify**: it splits every notebook
into per-language sidecar files that graphify already understands, then hands off
to the normal `/graphify` pipeline.

Each notebook cell is routed to the extractor that fits it:

| Cell | Sidecar | Extraction |
|------|---------|------------|
| code cell | `<stem>.ipynb.py` | tree-sitter **AST** (functions, classes, calls) — free, line-accurate |
| markdown cell / `%md` | `<stem>.ipynb.md` | semantic concept extraction |
| `%sql` cell | `<stem>.ipynb.sql` | SQL AST |
| `%sh` / `%bash` cell | `<stem>.ipynb.sh` | shell AST |
| `%scala` cell | `<stem>.ipynb.scala` | Scala AST |
| `%r` cell | `<stem>.ipynb.r` | R AST |

This is strictly better than treating a notebook as one opaque blob: code cells
get real AST nodes, prose gets semantic nodes, and Databricks `%sql`/`%md`/`%sh`
magics land in the right language.

## Usage

```
/ipynb-graphify                 # convert notebooks under cwd, then graphify .
/ipynb-graphify <path>          # convert + graphify a specific folder
/ipynb-graphify <path> --clean  # remove generated *.ipynb.<ext> sidecars and stop
/ipynb-graphify <path> --outdir <dir>   # mirror sidecars under <dir> instead of in-place
```

Any flags not consumed below (`--update`, `--directed`, `--no-viz`, `--mode deep`,
etc.) are forwarded verbatim to `/graphify`.

## What You Must Do When Invoked

If the user passed `--clean`, run only Step 2 with `--clean` and stop. Otherwise
follow all steps in order.

### Step 1 — Resolve the Python interpreter

Reuse graphify's saved interpreter if a graph already exists; otherwise fall back
to the platform Python. The converter is **stdlib-only**, so any Python 3.8+ works.

```powershell
$PY = "python"
if (Test-Path graphify-out\.graphify_python) {
    $PY = (Get-Content graphify-out\.graphify_python -Raw).Trim()
}
$PY | Out-File -FilePath graphify-out\.ipynb_python -Encoding utf8 -NoNewline -ErrorAction SilentlyContinue
```

(`graphify-out/` may not exist yet on a first run — that is fine, the converter
does not need it. Create it first if you want to persist the interpreter path:
`New-Item -ItemType Directory -Force -Path graphify-out | Out-Null`.)

### Step 2 — Convert notebooks to sidecars

Run the converter against the target path (substitute `INPUT_PATH`, default `.`).
The script lives next to this skill file.

```powershell
& $PY "$PSScriptRoot\ipynb_split.py" INPUT_PATH
```

If `$PSScriptRoot` is not available in your host, use the absolute path to
`ipynb_split.py` inside this skill directory.

The script prints a JSON summary. Read it silently and report a clean line, e.g.:

```
Converted N notebooks → M sidecars (X code, Y markdown, Z sql).
```

If `errors` is non-empty, name the count and the offending notebooks (a malformed
or non-notebook `.ipynb` is skipped, not fatal). If `notebooks` is 0, tell the
user no notebooks were found and continue to Step 3 anyway (the repo may still
have code/docs worth graphing) — or stop if the user only wanted notebooks.

**`--clean` mode:** if the user passed `--clean`, run instead:

```powershell
& $PY "$PSScriptRoot\ipynb_split.py" INPUT_PATH --clean
```

Report how many sidecars were removed, then stop. Do not run graphify.

### Step 3 — Run the graphify pipeline

Now that sidecars exist on disk, invoke the **graphify** skill on the *same*
`INPUT_PATH`, forwarding any extra flags the user gave. Follow the graphify
SKILL.md exactly (detect → extract → build → cluster → label → **consolidate** → report).
graphify will pick up the `.ipynb.py` / `.ipynb.md` / `.ipynb.sql` / … sidecars as normal
code and doc files. The original `.ipynb` files are skipped by graphify as before.

If graphify is already installed and a graph exists, prefer
`/graphify INPUT_PATH --update` so only the new sidecars are (re-)extracted.

When `graphify-out/_consolidate_communities.py` exists at the workspace root, graphify
**Step 5.5** runs after labeling — re-cluster, merge notebook sidecar fragments, and
apply section-root community names. Run graphify from the workspace root (`.`) even when
`INPUT_PATH` is a subfolder, so consolidation finds `graphify-out/`.

### Step 4 — Tell the user about cleanup

The sidecars are build artifacts. In your final summary, remind the user:

- Re-run `/ipynb-graphify <path>` after editing notebooks to refresh sidecars.
- Run `/ipynb-graphify <path> --clean` to delete them.
- To keep them out of version control, add to `.gitignore`:

```
*.ipynb.py
*.ipynb.md
*.ipynb.sql
*.ipynb.sh
*.ipynb.scala
*.ipynb.r
```

## Limitations (state these honestly)

- **Source locations point to the sidecar**, not the original notebook cell. Each
  generated file carries `# %% cell N [type]` markers so you can map a node back
  to its origin cell, but graphify's `source_location` will read `<stem>.ipynb.py`.
- **Cross-notebook `%run ./other` edges are not created** — the magic line is
  commented out (`#nb> %run ...`) so the Python parses cleanly; graphify won't
  infer a reference edge from it.
- Inline line-magics (`%timeit`, `!pip ...`) inside an otherwise-Python cell are
  commented with a `#nb> ` prefix so tree-sitter doesn't choke.

## Native Graphify path (PR 1498)

Stock Graphify v8 (0.9.57 as of 2026-09-10) still skips `.ipynb` — it is in
neither `CODE_EXTENSIONS` nor `DOC_EXTENSIONS`. 0.9.57 is a fix-only release
for incremental rebuild AST, richer-node duplicate merge, C# generic call
sites, and `this.X = function` members. Native support is proposed in
[Graphify-Labs/graphify#1498](https://github.com/Graphify-Labs/graphify/pull/1498)
(open, not merged: `KunojiLym feat/ipynb-notebook-support` → `v8`). Until that
lands, this skill remains the working path. Do not claim native notebook support
is already on v8.

PR 1498 is a weaker native path: one markdown sidecar classified as a document
(semantic extraction, kernel-language fenced code, outputs stripped). It does
not split cells into per-language AST sidecars and does not route Databricks
`%sql`/`%md`/`%sh` magics. This skill stays strictly better even after 1498
merges. Keep using `/ipynb-graphify` for notebooks-as-code.

Graphify lives at [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify).
Do not open a new PR to `safishamsi/graphify`.
