from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "databricks-graphify" / "lvdash_split.py"


def _run(*args: str, cwd: Path | None = None) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def test_lvdash_extracts_sql_sidecar(tmp_path: Path) -> None:
    dash = tmp_path / "metrics.lvdash.json"
    dash.write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "name": "ds1",
                        "displayName": "Daily",
                        "queryLines": ["SELECT * FROM gold.schema.table_one\n"],
                    }
                ],
                "pages": [{"displayName": "Overview"}],
            }
        ),
        encoding="utf-8",
    )
    summary = _run(str(tmp_path), cwd=tmp_path)
    assert summary["dashboards"] == 1
    sql = tmp_path / "metrics.lvdash.sql"
    assert sql.is_file()
    assert "gold.schema.table_one" in sql.read_text(encoding="utf-8")
