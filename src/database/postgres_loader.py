from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any

try:
    from config import PROCESSED_DB_FILE
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from src.config import PROCESSED_DB_FILE

DEFAULT_POSTGRES_URL = "postgresql://pipeline_user:pipeline_pass@localhost:5432/financial_pipeline"
POSTGRES_SCHEMA_FILE = Path(__file__).resolve().parent / "postgres_schema.sql"

TABLE_COLUMNS = {
    "dim_source": ["source_id", "source_name", "source_type", "description", "created_at"],
    "dim_bcb_series": ["series_id", "source_id", "series_code", "series_name", "description", "frequency", "unit", "created_at"],
    "dim_b3_ticker": ["ticker_id", "source_id", "ticker", "market", "currency", "asset_type", "created_at"],
    "fact_bcb_series_values": ["observation_id", "series_id", "reference_date", "value", "collected_at", "loaded_at"],
    "fact_b3_stock_prices": [
        "price_id",
        "ticker_id",
        "reference_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "adjusted_close_price",
        "volume",
        "collected_at",
        "loaded_at",
    ],
    "dim_cvm_fund": [
        "fund_id",
        "fund_cnpj",
        "fund_name",
        "fund_status",
        "registration_date",
        "fund_type",
        "target_investor",
        "source",
        "created_at",
        "updated_at",
    ],
    "fact_cvm_fund_daily_report": [
        "fund_report_id",
        "fund_id",
        "reference_date",
        "total_portfolio_value",
        "net_asset_value",
        "quota_value",
        "daily_subscriptions",
        "daily_redemptions",
        "number_of_shareholders",
        "collected_at",
        "loaded_at",
    ],
}

SERIAL_COLUMNS = {
    "dim_source": "source_id",
    "dim_bcb_series": "series_id",
    "dim_b3_ticker": "ticker_id",
    "fact_bcb_series_values": "observation_id",
    "fact_b3_stock_prices": "price_id",
    "dim_cvm_fund": "fund_id",
    "fact_cvm_fund_daily_report": "fund_report_id",
}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _read_sqlite_rows(sqlite_file: Path, table_name: str, columns: list[str]) -> list[tuple[Any, ...]]:
    selected_columns = ", ".join(columns)
    with sqlite3.connect(sqlite_file) as conn:
        rows = conn.execute(f"SELECT {selected_columns} FROM {table_name}").fetchall()
    return [tuple(_normalize_value(value) for value in row) for row in rows]


def _insert_rows(cursor, table_name: str, columns: list[str], rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return

    from psycopg2.extras import execute_values

    columns_sql = ", ".join(columns)
    sql = f"INSERT INTO {table_name} ({columns_sql}) VALUES %s"
    execute_values(cursor, sql, rows, page_size=1000)


def _reset_sequence(cursor, table_name: str, column_name: str) -> None:
    cursor.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table_name}', '{column_name}'),
            GREATEST(COALESCE((SELECT MAX({column_name}) FROM {table_name}), 1), 1),
            true
        )
        """
    )


def load_to_postgres(
    database_url: str,
    sqlite_database_file: Path | str = PROCESSED_DB_FILE,
    schema_file: Path | str = POSTGRES_SCHEMA_FILE,
) -> dict[str, int]:
    import psycopg2

    sqlite_file = Path(sqlite_database_file)
    if not sqlite_file.exists():
        raise FileNotFoundError(f"SQLite processado nao encontrado: {sqlite_file}")

    schema_sql = Path(schema_file).read_text(encoding="utf-8")
    counts: dict[str, int] = {}

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cursor:
            cursor.execute(schema_sql)
            for table_name, columns in TABLE_COLUMNS.items():
                rows = _read_sqlite_rows(sqlite_file, table_name, columns)
                _insert_rows(cursor, table_name, columns, rows)
                _reset_sequence(cursor, table_name, SERIAL_COLUMNS[table_name])
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                counts[table_name] = int(cursor.fetchone()[0])
        conn.commit()

    return counts
