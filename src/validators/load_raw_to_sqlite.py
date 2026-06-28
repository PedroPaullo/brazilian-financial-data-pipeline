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

def _load_optional_bcb_files(extra_bcb_files: list[Path] | None) -> list[pd.DataFrame]:
    dataframes = []
    for file_path in extra_bcb_files or []:
        if not file_path.exists():
            continue
        df = _standardize_date_column(_read_csv_safely(file_path))
        df = _coerce_numeric_columns(df, ["series_code", "value"])
        dataframes.append(df)
    return dataframes


def _load_optional_csv(file_path: Path | None, date_columns: list[str] | None = None, numeric_columns: list[str] | None = None) -> pd.DataFrame | None:
    if file_path is None or not Path(file_path).exists():
        return None
    df = _read_csv_safely(Path(file_path))
    for date_column in date_columns or []:
        if date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], errors="coerce").dt.strftime("%Y-%m-%d")
    df = _coerce_numeric_columns(df, numeric_columns or [])
    return df


def load_raw_files_to_sqlite(selic_file, ipca_file, stocks_file, database_file, extra_bcb_files=None, cvm_daily_file=None, cvm_registry_file=None):
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
    bcb_series_df = pd.concat(
        [selic_df, ipca_df, *_load_optional_bcb_files(extra_bcb_files)],
        ignore_index=True,
    )
    cvm_daily_df = _load_optional_csv(
        Path(cvm_daily_file) if cvm_daily_file else None,
        date_columns=["reference_date"],
        numeric_columns=[
            "total_portfolio_value",
            "net_asset_value",
            "quota_value",
            "daily_subscriptions",
            "daily_redemptions",
            "number_of_shareholders",
        ],
    )
    cvm_registry_df = _load_optional_csv(
        Path(cvm_registry_file) if cvm_registry_file else None,
        date_columns=["registration_date"],
    )
    with sqlite3.connect(database_file) as conn:
        selic_df.to_sql("raw_selic_daily", conn, if_exists="replace", index=False)
        ipca_df.to_sql("raw_ipca_monthly", conn, if_exists="replace", index=False)
        bcb_series_df.to_sql("raw_bcb_series", conn, if_exists="replace", index=False)
        stocks_df.to_sql("raw_stock_prices_daily", conn, if_exists="replace", index=False)
        if cvm_daily_df is not None:
            cvm_daily_df.to_sql("raw_cvm_funds_daily_reports", conn, if_exists="replace", index=False)
        if cvm_registry_df is not None:
            cvm_registry_df.to_sql("raw_cvm_funds_registry", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_selic_date_series ON raw_selic_daily(date, series_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_ipca_date_series ON raw_ipca_monthly(date, series_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_bcb_series_date_series ON raw_bcb_series(date, series_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_stocks_date_ticker ON raw_stock_prices_daily(date, ticker)")
        if cvm_daily_df is not None:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_cvm_daily_cnpj_date ON raw_cvm_funds_daily_reports(fund_cnpj, reference_date)")
        if cvm_registry_df is not None:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_cvm_registry_cnpj ON raw_cvm_funds_registry(fund_cnpj)")
    result = {
        "raw_selic_daily": len(selic_df),
        "raw_ipca_monthly": len(ipca_df),
        "raw_bcb_series": len(bcb_series_df),
        "raw_stock_prices_daily": len(stocks_df),
    }
    if cvm_daily_df is not None:
        result["raw_cvm_funds_daily_reports"] = len(cvm_daily_df)
    if cvm_registry_df is not None:
        result["raw_cvm_funds_registry"] = len(cvm_registry_df)
    return result
