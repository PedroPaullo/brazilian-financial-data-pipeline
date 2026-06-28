from __future__ import annotations
import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd

from config import BCB_SERIES

def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _read_csv(file_path):
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {file_path}")
    df = pd.read_csv(file_path)
    if df.empty:
        raise ValueError(f"Arquivo vazio: {file_path}")
    return df

def _standardize_date_column(df, column="date"):
    df = df.copy()
    df[column] = pd.to_datetime(df[column], errors="raise").dt.strftime("%Y-%m-%d")
    return df

def _execute_schema(conn, schema_file):
    schema_sql = schema_file.read_text(encoding="utf-8")
    conn.executescript(schema_sql)

def _insert_sources(conn):
    sources = [
        ("BCB_SGS", "MACROECONOMIC_TIME_SERIES", "Banco Central do Brasil - SGS"),
        ("YAHOO_FINANCE", "MARKET_DATA", "Cotacoes da B3 via yfinance"),
        ("CVM", "INSTITUTIONAL_FUNDS", "Comissao de Valores Mobiliarios - Fundos"),
    ]
    sql = "INSERT INTO dim_source (source_name, source_type, description) VALUES (?, ?, ?) ON CONFLICT(source_name) DO UPDATE SET source_type = excluded.source_type, description = excluded.description"
    conn.executemany(sql, sources)

def _get_source_id(conn, source_name):
    row = conn.execute("SELECT source_id FROM dim_source WHERE source_name = ?", (source_name,)).fetchone()
    if row is None:
        raise ValueError(f"Fonte nao encontrada: {source_name}")
    return int(row[0])

def _insert_bcb_series_dimensions(conn, bcb_df):
    source_id = _get_source_id(conn, "BCB_SGS")
    series_df = bcb_df[["series_code", "series_name"]].drop_duplicates().sort_values("series_code")
    rows = []
    for _, row in series_df.iterrows():
        series_code = int(row["series_code"])
        series_name = str(row["series_name"])
        metadata = BCB_SERIES.get(series_name, {})
        description = metadata.get("description", series_name)
        frequency = metadata.get("frequency", "unknown")
        unit = "percentual ao mes" if frequency == "monthly" else "percentual/valor diario"
        rows.append((source_id, series_code, series_name, description, frequency, unit))
    sql = "INSERT INTO dim_bcb_series (source_id, series_code, series_name, description, frequency, unit) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(source_id, series_code) DO UPDATE SET series_name = excluded.series_name, description = excluded.description, frequency = excluded.frequency, unit = excluded.unit"
    conn.executemany(sql, rows)

def _insert_b3_ticker_dimensions(conn, stocks_df):
    source_id = _get_source_id(conn, "YAHOO_FINANCE")
    tickers = sorted(stocks_df["ticker"].dropna().unique())
    rows = [
        (source_id, ticker, "B3", "BRL", "INDEX" if str(ticker).startswith("^") else "EQUITY")
        for ticker in tickers
    ]
    sql = "INSERT INTO dim_b3_ticker (source_id, ticker, market, currency, asset_type) VALUES (?, ?, ?, ?, ?) ON CONFLICT(source_id, ticker) DO UPDATE SET market = excluded.market, currency = excluded.currency, asset_type = excluded.asset_type"
    conn.executemany(sql, rows)

def _get_bcb_series_id_map(conn):
    rows = conn.execute("SELECT series_code, series_id FROM dim_bcb_series").fetchall()
    return {int(sc): int(sid) for sc, sid in rows}

def _get_ticker_id_map(conn):
    rows = conn.execute("SELECT ticker, ticker_id FROM dim_b3_ticker").fetchall()
    return {str(t): int(tid) for t, tid in rows}

def _insert_bcb_facts(conn, bcb_df):
    series_id_map = _get_bcb_series_id_map(conn)
    loaded_at = _now()
    bcb_df["series_code"] = pd.to_numeric(bcb_df["series_code"], errors="raise").astype(int)
    bcb_df["value"] = pd.to_numeric(bcb_df["value"], errors="raise")
    rows = []
    for _, row in bcb_df.iterrows():
        series_code = int(row["series_code"])
        if series_code not in series_id_map:
            raise ValueError(f"series_code sem dimensao: {series_code}")
        rows.append((series_id_map[series_code], row["date"], float(row["value"]), row.get("collected_at"), loaded_at))
    sql = "INSERT INTO fact_bcb_series_values (series_id, reference_date, value, collected_at, loaded_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(series_id, reference_date) DO UPDATE SET value = excluded.value, collected_at = excluded.collected_at, loaded_at = excluded.loaded_at"
    conn.executemany(sql, rows)
    return len(rows)

