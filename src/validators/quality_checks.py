from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd

CRITICAL_COLUMNS = {
    "raw_selic_daily": ["source", "series_code", "series_name", "date", "value"],
    "raw_ipca_monthly": ["source", "series_code", "series_name", "date", "value"],
    "raw_stock_prices_daily": ["source", "ticker", "date", "open", "high", "low", "close", "adjusted_close", "volume"],
}

def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _execute_scalar(conn, query):
    return int(conn.execute(query).fetchone()[0])

def _build_result(results, check_category, check_name, dataset, rule_type, severity, rows_affected, details, evidence_query=None):
    if rows_affected == 0:
        status = "PASS"
    else:
        status = "WARN" if severity == "warning" else "FAIL"
    results.append({
        "check_id": len(results) + 1,
        "check_category": check_category,
        "check_name": check_name,
        "dataset": dataset,
        "rule_type": rule_type,
        "severity": severity,
        "status": status,
        "rows_affected": rows_affected,
        "details": details,
        "evidence_query": evidence_query or "",
        "executed_at": _now(),
    })

def _check_nulls(conn, results):
    for table_name, columns in CRITICAL_COLUMNS.items():
        for column in columns:
            query = f"SELECT COUNT(*) FROM {table_name} WHERE {column} IS NULL OR TRIM(CAST({column} AS TEXT)) = ''"
            _build_result(results, "completeness", f"null_check_{column}", table_name, "sql", "error", _execute_scalar(conn, query), f"Coluna '{column}' nao deve conter NULL em {table_name}.", query)

def _check_duplicates(conn, results):
    rules = [
        {"dataset": "raw_selic_daily", "keys": "date, series_code"},
        {"dataset": "raw_ipca_monthly", "keys": "date, series_code"},
        {"dataset": "raw_stock_prices_daily", "keys": "date, ticker"},
    ]
    for rule in rules:
        query = f"SELECT COUNT(*) FROM (SELECT {rule['keys']}, COUNT(*) FROM {rule['dataset']} GROUP BY {rule['keys']} HAVING COUNT(*) > 1)"
        _build_result(results, "uniqueness", "duplicate_natural_key", rule["dataset"], "sql", "error", _execute_scalar(conn, query), "Duplicatas por chave natural.", query)

def _check_negative_values(conn, results):
    rules = [
        {"dataset": "raw_selic_daily", "column": "value"},
        {"dataset": "raw_stock_prices_daily", "column": "open"},
        {"dataset": "raw_stock_prices_daily", "column": "high"},
        {"dataset": "raw_stock_prices_daily", "column": "low"},
        {"dataset": "raw_stock_prices_daily", "column": "close"},
        {"dataset": "raw_stock_prices_daily", "column": "adjusted_close"},
        {"dataset": "raw_stock_prices_daily", "column": "volume"},
    ]
    for rule in rules:
        query = f"SELECT COUNT(*) FROM {rule['dataset']} WHERE CAST({rule['column']} AS REAL) < 0"
        _build_result(results, "validity", f"negative_value_{rule['column']}", rule["dataset"], "sql", "error", _execute_scalar(conn, query), f"Coluna {rule['column']} nao deve ser negativa.", query)

def _check_ipca_dates(conn, results):
    query = "SELECT COUNT(*) FROM raw_ipca_monthly WHERE date IS NOT NULL AND strftime('%d', date) <> '01'"
    _build_result(results, "consistency", "ipca_date_must_be_first_day", "raw_ipca_monthly", "sql", "error", _execute_scalar(conn, query), "Datas do IPCA devem ser dia 1 do mes.", query)

def _check_ohlc(conn, results):
    rules = [
        {"name": "high_lower_than_low", "query": "SELECT COUNT(*) FROM raw_stock_prices_daily WHERE high < low", "details": "High nao pode ser menor que low."},
        {"name": "close_outside_range", "query": "SELECT COUNT(*) FROM raw_stock_prices_daily WHERE close < low OR close > high", "details": "Close deve estar entre low e high."},
        {"name": "open_outside_range", "query": "SELECT COUNT(*) FROM raw_stock_prices_daily WHERE open < low OR open > high", "details": "Open deve estar entre low e high."},
    ]
    for rule in rules:
        _build_result(results, "consistency", rule["name"], "raw_stock_prices_daily", "sql", "error", _execute_scalar(conn, rule["query"]), rule["details"], rule["query"])

