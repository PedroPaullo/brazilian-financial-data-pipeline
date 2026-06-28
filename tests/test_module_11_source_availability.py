from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import run_pipeline
import source_availability
from collectors.bcb_sgs import fetch_bcb_sgs_series, save_bcb_series_to_csv
from config import BCB_SERIES, COLLECTION_STATUS_JSON_FILE
from source_availability import (
    BCB_CSV_COLUMNS,
    STATUS_NOT_YET_AVAILABLE,
    STATUS_SOURCE_HTTP_ERROR,
    expected_periods_for_series,
)
from validators.load_raw_to_sqlite import load_raw_files_to_sqlite
from validators.quality_checks import run_quality_checks


class DummyResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._payload


def _with_collection_status(payload: dict, callback):
    original = COLLECTION_STATUS_JSON_FILE.read_text(encoding="utf-8") if COLLECTION_STATUS_JSON_FILE.exists() else None
    COLLECTION_STATUS_JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    COLLECTION_STATUS_JSON_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        return callback()
    finally:
        if original is None:
            COLLECTION_STATUS_JSON_FILE.unlink(missing_ok=True)
        else:
            COLLECTION_STATUS_JSON_FILE.write_text(original, encoding="utf-8")


def _bcb_row(series_name: str, value: float = 1.0) -> dict:
    metadata = BCB_SERIES[series_name]
    return {
        "source": "BCB_SGS",
        "series_code": str(metadata["code"]),
        "series_name": series_name,
        "date": "2024-01-01",
        "value": value,
        "collected_at": "2024-01-02 00:00:00",
    }


def _stock_row() -> dict:
    return {
        "source": "YAHOO_FINANCE",
        "ticker": "PETR4.SA",
        "date": "2024-01-02",
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.5,
        "adjusted_close": 10.5,
        "volume": 1000,
        "collected_at": "2024-01-02 00:00:00",
    }


