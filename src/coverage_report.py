from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    COVERAGE_MISSING_DATES_FILE,
    COVERAGE_REPORT_FILE,
    COVERAGE_SUMMARY_FILE,
    PROCESSED_DB_FILE,
)
from financial_calendar import expected_dates
from logger import get_logger
from monitoring import record_data_artifact
from reference_data.b3_calendar import calendar_source, get_b3_expected_trading_dates

logger = get_logger(__name__)

STATUS_OK = "OK"
STATUS_WARNING = "WARNING"
STATUS_CRITICAL = "CRITICAL"
STATUS_UNKNOWN = "UNKNOWN"


def _now() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_date_string(value) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _source_frequency(source_name: str, dataset_name: str, frequency: str | None = None) -> str:
    if frequency == "monthly" or dataset_name == "ipca_monthly":
        return "monthly"
    if source_name == "YAHOO_FINANCE" or dataset_name.startswith("^") or dataset_name.endswith(".SA"):
        return "trading_day"
    return "daily_business"


def classify_coverage_status(coverage_pct: float | None, missing_observations: int) -> str:
    if coverage_pct is None:
        return STATUS_UNKNOWN
    if coverage_pct >= 98.0 and missing_observations <= 5:
        return STATUS_OK
    if coverage_pct >= 90.0:
        return STATUS_WARNING
    return STATUS_CRITICAL


def calculate_coverage(
    actual_dates,
    start_date,
    end_date,
    frequency: str,
    expected_override: list | None = None,
) -> dict[str, Any]:
    expected = expected_override if expected_override is not None else expected_dates(start_date, end_date, frequency)
    expected_set = {_to_date_string(d) for d in expected}

    actual = pd.to_datetime(pd.Series(list(actual_dates)), errors="coerce").dropna()
    actual_in_range = actual[
        (actual >= pd.to_datetime(start_date))
        & (actual <= pd.to_datetime(end_date))
    ]
    actual_set = {_to_date_string(d) for d in actual_in_range}

    missing_dates = sorted(expected_set - actual_set)
    actual_expected_count = len(expected_set & actual_set)
    expected_count = len(expected_set)
    coverage_pct = None if expected_count == 0 else round((actual_expected_count / expected_count) * 100, 2)

    return {
        "expected_observations": expected_count,
        "actual_observations": actual_expected_count,
        "missing_observations": len(missing_dates),
        "coverage_pct": coverage_pct,
        "missing_dates": missing_dates,
        "first_expected_date": min(expected_set) if expected_set else None,
        "last_expected_date": max(expected_set) if expected_set else None,
        "first_available_date": min(actual_set) if actual_set else None,
        "last_available_date": max(actual_set) if actual_set else None,
        "status": classify_coverage_status(coverage_pct, len(missing_dates)),
    }


