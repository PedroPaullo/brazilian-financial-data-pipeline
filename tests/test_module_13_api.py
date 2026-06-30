from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import api
from intelligence.loader import load_intelligence_views

DATA_ENDPOINTS = {
    "/indicators/latest": {"series_name", "latest_date", "latest_value", "previous_value", "change_pct"},
    "/assets/returns": {"ticker", "return_30d_pct", "return_90d_pct", "return_full_pct", "period_start", "period_end"},
    "/data/freshness": {"source_name", "series_name", "last_date", "days_since_update", "freshness_status"},
    "/pipeline/health": {"execution_date", "total_bcb_records", "total_stock_records", "overall_status"},
    "/sources/availability": {"source_name", "total_loaded", "last_update", "days_since_update"},
    "/indicators/macro/monthly": {"reference_month", "selic_avg", "ipca_value", "cdi_avg", "usd_brl_avg"},
}


def _create_api_database(database_file: Path) -> None:
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

        series_ids: dict[str, int] = {}
        for code, name, description, frequency, unit in [
            (11, "selic_daily", "Selic", "daily", "%"),
            (433, "ipca_monthly", "IPCA", "monthly", "%"),
            (12, "cdi_daily", "CDI", "daily", "%"),
            (1, "usd_brl_ptax_sell_daily", "PTAX", "daily", "BRL"),
        ]:
            series_ids[name] = conn.execute(
                """
                INSERT INTO dim_bcb_series
                    (source_id, series_code, series_name, description, frequency, unit)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (bcb_source_id, code, name, description, frequency, unit),
            ).lastrowid

        for series_name, reference_date, value in [
            ("selic_daily", "2024-01-02", 11.65),
            ("selic_daily", "2024-02-01", 11.25),
            ("ipca_monthly", "2024-01-01", 0.42),
            ("ipca_monthly", "2024-02-01", 0.83),
            ("cdi_daily", "2024-01-02", 0.04),
            ("cdi_daily", "2024-02-01", 0.03),
            ("usd_brl_ptax_sell_daily", "2024-01-02", 4.91),
            ("usd_brl_ptax_sell_daily", "2024-02-01", 4.95),
        ]:
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

    load_intelligence_views(database_file)


def test_api_health_returns_ok():
    client = TestClient(api.app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "timestamp" in payload


def test_api_openapi_docs_available():
    client = TestClient(api.app)

    docs_response = client.get("/docs")
    openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
    assert "/indicators/latest" in openapi_response.json()["paths"]


def test_api_data_endpoints_return_valid_json(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        database_file = Path(temp_name) / "financial_data.db"
        _create_api_database(database_file)
        monkeypatch.setattr(api, "DATABASE_FILE", database_file)
        client = TestClient(api.app)

        for endpoint, expected_keys in DATA_ENDPOINTS.items():
            response = client.get(endpoint)
            assert response.status_code == 200, endpoint
            payload = response.json()
            assert isinstance(payload, list), endpoint
            assert payload, endpoint
            assert expected_keys.issubset(payload[0]), endpoint


def test_api_data_endpoints_return_503_when_database_is_missing(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_name:
        monkeypatch.setattr(api, "DATABASE_FILE", Path(temp_name) / "missing.db")
        client = TestClient(api.app)

        response = client.get("/indicators/latest")

        assert response.status_code == 503
        assert "Banco processado nao encontrado" in response.json()["detail"]
