from __future__ import annotations

import pandas as pd


def calculate_period_return(first_value, last_value) -> float | None:
    """Return percentage change between two values."""
    if first_value is None or last_value is None or pd.isna(first_value) or pd.isna(last_value):
        return None

    first = float(first_value)
    last = float(last_value)
    if first == 0:
        return None

    return ((last / first) - 1) * 100


def calculate_cumulative_return(df: pd.DataFrame, date_col: str, price_col: str) -> pd.DataFrame:
    """Return a date-indexed cumulative return series in percent."""
    if df.empty or date_col not in df.columns or price_col not in df.columns:
        return pd.DataFrame(columns=[date_col, "cumulative_return_pct"])

    sorted_df = df[[date_col, price_col]].dropna().sort_values(date_col).copy()
    if sorted_df.empty:
        return pd.DataFrame(columns=[date_col, "cumulative_return_pct"])

    first_price = float(sorted_df.iloc[0][price_col])
    if first_price == 0:
        sorted_df["cumulative_return_pct"] = None
    else:
        sorted_df["cumulative_return_pct"] = ((sorted_df[price_col] / first_price) - 1) * 100

    return sorted_df[[date_col, "cumulative_return_pct"]]


def calculate_real_return(nominal_return_pct, inflation_pct) -> float | None:
    """Return inflation-adjusted return using compound formula."""
    if nominal_return_pct is None or inflation_pct is None or pd.isna(nominal_return_pct) or pd.isna(inflation_pct):
        return None

    return (((1 + float(nominal_return_pct) / 100) / (1 + float(inflation_pct) / 100)) - 1) * 100


def calculate_annualized_volatility(returns, periods_per_year: int = 252) -> float | None:
    """Return annualized volatility in percent from periodic returns."""
    series = pd.Series(returns).dropna()
    if series.empty or len(series) < 2:
        return None

    return float(series.std(ddof=1) * (periods_per_year ** 0.5) * 100)


def calculate_max_drawdown(price_series) -> float | None:
    """Return maximum drawdown in percent from a price series."""
    prices = pd.Series(price_series).dropna().astype(float)
    if prices.empty:
        return None

    running_max = prices.cummax()
    drawdowns = (prices / running_max - 1) * 100
    return float(drawdowns.min())


def calculate_correlation_matrix(price_df: pd.DataFrame) -> pd.DataFrame:
    """Return correlation matrix of daily returns from a wide price DataFrame."""
    if price_df.empty:
        return pd.DataFrame()

    returns_df = price_df.pct_change(fill_method=None).dropna(how="all")
    if returns_df.empty:
        return pd.DataFrame()

    return returns_df.corr()


def calculate_excess_return(asset_return_pct, benchmark_return_pct) -> float | None:
    """Return asset return minus benchmark return in percentage points."""
    if asset_return_pct is None or benchmark_return_pct is None or pd.isna(asset_return_pct) or pd.isna(benchmark_return_pct):
        return None

    return float(asset_return_pct) - float(benchmark_return_pct)


def _accumulated_inflation(ipca_df: pd.DataFrame) -> float | None:
    if ipca_df is None or ipca_df.empty or "ipca_monthly_value" not in ipca_df.columns:
        return None

    return float(((ipca_df["ipca_monthly_value"] / 100 + 1).prod() - 1) * 100)


def build_asset_performance_summary(
    stocks_df: pd.DataFrame,
    ipca_df: pd.DataFrame | None = None,
    benchmark_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build performance, risk and benchmark summary by ticker."""
    columns = [
        "ticker",
        "start_date",
        "end_date",
        "initial_price",
        "final_price",
        "nominal_return_pct",
        "real_return_pct",
        "annualized_volatility_pct",
        "max_drawdown_pct",
        "benchmark_return_pct",
        "excess_return_pct",
    ]
    if stocks_df.empty:
        return pd.DataFrame(columns=columns)

    benchmark_return_pct = None
    if benchmark_df is not None and not benchmark_df.empty:
        benchmark_df = benchmark_df.sort_values("reference_date")
        benchmark_return_pct = calculate_period_return(
            benchmark_df.iloc[0]["adjusted_close_price"],
            benchmark_df.iloc[-1]["adjusted_close_price"],
        )

    inflation_pct = _accumulated_inflation(ipca_df)
    rows = []
    for ticker, ticker_df in stocks_df.groupby("ticker"):
        ticker_df = ticker_df.sort_values("reference_date")
        initial_price = float(ticker_df.iloc[0]["adjusted_close_price"])
        final_price = float(ticker_df.iloc[-1]["adjusted_close_price"])
        nominal_return_pct = calculate_period_return(initial_price, final_price)
        periodic_returns = ticker_df["adjusted_close_price"].pct_change(fill_method=None).dropna()

        rows.append(
            {
                "ticker": ticker,
                "start_date": ticker_df.iloc[0]["reference_date"],
                "end_date": ticker_df.iloc[-1]["reference_date"],
                "initial_price": initial_price,
                "final_price": final_price,
                "nominal_return_pct": nominal_return_pct,
                "real_return_pct": calculate_real_return(nominal_return_pct, inflation_pct),
                "annualized_volatility_pct": calculate_annualized_volatility(periodic_returns),
                "max_drawdown_pct": calculate_max_drawdown(ticker_df["adjusted_close_price"]),
                "benchmark_return_pct": benchmark_return_pct,
                "excess_return_pct": calculate_excess_return(nominal_return_pct, benchmark_return_pct),
            }
        )

    return pd.DataFrame(rows, columns=columns).sort_values("ticker")
