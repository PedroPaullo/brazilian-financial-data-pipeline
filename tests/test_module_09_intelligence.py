from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from intelligence.loader import load_intelligence_views

EXPECTED_VIEWS = {
    "vw_market_latest_indicators": {"series_name", "latest_date", "latest_value", "previous_value", "change_pct"},
    "vw_asset_returns_ranking": {"ticker", "return_30d_pct", "return_90d_pct", "return_full_pct", "period_start", "period_end"},
    "vw_data_freshness_status": {"source_name", "series_name", "last_date", "days_since_update", "freshness_status"},
    "vw_pipeline_health_daily": {"execution_date", "total_bcb_records", "total_stock_records", "overall_status"},
    "vw_source_availability_summary": {"source_name", "total_loaded", "last_update", "days_since_update"},
    "vw_macro_indicators_summary": {"reference_month", "selic_avg", "ipca_value", "cdi_avg", "usd_brl_avg"},
}


def _create_test_database(database_file: Path) -> None:
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

        series = [
            (11, "selic_daily", "Selic", "daily", "%"),
            (433, "ipca_monthly", "IPCA", "monthly", "%"),
            (12, "cdi_daily", "CDI", "daily", "%"),
            (1, "usd_brl_ptax_sell_daily", "PTAX", "daily", "BRL"),
        ]
        series_ids: dict[str, int] = {}
        for code, name, description, frequency, unit in series:
            series_ids[name] = conn.execute(
                """
                INSERT INTO dim_bcb_series
                    (source_id, series_code, series_name, description, frequency, unit)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (bcb_source_id, code, name, description, frequency, unit),
            ).lastrowid

        bcb_rows = [
            ("selic_daily", "2024-01-02", 11.65),
            ("selic_daily", "2024-02-01", 11.25),
            ("ipca_monthly", "2024-01-01", 0.42),
            ("ipca_monthly", "2024-02-01", 0.83),
            ("cdi_daily", "2024-01-02", 0.04),
            ("cdi_daily", "2024-02-01", 0.03),
            ("usd_brl_ptax_sell_daily", "2024-01-02", 4.91),
            ("usd_brl_ptax_sell_daily", "2024-02-01", 4.95),
        ]
        for series_name, reference_date, value in bcb_rows:
            conn.execute(
                "INSERT INTO fact_bcb_series_values (series_id, reference_date, value) VALUES (?, ?, ?)",
                (series_ids[series_name], reference_date, value),
            )

        ticker_id = conn.execute(
            """
            INSERT INTO dim_b3_ticker (source_id, ticker, market, currency, asset_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (b3_source_id, "PETR4.SA", "B3", "BRL", "EQUITY"),
        ).lastrowid
        for reference_date, price in [("2024-01-02", 30.0), ("2024-02-01", 33.0)]:
            conn.execute(
                """
                INSERT INTO fact_b3_stock_prices
                    (ticker_id, reference_date, open_price, high_price, low_price,
                     close_price, adjusted_close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ticker_id, reference_date, price, price + 1, price - 1, price, price, 1000),
            )
        conn.commit()


def test_load_intelligence_views_creates_all_views_with_data():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        database_file = Path(temp_name) / "financial_data.db"
        _create_test_database(database_file)

        counts = load_intelligence_views(database_file)

        assert set(counts) == set(EXPECTED_VIEWS)
        assert all(row_count > 0 for row_count in counts.values())


def test_intelligence_views_expose_expected_columns():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        database_file = Path(temp_name) / "financial_data.db"
        _create_test_database(database_file)
        load_intelligence_views(database_file)

        with sqlite3.connect(database_file) as conn:
            for view_name, expected_columns in EXPECTED_VIEWS.items():
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({view_name})").fetchall()}
                assert expected_columns.issubset(columns), view_name


def test_load_intelligence_views_is_idempotent():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        database_file = Path(temp_name) / "financial_data.db"
        _create_test_database(database_file)

        first_counts = load_intelligence_views(database_file)
        second_counts = load_intelligence_views(database_file)

        assert second_counts == first_counts
