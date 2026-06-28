from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
import json

import pandas as pd

from config import BCB_SERIES, COLLECTION_STATUS_JSON_FILE, OUTPUT_FILES

STATUS_SUCCESS = "SUCCESS"
STATUS_NOT_YET_AVAILABLE = "NOT_YET_AVAILABLE"
STATUS_SOURCE_EMPTY = "SOURCE_EMPTY"
STATUS_SOURCE_HTTP_ERROR = "SOURCE_HTTP_ERROR"
STATUS_SOURCE_UNEXPECTED_ERROR = "SOURCE_UNEXPECTED_ERROR"
STATUS_SKIPPED = "SKIPPED"

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_ERROR = "ERROR"

BCB_CSV_COLUMNS = ["source", "series_code", "series_name", "date", "value", "collected_at"]
STOCK_CSV_COLUMNS = [
    "source",
    "ticker",
    "date",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
    "collected_at",
]

SERIES_TO_RAW_TABLE = {
    "selic_daily": "raw_selic_daily",
    "ipca_monthly": "raw_ipca_monthly",
    "stock_prices_daily": "raw_stock_prices_daily",
}

RAW_TABLE_TO_SERIES = {table: series for series, table in SERIES_TO_RAW_TABLE.items()}

CSV_SCHEMAS = {
    "selic_daily": BCB_CSV_COLUMNS,
    "ipca_monthly": BCB_CSV_COLUMNS,
    "usd_brl_ptax_sell_daily": BCB_CSV_COLUMNS,
    "cdi_daily": BCB_CSV_COLUMNS,
    "stock_prices_daily": STOCK_CSV_COLUMNS,
}

EXPECTED_EMPTY_STATUSES = {STATUS_NOT_YET_AVAILABLE, STATUS_SKIPPED}
CONTROLLED_EMPTY_STATUSES = {
    STATUS_NOT_YET_AVAILABLE,
    STATUS_SKIPPED,
    STATUS_SOURCE_EMPTY,
    STATUS_SOURCE_HTTP_ERROR,
    STATUS_SOURCE_UNEXPECTED_ERROR,
}


def today_date() -> date:
    return date.today()


def output_series_for_file(file_path: Path) -> str | None:
    resolved = Path(file_path).resolve()
    for series_name, output_file in OUTPUT_FILES.items():
        try:
            if Path(output_file).resolve() == resolved:
                return series_name
        except FileNotFoundError:
            continue
    return None


def empty_dataframe_for_series(series_name: str | None) -> pd.DataFrame:
    return pd.DataFrame(columns=CSV_SCHEMAS.get(str(series_name), []))


def _to_timestamp(value: str | date | pd.Timestamp) -> pd.Timestamp:
    return pd.to_datetime(value).normalize()


def expected_periods_for_series(
    series_name: str,
    start_date: str,
    end_date: str,
    as_of_date: date | pd.Timestamp | None = None,
) -> list[str]:
    metadata = BCB_SERIES.get(series_name, {})
    frequency = metadata.get("frequency", "daily")
    lag_days = int(metadata.get("publication_lag_days", 0))
    start_ts = _to_timestamp(start_date)
    end_ts = _to_timestamp(end_date)
    as_of_ts = _to_timestamp(as_of_date or today_date())

    if end_ts < start_ts:
        return []

    available_until = as_of_ts - pd.Timedelta(days=lag_days)
    range_end = min(end_ts, available_until)
    if range_end < start_ts:
        return []

    if frequency == "monthly":
        periods = pd.period_range(start=start_ts, end=end_ts, freq="M")
        expected: list[str] = []
        for period in periods:
            month_end = period.to_timestamp(how="end").normalize()
            available_on = month_end + pd.Timedelta(days=lag_days)
            if available_on <= as_of_ts:
                expected.append(period.strftime("%Y-%m"))
        return expected

    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start_ts, range_end)]


def is_data_expected(
    series_name: str,
    start_date: str,
    end_date: str,
    as_of_date: date | pd.Timestamp | None = None,
) -> bool:
    return bool(expected_periods_for_series(series_name, start_date, end_date, as_of_date=as_of_date))


