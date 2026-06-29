from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import collect_data
from artifact_retention import prune_artifacts
from metadata.manifest import create_run_manifest, write_run_manifest
from validation.reconciliation import _check, _write_reports


def _minimal_manifest(run_id: str) -> dict:
    return create_run_manifest(
        run_id=run_id,
        command=f"pytest {run_id}",
        parameters={"run_id": run_id},
        status="SUCCESS",
    )


def test_manifest_daily_overwrite_and_archive_runs():
    with tempfile.TemporaryDirectory() as temp_name:
        base_dir = Path(temp_name) / "manifests"
        first = _minimal_manifest("20260629_100000_test_first")
        second = _minimal_manifest("20260629_110000_test_second")

        with patch("metadata.manifest.today_stamp", return_value="20260629"):
            latest_path = write_run_manifest(first, base_dir=base_dir)
            write_run_manifest(second, base_dir=base_dir)

        assert latest_path == base_dir / "latest.json"
        assert (base_dir / "latest.json").exists()
        assert (base_dir / "daily" / "20260629.json").exists()
        assert not (base_dir / "runs").exists()

        latest = json.loads((base_dir / "latest.json").read_text(encoding="utf-8"))
        daily = json.loads((base_dir / "daily" / "20260629.json").read_text(encoding="utf-8"))
        assert latest["run_id"] == second["run_id"]
        assert daily["run_id"] == second["run_id"]
        assert len(list((base_dir / "daily").glob("*.json"))) == 1

        with patch("metadata.manifest.today_stamp", return_value="20260629"):
            write_run_manifest(second, archive_runs=True, base_dir=base_dir)
        assert (base_dir / "runs" / f"{second['run_id']}.json").exists()


def test_reconciliation_daily_overwrite_and_archive_runs():
    with tempfile.TemporaryDirectory() as temp_name:
        report_dir = Path(temp_name) / "reconciliation"
        checks = [_check("20260629_100000_test_first", "synthetic_check", "INFO", "PASSED")]

        with patch("validation.reconciliation.today_stamp", return_value="20260629"):
            _write_reports("20260629_100000_test_first", checks, "pytest first", "git-a", report_dir=report_dir)
            _write_reports("20260629_110000_test_second", checks, "pytest second", "git-b", report_dir=report_dir)

        assert (report_dir / "latest.json").exists()
        assert (report_dir / "daily" / "20260629.json").exists()
        assert (report_dir / "daily" / "20260629.csv").exists()
        assert (report_dir / "daily" / "20260629.md").exists()
        assert not (report_dir / "runs").exists()

        latest = json.loads((report_dir / "latest.json").read_text(encoding="utf-8"))
        daily = json.loads((report_dir / "daily" / "20260629.json").read_text(encoding="utf-8"))
        assert latest["summary"]["run_id"] == "20260629_110000_test_second"
        assert daily["summary"]["run_id"] == "20260629_110000_test_second"
        assert len(list((report_dir / "daily").glob("*.json"))) == 1

        with patch("validation.reconciliation.today_stamp", return_value="20260629"):
            _write_reports(
                "20260629_120000_test_archived",
                checks,
                "pytest archived",
                "git-c",
                report_dir=report_dir,
                archive_runs=True,
            )
        assert (report_dir / "runs" / "20260629_120000_test_archived.json").exists()
        assert (report_dir / "runs" / "20260629_120000_test_archived.csv").exists()
        assert (report_dir / "runs" / "20260629_120000_test_archived.md").exists()


def test_collection_daily_overwrite():
    original_values = (
        collect_data.COLLECTION_REPORT_DIR,
        collect_data.COLLECTION_DAILY_DIR,
        collect_data.COLLECTION_STATUS_JSON_FILE,
        collect_data.COLLECTION_STATUS_MD_FILE,
    )
    with tempfile.TemporaryDirectory() as temp_name:
        report_dir = Path(temp_name) / "collection"
        collect_data.COLLECTION_REPORT_DIR = report_dir
        collect_data.COLLECTION_DAILY_DIR = report_dir / "daily"
        collect_data.COLLECTION_STATUS_JSON_FILE = report_dir / "latest_collection_status.json"
        collect_data.COLLECTION_STATUS_MD_FILE = report_dir / "latest_collection_status.md"

        first = {"run_id": "first", "start_date": "2026-06-01", "end_date": "2026-06-28", "overall_status": "WARNING", "bcb_series": []}
        second = {"run_id": "second", "start_date": "2024-01-01", "end_date": "2024-12-31", "overall_status": "SUCCESS", "bcb_series": []}
        with patch("collect_data.today_stamp", return_value="20260629"):
            collect_data._write_collection_status_report(first)
            collect_data._write_collection_status_report(second)

        latest = json.loads((report_dir / "latest_collection_status.json").read_text(encoding="utf-8"))
        daily = json.loads((report_dir / "daily" / "20260629_collection_status.json").read_text(encoding="utf-8"))
        assert latest["run_id"] == "second"
        assert daily["run_id"] == "second"
        assert len(list((report_dir / "daily").glob("*_collection_status.json"))) == 1
    (
        collect_data.COLLECTION_REPORT_DIR,
        collect_data.COLLECTION_DAILY_DIR,
        collect_data.COLLECTION_STATUS_JSON_FILE,
        collect_data.COLLECTION_STATUS_MD_FILE,
    ) = original_values


def test_retention_keeps_latest_and_raw_data():
    with tempfile.TemporaryDirectory() as temp_name:
        base_dir = Path(temp_name)
        latest = base_dir / "latest.json"
        raw_file = base_dir / "data" / "raw" / "bcb" / "ipca_monthly.csv"
        daily_dir = base_dir / "daily"
        runs_dir = base_dir / "runs"
        old_daily = daily_dir / "20250501.json"
        old_run = runs_dir / "20250501_100000_test_old.json"
        new_daily = daily_dir / "20260629.json"

        for path in [latest, raw_file, old_daily, old_run, new_daily]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")

        removed = prune_artifacts([daily_dir, runs_dir], retention_days=30, today=date(2026, 6, 29))

        assert old_daily in removed
        assert old_run in removed
        assert latest.exists()
        assert raw_file.exists()
        assert new_daily.exists()


def main():
    test_manifest_daily_overwrite_and_archive_runs()
    test_reconciliation_daily_overwrite_and_archive_runs()
    test_collection_daily_overwrite()
    test_retention_keeps_latest_and_raw_data()
    print("\nTeste do Modulo 12 concluido com sucesso.")


if __name__ == "__main__":
    main()
