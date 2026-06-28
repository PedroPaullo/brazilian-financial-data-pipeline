from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from analytics.market_metrics import (
    build_asset_performance_summary,
    calculate_annualized_volatility,
    calculate_correlation_matrix,
    calculate_cumulative_return,
    calculate_excess_return,
    calculate_max_drawdown,
    calculate_period_return,
    calculate_real_return,
)


def main():
    prices = pd.DataFrame(
        {
            "reference_date": pd.date_range("2024-01-01", periods=4),
            "ticker": ["AAA"] * 4,
            "adjusted_close_price": [100.0, 110.0, 105.0, 120.0],
        }
    )
    benchmark = pd.DataFrame(
        {
            "reference_date": pd.date_range("2024-01-01", periods=4),
            "ticker": ["^BENCH"] * 4,
            "adjusted_close_price": [100.0, 102.0, 104.0, 108.0],
        }
    )
    ipca = pd.DataFrame(
        {
            "reference_date": pd.date_range("2024-01-01", periods=2, freq="MS"),
            "ipca_monthly_value": [0.4, 0.6],
        }
    )

    assert round(calculate_period_return(100, 120), 2) == 20.0
    assert round(calculate_real_return(20, 10), 2) == 9.09
    assert calculate_period_return(0, 120) is None

    cumulative = calculate_cumulative_return(prices, "reference_date", "adjusted_close_price")
    assert round(cumulative.iloc[-1]["cumulative_return_pct"], 2) == 20.0

    returns = prices["adjusted_close_price"].pct_change(fill_method=None).dropna()
    assert calculate_annualized_volatility(returns) is not None
    assert round(calculate_max_drawdown(prices["adjusted_close_price"]), 2) == -4.55

    price_matrix = pd.DataFrame({"AAA": [100, 101, 102, 104], "BBB": [50, 51, 49, 50]})
    correlation = calculate_correlation_matrix(price_matrix)
    assert set(correlation.columns) == {"AAA", "BBB"}

    assert round(calculate_excess_return(20, 8), 2) == 12.0

    summary = build_asset_performance_summary(prices, ipca_df=ipca, benchmark_df=benchmark)
    assert len(summary) == 1
    assert round(summary.iloc[0]["nominal_return_pct"], 2) == 20.0
    assert summary.iloc[0]["real_return_pct"] is not None
    assert round(summary.iloc[0]["benchmark_return_pct"], 2) == 8.0
    assert round(summary.iloc[0]["excess_return_pct"], 2) == 12.0

    print("\nTeste do Modulo 7 concluido com sucesso.")


def test_module_07_financial_analytics():
    main()


if __name__ == "__main__":
    main()