def build_coverage_report(
    bcb_series_df: pd.DataFrame,
    stocks_df: pd.DataFrame,
    start_date,
    end_date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    generated_at = _now()

    if not bcb_series_df.empty:
        for series_name, series_df in bcb_series_df.groupby("series_name"):
            frequency = _source_frequency(
                "BCB_SGS",
                str(series_name),
                str(series_df["frequency"].iloc[0]) if "frequency" in series_df.columns else None,
            )
            coverage = calculate_coverage(series_df["reference_date"], start_date, end_date, frequency)
            rows.append(
                {
                    "source_name": "BCB_SGS",
                    "dataset_name": str(series_name),
                    "expected_frequency": frequency,
                    "start_date": _to_date_string(start_date),
                    "end_date": _to_date_string(end_date),
                    "first_expected_date": coverage["first_expected_date"],
                    "last_expected_date": coverage["last_expected_date"],
                    "first_available_date": coverage["first_available_date"],
                    "last_available_date": coverage["last_available_date"],
                    "expected_observations": coverage["expected_observations"],
                    "actual_observations": coverage["actual_observations"],
                    "missing_observations": coverage["missing_observations"],
                    "coverage_pct": coverage["coverage_pct"],
                    "status": coverage["status"],
                    "calendar_source": "brazil_business_day" if frequency != "monthly" else "monthly_calendar",
                    "last_expected_trading_date": coverage["last_expected_date"],
                    "missing_sample": ", ".join(coverage["missing_dates"][:10]),
                    "generated_at": generated_at,
                }
            )
            missing_rows.extend(
                {
                    "source_name": "BCB_SGS",
                    "dataset_name": str(series_name),
                    "expected_frequency": frequency,
                    "missing_date": missing_date,
                    "generated_at": generated_at,
                }
                for missing_date in coverage["missing_dates"]
            )

    if not stocks_df.empty:
        for ticker, ticker_df in stocks_df.groupby("ticker"):
            frequency = _source_frequency("YAHOO_FINANCE", str(ticker))
            b3_expected_dates = get_b3_expected_trading_dates(start_date, end_date)
            coverage = calculate_coverage(
                ticker_df["reference_date"],
                start_date,
                end_date,
                frequency,
                expected_override=b3_expected_dates,
            )
            rows.append(
                {
                    "source_name": "YAHOO_FINANCE",
                    "dataset_name": str(ticker),
                    "expected_frequency": frequency,
                    "start_date": _to_date_string(start_date),
                    "end_date": _to_date_string(end_date),
                    "first_expected_date": coverage["first_expected_date"],
                    "last_expected_date": coverage["last_expected_date"],
                    "first_available_date": coverage["first_available_date"],
                    "last_available_date": coverage["last_available_date"],
                    "expected_observations": coverage["expected_observations"],
                    "actual_observations": coverage["actual_observations"],
                    "missing_observations": coverage["missing_observations"],
                    "coverage_pct": coverage["coverage_pct"],
                    "status": coverage["status"],
                    "calendar_source": calendar_source(),
                    "last_expected_trading_date": coverage["last_expected_date"],
                    "missing_sample": ", ".join(coverage["missing_dates"][:10]),
                    "generated_at": generated_at,
                }
            )
            missing_rows.extend(
                {
                    "source_name": "YAHOO_FINANCE",
                    "dataset_name": str(ticker),
                    "expected_frequency": frequency,
                    "missing_date": missing_date,
                    "generated_at": generated_at,
                }
                for missing_date in coverage["missing_dates"]
            )

    report_columns = [
        "source_name",
        "dataset_name",
        "expected_frequency",
        "start_date",
        "end_date",
        "first_expected_date",
        "last_expected_date",
        "first_available_date",
        "last_available_date",
        "expected_observations",
        "actual_observations",
        "missing_observations",
        "coverage_pct",
        "status",
        "calendar_source",
        "last_expected_trading_date",
        "missing_sample",
        "generated_at",
    ]
    missing_columns = [
        "source_name",
        "dataset_name",
        "expected_frequency",
        "missing_date",
        "generated_at",
    ]
    return pd.DataFrame(rows, columns=report_columns), pd.DataFrame(missing_rows, columns=missing_columns)


def load_processed_frames(database_file: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not database_file.exists():
        raise FileNotFoundError(f"Banco final nao encontrado: {database_file}")

    with sqlite3.connect(database_file) as conn:
        bcb_series_df = pd.read_sql_query(
            """
            SELECT series_name, frequency, reference_date
            FROM vw_bcb_series_values
            ORDER BY series_name, reference_date
            """,
            conn,
        )
        stocks_df = pd.read_sql_query(
            """
            SELECT ticker, reference_date
            FROM vw_b3_stock_prices
            ORDER BY ticker, reference_date
            """,
            conn,
        )

    bcb_series_df["reference_date"] = pd.to_datetime(bcb_series_df["reference_date"])
    stocks_df["reference_date"] = pd.to_datetime(stocks_df["reference_date"])
    return bcb_series_df, stocks_df


def _build_summary(report_df: pd.DataFrame, start_date, end_date) -> dict[str, Any]:
    if report_df.empty:
        return {
            "generated_at": _now(),
            "start_date": _to_date_string(start_date),
            "end_date": _to_date_string(end_date),
            "datasets": 0,
            "ok": 0,
            "warning": 0,
            "critical": 0,
            "unknown": 0,
            "average_coverage_pct": None,
            "minimum_coverage_pct": None,
            "overall_status": STATUS_UNKNOWN,
        }

    status_counts = report_df["status"].value_counts().to_dict()
    if status_counts.get(STATUS_CRITICAL, 0) > 0:
        overall_status = STATUS_CRITICAL
    elif status_counts.get(STATUS_WARNING, 0) > 0:
        overall_status = STATUS_WARNING
    elif status_counts.get(STATUS_UNKNOWN, 0) > 0:
        overall_status = STATUS_UNKNOWN
    else:
        overall_status = STATUS_OK

    coverage_values = report_df["coverage_pct"].dropna()
    average_coverage_pct = None if coverage_values.empty else round(float(coverage_values.mean()), 2)
    minimum_coverage_pct = None if coverage_values.empty else round(float(coverage_values.min()), 2)

    return {
        "generated_at": _now(),
        "start_date": _to_date_string(start_date),
        "end_date": _to_date_string(end_date),
        "datasets": int(len(report_df)),
        "ok": int(status_counts.get(STATUS_OK, 0)),
        "warning": int(status_counts.get(STATUS_WARNING, 0)),
        "critical": int(status_counts.get(STATUS_CRITICAL, 0)),
        "unknown": int(status_counts.get(STATUS_UNKNOWN, 0)),
        "average_coverage_pct": average_coverage_pct,
        "minimum_coverage_pct": minimum_coverage_pct,
        "overall_status": overall_status,
    }


def generate_coverage_artifacts(
    database_file: Path = PROCESSED_DB_FILE,
    report_file: Path = COVERAGE_REPORT_FILE,
    summary_file: Path = COVERAGE_SUMMARY_FILE,
    missing_dates_file: Path = COVERAGE_MISSING_DATES_FILE,
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    run_id: int | None = None,
) -> dict[str, Any]:
    bcb_series_df, stocks_df = load_processed_frames(database_file)
    report_df, missing_df = build_coverage_report(bcb_series_df, stocks_df, start_date, end_date)
    summary = _build_summary(report_df, start_date, end_date)

    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(report_file, index=False, encoding="utf-8")
    missing_df.to_csv(missing_dates_file, index=False, encoding="utf-8")
    with open(summary_file, "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=4)

    record_data_artifact("coverage_report", report_file, "data_coverage", len(report_df), status="CREATED", run_id=run_id)
    record_data_artifact("coverage_summary", summary_file, "data_coverage", 1, status="CREATED", run_id=run_id)
    record_data_artifact("coverage_missing_dates", missing_dates_file, "data_coverage", len(missing_df), status="CREATED", run_id=run_id)
    return summary


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-file", default=str(PROCESSED_DB_FILE))
    parser.add_argument("--report-file", default=str(COVERAGE_REPORT_FILE))
    parser.add_argument("--summary-file", default=str(COVERAGE_SUMMARY_FILE))
    parser.add_argument("--missing-dates-file", default=str(COVERAGE_MISSING_DATES_FILE))
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-12-31")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = generate_coverage_artifacts(
        database_file=Path(args.database_file),
        report_file=Path(args.report_file),
        summary_file=Path(args.summary_file),
        missing_dates_file=Path(args.missing_dates_file),
        start_date=args.start,
        end_date=args.end,
    )
    logger.info("Cobertura historica gerada: %s", summary)


if __name__ == "__main__":
    main()
