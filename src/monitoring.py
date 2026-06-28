from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import OPERATIONS_DB_FILE, PROCESSED_DB_FILE

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    records_input INTEGER,
    records_output INTEGER,
    warnings_count INTEGER,
    errors_count INTEGER,
    execution_time_seconds REAL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS source_freshness (
    source_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    last_available_date TEXT,
    expected_frequency TEXT NOT NULL,
    status TEXT NOT NULL,
    records_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source_name, dataset_name)
);
"""


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def initialize_monitoring_db(database_file: Path = OPERATIONS_DB_FILE) -> None:
    database_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_file) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def start_pipeline_run(module_name: str, database_file: Path = OPERATIONS_DB_FILE) -> int:
    initialize_monitoring_db(database_file)
    started_at = now_text()
    with sqlite3.connect(database_file) as conn:
        cursor = conn.execute(
            """
            INSERT INTO pipeline_runs (module_name, started_at, status)
            VALUES (?, ?, ?)
            """,
            (module_name, started_at, "RUNNING"),
        )
        conn.commit()
        return int(cursor.lastrowid)


def finish_pipeline_run(
    run_id: int,
    status: str,
    records_input: int | None = None,
    records_output: int | None = None,
    warnings_count: int | None = None,
    errors_count: int | None = None,
    error_message: str | None = None,
    database_file: Path = OPERATIONS_DB_FILE,
) -> None:
    finished_at = now_text()
    with sqlite3.connect(database_file) as conn:
        started_at = conn.execute(
            "SELECT started_at FROM pipeline_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        elapsed = (
            datetime.strptime(finished_at, "%Y-%m-%d %H:%M:%S")
            - datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
        ).total_seconds()

        conn.execute(
            """
            UPDATE pipeline_runs
            SET finished_at = ?,
                status = ?,
                records_input = ?,
                records_output = ?,
                warnings_count = ?,
                errors_count = ?,
                execution_time_seconds = ?,
                error_message = ?
            WHERE run_id = ?
            """,
            (
                finished_at,
                status,
                records_input,
                records_output,
                warnings_count,
                errors_count,
                elapsed,
                error_message,
                run_id,
            ),
        )
        conn.commit()


def classify_source_freshness(last_available_date: pd.Timestamp, expected_frequency: str) -> str:
    age_days = (pd.Timestamp.today().normalize() - last_available_date.normalize()).days

    if expected_frequency == "monthly":
        if age_days <= 45:
            return "OK"
        if age_days <= 75:
            return "Atencao"
        return "Desatualizado"

    if age_days <= 3:
        return "OK"
    if age_days <= 7:
        return "Atencao"
    return "Desatualizado"


def upsert_source_freshness(
    source_name: str,
    dataset_name: str,
    last_available_date: str,
    expected_frequency: str,
    records_count: int,
    database_file: Path = OPERATIONS_DB_FILE,
) -> None:
    initialize_monitoring_db(database_file)
    last_date = pd.to_datetime(last_available_date)
    status = classify_source_freshness(last_date, expected_frequency)

    with sqlite3.connect(database_file) as conn:
        conn.execute(
            """
            INSERT INTO source_freshness (
                source_name,
                dataset_name,
                last_available_date,
                expected_frequency,
                status,
                records_count,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, dataset_name) DO UPDATE SET
                last_available_date = excluded.last_available_date,
                expected_frequency = excluded.expected_frequency,
                status = excluded.status,
                records_count = excluded.records_count,
                updated_at = excluded.updated_at
            """,
            (
                source_name,
                dataset_name,
                last_date.strftime("%Y-%m-%d"),
                expected_frequency,
                status,
                records_count,
                now_text(),
            ),
        )
        conn.commit()


def refresh_source_freshness_from_processed_db(
    processed_db_file: Path = PROCESSED_DB_FILE,
    operations_db_file: Path = OPERATIONS_DB_FILE,
) -> None:
    with sqlite3.connect(processed_db_file) as conn:
        bcb_df = pd.read_sql_query(
            """
            SELECT series_name, MAX(reference_date) AS last_available_date, COUNT(*) AS records_count
            FROM vw_bcb_series_values
            GROUP BY series_name
            """,
            conn,
        )
        stocks_df = pd.read_sql_query(
            """
            SELECT ticker, MAX(reference_date) AS last_available_date, COUNT(*) AS records_count
            FROM vw_b3_stock_prices
            GROUP BY ticker
            """,
            conn,
        )

    for _, row in bcb_df.iterrows():
        expected_frequency = "monthly" if row["series_name"] == "ipca_monthly" else "daily"
        upsert_source_freshness(
            source_name="BCB_SGS",
            dataset_name=str(row["series_name"]),
            last_available_date=str(row["last_available_date"]),
            expected_frequency=expected_frequency,
            records_count=int(row["records_count"]),
            database_file=operations_db_file,
        )

    for _, row in stocks_df.iterrows():
        upsert_source_freshness(
            source_name="YAHOO_FINANCE",
            dataset_name=str(row["ticker"]),
            last_available_date=str(row["last_available_date"]),
            expected_frequency="daily",
            records_count=int(row["records_count"]),
            database_file=operations_db_file,
        )
