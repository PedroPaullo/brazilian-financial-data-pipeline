from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from config import PROCESSED_DB_FILE
from metadata.audit import ensure_audit_schema, register_dataset_version, register_etl_run
from metadata.dataset_versioning import create_dataset_version_id, dataframe_dataset_version
from metadata.manifest import (
    calculate_dataframe_checksum,
    calculate_file_checksum,
    create_run_id,
    create_run_manifest,
    load_run_manifest,
    write_run_manifest,
)
from validation.reconciliation import reconcile


def _run(command: list[str]):
    return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)


def main():
    run_id = create_run_id("test")
    assert run_id

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        temp_dir = Path(temp_name)
        temp_file = temp_dir / "traceability_test.txt"
        temp_file.write_text("traceability", encoding="utf-8")
        checksum = calculate_file_checksum(temp_file)
        assert checksum and len(checksum) == 64

        df = pd.DataFrame({"id": [1, 2], "value": ["a", "b"]})
        df_checksum = calculate_dataframe_checksum(df)
        assert df_checksum and len(df_checksum) == 64

        manifest = create_run_manifest(
            run_id=run_id,
            command="pytest traceability",
            parameters={"test": True},
            input_files=[temp_file],
            output_files=[temp_file],
            status="SUCCESS",
        )
        manifest_path = write_run_manifest(manifest, temp_dir / "manifest.json")
        loaded_manifest = load_run_manifest(manifest_path)
        assert loaded_manifest["run_id"] == run_id

        test_db = temp_dir / "traceability_test.db"
        ensure_audit_schema(test_db)
        register_etl_run(manifest, test_db)

        version = dataframe_dataset_version("synthetic", "TEST", df, run_id)
        register_dataset_version(version, test_db)
        deterministic_id = create_dataset_version_id(
            version["dataset_name"],
            version["source_name"],
            version["period_start"],
            version["period_end"],
            version["checksum"],
            version["schema_hash"],
        )
        assert deterministic_id == version["dataset_version_id"]

        with sqlite3.connect(test_db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM etl_run").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM etl_dataset_version").fetchone()[0] == 1

        reconciliation_db = temp_dir / "financial_data.db"
        shutil.copy2(PROCESSED_DB_FILE, reconciliation_db)
        report_dir = temp_dir / "reconciliation"
        result = reconcile(run_id, command="test reconciliation", manifest_path=manifest_path, database_file=reconciliation_db, report_dir=report_dir)
        assert result["overall_status"] in {"PASSED", "WARNING"}
        statuses = {check["status"] for check in result["checks"]}
        assert "PASSED" in statuses
        assert "SKIPPED" in statuses
        assert (report_dir / "latest.md").exists()
        assert (report_dir / "latest.csv").exists()
        assert (report_dir / "latest.json").exists()
        with open(report_dir / "latest.json", "r", encoding="utf-8") as file:
            latest = json.load(file)
        assert latest["summary"]["run_id"] == run_id

    assert (PROJECT_ROOT / "collect_data.py").exists()
    assert (PROJECT_ROOT / "run_pipeline.py").exists()
    collect_help = _run([sys.executable, "collect_data.py", "--help"])
    pipeline_help = _run([sys.executable, "run_pipeline.py", "--help"])
    assert collect_help.returncode == 0, collect_help.stderr
    assert pipeline_help.returncode == 0, pipeline_help.stderr
    assert "--start-date" in collect_help.stdout
    assert "--enable-manifest" in pipeline_help.stdout
    assert "--reconcile-only" in pipeline_help.stdout
    assert "--database-backend" in pipeline_help.stdout

    print("\nTeste do Modulo 10 concluido com sucesso.")


def test_module_10_traceability_reconciliation_versioning():
    main()


if __name__ == "__main__":
    main()
