from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
import py_compile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
OPERATIONS_DB_FILE = PROJECT_ROOT / "data" / "operations" / "pipeline_operations.db"
ALERTS_JSON_FILE = PROJECT_ROOT / "reports" / "operations" / "alerts.json"
ALERTS_CSV_FILE = PROJECT_ROOT / "reports" / "operations" / "alerts.csv"


def _run(command: list[str]):
    return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)


def main():
    assert (SRC_DIR / "run_pipeline.py").exists()
    assert (SRC_DIR / "alerts.py").exists()
    assert (SRC_DIR / "financial_calendar.py").exists()

    help_result = _run([sys.executable, str(SRC_DIR / "run_pipeline.py"), "--help"])
    assert help_result.returncode == 0, help_result.stderr

    alerts_result = _run([sys.executable, str(SRC_DIR / "alerts.py")])
    assert alerts_result.returncode == 0, alerts_result.stderr

    assert ALERTS_JSON_FILE.exists()
    assert ALERTS_CSV_FILE.exists()
    assert OPERATIONS_DB_FILE.exists()

    with sqlite3.connect(OPERATIONS_DB_FILE) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert {"pipeline_runs", "source_freshness", "data_artifacts"}.issubset(tables)

    py_compile.compile(str(SRC_DIR / "dashboard.py"), doraise=True)
    py_compile.compile(str(SRC_DIR / "run_pipeline.py"), doraise=True)
    py_compile.compile(str(SRC_DIR / "alerts.py"), doraise=True)

    print("\nTeste do Modulo 6 concluido com sucesso.")


if __name__ == "__main__":
    main()
