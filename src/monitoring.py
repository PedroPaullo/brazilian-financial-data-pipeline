from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import OPERATIONS_DB_FILE, PROCESSED_DB_FILE
from financial_calendar import calculate_lag_days, classify_freshness_status, source_sla

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
    max_lag_days INTEGER,
    lag_days INTEGER,
    freshness_status TEXT,
    details TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source_name, dataset_name)
);

CREATE TABLE IF NOT EXISTS data_artifacts (
    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    artifact_type TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    dataset_name TEXT,
    created_at TEXT NOT NULL,
    row_count INTEGER,
    status TEXT NOT NULL,
    details TEXT
);
"""

SOURCE_FRESHNESS_COLUMNS = {
    "max_lag_days": "INTEGER",
    "lag_days": "INTEGER",
    "freshness_status": "TEXT",
    "details": "TEXT",
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def initialize_monitoring_db(database_file: Path = OPERATIONS_DB_FILE) -> None:
    database_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_file) as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_columns(conn, "source_freshness", SOURCE_FRESHNESS_COLUMNS)
        conn.commit()


def _ensure_columns(conn: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
    existing_columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


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


def upsert_source_freshness(
    source_name: str,
    dataset_name: str,
    last_available_date: str,
    expected_frequency: str,
    records_count: int,
    max_lag_days: int | None = None,
    details: str | None = None,
    database_file: Path = OPERATIONS_DB_FILE,
) -> None:
    initialize_monitoring_db(database_file)
    last_date = pd.to_datetime(last_available_date)
    if max_lag_days is None:
        sla = source_sla(dataset_name, source_name)
        expected_frequency = str(sla["expected_frequency"])
        max_lag_days = int(sla["max_lag_days"])

    lag_days = calculate_lag_days(last_date, frequency=expected_frequency)
    freshness_status = classify_freshness_status(lag_days, max_lag_days)

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
                max_lag_days,
                lag_days,
                freshness_status,
                details,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, dataset_name) DO UPDATE SET
                last_available_date = excluded.last_available_date,
                expected_frequency = excluded.expected_frequency,
                status = excluded.status,
                records_count = excluded.records_count,
                max_lag_days = excluded.max_lag_days,
                lag_days = excluded.lag_days,
                freshness_status = excluded.freshness_status,
                details = excluded.details,
                updated_at = excluded.updated_at
            """,
            (
                source_name,
                dataset_name,
                last_date.strftime("%Y-%m-%d"),
                expected_frequency,
                freshness_status,
                records_count,
                max_lag_days,
                lag_days,
                freshness_status,
                details or "",
                now_text(),
            ),
        )
        conn.commit()


def record_data_artifact(
    artifact_type: str,
    artifact_path: Path,
    dataset_name: str | None = None,
    row_count: int | None = None,
    status: str = "CREATED",
    details: str | None = None,
    run_id: int | None = None,
    database_file: Path = OPERATIONS_DB_FILE,
) -> None:
    initialize_monitoring_db(database_file)
    artifact_path = Path(artifact_path)
    with sqlite3.connect(database_file) as conn:
        conn.execute(
            """
            INSERT INTO data_artifacts (
                run_id,
                artifact_type,
                artifact_path,
                dataset_name,
                created_at,
                row_count,
                status,
                details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                artifact_type,
                str(artifact_path),
                dataset_name,
                now_text(),
                row_count,
                status,
                details or "",
            ),
        )
        conn.commit()


def upsert_source_status(
    source_name: str,
    dataset_name: str,
    status: str,
    expected_frequency: str = "optional",
    records_count: int = 0,
    details: str | None = None,
    database_file: Path = OPERATIONS_DB_FILE,
) -> None:
    initialize_monitoring_db(database_file)
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
                max_lag_days,
                lag_days,
                freshness_status,
                details,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, dataset_name) DO UPDATE SET
                last_available_date = excluded.last_available_date,
                expected_frequency = excluded.expected_frequency,
                status = excluded.status,
                records_count = excluded.records_count,
                max_lag_days = excluded.max_lag_days,
                lag_days = excluded.lag_days,
                freshness_status = excluded.freshness_status,
                details = excluded.details,
                updated_at = excluded.updated_at
            """,
            (
                source_name,
                dataset_name,
                None,
                expected_frequency,
                status,
                records_count,
                None,
                None,
                status,
                details or "",
                now_text(),
            ),
        )
        conn.commit()


def _object_exists(conn: sqlite3.Connection, object_type: str, object_name: str) -> bool:
    query = "SELECT COUNT(*) FROM sqlite_master WHERE type = ? AND name = ?"
    return int(conn.execute(query, (object_type, object_name)).fetchone()[0]) > 0


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
        if _object_exists(conn, "view", "vw_cvm_fund_daily_reports"):
            cvm_df = pd.read_sql_query(
                """
                SELECT MAX(reference_date) AS last_available_date, COUNT(*) AS records_count
                FROM vw_cvm_fund_daily_reports
                """,
                conn,
            )
        else:
            cvm_df = pd.DataFrame()

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

    if not cvm_df.empty and int(cvm_df.iloc[0]["records_count"]) > 0:
        upsert_source_freshness(
            source_name="CVM",
            dataset_name="cvm_funds_daily_reports",
            last_available_date=str(cvm_df.iloc[0]["last_available_date"]),
            expected_frequency="daily_business",
            records_count=int(cvm_df.iloc[0]["records_count"]),
            database_file=operations_db_file,
        )
    else:
        upsert_source_status(
            source_name="CVM",
            dataset_name="cvm_funds_daily_reports",
            status="SKIPPED",
            expected_frequency="optional",
            records_count=0,
            details="Dados CVM Fundos nao carregados nesta execucao.",
            database_file=operations_db_file,
        )

    upsert_source_status(
        source_name="ANBIMA",
        dataset_name="anbima_adapter",
        status="SKIPPED",
        expected_frequency="optional",
        records_count=0,
        details="ANBIMA_ENABLE=false ou credenciais ausentes; adapter preparado para Melhoria 9.",
        database_file=operations_db_file,
    )
