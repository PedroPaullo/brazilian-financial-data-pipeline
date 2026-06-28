from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OUTPUT_FILES, PROCESSED_DB_FILE
from storage.load_processed_sqlite import load_processed_database
from logger import get_logger

SCHEMA_FILE = Path(__file__).resolve().parent / "storage" / "schema.sql"
logger = get_logger(__name__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selic-file", default=str(OUTPUT_FILES["selic_daily"]))
    parser.add_argument("--ipca-file", default=str(OUTPUT_FILES["ipca_monthly"]))
    parser.add_argument("--stocks-file", default=str(OUTPUT_FILES["stock_prices_daily"]))
    parser.add_argument("--database-file", default=str(PROCESSED_DB_FILE))
    parser.add_argument("--append", action="store_true")
    return parser.parse_args()

def main():
    args = parse_args()
    replace_database = not args.append
    logger.info("Iniciando Modulo 3 - Armazenamento final")
    logger.info("Banco final: %s", args.database_file)
    logger.info("Modo: %s", "replace" if replace_database else "append")

    table_counts = load_processed_database(
        selic_file=Path(args.selic_file),
        ipca_file=Path(args.ipca_file),
        stocks_file=Path(args.stocks_file),
        database_file=Path(args.database_file),
        schema_file=SCHEMA_FILE,
        replace_database=replace_database,
    )

    logger.info("=" * 60)
    logger.info("RESUMO - MODULO 3")
    logger.info("=" * 60)
    logger.info("dim_source          : %s", table_counts["dim_source"])
    logger.info("dim_bcb_series      : %s", table_counts["dim_bcb_series"])
    logger.info("dim_b3_ticker       : %s", table_counts["dim_b3_ticker"])
    logger.info("fact_bcb_series     : %s", table_counts["fact_bcb_series_values"])
    logger.info("fact_b3_stock_prices: %s", table_counts["fact_b3_stock_prices"])
    logger.info("=" * 60)
    logger.info("Carga final concluida com sucesso.")

if __name__ == "__main__":
    main()
