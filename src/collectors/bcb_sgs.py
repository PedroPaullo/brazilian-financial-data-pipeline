from __future__ import annotations
from datetime import datetime
import pandas as pd
import requests

BCB_SGS_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_code}/dados"

def _format_date_to_bcb(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")

def fetch_bcb_sgs_series(series_code, series_name, start_date, end_date, timeout=30):
    url = BCB_SGS_BASE_URL.format(series_code=series_code)
    params = {"formato": "json", "dataInicial": _format_date_to_bcb(start_date), "dataFinal": _format_date_to_bcb(end_date)}
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"Nenhum dado retornado para serie {series_code}.")
    df = pd.DataFrame(data).rename(columns={"data": "date", "valor": "value"})
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")
    df["value"] = df["value"].astype(str).str.replace(",", ".", regex=False).astype(float)
    df["source"] = "BCB_SGS"
    df["series_code"] = series_code
    df["series_name"] = series_name
    df["collected_at"] = pd.Timestamp.now(tz="America/Sao_Paulo")
    return df[["source", "series_code", "series_name", "date", "value", "collected_at"]]

def save_bcb_series_to_csv(df, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
