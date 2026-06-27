from __future__ import annotations
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

def _add_one_day(date_str):
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

def fetch_b3_stock_prices(tickers, start_date, end_date):
    frames = []
    for ticker in tickers:
        raw_df = yf.download(
            tickers=ticker,
            start=start_date,
            end=_add_one_day(end_date),
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if raw_df.empty:
            raise ValueError(f"Nenhuma cotacao retornada para {ticker}.")

        # MultiIndex: (campo, ticker) -> pega so o primeiro nivel
        raw_df.columns = [col[0] for col in raw_df.columns]

        # Index Date -> coluna date
        raw_df = raw_df.reset_index()
        raw_df = raw_df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adjusted_close",
            "Volume": "volume",
        })

        raw_df["source"] = "YAHOO_FINANCE"
        raw_df["ticker"] = ticker
        raw_df["collected_at"] = pd.Timestamp.now(tz="America/Sao_Paulo")
        raw_df["date"] = pd.to_datetime(raw_df["date"]).dt.date

        frames.append(raw_df[[
            "source", "ticker", "date", "open", "high",
            "low", "close", "adjusted_close", "volume", "collected_at"
        ]])

    return pd.concat(frames, ignore_index=True)

def save_b3_prices_to_csv(df, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")