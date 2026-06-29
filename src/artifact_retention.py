from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_RETENTION_DAYS = 30


def today_stamp() -> str:
    return date.today().strftime("%Y%m%d")


def resolve_retention_days(value: int | None = None) -> int:
    if value is not None:
        return max(0, int(value))
    env_value = os.getenv("PIPELINE_RETENTION_DAYS")
    if env_value:
        try:
            return max(0, int(env_value))
        except ValueError:
            return DEFAULT_RETENTION_DAYS
    return DEFAULT_RETENTION_DAYS


def _date_from_name(path: Path) -> date | None:
    prefix = path.stem[:8]
    if len(prefix) != 8 or not prefix.isdigit():
        return None
    try:
        return datetime.strptime(prefix, "%Y%m%d").date()
    except ValueError:
        return None


def prune_artifacts(paths: list[Path], retention_days: int | None = None, today: date | None = None) -> list[Path]:
    cutoff = (today or date.today()) - timedelta(days=resolve_retention_days(retention_days))
    removed: list[Path] = []
    for directory in paths:
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file():
                continue
            file_date = _date_from_name(path)
            if file_date is None or file_date >= cutoff:
                continue
            path.unlink()
            removed.append(path)
    return removed
