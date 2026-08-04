from __future__ import annotations

from datetime import datetime
import logging

import pandas as pd
import requests

from source_availability import (
    BCB_CSV_COLUMNS,
    apply_status_to_dataframe,
    build_bcb_success_status,
    classify_bcb_failure,
)

BCB_SGS_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_code}/dados"

logger = logging.getLogger(__name__)

BCB_COLUMNS = BCB_CSV_COLUMNS


def _format_date_to_bcb(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")


def _empty_bcb_result(
    series_code,
    series_name,
    status_record: dict,
) -> pd.DataFrame:
    df = pd.DataFrame(columns=BCB_COLUMNS)
    df.attrs["series_code"] = str(series_code)
    df.attrs["series_name"] = str(series_name)
    return apply_status_to_dataframe(df, status_record)


def fetch_bcb_sgs_series(series_code, series_name, start_date, end_date, timeout=30, metadata=None):
    metadata = metadata or {"code": series_code}
    url = BCB_SGS_BASE_URL.format(series_code=series_code)
    params = {
        "formato": "json",
        "dataInicial": _format_date_to_bcb(start_date),
        "dataFinal": _format_date_to_bcb(end_date),
    }

    try:
        response = requests.get(url, params=params, timeout=timeout)

        if response.status_code == 404:
            reason = (
                f"BCB SGS retornou 404 para serie={series_code}, "
                f"nome={series_name}, periodo={start_date} a {end_date}."
            )
            logger.warning(reason)
            status_record = classify_bcb_failure(
                series_name=series_name,
                metadata=metadata,
                start_date=start_date,
                end_date=end_date,
                failure_type="HTTP_404",
                reason=reason,
                http_status_code=response.status_code,
            )
            return _empty_bcb_result(
                series_code=series_code,
                series_name=series_name,
                status_record=status_record,
            )

        response.raise_for_status()

    except requests.RequestException as exc:
        reason = (
            f"Falha HTTP ao coletar BCB SGS serie={series_code}, "
            f"nome={series_name}, periodo={start_date} a {end_date}: {exc}"
        )
        logger.warning(reason)
        status_record = classify_bcb_failure(
            series_name=series_name,
            metadata=metadata,
            start_date=start_date,
            end_date=end_date,
            failure_type="HTTP_ERROR",
            reason=reason,
            http_status_code=getattr(getattr(exc, "response", None), "status_code", None),
        )
        return _empty_bcb_result(
            series_code=series_code,
            series_name=series_name,
            status_record=status_record,
        )

    try:
        data = response.json()
    except ValueError as exc:
        reason = (
            f"Resposta JSON invalida do BCB SGS serie={series_code}, "
            f"nome={series_name}, periodo={start_date} a {end_date}: {exc}"
        )
        logger.warning(reason)
        status_record = classify_bcb_failure(
            series_name=series_name,
            metadata=metadata,
            start_date=start_date,
            end_date=end_date,
            failure_type="UNEXPECTED",
            reason=reason,
            http_status_code=response.status_code,
        )
        return _empty_bcb_result(
            series_code=series_code,
            series_name=series_name,
            status_record=status_record,
        )

    if not data:
        reason = (
            f"Nenhum dado retornado pelo BCB SGS para serie={series_code}, "
            f"nome={series_name}, periodo={start_date} a {end_date}."
        )
        logger.warning(reason)
        status_record = classify_bcb_failure(
            series_name=series_name,
            metadata=metadata,
            start_date=start_date,
            end_date=end_date,
            failure_type="EMPTY_PAYLOAD",
            reason=reason,
            http_status_code=response.status_code,
        )
        return _empty_bcb_result(
            series_code=series_code,
            series_name=series_name,
            status_record=status_record,
        )

    try:
        df = pd.DataFrame(data).rename(columns={"data": "date", "valor": "value"})
        df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")
        df["value"] = df["value"].astype(str).str.replace(",", ".", regex=False).astype(float)
        df["source"] = "BCB_SGS"
        df["series_code"] = str(series_code)
        df["series_name"] = series_name
        df["collected_at"] = pd.Timestamp.now(tz="America/Sao_Paulo")
        df = df[BCB_COLUMNS]
    except Exception as exc:
        reason = (
            f"Falha ao normalizar dados BCB SGS serie={series_code}, "
            f"nome={series_name}, periodo={start_date} a {end_date}: {exc}"
        )
        logger.warning(reason)
        status_record = classify_bcb_failure(
            series_name=series_name,
            metadata=metadata,
            start_date=start_date,
            end_date=end_date,
            failure_type="UNEXPECTED",
            reason=reason,
            http_status_code=response.status_code,
        )
        return _empty_bcb_result(
            series_code=series_code,
            series_name=series_name,
            status_record=status_record,
        )

    df.attrs["series_code"] = str(series_code)
    df.attrs["series_name"] = str(series_name)
    status_record = build_bcb_success_status(
        series_name=series_name,
        metadata=metadata,
        start_date=start_date,
        end_date=end_date,
        rows=len(df),
        http_status_code=response.status_code,
    )
    apply_status_to_dataframe(df, status_record)

    return df


def save_bcb_series_to_csv(df, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not df.empty:
        try:
            previous = pd.read_csv(output_path)
            combined = pd.concat([previous, df], ignore_index=True)
            combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            df = combined.dropna(subset=["date"]).drop_duplicates(subset=["series_code", "date"], keep="last")
        except (OSError, ValueError, pd.errors.ParserError):
            pass
    df.to_csv(output_path, index=False, encoding="utf-8")
