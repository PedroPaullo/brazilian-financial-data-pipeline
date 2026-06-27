from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OUTPUT_FILES, VALIDATION_DB_FILE, VALIDATION_OUTPUT_FILES
from validators.load_raw_to_sqlite import load_raw_files_to_sqlite
from validators.quality_checks import run_quality_checks, save_validation_outputs

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selic-file", default=str(OUTPUT_FILES["selic_daily"]))
    parser.add_argument("--ipca-file", default=str(OUTPUT_FILES["ipca_monthly"]))
    parser.add_argument("--stocks-file", default=str(OUTPUT_FILES["stock_prices_daily"]))
    parser.add_argument("--database-file", default=str(VALIDATION_DB_FILE))
    return parser.parse_args()

def main():
    args = parse_args()
    print("Iniciando Modulo 2 - Validacao de dados")

    loaded_rows = load_raw_files_to_sqlite(
        selic_file=Path(args.selic_file),
        ipca_file=Path(args.ipca_file),
        stocks_file=Path(args.stocks_file),
        database_file=Path(args.database_file),
    )

    print("\nRegistros carregados no SQLite:")
    for table, count in loaded_rows.items():
        print(f"  {table}: {count} linhas")

    results_df, gaps_df, summary = run_quality_checks(Path(args.database_file))

    save_validation_outputs(
        results_df=results_df,
        gaps_df=gaps_df,
        summary=summary,
        quality_results_file=VALIDATION_OUTPUT_FILES["quality_results"],
        quality_summary_file=VALIDATION_OUTPUT_FILES["quality_summary"],
        date_gaps_detail_file=VALIDATION_OUTPUT_FILES["date_gaps_detail"],
    )

    print("\n" + "=" * 60)
    print("RESUMO DA VALIDACAO - MODULO 2")
    print("=" * 60)
    print(f"Status geral : {summary['overall_status']}")
    print(f"Total checks : {summary['total_checks']}")
    print(f"PASS         : {summary['pass']}")
    print(f"WARN         : {summary['warn']}")
    print(f"FAIL         : {summary['fail']}")
    print("=" * 60)

    if summary["fail"] > 0:
        print("\nValidacao concluida COM FALHAS.")
        raise SystemExit(1)

    print("\nValidacao concluida sem falhas criticas.")

if __name__ == "__main__":
    main()