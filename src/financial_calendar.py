from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

try:
    import holidays
except ImportError:  # pragma: no cover - fallback for minimal environments
    holidays = None


STATUS_OK = "OK"
STATUS_WARNING = "WARNING"
STATUS_CRITICAL = "CRITICAL"
STATUS_UNKNOWN = "UNKNOWN"

FALLBACK_BR_HOLIDAYS = {
    # National and banking-market relevant holidays used when the holidays
    # package is not available in the local environment.
    date(2024, 1, 1),
    date(2024, 2, 12),
    date(2024, 2, 13),
    date(2024, 3, 29),
    date(2024, 5, 1),
    date(2024, 5, 30),
    date(2024, 11, 15),
    date(2024, 11, 20),
    date(2024, 12, 25),
    date(2025, 1, 1),
    date(2025, 3, 3),
    date(2025, 3, 4),
    date(2025, 4, 18),
    date(2025, 4, 21),
    date(2025, 5, 1),
    date(2025, 6, 19),
    date(2025, 11, 20),
    date(2025, 12, 25),
    date(2026, 1, 1),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 4, 3),
    date(2026, 4, 21),
    date(2026, 5, 1),
    date(2026, 6, 4),
    date(2026, 9, 7),
    date(2026, 10, 12),
    date(2026, 11, 2),
    date(2026, 11, 20),
    date(2026, 12, 25),
}


def _to_date(value) -> date:
    return pd.to_datetime(value).date()


def is_weekday(value) -> bool:
    return _to_date(value).weekday() < 5


def is_brazil_holiday(value) -> bool:
    value_date = _to_date(value)
    if holidays is None:
        return value_date in FALLBACK_BR_HOLIDAYS

    return value_date in holidays.country_holidays("BR")


def is_brazil_business_day(value) -> bool:
    return is_weekday(value) and not is_brazil_holiday(value)


def expected_dates(start, end, frequency: str) -> list[date]:
    start_date = _to_date(start)
    end_date = _to_date(end)

    if frequency in {"daily_business", "trading_day"}:
        dates = pd.date_range(start_date, end_date, freq="D")
        return [d.date() for d in dates if is_brazil_business_day(d)]

    if frequency == "monthly":
        return [d.date() for d in pd.date_range(start_date, end_date, freq="MS")]

    if frequency == "pipeline_artifact":
        return [_to_date(end)]

    return []


def calculate_lag_days(last_available_date, reference_date=None, frequency: str = "calendar") -> int | None:
    if last_available_date is None or pd.isna(last_available_date):
        return None

    last_date = _to_date(last_available_date)
    ref_date = _to_date(reference_date or pd.Timestamp.today())

    if last_date > ref_date:
        return 0

    if frequency in {"daily_business", "trading_day"}:
        days: Iterable[pd.Timestamp] = pd.date_range(last_date, ref_date, freq="D")
        return max(sum(1 for day in days if is_brazil_business_day(day)) - 1, 0)

    return max((ref_date - last_date).days, 0)


def classify_freshness_status(lag_days: int | None, max_lag_days: int | None) -> str:
    if lag_days is None or max_lag_days is None:
        return STATUS_UNKNOWN

    if lag_days <= max_lag_days:
        return STATUS_OK

    if lag_days <= max_lag_days * 2:
        return STATUS_WARNING

    return STATUS_CRITICAL


def source_sla(dataset_name: str, source_name: str | None = None) -> dict[str, int | str]:
    if dataset_name == "ipca_monthly":
        return {"expected_frequency": "monthly", "max_lag_days": 60}

    if dataset_name in {"selic_daily", "cdi_daily", "usd_brl_ptax_sell_daily"}:
        return {"expected_frequency": "daily_business", "max_lag_days": 2}

    if source_name == "YAHOO_FINANCE" or dataset_name.startswith("^") or dataset_name.endswith(".SA"):
        return {"expected_frequency": "trading_day", "max_lag_days": 2}

    if source_name == "CVM" or dataset_name.startswith("cvm_"):
        return {"expected_frequency": "daily_business", "max_lag_days": 7}

    if source_name == "ANBIMA":
        return {"expected_frequency": "optional", "max_lag_days": 30}

    if dataset_name in {"financial_report.xlsx", "alerts.json", "alerts.csv"}:
        return {"expected_frequency": "pipeline_artifact", "max_lag_days": 7}

    return {"expected_frequency": "calendar", "max_lag_days": 7}
