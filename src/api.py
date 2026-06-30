from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from .config import PROCESSED_DB_FILE
except ImportError:  # pragma: no cover - direct module import fallback
    from config import PROCESSED_DB_FILE

DATABASE_FILE = PROCESSED_DB_FILE

app = FastAPI(
    title="Brazilian Financial Data Pipeline API",
    description="API REST para consumo externo da camada de inteligencia financeira.",
    version="1.0.0",
)


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class MarketLatestIndicator(BaseModel):
    series_name: str
    latest_date: str | None
    latest_value: float | None
    previous_value: float | None
    change_pct: float | None


class AssetReturnsRanking(BaseModel):
    ticker: str
    return_30d_pct: float | None
    return_90d_pct: float | None
    return_full_pct: float | None
    period_start: str | None
    period_end: str | None


class DataFreshnessStatus(BaseModel):
    source_name: str
    series_name: str
    last_date: str | None
    days_since_update: int | None
    freshness_status: str | None


class PipelineHealthDaily(BaseModel):
    execution_date: str
    total_bcb_records: int
    total_stock_records: int
    overall_status: str


class SourceAvailabilitySummary(BaseModel):
    source_name: str
    total_loaded: int
    last_update: str | None
    days_since_update: int | None


class MacroIndicatorsSummary(BaseModel):
    reference_month: str
    selic_avg: float | None
    ipca_value: float | None
    cdi_avg: float | None
    usd_brl_avg: float | None


def _database_path() -> Path:
    return Path(DATABASE_FILE)


def _query_view(query: str) -> list[dict]:
    database_file = _database_path()
    if not database_file.exists():
        raise HTTPException(status_code=503, detail=f"Banco processado nao encontrado: {database_file}")

    try:
        with sqlite3.connect(database_file) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Banco processado indisponivel: {exc}") from exc

    return [dict(row) for row in rows]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(timezone.utc).isoformat())


@app.get("/indicators/latest", response_model=list[MarketLatestIndicator])
def latest_indicators() -> list[dict]:
    return _query_view(
        """
        SELECT series_name, latest_date, latest_value, previous_value, change_pct
        FROM vw_market_latest_indicators
        ORDER BY series_name
        """
    )


@app.get("/assets/returns", response_model=list[AssetReturnsRanking])
def asset_returns() -> list[dict]:
    return _query_view(
        """
        SELECT ticker, return_30d_pct, return_90d_pct, return_full_pct, period_start, period_end
        FROM vw_asset_returns_ranking
        ORDER BY return_full_pct DESC
        """
    )


@app.get("/data/freshness", response_model=list[DataFreshnessStatus])
def data_freshness() -> list[dict]:
    return _query_view(
        """
        SELECT source_name, series_name, last_date, days_since_update, freshness_status
        FROM vw_data_freshness_status
        ORDER BY source_name, series_name
        """
    )


@app.get("/pipeline/health", response_model=list[PipelineHealthDaily])
def pipeline_health() -> list[dict]:
    return _query_view(
        """
        SELECT execution_date, total_bcb_records, total_stock_records, overall_status
        FROM vw_pipeline_health_daily
        ORDER BY execution_date DESC
        """
    )


@app.get("/sources/availability", response_model=list[SourceAvailabilitySummary])
def sources_availability() -> list[dict]:
    return _query_view(
        """
        SELECT source_name, total_loaded, last_update, days_since_update
        FROM vw_source_availability_summary
        ORDER BY source_name
        """
    )


@app.get("/indicators/macro/monthly", response_model=list[MacroIndicatorsSummary])
def macro_indicators_monthly() -> list[dict]:
    return _query_view(
        """
        SELECT reference_month, selic_avg, ipca_value, cdi_avg, usd_brl_avg
        FROM vw_macro_indicators_summary
        ORDER BY reference_month
        """
    )