def _write_csv(path: Path, rows: list[dict], columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _quality_for_ipca_status(ipca_status: str | None):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        temp_dir = Path(temp_name)
        selic_file = temp_dir / "selic_daily.csv"
        ipca_file = temp_dir / "ipca_monthly.csv"
        usd_file = temp_dir / "usd_brl_ptax_sell_daily.csv"
        cdi_file = temp_dir / "cdi_daily.csv"
        stocks_file = temp_dir / "stock_prices_daily.csv"
        db_file = temp_dir / "validation.db"

        _write_csv(selic_file, [_bcb_row("selic_daily")], BCB_CSV_COLUMNS)
        _write_csv(ipca_file, [], BCB_CSV_COLUMNS)
        _write_csv(usd_file, [_bcb_row("usd_brl_ptax_sell_daily", 5.0)], BCB_CSV_COLUMNS)
        _write_csv(cdi_file, [_bcb_row("cdi_daily")], BCB_CSV_COLUMNS)
        _write_csv(stocks_file, [_stock_row()], list(_stock_row().keys()))

        statuses = []
        for series_name in BCB_SERIES:
            status = "SUCCESS"
            severity = "INFO"
            expected = True
            rows = 1
            if series_name == "ipca_monthly":
                status = ipca_status or "SOURCE_EMPTY"
                severity = "WARNING" if status == STATUS_NOT_YET_AVAILABLE else "ERROR"
                expected = status != STATUS_NOT_YET_AVAILABLE
                rows = 0
            statuses.append(
                {
                    "series_name": series_name,
                    "series_code": str(BCB_SERIES[series_name]["code"]),
                    "frequency": BCB_SERIES[series_name]["frequency"],
                    "requested_start_date": "2024-01-01",
                    "requested_end_date": "2024-01-31",
                    "rows_collected": rows,
                    "rows": rows,
                    "status": status,
                    "severity": severity,
                    "reason": "test",
                    "expected": expected,
                    "output_file": str(ipca_file if series_name == "ipca_monthly" else selic_file),
                }
            )

        def run():
            load_raw_files_to_sqlite(
                selic_file=selic_file,
                ipca_file=ipca_file,
                stocks_file=stocks_file,
                database_file=db_file,
                extra_bcb_files=[usd_file, cdi_file],
            )
            results_df, _, summary = run_quality_checks(db_file)
            return results_df, summary

        return _with_collection_status({"bcb_series": statuses}, run)


def test_bcb_ipca_recent_not_yet_available():
    with patch.object(source_availability, "today_date", return_value=date(2026, 6, 28)):
        with patch("collectors.bcb_sgs.requests.get", return_value=DummyResponse(404)):
            df = fetch_bcb_sgs_series(
                433,
                "ipca_monthly",
                "2026-06-01",
                "2026-06-28",
                metadata=BCB_SERIES["ipca_monthly"],
            )
    assert df.empty
    assert df.attrs["collection_status"] == STATUS_NOT_YET_AVAILABLE
    assert df.attrs["severity"] == "WARNING"
    assert df.attrs["expected"] is False


def test_bcb_daily_http_error():
    with patch.object(source_availability, "today_date", return_value=date(2026, 6, 28)):
        with patch("collectors.bcb_sgs.requests.get", side_effect=requests.RequestException("offline")):
            df = fetch_bcb_sgs_series(
                11,
                "selic_daily",
                "2024-01-01",
                "2024-01-31",
                metadata=BCB_SERIES["selic_daily"],
            )
    assert df.empty
    assert df.attrs["collection_status"] == STATUS_SOURCE_HTTP_ERROR
    assert df.attrs["severity"] == "ERROR"
    assert df.attrs["expected"] is True


def test_no_stale_csv_reuse():
    with tempfile.TemporaryDirectory() as temp_name:
        csv_file = Path(temp_name) / "ipca_monthly.csv"
        _write_csv(csv_file, [_bcb_row("ipca_monthly")], BCB_CSV_COLUMNS)
        assert len(pd.read_csv(csv_file)) == 1
        empty_df = pd.DataFrame(columns=BCB_CSV_COLUMNS)
        save_bcb_series_to_csv(empty_df, csv_file)
        assert pd.read_csv(csv_file).empty


def test_validation_accepts_expected_empty_source():
    results_df, summary = _quality_for_ipca_status(STATUS_NOT_YET_AVAILABLE)
    assert summary["fail"] == 0
    assert summary["warn"] > 0
    assert "ipca_monthly_empty_source_status" in set(results_df["check_name"])


def test_validation_fails_unexpected_empty_source():
    results_df, summary = _quality_for_ipca_status("SOURCE_EMPTY")
    assert summary["fail"] > 0
    failed = results_df[results_df["status"] == "FAIL"]
    assert "ipca_monthly_empty_source_status" in set(failed["check_name"])


def test_skip_collection_does_not_collect():
    args = argparse.Namespace(
        start="2024-01-01",
        end="2024-12-31",
        skip_collection=True,
        skip_report=True,
        include_cvm=False,
        cvm_year_month=None,
        cvm_top_n=None,
        enable_manifest=False,
        reconcile=False,
        reconcile_only=False,
        run_id=None,
        database_backend="sqlite",
        database_url=None,
        modules=None,
    )
    calls = []

    def fake_run(command, cwd=None, check=False):
        calls.append([str(part) for part in command])
        return None

    with patch.object(run_pipeline.subprocess, "run", side_effect=fake_run):
        with patch.object(run_pipeline, "start_pipeline_run", return_value=1):
            with patch.object(run_pipeline, "finish_pipeline_run", return_value=None):
                with patch.object(run_pipeline, "_record_standard_artifacts", return_value=None):
                    with patch.object(run_pipeline, "generate_operational_alerts", return_value=None):
                        assert run_pipeline.run_pipeline(args) == 0

    flattened = " ".join(" ".join(call) for call in calls)
    assert "collect_data.py" not in flattened


def test_2024_closed_year_still_passes():
    months = expected_periods_for_series("ipca_monthly", "2024-01-01", "2024-12-31", as_of_date=date(2026, 6, 28))
    selic_days = expected_periods_for_series("selic_daily", "2024-01-01", "2024-12-31", as_of_date=date(2026, 6, 28))
    assert len(months) == 12
    assert len(selic_days) >= 250


def main():
    test_bcb_ipca_recent_not_yet_available()
    test_bcb_daily_http_error()
    test_no_stale_csv_reuse()
    test_validation_accepts_expected_empty_source()
    test_validation_fails_unexpected_empty_source()
    test_skip_collection_does_not_collect()
    test_2024_closed_year_still_passes()
    print("\nTeste do Modulo 11 concluido com sucesso.")


if __name__ == "__main__":
    main()
