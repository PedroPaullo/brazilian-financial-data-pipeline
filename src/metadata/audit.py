from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from config import PROCESSED_DB_FILE
from metadata.manifest import calculate_file_checksum, now_text

AUDIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS etl_run (
    run_id TEXT PRIMARY KEY,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    command TEXT,
    parameters_json TEXT,
    git_commit TEXT,
    database_backend TEXT,
    warnings_json TEXT,
    errors_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS etl_dataset_version (
    dataset_version_id TEXT PRIMARY KEY,
    run_id TEXT,
    dataset_name TEXT,
    source_name TEXT,
    period_start TEXT,
    period_end TEXT,
    row_count INTEGER,
    checksum TEXT,
    storage_path TEXT,
    schema_hash TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS etl_reconciliation_check (
    check_id TEXT PRIMARY KEY,
    run_id TEXT,
    check_name TEXT,
    severity TEXT,
    status TEXT,
    expected_value TEXT,
    actual_value TEXT,
    difference_value TEXT,
    details_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS etl_source_file (
    source_file_id TEXT PRIMARY KEY,
    run_id TEXT,
    source_name TEXT,
    file_path TEXT,
    file_name TEXT,
    file_size_bytes INTEGER,
    checksum TEXT,
    modified_at TEXT,
    created_at TEXT
);

DROP VIEW IF EXISTS vw_etl_runs_latest;
CREATE VIEW vw_etl_runs_latest AS
SELECT *
FROM etl_run
ORDER BY created_at DESC
LIMIT 50;

DROP VIEW IF EXISTS vw_dataset_versions_latest;
CREATE VIEW vw_dataset_versions_latest AS
WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY dataset_name, source_name ORDER BY created_at DESC) AS rn
    FROM etl_dataset_version
)
SELECT *
FROM ranked
WHERE rn = 1;

DROP VIEW IF EXISTS vw_reconciliation_summary;
CREATE VIEW vw_reconciliation_summary AS
SELECT run_id, status, severity, COUNT(*) AS checks_count
FROM etl_reconciliation_check
GROUP BY run_id, status, severity;

DROP VIEW IF EXISTS vw_reconciliation_failures;
CREATE VIEW vw_reconciliation_failures AS
SELECT *
FROM etl_reconciliation_check
WHERE status = 'FAILED'
ORDER BY created_at DESC;
"""


def ensure_audit_schema(database_file: Path = PROCESSED_DB_FILE) -> None:
    database_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_file) as conn:
        conn.executescript(AUDIT_SCHEMA_SQL)
        conn.commit()


def register_etl_run(manifest: dict[str, Any], database_file: Path = PROCESSED_DB_FILE) -> None:
    ensure_audit_schema(database_file)
    with sqlite3.connect(database_file) as conn:
        conn.execute(
            """
            INSERT INTO etl_run (
                run_id, started_at, finished_at, status, command, parameters_json,
                git_commit, database_backend, warnings_json, errors_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                finished_at = excluded.finished_at,
                status = excluded.status,
                parameters_json = excluded.parameters_json,
                warnings_json = excluded.warnings_json,
                errors_json = excluded.errors_json
            """,
            (
                manifest.get("run_id"),
                manifest.get("started_at"),
                manifest.get("finished_at"),
                manifest.get("status"),
                manifest.get("command"),
                json.dumps(manifest.get("parameters", {}), ensure_ascii=False),
                manifest.get("git_commit"),
                manifest.get("database_backend"),
                json.dumps(manifest.get("warnings", []), ensure_ascii=False),
                json.dumps(manifest.get("errors", []), ensure_ascii=False),
                now_text(),
            ),
        )
        conn.commit()


def register_dataset_version(version: dict[str, Any], database_file: Path = PROCESSED_DB_FILE) -> None:
    ensure_audit_schema(database_file)
    with sqlite3.connect(database_file) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO etl_dataset_version (
                dataset_version_id, run_id, dataset_name, source_name, period_start,
                period_end, row_count, checksum, storage_path, schema_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version.get("dataset_version_id"),
                version.get("run_id"),
                version.get("dataset_name"),
                version.get("source_name"),
                version.get("period_start"),
                version.get("period_end"),
                version.get("row_count"),
                version.get("checksum"),
                version.get("storage_path"),
                version.get("schema_hash"),
                version.get("created_at"),
            ),
        )
        conn.commit()


def register_source_file(run_id: str, source_name: str, file_path: Path, database_file: Path = PROCESSED_DB_FILE) -> None:
    ensure_audit_schema(database_file)
    file_path = Path(file_path)
    source_file_id = uuid.uuid4().hex
    exists = file_path.exists() and file_path.is_file()
    with sqlite3.connect(database_file) as conn:
        conn.execute(
            """
            INSERT INTO etl_source_file (
                source_file_id, run_id, source_name, file_path, file_name,
                file_size_bytes, checksum, modified_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_file_id,
                run_id,
                source_name,
                str(file_path),
                file_path.name,
                file_path.stat().st_size if exists else None,
                calculate_file_checksum(file_path) if exists else None,
                now_text() if exists else None,
                now_text(),
            ),
        )
        conn.commit()


def register_reconciliation_checks(run_id: str, checks: list[dict[str, Any]], database_file: Path = PROCESSED_DB_FILE) -> None:
    ensure_audit_schema(database_file)
    rows = []
    for check in checks:
        rows.append(
            (
                check.get("check_id") or uuid.uuid4().hex,
                run_id,
                check.get("check_name"),
                check.get("severity"),
                check.get("status"),
                str(check.get("expected_value", "")),
                str(check.get("actual_value", "")),
                str(check.get("difference_value", "")),
                json.dumps(check.get("details", {}), ensure_ascii=False),
                check.get("created_at") or now_text(),
            )
        )
    with sqlite3.connect(database_file) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO etl_reconciliation_check (
                check_id, run_id, check_name, severity, status, expected_value,
                actual_value, difference_value, details_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
