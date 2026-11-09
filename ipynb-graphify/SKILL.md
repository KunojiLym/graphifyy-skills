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

### Step 1 — Resolve skill paths, target path, and Python

**Set the scan target explicitly** from the user's `/ipynb-graphify <path>` request (default `"."`). Do not rely on `$args[0]`, `$1`, or `$PSScriptRoot` — agents usually run these lines **ad hoc** and those values are empty.

Probe known install roots (project `.claude/skills/graphifyy-skills`, global `~/.claude/skills/graphifyy-skills`, `.cursor/skills/graphifyy-skills`, dev checkout cwd, or `GRAPHIFYY_SKILLS_ROOT`). Use `$PSScriptRoot` / `BASH_SOURCE` only when non-empty **and** the path contains `ipynb_split.py`. **Fail loudly** if no converter is found.

**PowerShell** (quote paths that contain spaces):

```powershell
# Set from the user's slash command before running ad hoc:
$ScanTarget = "."

function Resolve-GraphifyySkillsRoot {
  if ($env:GRAPHIFYY_SKILL_DIR -and (Test-Path -LiteralPath (Join-Path $env:GRAPHIFYY_SKILL_DIR "ipynb_split.py"))) {
    return (Split-Path $env:GRAPHIFYY_SKILL_DIR -Parent)
  }
  if ($PSScriptRoot -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot "ipynb_split.py"))) {
    return (Split-Path $PSScriptRoot -Parent)
  }
  $cwd = (Get-Location).Path
  $userHome = if ($env:HOME) { $env:HOME } else { $env:USERPROFILE }
  $candidates = @()
  if ($env:GRAPHIFYY_SKILLS_ROOT) { $candidates += $env:GRAPHIFYY_SKILLS_ROOT }
  $candidates += @(
    $cwd,
    (Join-Path $cwd ".claude\skills\graphifyy-skills"),
    (Join-Path $userHome ".claude\skills\graphifyy-skills"),
    (Join-Path $cwd ".cursor\skills\graphifyy-skills")
  )
  foreach ($root in $candidates) {
    if (-not $root) { continue }
    $ipynb = Join-Path $root "ipynb-graphify\ipynb_split.py"
    $lv = Join-Path $root "databricks-graphify\lvdash_split.py"
    if ((Test-Path -LiteralPath $ipynb) -and (Test-Path -LiteralPath $lv)) {
      return (Resolve-Path -LiteralPath $root).Path
    }
  }
  throw "graphifyy-skills not found: install to ~/.claude/skills/graphifyy-skills or .claude/skills/graphifyy-skills (or set GRAPHIFYY_SKILLS_ROOT)."
}

$SkillsRoot = Resolve-GraphifyySkillsRoot
$Script = Join-Path $SkillsRoot "ipynb-graphify\ipynb_split.py"
if (-not (Test-Path -LiteralPath $Script)) { throw "Converter missing: $Script" }

$PY = "python"
if (Test-Path graphify-out\.graphify_python) {
  $PY = (Get-Content graphify-out\.graphify_python -Raw).Trim()
}
New-Item -ItemType Directory -Force -Path graphify-out -ErrorAction SilentlyContinue | Out-Null
# Optional: set when the user passed --outdir <dir>
$OutDir = $null
# Optional: $true when the user passed --clean
$RunClean = $false
```

**Bash**:

```bash
# Set from the user's slash command before running ad hoc:
SCAN_TARGET="."

resolve_graphifyy_skills_root() {
  local cwd="${1:-$(pwd)}" home="${2:-$HOME}" candidate
  if [[ -n "${GRAPHIFYY_SKILL_DIR:-}" && -f "${GRAPHIFYY_SKILL_DIR}/ipynb_split.py" ]]; then
    (cd "$(dirname "$GRAPHIFYY_SKILL_DIR")" && pwd); return 0
  fi
  if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != bash && -f "$(dirname "${BASH_SOURCE[0]}")/ipynb_split.py" ]]; then
    (cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd); return 0
  fi
  local roots=()
  [[ -n "${GRAPHIFYY_SKILLS_ROOT:-}" ]] && roots+=("$GRAPHIFYY_SKILLS_ROOT")
  roots+=("$cwd" "$cwd/.claude/skills/graphifyy-skills" "$home/.claude/skills/graphifyy-skills" "$cwd/.cursor/skills/graphifyy-skills")
  for candidate in "${roots[@]}"; do
    if [[ -f "$candidate/ipynb-graphify/ipynb_split.py" && -f "$candidate/databricks-graphify/lvdash_split.py" ]]; then
      (cd "$candidate" && pwd); return 0
    fi
  done
  echo "error: graphifyy-skills not found (set GRAPHIFYY_SKILLS_ROOT or install under .claude/skills)." >&2
  return 1
}

SKILLS_ROOT="$(resolve_graphifyy_skills_root)" || exit 1
SCRIPT="$SKILLS_ROOT/ipynb-graphify/ipynb_split.py"
[[ -f "$SCRIPT" ]] || { echo "error: converter missing: $SCRIPT" >&2; exit 1; }
PY=python3
if [[ -f graphify-out/.graphify_python ]]; then PY="$(tr -d '\n' < graphify-out/.graphify_python)"; fi
# Optional: OUTDIR="..." when the user passed --outdir <dir>
# Optional: RUN_CLEAN=1 when the user passed --clean
```

