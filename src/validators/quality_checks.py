from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd

from reference_data.b3_calendar import CALENDAR_FILE, calendar_source, get_missing_trading_dates

CRITICAL_COLUMNS = {
    "raw_selic_daily": ["source", "series_code", "series_name", "date", "value"],
    "raw_ipca_monthly": ["source", "series_code", "series_name", "date", "value"],
    "raw_bcb_series": ["source", "series_code", "series_name", "date", "value"],
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


def _build_skipped(results, check_category, check_name, dataset, details):
    results.append({
        "check_id": len(results) + 1,
        "check_category": check_category,
        "check_name": check_name,
        "dataset": dataset,
        "rule_type": "python",
        "severity": "info",
        "status": "SKIPPED",
        "rows_affected": 0,
        "details": details,
        "evidence_query": "",
        "executed_at": _now(),
    })


def _table_exists(conn, table_name: str) -> bool:
    query = "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = ?"
    return int(conn.execute(query, (table_name,)).fetchone()[0]) > 0


def _check_nulls(conn, results):
    for table_name, columns in CRITICAL_COLUMNS.items():
        for column in columns:
            query = f"SELECT COUNT(*) FROM {table_name} WHERE {column} IS NULL OR TRIM(CAST({column} AS TEXT)) = ''"
            _build_result(results, "completeness", f"null_check_{column}", table_name, "sql", "error", _execute_scalar(conn, query), f"Coluna '{column}' nao deve conter NULL em {table_name}.", query)

def _check_duplicates(conn, results):
    rules = [
        {"dataset": "raw_selic_daily", "keys": "date, series_code"},
        {"dataset": "raw_ipca_monthly", "keys": "date, series_code"},
        {"dataset": "raw_bcb_series", "keys": "date, series_code"},
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

    bcb_query = "SELECT COUNT(*) FROM raw_bcb_series WHERE series_name <> 'ipca_monthly' AND CAST(value AS REAL) < 0"
    _build_result(results, "validity", "negative_value_non_ipca_bcb_series", "raw_bcb_series", "sql", "error", _execute_scalar(conn, bcb_query), "Series BCB nao relacionadas ao IPCA nao devem ser negativas.", bcb_query)

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
        missing = get_missing_trading_dates(
            tdf["date"].drop_duplicates(),
            tdf["date"].min(),
            tdf["date"].max(),
        )
        total_missing += len(missing)
        for d in missing:
            gaps.append({"dataset": "raw_stock_prices_daily", "key": ticker, "missing_date": d.strftime("%Y-%m-%d"), "check_name": "stock_coverage"})
    _build_result(results, "coverage", "stock_business_day_coverage", "raw_stock_prices_daily", "python", "warning", total_missing, "Gaps podem ser feriados da B3.")
    fallback_rows = 0 if CALENDAR_FILE.exists() else 1
    _build_result(
        results,
        "coverage",
        "b3_calendar_source",
        "raw_stock_prices_daily",
        "python",
        "warning",
        fallback_rows,
        f"Calendario B3 usado: {calendar_source()}.",
    )


def _check_bcb_series_coverage(conn, results, gaps):
    df = _load_dates(conn, "raw_bcb_series", "series_name")
    total_missing_daily = 0
    total_missing_monthly = 0

    for series_name, sdf in df.groupby("series_name"):
        if series_name.endswith("_monthly"):
            expected = pd.date_range(sdf["date"].min().replace(day=1), sdf["date"].max().replace(day=1), freq="MS")
            actual = pd.DatetimeIndex(sdf["date"].dt.to_period("M").dt.to_timestamp().drop_duplicates())
            missing = expected.difference(actual)
            total_missing_monthly += len(missing)
            check_name = "bcb_monthly_coverage"
        else:
            expected = pd.date_range(sdf["date"].min(), sdf["date"].max(), freq="B")
            missing = expected.difference(pd.DatetimeIndex(sdf["date"].drop_duplicates()))
            total_missing_daily += len(missing)
            check_name = "bcb_business_day_coverage"

        for d in missing:
            gaps.append({
                "dataset": "raw_bcb_series",
                "key": series_name,
                "missing_date": d.strftime("%Y-%m-%d"),
                "check_name": check_name,
            })

    _build_result(results, "coverage", "bcb_daily_series_business_day_coverage", "raw_bcb_series", "python", "warning", total_missing_daily, "Gaps podem ser feriados nacionais.")
    _build_result(results, "coverage", "bcb_monthly_series_coverage", "raw_bcb_series", "python", "error", total_missing_monthly, "Series BCB mensais devem ter um registro por mes.")


def _check_cvm_funds(conn, results):
    daily_table = "raw_cvm_funds_daily_reports"
    registry_table = "raw_cvm_funds_registry"
    if not _table_exists(conn, daily_table):
        _build_skipped(results, "institutional_source", "cvm_daily_reports_available", daily_table, "Arquivos CVM Fundos nao encontrados; validacao CVM pulada.")
        return

    cvm_rules = [
        ("fund_cnpj_not_null", "fund_cnpj IS NULL OR TRIM(CAST(fund_cnpj AS TEXT)) = ''", "fund_cnpj nao deve ser nulo."),
        ("reference_date_not_null", "reference_date IS NULL OR TRIM(CAST(reference_date AS TEXT)) = ''", "reference_date nao deve ser nula."),
        ("net_asset_value_non_negative", "CAST(net_asset_value AS REAL) < 0", "Patrimonio liquido nao deve ser negativo."),
        ("quota_value_positive", "CAST(quota_value AS REAL) <= 0", "Valor da cota deve ser positivo."),
        ("shareholders_non_negative", "CAST(number_of_shareholders AS REAL) < 0", "Numero de cotistas nao deve ser negativo."),
    ]
    for check_name, where_clause, details in cvm_rules:
        query = f"SELECT COUNT(*) FROM {daily_table} WHERE {where_clause}"
        _build_result(results, "cvm_funds", check_name, daily_table, "sql", "error", _execute_scalar(conn, query), details, query)

    duplicate_query = f"SELECT COUNT(*) FROM (SELECT fund_cnpj, reference_date, COUNT(*) FROM {daily_table} GROUP BY fund_cnpj, reference_date HAVING COUNT(*) > 1)"
    _build_result(results, "cvm_funds", "duplicate_fund_date", daily_table, "sql", "error", _execute_scalar(conn, duplicate_query), "Duplicatas por fund_cnpj + reference_date.", duplicate_query)

    extreme_pl_query = f"SELECT COUNT(*) FROM {daily_table} WHERE CAST(net_asset_value AS REAL) > 1000000000000"
    _build_result(results, "cvm_funds", "extreme_net_asset_value", daily_table, "sql", "warning", _execute_scalar(conn, extreme_pl_query), "PL acima de faixa extrema deve ser revisado.", extreme_pl_query)

    if not _table_exists(conn, registry_table):
        _build_result(results, "cvm_funds", "registry_available", registry_table, "python", "warning", 1, "Cadastro CVM ausente para cruzar fundos do informe diario.")
        return

    missing_registry_query = f"""
        SELECT COUNT(*)
        FROM (SELECT DISTINCT fund_cnpj FROM {daily_table}) d
        LEFT JOIN (SELECT DISTINCT fund_cnpj FROM {registry_table}) r
            ON d.fund_cnpj = r.fund_cnpj
        WHERE r.fund_cnpj IS NULL
    """
    _build_result(results, "cvm_funds", "daily_fund_has_registry", daily_table, "sql", "warning", _execute_scalar(conn, missing_registry_query), "Fundo com informe diario sem cadastro correspondente.", missing_registry_query)


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
        _check_bcb_series_coverage(conn, results, gaps)
        _check_stock_coverage(conn, results, gaps)
        _check_cvm_funds(conn, results)
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
        "skipped": int((results_df["status"] == "SKIPPED").sum()),
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
