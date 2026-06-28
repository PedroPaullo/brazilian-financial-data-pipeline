from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import OUTPUT_FILES
from logger import get_logger
from monitoring import record_data_artifact

logger = get_logger(__name__)

CVM_INF_DIARIO_URL = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{year_month}.zip"
CVM_REGISTRY_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"

DAILY_COLUMNS = [
    "fund_cnpj",
    "reference_date",
    "total_portfolio_value",
    "net_asset_value",
    "quota_value",
    "daily_subscriptions",
    "daily_redemptions",
    "number_of_shareholders",
    "source",
    "collected_at",
]

REGISTRY_COLUMNS = [
    "fund_cnpj",
    "fund_name",
    "fund_status",
    "registration_date",
    "fund_type",
    "target_investor",
    "source",
    "collected_at",
]


def _now() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {column.upper(): column for column in df.columns}
    for candidate in candidates:
        if candidate.upper() in normalized:
            return normalized[candidate.upper()]
    return None


def _extract_column(df: pd.DataFrame, candidates: list[str], default=None) -> pd.Series:
    column = _first_existing_column(df, candidates)
    if column is None:
        return pd.Series([default] * len(df))
    return df[column]


def _parse_numeric(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    comma_decimal = text.str.contains(",", regex=False)
    text = text.where(~comma_decimal, text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    text = text.replace({"": None, "nan": None, "None": None})
    return pd.to_numeric(text, errors="coerce")


def _parse_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=False).dt.strftime("%Y-%m-%d")


def normalize_daily_reports(raw_df: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    df = raw_df.copy()
    normalized = pd.DataFrame(
        {
            "fund_cnpj": _extract_column(df, ["CNPJ_FUNDO", "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO_COTA"]).astype(str).str.strip(),
            "reference_date": _parse_date(_extract_column(df, ["DT_COMPTC", "DT_REFER", "DATA_COMPTC"])),
            "total_portfolio_value": _parse_numeric(_extract_column(df, ["VL_TOTAL", "VL_TOTAL_CARTEIRA"], 0)),
            "net_asset_value": _parse_numeric(_extract_column(df, ["VL_PATRIM_LIQ", "VL_PL"], 0)),
            "quota_value": _parse_numeric(_extract_column(df, ["VL_QUOTA", "VL_COTA"], 0)),
            "daily_subscriptions": _parse_numeric(_extract_column(df, ["CAPTC_DIA", "CAPTACAO_DIA"], 0)),
            "daily_redemptions": _parse_numeric(_extract_column(df, ["RESG_DIA", "RESGATE_DIA"], 0)),
            "number_of_shareholders": _parse_numeric(_extract_column(df, ["NR_COTST", "NR_COTISTAS"], 0)),
            "source": "CVM_INF_DIARIO_FI",
            "collected_at": _now(),
        }
    )
    normalized = normalized.dropna(subset=["fund_cnpj", "reference_date"])
    normalized = normalized[normalized["fund_cnpj"].str.lower() != "nan"].copy()
    normalized["number_of_shareholders"] = normalized["number_of_shareholders"].fillna(0).astype(int)
    if top_n is not None and top_n > 0:
        normalized = normalized.sort_values("net_asset_value", ascending=False).head(top_n)
    return normalized[DAILY_COLUMNS]


def normalize_registry(raw_df: pd.DataFrame, fund_cnpjs: set[str] | None = None) -> pd.DataFrame:
    df = raw_df.copy()
    normalized = pd.DataFrame(
        {
            "fund_cnpj": _extract_column(df, ["CNPJ_FUNDO", "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO_COTA"]).astype(str).str.strip(),
            "fund_name": _extract_column(df, ["DENOM_SOCIAL", "DENOMINACAO_SOCIAL", "NM_FUNDO", "NOME_FUNDO"], ""),
            "fund_status": _extract_column(df, ["SIT", "SITUACAO", "SIT_REG"], ""),
            "registration_date": _parse_date(_extract_column(df, ["DT_REG", "DT_INI_ATIV", "DT_CONST"])),
            "fund_type": _extract_column(df, ["TP_FUNDO", "CLASSE", "CATEGORIA"], ""),
            "target_investor": _extract_column(df, ["PUBLICO_ALVO", "INVESTIDOR_QUALIFICADO", "FUNDO_EXCLUSIVO"], ""),
            "source": "CVM_CAD_FI",
            "collected_at": _now(),
        }
    )
    normalized = normalized.dropna(subset=["fund_cnpj"])
    normalized = normalized[normalized["fund_cnpj"].str.lower() != "nan"].copy()
    if fund_cnpjs:
        normalized = normalized[normalized["fund_cnpj"].isin(fund_cnpjs)].copy()
    normalized = normalized.drop_duplicates(subset=["fund_cnpj"], keep="first")
    return normalized[REGISTRY_COLUMNS]


def _read_first_csv_from_zip(content: bytes, preferred_names: list[str] | None = None) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if preferred_names:
            preferred = [
                name
                for name in names
                if any(preferred_name.lower() in Path(name).name.lower() for preferred_name in preferred_names)
            ]
            names = preferred or names
        if not names:
            raise ValueError("Nenhum CSV encontrado no arquivo ZIP da CVM.")
        with archive.open(names[0]) as file:
            return pd.read_csv(file, sep=";", encoding="latin1", low_memory=False)


def _download_zip(url: str, timeout: int = 60) -> bytes:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def collect_cvm_funds(
    year_month: str,
    top_n: int | None = None,
    daily_output_file: Path = OUTPUT_FILES["cvm_funds_daily_reports"],
    registry_output_file: Path = OUTPUT_FILES["cvm_funds_registry"],
) -> dict[str, Any]:
    try:
        daily_url = CVM_INF_DIARIO_URL.format(year_month=year_month)
        logger.info("Coletando CVM Informe Diario FI: %s", daily_url)
        daily_raw = _read_first_csv_from_zip(_download_zip(daily_url), ["inf_diario"])
        daily_df = normalize_daily_reports(daily_raw, top_n=top_n)

        logger.info("Coletando CVM cadastro de fundos/classes: %s", CVM_REGISTRY_URL)
        registry_raw = _read_first_csv_from_zip(_download_zip(CVM_REGISTRY_URL), ["registro_fundo", "registro_classe"])
        registry_df = normalize_registry(registry_raw, set(daily_df["fund_cnpj"].unique()))

        daily_output_file.parent.mkdir(parents=True, exist_ok=True)
        registry_output_file.parent.mkdir(parents=True, exist_ok=True)
        daily_df.to_csv(daily_output_file, index=False, encoding="utf-8")
        registry_df.to_csv(registry_output_file, index=False, encoding="utf-8")

        record_data_artifact("raw_csv", daily_output_file, "cvm_funds_daily_reports", len(daily_df), status="CREATED")
        record_data_artifact("raw_csv", registry_output_file, "cvm_funds_registry", len(registry_df), status="CREATED")
        return {
            "status": "SUCCESS",
            "daily_rows": len(daily_df),
            "registry_rows": len(registry_df),
            "daily_output_file": str(daily_output_file),
            "registry_output_file": str(registry_output_file),
        }
    except Exception as exc:
        logger.warning("Coleta CVM pulada por indisponibilidade ou layout inesperado: %s", exc)
        record_data_artifact("raw_csv", daily_output_file, "cvm_funds_daily_reports", 0, status="SKIPPED", details=str(exc))
        record_data_artifact("raw_csv", registry_output_file, "cvm_funds_registry", 0, status="SKIPPED", details=str(exc))
        return {"status": "SKIPPED", "error": str(exc), "daily_rows": 0, "registry_rows": 0}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year-month", required=True)
    parser.add_argument("--top-n", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = collect_cvm_funds(args.year_month, top_n=args.top_n)
    logger.info("Resultado CVM Fundos: %s", result)


if __name__ == "__main__":
    main()