def build_bcb_status(
    series_name: str,
    metadata: dict[str, Any],
    start_date: str,
    end_date: str,
    rows: int,
    status: str,
    severity: str,
    reason: str,
    expected: bool,
    http_status_code: int | None = None,
    output_file: Path | None = None,
) -> dict[str, Any]:
    return {
        "source": "BCB_SGS",
        "series_name": series_name,
        "series_code": str(metadata.get("code", "")),
        "frequency": metadata.get("frequency", "unknown"),
        "required": bool(metadata.get("required", True)),
        "publication_lag_days": int(metadata.get("publication_lag_days", 0)),
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "rows_collected": int(rows),
        "rows": int(rows),
        "status": status,
        "severity": severity,
        "reason": reason,
        "expected": bool(expected),
        "data_expected": bool(expected),
        "http_status_code": http_status_code,
        "output_file": str(output_file) if output_file else str(OUTPUT_FILES.get(series_name, "")),
    }


def classify_bcb_failure(
    series_name: str,
    metadata: dict[str, Any],
    start_date: str,
    end_date: str,
    failure_type: str,
    reason: str,
    http_status_code: int | None = None,
) -> dict[str, Any]:
    expected = is_data_expected(series_name, start_date, end_date)
    required = bool(metadata.get("required", True))

    if failure_type in {"HTTP_404", "EMPTY_PAYLOAD"} and not expected:
        return build_bcb_status(
            series_name,
            metadata,
            start_date,
            end_date,
            rows=0,
            status=STATUS_NOT_YET_AVAILABLE,
            severity=SEVERITY_WARNING,
            reason=reason,
            expected=False,
            http_status_code=http_status_code,
        )

    if failure_type == "EMPTY_PAYLOAD":
        status = STATUS_SOURCE_EMPTY
    elif failure_type in {"HTTP_404", "HTTP_ERROR"}:
        status = STATUS_SOURCE_HTTP_ERROR
    else:
        status = STATUS_SOURCE_UNEXPECTED_ERROR

    severity = SEVERITY_ERROR if required and expected else SEVERITY_WARNING
    return build_bcb_status(
        series_name,
        metadata,
        start_date,
        end_date,
        rows=0,
        status=status,
        severity=severity,
        reason=reason,
        expected=expected,
        http_status_code=http_status_code,
    )


def build_bcb_success_status(
    series_name: str,
    metadata: dict[str, Any],
    start_date: str,
    end_date: str,
    rows: int,
    http_status_code: int | None = None,
) -> dict[str, Any]:
    return build_bcb_status(
        series_name,
        metadata,
        start_date,
        end_date,
        rows=rows,
        status=STATUS_SUCCESS,
        severity=SEVERITY_INFO,
        reason="Dados coletados com sucesso.",
        expected=is_data_expected(series_name, start_date, end_date),
        http_status_code=http_status_code,
    )


def apply_status_to_dataframe(df: pd.DataFrame, status_record: dict[str, Any]) -> pd.DataFrame:
    df.attrs["collection_status_record"] = status_record
    for key, value in status_record.items():
        df.attrs[key] = value
    df.attrs["collection_status"] = status_record.get("status")
    df.attrs["collection_reason"] = status_record.get("reason", "")
    return df


def load_collection_status(path: Path = COLLECTION_STATUS_JSON_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def collection_status_by_series(path: Path = COLLECTION_STATUS_JSON_FILE) -> dict[str, dict[str, Any]]:
    payload = load_collection_status(path)
    return {item.get("series_name"): item for item in payload.get("bcb_series", []) if item.get("series_name")}


def get_collection_item(series_name: str, path: Path = COLLECTION_STATUS_JSON_FILE) -> dict[str, Any] | None:
    return collection_status_by_series(path).get(series_name)


def is_expected_empty_status(item: dict[str, Any] | None) -> bool:
    return bool(item and item.get("status") in EXPECTED_EMPTY_STATUSES)


def is_controlled_empty_status(item: dict[str, Any] | None) -> bool:
    return bool(item and item.get("status") in CONTROLLED_EMPTY_STATUSES)