(`lib/resolve_skills_root.sh` / `lib/resolve_skills_root.ps1` mirror this logic for copy/paste maintenance.)

The converter is **stdlib-only** (Python 3.8+). It adds the skills repo root to `sys.path` so `lib/safe_write.py` is found when scripts are invoked by absolute path.

### Step 2 — Convert notebooks to sidecars

Run the converter **once** with all flags from Step 1 variables (do not invoke it in Step 1):

```powershell
$invokeArgs = @($ScanTarget)
if ($OutDir) { $invokeArgs += "--outdir"; $invokeArgs += $OutDir }
if ($RunClean) { $invokeArgs += "--clean" }
& $PY $Script @invokeArgs
```

```bash
ARGS=("$SCAN_TARGET")
[[ -n "${OUTDIR:-}" ]] && ARGS+=("--outdir" "$OUTDIR")
[[ -n "${RUN_CLEAN:-}" ]] && ARGS+=("--clean")
"$PY" "$SCRIPT" "${ARGS[@]}"
```

When the user passes `--outdir`, set `$OutDir` / `OUTDIR` only in Step 1 and include it here so sidecars are **not** also written beside the notebooks in the source tree.

The script prints a JSON summary on stdout. Read it silently and report a clean line, e.g.:

```
Converted N notebooks → M sidecars (X code, Y markdown, Z sql).
```

If `errors` is non-empty, name the count and the offending notebooks (a malformed
or non-notebook `.ipynb` is skipped, not fatal). If `notebooks` is 0, tell the
user no notebooks were found and continue to Step 3 anyway (the repo may still
have code/docs worth graphing) — or stop if the user only wanted notebooks.

**`--clean` mode:** if the user passed `--clean`, append `--clean` to the converter argv
(and keep `$ScanTarget` / `$SCAN_TARGET` quoted), report how many sidecars were removed, then stop — do not
run graphify.

**`--outdir`:** pass `--outdir` and a quoted directory path as separate argv tokens after
`$ScanTarget` / `$SCAN_TARGET`.

### Step 3 — Run the graphify pipeline

Invoke the **graphify** skill on the same scan target, forwarding extra flags (`--directed`,
`--no-viz`, `--mode deep`, …). Stock graphify runs detect → extract → build → cluster →
label → report (see the graphify skill). It picks up `.ipynb.py` / `.ipynb.md` / `.ipynb.sql`
/ … sidecars; original `.ipynb` files remain skipped.

If `graphify-out/graph.json` already exists for this project, prefer **`/graphify <target> --update`**
so graphify 0.9.104's content-only incremental re-extract picks up new sidecars without a full rebuild.

**Optional project-local post-label hook:** some workspaces keep a custom
`graphify-out/_consolidate_communities.py`. That script is **not** part of stock Graphify.
Only run it when the user explicitly maintains it and the base graphify skill documents it
for that repo; do not treat it as a required step of `/ipynb-graphify`.

### Step 4 — Verify relationships (graphify 0.9.104)

After the graph build, sanity-check Databricks value with supported CLI commands
(run from the project root where `graphify-out/graph.json` lives):

```bash
graphify query "gold.linkedin daily statistics pipeline" --graph graphify-out/graph.json
graphify explain "refresh materialized view" --graph graphify-out/graph.json
graphify path "linkedin_pipeline.ipynb.py" "gold.linkedin.daily_statistics" --graph graphify-out/graph.json
```

Use `--seed`, `--budget`, and `--depth` when the project's `.graphifyrc` sets query defaults.

When reporting findings, separate evidence types:

| Source | Confidence in graph | Meaning |
|--------|---------------------|---------|
| `.ipynb.py` / `.ipynb.sql` / `.ipynb.sh` … | **EXTRACTED** | tree-sitter / SQL AST from sidecars |
| `.ipynb.md` prose | mix of **EXTRACTED** / **INFERRED** | semantic doc links per graphify markdown rules |
| User paraphrase | n/a | not a graph edge — cite `graphify query` output |

Notebook / Lakeview **limitations** still apply: `source_location` on nodes points at
**sidecar paths**, not `.ipynb` cells (use `# %% cell N` markers to map back). Cross-notebook
`%run` is not an edge. Lakeview table lists in `.lvdash.md` from `/databricks-graphify` use
regex heuristics; SQL table refs in `.lvdash.sql` / `.ipynb.sql` become **EXTRACTED** once
graphify's SQL extractor runs.

### Step 5 — Tell the user about cleanup

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

Stock Graphify v8 (0.9.104 as of 2026-11-08) still skips `.ipynb` — it is in
neither `CODE_EXTENSIONS` nor `DOC_EXTENSIONS`. 0.9.104 (with 0.9.96–0.9.103)
adds weakest-hop path confidence and parallel-edge `also_seen` provenance,
centralises LLM rationale credential redaction, fixes case-distinct
type/function node ids and JVM cross-file import resolution, incremental
content-only `graphify update`, query depth/budget from `.graphifyrc`, broad
call-resolution and cache/watch fixes, and skill runbook scan-root hardening
via `.graphify_root`.
Native support is proposed in
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
