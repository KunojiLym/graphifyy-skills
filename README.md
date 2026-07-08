# graphify-skills

Extends [graphify](https://github.com/github/graphify) to index **Jupyter/Databricks notebooks** and **Lakeview dashboards** as first-class knowledge graph assets.

Stock graphify skips `.ipynb` and `.lvdash.json` files. These skills split them into per-language sidecars so graphify can extract meaningful AST nodes, SQL references, and semantic concepts from pipeline logic and dashboard queries.

## Features

- **ipynb-graphify**: Converts `.ipynb` notebooks into per-language sidecars (`.ipynb.py`, `.ipynb.sql`, `.ipynb.md`, etc.)
- **databricks-graphify**: Orchestrates both notebook and Lakeview dashboard conversion
- **No external dependencies** — stdlib-only, works with any Python 3.8+
- **Smart cell routing** — `%sql` → SQL AST, `%md` → semantic extraction, code cells → tree-sitter AST
- **Graphify-native** — Sidecars work with existing graphify extractors; no fork needed

## Skills

### ipynb-graphify

Splits Jupyter/Databricks notebooks into per-language sidecar files, preserving AST information that graphify can extract:

| Cell Type | Sidecar | Extraction |
|-----------|---------|-----------|
| Code cell | `<stem>.ipynb.py` | Tree-sitter AST (functions, classes, calls) |
| Markdown / `%md` | `<stem>.ipynb.md` | Semantic concept extraction |
| `%sql` | `<stem>.ipynb.sql` | SQL AST (table references) |
| `%sh` / `%bash` | `<stem>.ipynb.sh` | Shell AST |
| `%scala` | `<stem>.ipynb.scala` | Scala AST |
| `%r` | `<stem>.ipynb.r` | R AST |

**Usage:**
```bash
/ipynb-graphify                    # convert notebooks in cwd, then graphify
/ipynb-graphify <path>             # convert + graphify a specific folder
/ipynb-graphify <path> --clean     # remove generated sidecars
/ipynb-graphify <path> --outdir <dir>  # mirror sidecars to alternate location
```

### databricks-graphify

Orchestrates both notebook and dashboard conversion:

| Asset | Converter | Output |
|-------|-----------|--------|
| Notebooks | `ipynb_split.py` | `*.ipynb.{py,md,sql,sh,scala,r}` |
| Lakeview dashboards | `lvdash_split.py` | `*.lvdash.sql`, `*.lvdash.md` |

**Usage:**
```bash
/databricks-graphify                    # convert all notebooks + dashboards, then graphify
/databricks-graphify <path>             # scoped to subfolder
/databricks-graphify <path> --clean     # remove all generated sidecars
/databricks-graphify <path> --outdir <dir>  # mirror sidecars to alternate root
```

## Installation

Add this repository to your `.claude/skills/` directory:

```bash
git clone https://github.com/KunojiLym/graphifyy-skills.git \
  ~/.claude/skills/graphifyy-skills
```

Then use in Claude Chat:
- `/ipynb-graphify` — for notebooks only
- `/databricks-graphify` — for full Databricks workspace coverage (notebooks + dashboards)

## Architecture

```
Input Files (.ipynb, .lvdash.json)
    ↓
Converters (ipynb_split.py, lvdash_split.py)
    ↓
Per-language Sidecars (*.ipynb.{py,sql,md}, *.lvdash.{sql,md})
    ↓
graphify Pipeline (detect → extract → build → cluster → label → consolidate)
    ↓
Knowledge Graph
    ├─ SQL nodes (table references from notebooks and dashboards)
    ├─ Code nodes (functions, classes, method calls)
    ├─ Semantic nodes (markdown concepts, data dependencies)
    └─ Dashboard metadata (datasets, pages, data sources)
```

## Examples

### Notebook Conversion

Before:
```
my_pipeline.ipynb (opaque to graphify)
```

After running `/ipynb-graphify`:
```
my_pipeline.ipynb.py      # code cells → AST nodes
my_pipeline.ipynb.sql     # %sql cells → SQL table refs
my_pipeline.ipynb.md      # %md + markdown cells → concepts
```

### Dashboard Conversion

Before:
```
daily_metrics.lvdash.json (generic JSON, no semantic meaning)
```

After running `/databricks-graphify`:
```
daily_metrics.lvdash.sql  # dataset queries → SQL AST (table refs)
daily_metrics.lvdash.md   # dashboard summary + "Consumes" table list
```

## How It Works

### ipynb_split.py

1. **Scan** for `.ipynb` files (respecting ignore dirs: `.git`, `.venv`, `__pycache__`, etc.)
2. **Parse** notebook JSON
3. **Route** each cell by magic/type:
   - Whole-cell magic (`%sql`) → matched bucket
   - No magic, code cell → Python (sanitize inline magics)
   - Markdown cell → Markdown
4. **Sanitize** Python cells (comment out `%time`, `!shell` to keep tree-sitter happy)
5. **Write** sidecars with cell index markers in headers
6. **Report** JSON summary

### lvdash_split.py

1. **Scan** for `.lvdash.json` files
2. **Parse** Lakeview dashboard JSON
3. **Extract** datasets and queries
4. **Regex-match** `FROM`/`JOIN` to collect table references
5. **Write** sidecars:
   - `.lvdash.sql` — dataset queries with `-- %% dataset` headers
   - `.lvdash.md` — dashboard title, "Consumes" table list, dataset summary
6. **Report** JSON summary (dashboards, unique tables, errors)

## Limitations

- **Inline line magics** (e.g., `%time result = foo()`) in the middle of a cell are commented out but not extracted separately
- **Dynamic table names** in SQL (e.g., CTEs, subqueries) may not be detected by regex pattern
- **SQL comments** in dashboards could cause false matches (rare in practice)
- **Sidecars are generated files** — marked with "do not edit" headers; regenerate to refresh

## Dependencies

- **Python 3.8+** (no pip packages required)
- graphify (for the final pipeline)
- PowerShell (for skill invocation on Windows; Linux/Mac use equivalent shell)

## Contributing

PRs welcome! Focus areas:
- Improve SQL regex for complex queries (CTEs, dynamic tables)
- Add support for additional notebook magics or cell types
- Enhance sidecar metadata for better graphify extraction
- Test coverage for edge cases

## License

Pair with [graphify](https://github.com/github/graphify) — same license.

## See Also

- [graphify](https://github.com/github/graphify) — knowledge graph extraction from any input
- [Databricks Notebooks](https://docs.databricks.com/en/notebooks/index.html)
- [Lakeview Dashboards](https://docs.databricks.com/en/dashboards/index.html)
