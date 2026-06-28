from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import FINANCIAL_REPORT_FILE, PROCESSED_DB_FILE
from reports.excel_report import create_financial_report
from logger import get_logger
from monitoring import finish_pipeline_run, start_pipeline_run

logger = get_logger(__name__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-file", default=str(PROCESSED_DB_FILE))
    parser.add_argument("--output-file", default=str(FINANCIAL_REPORT_FILE))
    return parser.parse_args()

def main():
    args = parse_args()
    run_id = start_pipeline_run("generate_report")

    try:
        logger.info("Iniciando Modulo 4 - Relatorio Excel")
        logger.info("Banco: %s", args.database_file)
        logger.info("Saida: %s", args.output_file)
        summary = create_financial_report(Path(args.database_file), Path(args.output_file))
        records_input = summary["selic_rows"] + summary["ipca_rows"] + summary["stock_rows"]
        finish_pipeline_run(run_id, "SUCCESS", records_input=records_input, records_output=1, errors_count=0)

        logger.info("=" * 60)
        logger.info("RESUMO - MODULO 4")
        logger.info("=" * 60)
        logger.info("Arquivo : %s", summary["output_file"])
        logger.info("Selic   : %s registros", summary["selic_rows"])
        logger.info("IPCA    : %s registros", summary["ipca_rows"])
        logger.info("BCB     : %s registros", summary["bcb_series_rows"])
        logger.info("Acoes   : %s registros", summary["stock_rows"])
        logger.info("Cobertura: %s datasets", summary["coverage_datasets"])
        logger.info("CVM     : %s registros, %s fundos", summary["cvm_fund_rows"], summary["cvm_funds"])
        logger.info("Tickers : %s", ", ".join(summary["tickers"]))
        logger.info("Selic   : %.6f em %s", summary["latest_selic_value"], summary["latest_selic_date"])
        if summary["ipca_accumulated_2024"]:
            logger.info("IPCA    : %.2f%% acumulado 2024", summary["ipca_accumulated_2024"])
        logger.info("=" * 60)
        logger.info("Relatorio gerado com sucesso.")
    except Exception as exc:
        finish_pipeline_run(run_id, "FAILED", errors_count=1, error_message=str(exc))
        raise

if __name__ == "__main__":
    main()