def _insert_b3_stock_facts(conn, stocks_df):
    ticker_id_map = _get_ticker_id_map(conn)
    loaded_at = _now()
    for col in ["open", "high", "low", "close", "adjusted_close", "volume"]:
        stocks_df[col] = pd.to_numeric(stocks_df[col], errors="raise")
    rows = []
    for _, row in stocks_df.iterrows():
        ticker = str(row["ticker"])
        if ticker not in ticker_id_map:
            raise ValueError(f"ticker sem dimensao: {ticker}")
        rows.append((ticker_id_map[ticker], row["date"], float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), float(row["adjusted_close"]), int(row["volume"]), row.get("collected_at"), loaded_at))
    sql = "INSERT INTO fact_b3_stock_prices (ticker_id, reference_date, open_price, high_price, low_price, close_price, adjusted_close_price, volume, collected_at, loaded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(ticker_id, reference_date) DO UPDATE SET open_price = excluded.open_price, high_price = excluded.high_price, low_price = excluded.low_price, close_price = excluded.close_price, adjusted_close_price = excluded.adjusted_close_price, volume = excluded.volume, collected_at = excluded.collected_at, loaded_at = excluded.loaded_at"
    conn.executemany(sql, rows)
    return len(rows)


def _insert_cvm_fund_dimensions(conn, cvm_daily_df, cvm_registry_df=None):
    if cvm_daily_df is None or cvm_daily_df.empty:
        return 0

    if cvm_registry_df is None or cvm_registry_df.empty:
        registry_df = pd.DataFrame({"fund_cnpj": sorted(cvm_daily_df["fund_cnpj"].dropna().unique())})
    else:
        registry_df = cvm_registry_df.copy()

    for column in ["fund_name", "fund_status", "registration_date", "fund_type", "target_investor", "source"]:
        if column not in registry_df.columns:
            registry_df[column] = ""

    registry_df = registry_df.dropna(subset=["fund_cnpj"]).drop_duplicates(subset=["fund_cnpj"], keep="first")
    daily_cnpjs = set(cvm_daily_df["fund_cnpj"].dropna().astype(str).unique())
    registry_cnpjs = set(registry_df["fund_cnpj"].dropna().astype(str).unique())
    missing_cnpjs = sorted(daily_cnpjs - registry_cnpjs)
    if missing_cnpjs:
        registry_df = pd.concat(
            [
                registry_df,
                pd.DataFrame(
                    {
                        "fund_cnpj": missing_cnpjs,
                        "fund_name": "",
                        "fund_status": "",
                        "registration_date": None,
                        "fund_type": "",
                        "target_investor": "",
                        "source": "CVM_INF_DIARIO_FI",
                    }
                ),
            ],
            ignore_index=True,
        )
    rows = [
        (
            str(row["fund_cnpj"]),
            row.get("fund_name") or "",
            row.get("fund_status") or "",
            row.get("registration_date") or None,
            row.get("fund_type") or "",
            row.get("target_investor") or "",
            row.get("source") or "CVM",
            _now(),
        )
        for _, row in registry_df.iterrows()
    ]
    sql = """
        INSERT INTO dim_cvm_fund (
            fund_cnpj, fund_name, fund_status, registration_date, fund_type,
            target_investor, source, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fund_cnpj) DO UPDATE SET
            fund_name = excluded.fund_name,
            fund_status = excluded.fund_status,
            registration_date = excluded.registration_date,
            fund_type = excluded.fund_type,
            target_investor = excluded.target_investor,
            source = excluded.source,
            updated_at = excluded.updated_at
    """
    conn.executemany(sql, rows)
    return len(rows)


def _get_cvm_fund_id_map(conn):
    rows = conn.execute("SELECT fund_cnpj, fund_id FROM dim_cvm_fund").fetchall()
    return {str(cnpj): int(fund_id) for cnpj, fund_id in rows}


