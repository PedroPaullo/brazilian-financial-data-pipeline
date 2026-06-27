from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import FINANCIAL_REPORT_FILE, PROCESSED_DB_FILE
from reports.excel_report import create_financial_report

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-file", default=str(PROCESSED_DB_FILE))
    parser.add_argument("--output-file", default=str(FINANCIAL_REPORT_FILE))
    return parser.parse_args()

def main():
    args = parse_args()
    print("Iniciando Modulo 4 - Relatorio Excel")
    print(f"Banco: {args.database_file}")
    print(f"Saida: {args.output_file}")
    summary = create_financial_report(Path(args.database_file), Path(args.output_file))
    print("\n" + "=" * 60)
    print("RESUMO - MODULO 4")
    print("=" * 60)
    print(f"Arquivo : {summary['output_file']}")
    print(f"Selic   : {summary['selic_rows']} registros")
    print(f"IPCA    : {summary['ipca_rows']} registros")
    print(f"Acoes   : {summary['stock_rows']} registros")
    print(f"Tickers : {', '.join(summary['tickers'])}")
    print(f"Selic   : {summary['latest_selic_value']:.6f} em {summary['latest_selic_date']}")
    if summary['ipca_accumulated_2024']:
        print(f"IPCA    : {summary['ipca_accumulated_2024']:.2f}% acumulado 2024")
    print("=" * 60)
    print("Relatorio gerado com sucesso.")

if __name__ == "__main__":
    main()