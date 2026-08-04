from __future__ import annotations

import argparse
from datetime import date
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifact_retention import prune_artifacts, today_stamp
from config import BCB_SERIES, COLLECTION_DAILY_DIR, COLLECTION_REPORT_DIR, COLLECTION_STATUS_JSON_FILE, COLLECTION_STATUS_MD_FILE, DEFAULT_B3_TICKERS, OUTPUT_FILES
from logger import get_logger
from monitoring import finish_pipeline_run, start_pipeline_run
from source_availability import today_date

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", "--start-date", dest="start", default="2024-01-01")
    parser.add_argument("--end", "--end-date", dest="end", default=today_date().strftime("%Y-%m-%d"))
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_B3_TICKERS)
    parser.add_argument("--include-cvm", action="store_true")
    parser.add_argument("--cvm-year-month", default=None)
    parser.add_argument("--cvm-top-n", type=int, default=None)
    parser.add_argument("--retention-days", type=int, default=None)
    return parser.parse_args()


def _write_collection_status_report(status_report: dict, retention_days: int | None = None) -> None:
    COLLECTION_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    COLLECTION_DAILY_DIR.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(status_report, ensure_ascii=False, indent=2, default=str)
    COLLECTION_STATUS_JSON_FILE.write_text(json_text, encoding="utf-8")
    (COLLECTION_DAILY_DIR / f"{today_stamp()}_collection_status.json").write_text(json_text, encoding="utf-8")

    bcb_lines = []
    for item in status_report.get("bcb_series", []):
        bcb_lines.append(
            "| {series_name} | {series_code} | {frequency} | {start} a {end} | {rows} | {status} | {severity} | {expected} | {reason} |".format(
                series_name=item["series_name"],
                series_code=item["series_code"],
                frequency=item["frequency"],
                start=item["requested_start_date"],
                end=item["requested_end_date"],
                rows=item["rows_collected"],
                status=item["status"],
                severity=item["severity"],
                expected=item["expected"],
                reason=item.get("reason", "").replace("|", "/"),
            )
        )

    md = [
        "# Collection Status",
        "",
        f"- run_id: `{status_report.get('run_id')}`",
        f"- started_period: `{status_report.get('start_date')}`",
        f"- ended_period: `{status_report.get('end_date')}`",
        f"- overall_status: `{status_report.get('overall_status')}`",
        f"- records_output: `{status_report.get('records_output')}`",
        f"- errors_count: `{status_report.get('errors_count')}`",
        f"- warnings_count: `{status_report.get('warnings_count')}`",
        "",
        "## BCB SGS",
        "| serie | codigo | frequencia | periodo solicitado | linhas | status | severidade | dado esperado | motivo |",
        "|---|---:|---|---|---:|---|---|---|---|",
        *bcb_lines,
        "",
        "## Stocks",
        f"- status: `{status_report.get('stocks', {}).get('status')}`",
        f"- rows: `{status_report.get('stocks', {}).get('rows')}`",
        "",
        "## CVM Fundos",
        f"- status: `{status_report.get('cvm', {}).get('status')}`",
        f"- daily_rows: `{status_report.get('cvm', {}).get('daily_rows')}`",
        f"- registry_rows: `{status_report.get('cvm', {}).get('registry_rows')}`",
        "",
    ]

    markdown_text = "\n".join(md)
    COLLECTION_STATUS_MD_FILE.write_text(markdown_text, encoding="utf-8")
    (COLLECTION_DAILY_DIR / f"{today_stamp()}_collection_status.md").write_text(markdown_text, encoding="utf-8")
    prune_artifacts([COLLECTION_DAILY_DIR], retention_days=retention_days, today=date.fromisoformat(today_stamp()))


