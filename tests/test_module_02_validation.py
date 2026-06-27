from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DB_FILE = PROJECT_ROOT / "data" / "validation" / "financial_raw_validation.db"
QUALITY_RESULTS_FILE = PROJECT_ROOT / "reports" / "validation" / "data_quality_results.csv"
QUALITY_SUMMARY_FILE = PROJECT_ROOT / "reports" / "validation" / "data_quality_summary.json"
DATE_GAPS_DETAIL_FILE = PROJECT_ROOT / "reports" / "validation" / "date_gaps_detail.csv"

def main():
    for f in [VALIDATION_DB_FILE, QUALITY_RESULTS_FILE, QUALITY_SUMMARY_FILE, DATE_GAPS_DETAIL_FILE]:
        assert f.exists(), f"Arquivo nao encontrado: {f}"

    results_df = pd.read_csv(QUALITY_RESULTS_FILE)
    assert not results_df.empty

    expected_columns = {"check_id", "check_category", "check_name", "dataset", "rule_type", "severity", "status", "rows_affected", "details", "evidence_query", "executed_at"}
    missing = expected_columns - set(results_df.columns)
    assert not missing, f"Colunas ausentes: {missing}"

    with open(QUALITY_SUMMARY_FILE, "r", encoding="utf-8") as f:
        summary = json.load(f)

    assert summary["total_checks"] > 0
    assert summary["fail"] == 0, "Existem falhas criticas. Verifique data_quality_results.csv"

    print("\nTeste do Modulo 2 concluido com sucesso.")
    print(f"Status geral : {summary['overall_status']}")
    print(f"Total checks : {summary['total_checks']}")
    print(f"PASS         : {summary['pass']}")
    print(f"WARN         : {summary['warn']}")
    print(f"FAIL         : {summary['fail']}")

if __name__ == "__main__":
    main()