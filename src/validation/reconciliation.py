from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import (
    COVERAGE_REPORT_FILE,
    COVERAGE_SUMMARY_FILE,
    FINANCIAL_REPORT_FILE,
    OUTPUT_FILES,
    PROCESSED_DB_FILE,
    PROJECT_ROOT,
)
from metadata.audit import ensure_audit_schema, register_dataset_version, register_reconciliation_checks, register_source_file
from metadata.dataset_versioning import dataframe_dataset_version, file_dataset_version
from metadata.manifest import get_git_commit, now_text

REPORT_DIR = PROJECT_ROOT / "reports" / "reconciliation"
REPORT_RUNS_DIR = REPORT_DIR / "runs"


def _check(run_id: str, check_name: str, severity: str, status: str, expected_value="", actual_value="", difference_value="", details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "check_id": uuid.uuid4().hex,
        "run_id": run_id,
        "check_name": check_name,
        "severity": severity,
        "status": status,
        "expected_value": expected_value,
        "actual_value": actual_value,
        "difference_value": difference_value,
        "details": details or {},
        "created_at": now_text(),
    }


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return int(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)).fetchone()[0]) > 0


def _view_exists(conn: sqlite3.Connection, view_name: str) -> bool:
    return int(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'view' AND name = ?", (view_name,)).fetchone()[0]) > 0


def _count(conn: sqlite3.Connection, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _duplicate_count(conn: sqlite3.Connection, table_name: str, keys: list[str]) -> int:
    key_sql = ", ".join(keys)
    return int(conn.execute(f"SELECT COUNT(*) FROM (SELECT {key_sql}, COUNT(*) FROM {table_name} GROUP BY {key_sql} HAVING COUNT(*) > 1)").fetchone()[0])


def register_dataset_versions_from_local_state(run_id: str, database_file: Path = PROCESSED_DB_FILE) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    if database_file.exists():
        ensure_audit_schema(database_file)
        with sqlite3.connect(database_file) as conn:
            queries = [
                ("bcb_series_values", "BCB_SGS", "SELECT * FROM vw_bcb_series_values", "reference_date"),
                ("b3_stock_prices", "YAHOO_FINANCE", "SELECT * FROM vw_b3_stock_prices", "reference_date"),
                ("cvm_fund_daily_reports", "CVM", "SELECT * FROM vw_cvm_fund_daily_reports", "reference_date"),
            ]
            for dataset_name, source_name, query, date_column in queries:
                try:
                    df = pd.read_sql_query(query, conn)
                except Exception:
                    continue
                if df.empty:
                    continue
                version = dataframe_dataset_version(dataset_name, source_name, df, run_id, date_column=date_column, storage_path=str(database_file))
                register_dataset_version(version, database_file)
                versions.append(version)

    file_versions = [
        ("b3_trading_calendar", "B3_REFERENCE", PROJECT_ROOT / "data" / "reference" / "b3_trading_calendar.csv"),
        ("financial_report", "PIPELINE_EXPORT", FINANCIAL_REPORT_FILE),
        ("coverage_report", "PIPELINE_EXPORT", COVERAGE_REPORT_FILE),
    ]
    for dataset_name, source_name, path in file_versions:
        if path.exists():
            version = file_dataset_version(dataset_name, source_name, path, run_id)
            register_dataset_version(version, database_file)
            versions.append(version)

    for dataset_name, path in OUTPUT_FILES.items():
        register_source_file(run_id, dataset_name, path, database_file)
    return versions


def run_reconciliation(
    run_id: str,
    command: str = "",
    manifest_path: Path | None = None,
    database_file: Path = PROCESSED_DB_FILE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []

    expected_files = [
        OUTPUT_FILES["selic_daily"],
        OUTPUT_FILES["ipca_monthly"],
        OUTPUT_FILES["usd_brl_ptax_sell_daily"],
        OUTPUT_FILES["cdi_daily"],
        OUTPUT_FILES["stock_prices_daily"],
        PROJECT_ROOT / "data" / "reference" / "b3_trading_calendar.csv",
        COVERAGE_SUMMARY_FILE,
        FINANCIAL_REPORT_FILE,
    ]
    for file_path in expected_files:
        checks.append(_check(run_id, f"file_exists:{file_path.name}", "ERROR", "PASSED" if Path(file_path).exists() else "FAILED", "exists", Path(file_path).exists(), details={"path": str(file_path)}))

    checks.append(_check(run_id, "sqlite_database_exists", "ERROR", "PASSED" if database_file.exists() else "FAILED", "exists", database_file.exists(), details={"path": str(database_file)}))

    dataset_versions: list[dict[str, Any]] = []
    if database_file.exists():
        ensure_audit_schema(database_file)
        dataset_versions = register_dataset_versions_from_local_state(run_id, database_file)
        with sqlite3.connect(database_file) as conn:
            required_tables = [
                "dim_source",
                "dim_bcb_series",
                "dim_b3_ticker",
                "fact_bcb_series_values",
                "fact_b3_stock_prices",
                "dim_cvm_fund",
                "fact_cvm_fund_daily_report",
                "etl_run",
                "etl_dataset_version",
                "etl_reconciliation_check",
                "etl_source_file",
            ]
            for table in required_tables:
                exists = _table_exists(conn, table)
                checks.append(_check(run_id, f"table_exists:{table}", "ERROR", "PASSED" if exists else "FAILED", "exists", exists))
                if exists:
                    checks.append(_check(run_id, f"table_row_count:{table}", "INFO", "PASSED", ">=0", _count(conn, table)))

            duplicate_rules = [
                ("fact_bcb_series_values", ["series_id", "reference_date"]),
                ("fact_b3_stock_prices", ["ticker_id", "reference_date"]),
                ("fact_cvm_fund_daily_report", ["fund_id", "reference_date"]),
            ]
            for table, keys in duplicate_rules:
                if _table_exists(conn, table):
                    duplicates = _duplicate_count(conn, table, keys)
                    checks.append(_check(run_id, f"duplicates:{table}", "ERROR", "PASSED" if duplicates == 0 else "FAILED", 0, duplicates))

            future_rules = [
                ("fact_bcb_series_values", "reference_date"),
                ("fact_b3_stock_prices", "reference_date"),
                ("fact_cvm_fund_daily_report", "reference_date"),
            ]
            today = pd.Timestamp.today().strftime("%Y-%m-%d")
            for table, date_column in future_rules:
                if _table_exists(conn, table):
                    future_count = int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {date_column} > ?", (today,)).fetchone()[0])
                    checks.append(_check(run_id, f"future_dates:{table}", "ERROR", "PASSED" if future_count == 0 else "FAILED", 0, future_count))

            null_rules = [
                ("fact_bcb_series_values", "reference_date"),
                ("fact_b3_stock_prices", "reference_date"),
                ("dim_b3_ticker", "ticker"),
                ("dim_cvm_fund", "fund_cnpj"),
            ]
            for table, column in null_rules:
                if _table_exists(conn, table):
                    nulls = int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL OR TRIM(CAST({column} AS TEXT)) = ''").fetchone()[0])
                    checks.append(_check(run_id, f"nulls:{table}.{column}", "ERROR", "PASSED" if nulls == 0 else "FAILED", 0, nulls))

            if _table_exists(conn, "fact_cvm_fund_daily_report") and _count(conn, "fact_cvm_fund_daily_report") > 0:
                bad_cvm = int(conn.execute("SELECT COUNT(*) FROM fact_cvm_fund_daily_report WHERE net_asset_value < 0 OR quota_value <= 0").fetchone()[0])
                checks.append(_check(run_id, "cvm_values_valid", "ERROR", "PASSED" if bad_cvm == 0 else "FAILED", 0, bad_cvm))
            else:
                checks.append(_check(run_id, "cvm_optional_data", "INFO", "SKIPPED", "CVM files loaded", "not loaded", details={"reason": "CVM opcional ausente ou nao coletado nesta execucao."}))

    if os.getenv("ANBIMA_ENABLE", "false").lower() not in {"true", "1", "yes", "sim"}:
        checks.append(_check(run_id, "anbima_configuration", "INFO", "SKIPPED", "ANBIMA enabled", "ANBIMA_ENABLE=false"))
    else:
        has_creds = bool(os.getenv("ANBIMA_ACCESS_TOKEN") or (os.getenv("ANBIMA_CLIENT_ID") and os.getenv("ANBIMA_CLIENT_SECRET")))
        checks.append(_check(run_id, "anbima_configuration", "WARNING", "PASSED" if has_creds else "FAILED", "credentials available", has_creds))

    if manifest_path is not None:
        checks.append(_check(run_id, "manifest_created", "ERROR", "PASSED" if manifest_path.exists() else "FAILED", "exists", manifest_path.exists(), details={"path": str(manifest_path)}))

    checks.append(_check(run_id, "dataset_versions_registered", "ERROR", "PASSED" if dataset_versions else "FAILED", ">0", len(dataset_versions)))

    if COVERAGE_SUMMARY_FILE.exists():
        with open(COVERAGE_SUMMARY_FILE, "r", encoding="utf-8") as file:
            summary = json.load(file)
        status = summary.get("overall_status")
        checks.append(_check(run_id, "coverage_summary_status", "WARNING", "PASSED" if status in {"OK", "PASS"} else "FAILED", "OK", status, details=summary))
    else:
        checks.append(_check(run_id, "coverage_summary_status", "WARNING", "SKIPPED", "coverage summary", "missing"))

    register_reconciliation_checks(run_id, checks, database_file)
    return checks, dataset_versions


def _overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "FAILED" and check["severity"] == "ERROR" for check in checks):
        return "FAILED"
    if any(check["status"] == "FAILED" for check in checks):
        return "WARNING"
    return "PASSED"


def _write_reports(run_id: str, checks: list[dict[str, Any]], command: str, git_commit: str, report_dir: Path = REPORT_DIR) -> dict[str, Path]:
    report_runs_dir = report_dir / "runs"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_runs_dir.mkdir(parents=True, exist_ok=True)
    checks_df = pd.DataFrame(checks)
    summary = {
        "run_id": run_id,
        "git_commit": git_commit,
        "command": command,
        "overall_status": _overall_status(checks),
        "passed": int((checks_df["status"] == "PASSED").sum()),
        "failed": int((checks_df["status"] == "FAILED").sum()),
        "skipped": int((checks_df["status"] == "SKIPPED").sum()),
        "generated_at": now_text(),
    }
    paths = {
        "latest_json": report_dir / "latest.json",
        "latest_csv": report_dir / "latest.csv",
        "latest_md": report_dir / "latest.md",
        "run_json": report_runs_dir / f"{run_id}.json",
        "run_csv": report_runs_dir / f"{run_id}.csv",
        "run_md": report_runs_dir / f"{run_id}.md",
    }
    for path in [paths["latest_json"], paths["run_json"]]:
        with open(path, "w", encoding="utf-8") as file:
            json.dump({"summary": summary, "checks": checks}, file, ensure_ascii=False, indent=4)
    for path in [paths["latest_csv"], paths["run_csv"]]:
        checks_df.to_csv(path, index=False, encoding="utf-8")

    failures = checks_df[checks_df["status"] == "FAILED"] if not checks_df.empty else pd.DataFrame()
    markdown = [
        "# Reconciliation Report",
        "",
        f"- run_id: `{run_id}`",
        f"- git_commit: `{git_commit}`",
        f"- command: `{command}`",
        f"- overall_status: `{summary['overall_status']}`",
        f"- PASSED: {summary['passed']}",
        f"- FAILED: {summary['failed']}",
        f"- SKIPPED: {summary['skipped']}",
        "",
        "## Failed Checks",
    ]
    if failures.empty:
        markdown.append("No failed checks.")
    else:
        for _, row in failures.iterrows():
            markdown.append(f"- {row['severity']} `{row['check_name']}` expected `{row['expected_value']}` actual `{row['actual_value']}`")
    markdown.extend(
        [
            "",
            "## Known Limitations",
            "- CVM and ANBIMA are optional institutional sources.",
            "- PostgreSQL is prepared as an optional backend and is not required by default.",
            "- Historical coverage for more than 2024 depends on executing and validating the real backfill.",
        ]
    )
    for path in [paths["latest_md"], paths["run_md"]]:
        path.write_text("\n".join(markdown), encoding="utf-8")
    return paths


def reconcile(
    run_id: str,
    command: str = "",
    manifest_path: Path | None = None,
    database_file: Path = PROCESSED_DB_FILE,
    report_dir: Path = REPORT_DIR,
) -> dict[str, Any]:
    checks, dataset_versions = run_reconciliation(run_id, command=command, manifest_path=manifest_path, database_file=database_file)
    report_paths = _write_reports(run_id, checks, command, get_git_commit(), report_dir=report_dir)
    return {
        "run_id": run_id,
        "overall_status": _overall_status(checks),
        "checks": checks,
        "dataset_versions": dataset_versions,
        "report_paths": {key: str(value) for key, value in report_paths.items()},
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--manifest-path", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = reconcile(args.run_id, command=" ".join(sys.argv), manifest_path=Path(args.manifest_path) if args.manifest_path else None)
    print(json.dumps({"run_id": result["run_id"], "overall_status": result["overall_status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