def main():
    args = parse_args()
    from collectors.bcb_sgs import fetch_bcb_sgs_series, save_bcb_series_to_csv
    from collectors.b3_yfinance import fetch_b3_stock_prices, save_b3_prices_to_csv
    from collectors.cvm_funds import collect_cvm_funds
    from source_availability import SEVERITY_ERROR, SEVERITY_WARNING, STATUS_SUCCESS, STATUS_NOT_YET_AVAILABLE, today_date

    run_id = start_pipeline_run("collect_data")

    bcb_dfs = {}
    bcb_statuses = []
    stocks_df = None
    cvm_result = {"status": "SKIPPED", "daily_rows": 0, "registry_rows": 0}

    try:
        logger.info("Coletando dados de %s ate %s...", args.start, args.end)

        for series_name, metadata in BCB_SERIES.items():
            series_code = metadata["code"]
            bcb_df = fetch_bcb_sgs_series(series_code, series_name, args.start, args.end, metadata=metadata)

            status_record = dict(bcb_df.attrs.get("collection_status_record", {}))
            if not status_record:
                status_record = {
                    "series_name": series_name,
                    "series_code": str(series_code),
                    "frequency": metadata.get("frequency", "unknown"),
                    "requested_start_date": args.start,
                    "requested_end_date": args.end,
                    "rows_collected": int(len(bcb_df)),
                    "rows": int(len(bcb_df)),
                    "status": bcb_df.attrs.get("collection_status", "UNKNOWN"),
                    "severity": "ERROR",
                    "reason": bcb_df.attrs.get("collection_reason", ""),
                    "expected": True,
                }
            status_record["output_file"] = str(OUTPUT_FILES[series_name])
            bcb_statuses.append(status_record)

            if bcb_df.empty:
                # Sobrescreve o CSV da serie com cabecalho vazio para evitar
                # reaproveitamento silencioso de dados antigos em execucoes futuras.
                if status_record.get("status") != STATUS_NOT_YET_AVAILABLE:
                    save_bcb_series_to_csv(bcb_df, OUTPUT_FILES[series_name])
                logger.warning(
                    "%s: %s registros. Status=%s. Motivo=%s",
                    series_name,
                    len(bcb_df),
                    status_record["status"],
                    status_record["reason"],
                )
                continue

            save_bcb_series_to_csv(bcb_df, OUTPUT_FILES[series_name])
            bcb_dfs[series_name] = bcb_df

        stocks_df = fetch_b3_stock_prices(args.tickers, args.start, args.end)
        save_b3_prices_to_csv(stocks_df, OUTPUT_FILES["stock_prices_daily"])

        if args.include_cvm:
            cvm_year_month = args.cvm_year_month or args.start[:7].replace("-", "")
            cvm_result = collect_cvm_funds(cvm_year_month, top_n=args.cvm_top_n)
        else:
            logger.info("Coleta CVM Fundos pulada. Use --include-cvm para habilitar.")

        bcb_records = sum(len(df) for df in bcb_dfs.values())
        stock_records = len(stocks_df) if stocks_df is not None else 0
        cvm_records = int(cvm_result.get("daily_rows", 0)) + int(cvm_result.get("registry_rows", 0))
        records_output = bcb_records + stock_records + cvm_records

        bcb_errors = [item for item in bcb_statuses if item.get("severity") == SEVERITY_ERROR]
        bcb_warnings = [item for item in bcb_statuses if item.get("severity") == SEVERITY_WARNING]
        bcb_non_success = [item for item in bcb_statuses if item.get("status") != STATUS_SUCCESS]

        if records_output == 0:
            overall_status = "FAILED"
        elif bcb_errors or bcb_warnings:
            overall_status = "PARTIAL_SUCCESS"
        else:
            overall_status = "SUCCESS"

        status_report = {
            "run_id": run_id,
            "start_date": args.start,
            "end_date": args.end,
            "overall_status": overall_status,
            "records_output": records_output,
            "errors_count": len(bcb_errors),
            "warnings_count": len(bcb_warnings),
            "bcb_series": bcb_statuses,
            "stocks": {
                "status": "SUCCESS",
                "rows": stock_records,
                "tickers": args.tickers,
            },
            "cvm": cvm_result,
        }

        _write_collection_status_report(status_report, retention_days=args.retention_days)

        finish_pipeline_run(
            run_id,
            overall_status,
            records_output=records_output,
            errors_count=len(bcb_errors),
        )

        for series_name, bcb_df in bcb_dfs.items():
            logger.info("%s: %s registros", series_name, len(bcb_df))

        for item in bcb_non_success:
            logger.warning(
                "%s: %s. Codigo=%s. Severidade=%s. Esperado=%s. Motivo=%s",
                item["series_name"],
                item["status"],
                item["series_code"],
                item.get("severity"),
                item.get("expected"),
                item["reason"],
            )

        logger.info("Acoes: %s registros", stock_records)
        logger.info("CVM Fundos: %s", cvm_result)
        logger.info("Coleta finalizada com status %s.", overall_status)

        if overall_status == "FAILED":
            logger.error("Nenhum registro foi coletado. Verifique reports/collection/latest_collection_status.md.")
            sys.exit(1)

    except Exception as exc:
        finish_pipeline_run(run_id, "FAILED", errors_count=1, error_message=str(exc))
        logger.exception("Coleta finalizada com erro fatal: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