def _insert_cvm_fund_facts(conn, cvm_daily_df):
    if cvm_daily_df is None or cvm_daily_df.empty:
        return 0

    fund_id_map = _get_cvm_fund_id_map(conn)
    loaded_at = _now()
    numeric_columns = [
        "total_portfolio_value",
        "net_asset_value",
        "quota_value",
        "daily_subscriptions",
        "daily_redemptions",
        "number_of_shareholders",
    ]
    for column in numeric_columns:
        cvm_daily_df[column] = pd.to_numeric(cvm_daily_df[column], errors="coerce").fillna(0)

    rows = []
    for _, row in cvm_daily_df.iterrows():
        fund_cnpj = str(row["fund_cnpj"])
        if fund_cnpj not in fund_id_map:
            continue
        rows.append(
            (
                fund_id_map[fund_cnpj],
                row["reference_date"],
                float(row["total_portfolio_value"]),
                float(row["net_asset_value"]),
                float(row["quota_value"]),
                float(row["daily_subscriptions"]),
                float(row["daily_redemptions"]),
                int(row["number_of_shareholders"]),
                row.get("collected_at"),
                loaded_at,
            )
        )
    sql = """
        INSERT INTO fact_cvm_fund_daily_report (
            fund_id, reference_date, total_portfolio_value, net_asset_value,
            quota_value, daily_subscriptions, daily_redemptions,
            number_of_shareholders, collected_at, loaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fund_id, reference_date) DO UPDATE SET
            total_portfolio_value = excluded.total_portfolio_value,
            net_asset_value = excluded.net_asset_value,
            quota_value = excluded.quota_value,
            daily_subscriptions = excluded.daily_subscriptions,
            daily_redemptions = excluded.daily_redemptions,
            number_of_shareholders = excluded.number_of_shareholders,
            collected_at = excluded.collected_at,
            loaded_at = excluded.loaded_at
    """
    conn.executemany(sql, rows)
    return len(rows)


def _count_rows(conn, table_name):
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

def _read_optional_bcb_files(extra_bcb_files):
    dataframes = []
    for file_path in extra_bcb_files or []:
        file_path = Path(file_path)
        if not file_path.exists():
            continue
        dataframes.append(_standardize_date_column(_read_csv(file_path)))
    return dataframes


def _read_optional_csv(file_path, date_columns=None):
    file_path = Path(file_path) if file_path else None
    if file_path is None or not file_path.exists():
        return None
    df = _read_csv(file_path)
    for column in date_columns or []:
        if column in df.columns:
            df = _standardize_date_column(df, column)
    return df


def load_processed_database(selic_file, ipca_file, stocks_file, database_file, schema_file, replace_database=True, extra_bcb_files=None, cvm_daily_file=None, cvm_registry_file=None):
    if replace_database and database_file.exists():
        database_file.unlink()
    database_file.parent.mkdir(parents=True, exist_ok=True)
    selic_df = _standardize_date_column(_read_csv(selic_file))
    ipca_df = _standardize_date_column(_read_csv(ipca_file))
    bcb_df = pd.concat(
        [selic_df, ipca_df, *_read_optional_bcb_files(extra_bcb_files)],
        ignore_index=True,
    )
    stocks_df = _standardize_date_column(_read_csv(stocks_file))
    cvm_daily_df = _read_optional_csv(cvm_daily_file, ["reference_date"])
    cvm_registry_df = _read_optional_csv(cvm_registry_file, ["registration_date"])
    with sqlite3.connect(database_file) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        _execute_schema(conn, schema_file)
        _insert_sources(conn)
        _insert_bcb_series_dimensions(conn, bcb_df)
        _insert_b3_ticker_dimensions(conn, stocks_df)
        inserted_cvm_dimensions = _insert_cvm_fund_dimensions(conn, cvm_daily_df, cvm_registry_df)
        inserted_bcb = _insert_bcb_facts(conn, bcb_df)
        inserted_stocks = _insert_b3_stock_facts(conn, stocks_df)
        inserted_cvm = _insert_cvm_fund_facts(conn, cvm_daily_df)
        conn.commit()
        return {
            "dim_source": _count_rows(conn, "dim_source"),
            "dim_bcb_series": _count_rows(conn, "dim_bcb_series"),
            "dim_b3_ticker": _count_rows(conn, "dim_b3_ticker"),
            "dim_cvm_fund": _count_rows(conn, "dim_cvm_fund"),
            "fact_bcb_series_values": _count_rows(conn, "fact_bcb_series_values"),
            "fact_b3_stock_prices": _count_rows(conn, "fact_b3_stock_prices"),
            "fact_cvm_fund_daily_report": _count_rows(conn, "fact_cvm_fund_daily_report"),
            "input_bcb_rows_loaded": inserted_bcb,
            "input_stock_rows_loaded": inserted_stocks,
            "input_cvm_fund_rows_loaded": inserted_cvm,
            "input_cvm_registry_rows_loaded": inserted_cvm_dimensions,
        }
