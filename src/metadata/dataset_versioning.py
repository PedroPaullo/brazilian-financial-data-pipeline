from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from metadata.manifest import calculate_dataframe_checksum, calculate_file_checksum, calculate_schema_hash, now_text


def create_dataset_version_id(
    dataset_name: str,
    source_name: str,
    period_start: str | None,
    period_end: str | None,
    checksum: str | None,
    schema_hash: str | None,
) -> str:
    raw = "|".join(
        [
            dataset_name,
            source_name,
            period_start or "",
            period_end or "",
            checksum or "",
            schema_hash or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dataframe_dataset_version(
    dataset_name: str,
    source_name: str,
    df: pd.DataFrame,
    run_id: str,
    date_column: str | None = None,
    storage_path: str | None = None,
) -> dict[str, Any]:
    period_start = None
    period_end = None
    if date_column and date_column in df.columns and not df.empty:
        dates = pd.to_datetime(df[date_column], errors="coerce").dropna()
        if not dates.empty:
            period_start = dates.min().strftime("%Y-%m-%d")
            period_end = dates.max().strftime("%Y-%m-%d")

    checksum = calculate_dataframe_checksum(df)
    schema_hash = calculate_schema_hash(df)
    return {
        "dataset_version_id": create_dataset_version_id(dataset_name, source_name, period_start, period_end, checksum, schema_hash),
        "run_id": run_id,
        "dataset_name": dataset_name,
        "source_name": source_name,
        "period_start": period_start,
        "period_end": period_end,
        "row_count": int(len(df)),
        "checksum": checksum,
        "storage_path": storage_path or "",
        "schema_hash": schema_hash,
        "created_at": now_text(),
    }


def file_dataset_version(
    dataset_name: str,
    source_name: str,
    path: Path,
    run_id: str,
    row_count: int | None = None,
) -> dict[str, Any]:
    checksum = calculate_file_checksum(path)
    schema_hash = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return {
        "dataset_version_id": create_dataset_version_id(dataset_name, source_name, None, None, checksum, schema_hash),
        "run_id": run_id,
        "dataset_name": dataset_name,
        "source_name": source_name,
        "period_start": None,
        "period_end": None,
        "row_count": row_count,
        "checksum": checksum,
        "storage_path": str(path),
        "schema_hash": schema_hash,
        "created_at": now_text(),
    }
