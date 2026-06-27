from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd

def _read_csv_safely(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {file_path}")
    df = pd.read_csv(file_path)
    if df.empty:
        raise ValueError(f"Arquivo vazio: {file_path}")
    return df

def _standardize_date_column(df: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
    df = df.copy()
    if date_column not in df.columns:
        raise ValueError(f"Coluna obrigatoria ausente: {date_column}")
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce").dt.strftime("%Y-%m-%d")
    return df

def _coerce_numeric_columns(df: pd.DataFrame, numeric_columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df

def load_raw_files_to_sqlite(selic_file, ipca_file, stocks_file, database_file):
    database_file.parent.mkdir(parents=True, exist_ok=True)
    selic_df = _read_csv_safely(selic_file)
    ipca_df = _read_csv_safely(ipca_file)
    stocks_df = _read_csv_safely(stocks_file)
    selic_df = _standardize_date_column(selic_df)
    ipca_df = _standardize_date_column(ipca_df)
    stocks_df = _standardize_date_column(stocks_df)
    selic_df = _coerce_numeric_columns(selic_df, ["series_code", "value"])
    ipca_df = _coerce_numeric_columns(ipca_df, ["series_code", "value"])
    stocks_df = _coerce_numeric_columns(stocks_df, ["open", "high", "low", "close", "adjusted_close", "volume"])
    with sqlite3.connect(database_file) as conn:
        selic_df.to_sql("raw_selic_daily", conn, if_exists="replace", index=False)
        ipca_df.to_sql("raw_ipca_monthly", conn, if_exists="replace", index=False)
        stocks_df.to_sql("raw_stock_prices_daily", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_selic_date_series ON raw_selic_daily(date, series_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_ipca_date_series ON raw_ipca_monthly(date, series_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_stocks_date_ticker ON raw_stock_prices_daily(date, ticker)")
    return {
        "raw_selic_daily": len(selic_df),
        "raw_ipca_monthly": len(ipca_df),
        "raw_stock_prices_daily": len(stocks_df),
    }
