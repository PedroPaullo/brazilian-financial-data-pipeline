from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from coverage_report import (
    build_coverage_report,
    calculate_coverage,
    classify_coverage_status,
)

COVERAGE_REPORT_FILE = PROJECT_ROOT / "reports" / "coverage" / "data_coverage_report.csv"
COVERAGE_SUMMARY_FILE = PROJECT_ROOT / "reports" / "coverage" / "data_coverage_summary.json"
COVERAGE_MISSING_DATES_FILE = PROJECT_ROOT / "reports" / "coverage" / "data_coverage_missing_dates.csv"


def _run(command: list[str]):
    return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)


def main():
    assert (SRC_DIR / "coverage_report.py").exists()

    synthetic_coverage = calculate_coverage(
        actual_dates=["2024-01-02", "2024-01-03", "2024-01-05"],
        start_date="2024-01-02",
        end_date="2024-01-05",
        frequency="daily_business",
    )
    assert synthetic_coverage["expected_observations"] == 4
    assert synthetic_coverage["actual_observations"] == 3
    assert synthetic_coverage["missing_observations"] == 1
    assert synthetic_coverage["coverage_pct"] == 75.0
    assert classify_coverage_status(99.0, 0) == "OK"
    assert classify_coverage_status(95.0, 3) == "WARNING"
    assert classify_coverage_status(80.0, 10) == "CRITICAL"

    bcb_df = pd.DataFrame(
        {
            "series_name": ["selic_daily", "selic_daily", "ipca_monthly"],
            "frequency": ["daily", "daily", "monthly"],
            "reference_date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-01"]),
        }
    )
    stocks_df = pd.DataFrame(
        {
            "ticker": ["PETR4.SA", "PETR4.SA"],
            "reference_date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
        }
    )
    report_df, missing_df = build_coverage_report(bcb_df, stocks_df, "2024-01-01", "2024-01-05")
    assert {"selic_daily", "ipca_monthly", "PETR4.SA"}.issubset(set(report_df["dataset_name"]))
    assert "missing_date" in missing_df.columns

    result = _run([sys.executable, str(SRC_DIR / "coverage_report.py"), "--start", "2024-01-01", "--end", "2024-12-31"])
    assert result.returncode == 0, result.stderr

    for file_path in [COVERAGE_REPORT_FILE, COVERAGE_SUMMARY_FILE, COVERAGE_MISSING_DATES_FILE]:
        assert file_path.exists(), f"Arquivo nao encontrado: {file_path}"

    generated_report_df = pd.read_csv(COVERAGE_REPORT_FILE)
    expected_columns = {
        "source_name",
        "dataset_name",
        "expected_frequency",
        "expected_observations",
        "actual_observations",
        "missing_observations",
        "coverage_pct",
        "status",
    }
    assert expected_columns.issubset(set(generated_report_df.columns))
    assert {"selic_daily", "ipca_monthly", "usd_brl_ptax_sell_daily", "cdi_daily"}.issubset(set(generated_report_df["dataset_name"]))
    assert {"PETR4.SA", "VALE3.SA", "ITUB4.SA", "^BVSP"}.issubset(set(generated_report_df["dataset_name"]))

    with open(COVERAGE_SUMMARY_FILE, "r", encoding="utf-8") as file:
        summary = json.load(file)
    assert summary["datasets"] >= 8
    assert summary["minimum_coverage_pct"] is not None

    print("\nTeste do Modulo 8 concluido com sucesso.")


if __name__ == "__main__":
    main()
