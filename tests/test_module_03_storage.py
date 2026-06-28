from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DB_FILE = PROJECT_ROOT / "data" / "processed" / "financial_data.db"


def main():
    assert PROCESSED_DB_FILE.exists(), f"Banco final nao encontrado: {PROCESSED_DB_FILE}"

    with sqlite3.connect(PROCESSED_DB_FILE) as conn:
        series_names = {
            row[0]
            for row in conn.execute("SELECT DISTINCT series_name FROM vw_bcb_series_values")
        }
        tickers = {
            row[0]
            for row in conn.execute("SELECT DISTINCT ticker FROM vw_b3_stock_prices")
        }
        views = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'view'")
        }
        b3_returns_count = conn.execute("SELECT COUNT(*) FROM vw_b3_asset_returns").fetchone()[0]
        bcb_snapshot_count = conn.execute("SELECT COUNT(*) FROM vw_bcb_latest_snapshot").fetchone()[0]

    expected_series = {"selic_daily", "ipca_monthly", "usd_brl_ptax_sell_daily", "cdi_daily"}
    expected_tickers = {"PETR4.SA", "VALE3.SA", "ITUB4.SA", "^BVSP"}
    expected_views = {"vw_bcb_latest_snapshot", "vw_b3_asset_returns"}

    assert expected_series.issubset(series_names)
    assert expected_tickers.issubset(tickers)
    assert expected_views.issubset(views)
    assert b3_returns_count >= len(expected_tickers)
    assert bcb_snapshot_count >= len(expected_series)

    print("\nTeste do Modulo 3 concluido com sucesso.")


if __name__ == "__main__":
    main()
