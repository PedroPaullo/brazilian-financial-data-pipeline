from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OUTPUT_FILES, PROCESSED_DB_FILE
from storage.load_processed_sqlite import load_processed_database

SCHEMA_FILE = Path(__file__).resolve().parent / "storage" / "schema.sql"

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
    print("Iniciando Modulo 3 - Armazenamento final")
    print(f"Banco final: {args.database_file}")
    print(f"Modo: {'replace' if replace_database else 'append'}")

    table_counts = load_processed_database(
        selic_file=Path(args.selic_file),
        ipca_file=Path(args.ipca_file),
        stocks_file=Path(args.stocks_file),
        database_file=Path(args.database_file),
        schema_file=SCHEMA_FILE,
        replace_database=replace_database,
    )

    print("\n" + "=" * 60)
    print("RESUMO - MODULO 3")
    print("=" * 60)
    print(f"dim_source          : {table_counts['dim_source']}")
    print(f"dim_bcb_series      : {table_counts['dim_bcb_series']}")
    print(f"dim_b3_ticker       : {table_counts['dim_b3_ticker']}")
    print(f"fact_bcb_series     : {table_counts['fact_bcb_series_values']}")
    print(f"fact_b3_stock_prices: {table_counts['fact_b3_stock_prices']}")
    print("=" * 60)
    print("Carga final concluida com sucesso.")

if __name__ == "__main__":
    main()