from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import dashboard
from intelligence.loader import load_intelligence_views


def _clear_dashboard_caches() -> None:
    for function_name in [
        "load_bcb_series",
        "load_b3_prices",
        "load_latest_run",
        "load_market_latest_indicators",
        "load_asset_returns_ranking",
        "load_data_freshness_status",
        "load_macro_indicators_summary",
    ]:
        clear = getattr(getattr(dashboard, function_name), "clear", None)
        if clear is not None:
            clear()


def _create_dashboard_database(database_file: Path) -> None:
    schema_sql = (SRC_DIR / "storage" / "schema.sql").read_text(encoding="utf-8")
    with sqlite3.connect(database_file) as conn:
        conn.executescript(schema_sql)
        bcb_source_id = conn.execute(
            "INSERT INTO dim_source (source_name, source_type, description) VALUES (?, ?, ?)",
            ("BCB_SGS", "API", "Banco Central do Brasil"),
        ).lastrowid
        b3_source_id = conn.execute(
            "INSERT INTO dim_source (source_name, source_type, description) VALUES (?, ?, ?)",
            ("YAHOO_FINANCE", "API", "Yahoo Finance"),
        ).lastrowid
        series_id = conn.execute(
            """
            INSERT INTO dim_bcb_series
                (source_id, series_code, series_name, description, frequency, unit)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (bcb_source_id, 11, "selic_daily", "Selic", "daily", "%"),
        ).lastrowid
        conn.execute(
            "INSERT INTO fact_bcb_series_values (series_id, reference_date, value) VALUES (?, ?, ?)",
            (series_id, "2024-01-02", 11.65),
        )
        ticker_id = conn.execute(
            """
            INSERT INTO dim_b3_ticker (source_id, ticker, market, currency, asset_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (b3_source_id, "PETR4.SA", "B3", "BRL", "EQUITY"),
        ).lastrowid
        conn.execute(
            """
            INSERT INTO fact_b3_stock_prices
                (ticker_id, reference_date, open_price, high_price, low_price,
                 close_price, adjusted_close_price, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ticker_id, "2024-01-02", 30.0, 31.0, 29.0, 30.5, 30.5, 1000),
        )
        conn.commit()


def _create_empty_dashboard_database(database_file: Path) -> None:
    schema_sql = (SRC_DIR / "storage" / "schema.sql").read_text(encoding="utf-8")
    with sqlite3.connect(database_file) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    load_intelligence_views(database_file)


def test_dashboard_data_loaders_return_dataframes(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        database_file = Path(temp_name) / "financial_data.db"
        _create_dashboard_database(database_file)
        monkeypatch.setattr(dashboard, "DATABASE_FILE", database_file)
        _clear_dashboard_caches()

        bcb_df = dashboard.load_bcb_series()
        b3_df = dashboard.load_b3_prices()

        assert not bcb_df.empty
        assert not b3_df.empty
        assert {"series_name", "reference_date", "value"}.issubset(bcb_df.columns)
        assert {"ticker", "reference_date", "adjusted_close_price"}.issubset(b3_df.columns)
        assert bcb_df.iloc[0]["series_name"] == "selic_daily"
        assert b3_df.iloc[0]["ticker"] == "PETR4.SA"


def test_dashboard_loaders_handle_empty_database_without_crashing(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        database_file = Path(temp_name) / "empty.db"
        _create_empty_dashboard_database(database_file)
        monkeypatch.setattr(dashboard, "DATABASE_FILE", database_file)
        _clear_dashboard_caches()

        assert dashboard.load_bcb_series().empty
        assert dashboard.load_b3_prices().empty
        assert dashboard.load_latest_run().empty
        assert dashboard.load_market_latest_indicators().empty
        assert dashboard.load_asset_returns_ranking().empty
        assert dashboard.load_data_freshness_status().empty
        assert dashboard.load_macro_indicators_summary().empty