def _load_dates(conn, table, key_col=None):
    cols = "date" + (f", {key_col}" if key_col else "")
    df = pd.read_sql_query(f"SELECT {cols} FROM {table} WHERE date IS NOT NULL", conn)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"])

def _check_selic_coverage(conn, results, gaps):
    df = _load_dates(conn, "raw_selic_daily")
    expected = pd.date_range(df["date"].min(), df["date"].max(), freq="B")
    missing = expected.difference(pd.DatetimeIndex(df["date"].drop_duplicates()))
    for d in missing:
        gaps.append({"dataset": "raw_selic_daily", "key": "selic_daily", "missing_date": d.strftime("%Y-%m-%d"), "check_name": "selic_coverage"})
    _build_result(results, "coverage", "selic_business_day_coverage", "raw_selic_daily", "python", "warning", len(missing), "Gaps podem ser feriados nacionais.")

def _check_ipca_coverage(conn, results, gaps):
    df = _load_dates(conn, "raw_ipca_monthly")
    expected = pd.date_range(df["date"].min().replace(day=1), df["date"].max().replace(day=1), freq="MS")
    actual = pd.DatetimeIndex(df["date"].dt.to_period("M").dt.to_timestamp().drop_duplicates())
    missing = expected.difference(actual)
    for d in missing:
        gaps.append({"dataset": "raw_ipca_monthly", "key": "ipca_monthly", "missing_date": d.strftime("%Y-%m-%d"), "check_name": "ipca_coverage"})
    _build_result(results, "coverage", "ipca_monthly_coverage", "raw_ipca_monthly", "python", "error", len(missing), "Deve existir um registro de IPCA por mes.")

def _check_stock_coverage(conn, results, gaps):
    df = _load_dates(conn, "raw_stock_prices_daily", "ticker")
    total_missing = 0
    for ticker, tdf in df.groupby("ticker"):
        expected = pd.date_range(tdf["date"].min(), tdf["date"].max(), freq="B")
        missing = expected.difference(pd.DatetimeIndex(tdf["date"].drop_duplicates()))
        total_missing += len(missing)
        for d in missing:
            gaps.append({"dataset": "raw_stock_prices_daily", "key": ticker, "missing_date": d.strftime("%Y-%m-%d"), "check_name": "stock_coverage"})
    _build_result(results, "coverage", "stock_business_day_coverage", "raw_stock_prices_daily", "python", "warning", total_missing, "Gaps podem ser feriados da B3.")

def run_quality_checks(database_file):
    results, gaps = [], []
    with sqlite3.connect(database_file) as conn:
        _check_nulls(conn, results)
        _check_duplicates(conn, results)
        _check_negative_values(conn, results)
        _check_ipca_dates(conn, results)
        _check_ohlc(conn, results)
        _check_selic_coverage(conn, results, gaps)
        _check_ipca_coverage(conn, results, gaps)
        _check_stock_coverage(conn, results, gaps)
    results_df = pd.DataFrame(results)
    gaps_df = pd.DataFrame(gaps)
    fail_count = int((results_df["status"] == "FAIL").sum())
    warn_count = int((results_df["status"] == "WARN").sum())
    overall = "FAIL" if fail_count > 0 else ("PASS_WITH_WARNINGS" if warn_count > 0 else "PASS")
    summary = {
        "generated_at": _now(),
        "database_file": str(database_file),
        "total_checks": len(results_df),
        "pass": int((results_df["status"] == "PASS").sum()),
        "warn": warn_count,
        "fail": fail_count,
        "overall_status": overall,
    }
    return results_df, gaps_df, summary

def save_validation_outputs(results_df, gaps_df, summary, quality_results_file, quality_summary_file, date_gaps_detail_file):
    for f in [quality_results_file, quality_summary_file, date_gaps_detail_file]:
        f.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(quality_results_file, index=False, encoding="utf-8")
    if gaps_df.empty:
        gaps_df = pd.DataFrame(columns=["dataset", "key", "missing_date", "check_name"])
    gaps_df.to_csv(date_gaps_detail_file, index=False, encoding="utf-8")
    with open(quality_summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=4)