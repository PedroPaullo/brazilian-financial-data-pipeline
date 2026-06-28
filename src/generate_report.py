from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import FINANCIAL_REPORT_FILE, PROCESSED_DB_FILE
from reports.excel_report import create_financial_report
from logger import get_logger

logger = get_logger(__name__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-file", default=str(PROCESSED_DB_FILE))
    parser.add_argument("--output-file", default=str(FINANCIAL_REPORT_FILE))
    return parser.parse_args()

def main():
    args = parse_args()
    logger.info("Iniciando Modulo 4 - Relatorio Excel")
    logger.info("Banco: %s", args.database_file)
    logger.info("Saida: %s", args.output_file)
    summary = create_financial_report(Path(args.database_file), Path(args.output_file))
    logger.info("=" * 60)
    logger.info("RESUMO - MODULO 4")
    logger.info("=" * 60)
    logger.info("Arquivo : %s", summary["output_file"])
    logger.info("Selic   : %s registros", summary["selic_rows"])
    logger.info("IPCA    : %s registros", summary["ipca_rows"])
    logger.info("Acoes   : %s registros", summary["stock_rows"])
    logger.info("Tickers : %s", ", ".join(summary["tickers"]))
    logger.info("Selic   : %.6f em %s", summary["latest_selic_value"], summary["latest_selic_date"])
    if summary["ipca_accumulated_2024"]:
        logger.info("IPCA    : %.2f%% acumulado 2024", summary["ipca_accumulated_2024"])
    logger.info("=" * 60)
    logger.info("Relatorio gerado com sucesso.")

if __name__ == "__main__":
    main()
