from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

try:
    from config import PROJECT_ROOT
except ImportError:  # pragma: no cover
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

CALENDAR_FILE = PROJECT_ROOT / "data" / "reference" / "b3_trading_calendar.csv"

FALLBACK_B3_HOLIDAYS = {
    date(2024, 1, 1),
    date(2024, 2, 12),
    date(2024, 2, 13),
    date(2024, 3, 29),
    date(2024, 5, 1),
    date(2024, 5, 30),
    date(2024, 11, 15),
    date(2024, 11, 20),
    date(2024, 12, 24),
    date(2024, 12, 25),
    date(2024, 12, 31),
    date(2025, 1, 1),
    date(2025, 3, 3),
    date(2025, 3, 4),
    date(2025, 4, 18),
    date(2025, 4, 21),
    date(2025, 5, 1),
    date(2025, 6, 19),
    date(2025, 11, 20),
    date(2025, 12, 24),
    date(2025, 12, 25),
    date(2025, 12, 31),
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
    date(2026, 12, 24),
    date(2026, 12, 25),
    date(2026, 12, 31),
}


def _to_timestamp(value) -> pd.Timestamp:
    return pd.to_datetime(value).normalize()


def _fallback_calendar(start_date, end_date) -> pd.DataFrame:
    dates = pd.date_range(_to_timestamp(start_date), _to_timestamp(end_date), freq="D")
    rows = []
    updated_at = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    for current in dates:
        current_date = current.date()
        is_weekend = current.weekday() >= 5
        is_holiday = current_date in FALLBACK_B3_HOLIDAYS
        rows.append(
            {
                "date": current.strftime("%Y-%m-%d"),
                "is_trading_day": not is_weekend and not is_holiday,
                "market": "B3",
                "reason": "weekend" if is_weekend else ("holiday_or_no_session" if is_holiday else "regular_session"),
                "source": "fallback_generated",
                "updated_at": updated_at,
            }
        )
    return pd.DataFrame(rows)


def load_b3_calendar(calendar_file: Path = CALENDAR_FILE) -> pd.DataFrame:
    if calendar_file.exists():
        calendar_df = pd.read_csv(calendar_file)
        calendar_df["date"] = pd.to_datetime(calendar_df["date"]).dt.strftime("%Y-%m-%d")
        calendar_df["is_trading_day"] = calendar_df["is_trading_day"].map(
            lambda value: str(value).strip().lower() in {"true", "1", "yes"}
        )
        return calendar_df

    return _fallback_calendar("2024-01-01", "2026-12-31")


def calendar_source(calendar_file: Path = CALENDAR_FILE) -> str:
    if calendar_file.exists():
        return "manual_reference"
    return "fallback_generated"


def is_b3_trading_day(value, calendar_file: Path = CALENDAR_FILE) -> bool:
    value_text = _to_timestamp(value).strftime("%Y-%m-%d")
    calendar_df = load_b3_calendar(calendar_file)
    row = calendar_df[calendar_df["date"] == value_text]
    if row.empty:
        return bool(_fallback_calendar(value_text, value_text).iloc[0]["is_trading_day"])
    return bool(row.iloc[0]["is_trading_day"])


def get_b3_expected_trading_dates(start_date, end_date, calendar_file: Path = CALENDAR_FILE) -> list[date]:
    start = _to_timestamp(start_date)
    end = _to_timestamp(end_date)
    calendar_df = load_b3_calendar(calendar_file)
    calendar_df["date_ts"] = pd.to_datetime(calendar_df["date"])
    filtered = calendar_df[
        (calendar_df["date_ts"] >= start)
        & (calendar_df["date_ts"] <= end)
        & (calendar_df["is_trading_day"])
    ].copy()

    if filtered.empty:
        filtered = _fallback_calendar(start, end)
        filtered["date_ts"] = pd.to_datetime(filtered["date"])
        filtered = filtered[filtered["is_trading_day"]]

    return [value.date() for value in filtered["date_ts"]]


def get_missing_trading_dates(actual_dates, start_date, end_date, calendar_file: Path = CALENDAR_FILE) -> list[date]:
    expected = {pd.Timestamp(value).date() for value in get_b3_expected_trading_dates(start_date, end_date, calendar_file)}
    actual = {
        pd.Timestamp(value).date()
        for value in pd.to_datetime(pd.Series(list(actual_dates)), errors="coerce").dropna()
    }
    return sorted(expected - actual)


def classify_b3_gap(value, calendar_file: Path = CALENDAR_FILE) -> str:
    if is_b3_trading_day(value, calendar_file):
        return "unexpected_missing_trading_day"
    return "expected_no_trading_session"
