from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
RAW_BCB_DIR = RAW_DATA_DIR / "bcb"
RAW_B3_DIR = RAW_DATA_DIR / "b3"
RAW_CVM_DIR = RAW_DATA_DIR / "cvm"

BCB_SERIES = {
    "selic_daily": {"code": 11, "description": "Taxa Selic diaria", "frequency": "daily", "required": True, "publication_lag_days": 1},
    "ipca_monthly": {"code": 433, "description": "IPCA mensal", "frequency": "monthly", "required": True, "publication_lag_days": 15},
    "usd_brl_ptax_sell_daily": {"code": 1, "description": "Dolar americano venda PTAX diario", "frequency": "daily", "required": True, "publication_lag_days": 1},
    "cdi_daily": {"code": 12, "description": "Taxa CDI diaria", "frequency": "daily", "required": True, "publication_lag_days": 1},
}

DEFAULT_B3_TICKERS = ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "^BVSP"]

OUTPUT_FILES = {
    series_name: RAW_BCB_DIR / f"{series_name}.csv"
    for series_name in BCB_SERIES
}
OUTPUT_FILES.update({
    "stock_prices_daily": RAW_B3_DIR / "stock_prices_daily.csv",
    "cvm_funds_daily_reports": RAW_CVM_DIR / "funds_daily_reports.csv",
    "cvm_funds_registry": RAW_CVM_DIR / "funds_registry.csv",
})

VALIDATION_DATA_DIR = PROJECT_ROOT / "data" / "validation"
VALIDATION_REPORT_DIR = PROJECT_ROOT / "reports" / "validation"
VALIDATION_DB_FILE = VALIDATION_DATA_DIR / "financial_raw_validation.db"

VALIDATION_OUTPUT_FILES = {
    "quality_results": VALIDATION_REPORT_DIR / "data_quality_results.csv",
    "quality_summary": VALIDATION_REPORT_DIR / "data_quality_summary.json",
    "date_gaps_detail": VALIDATION_REPORT_DIR / "date_gaps_detail.csv",
}

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DB_FILE = PROCESSED_DATA_DIR / "financial_data.db"

OPERATIONS_DATA_DIR = PROJECT_ROOT / "data" / "operations"
OPERATIONS_DB_FILE = OPERATIONS_DATA_DIR / "pipeline_operations.db"

REPORTS_DIR = PROJECT_ROOT / "reports"
FINANCIAL_REPORT_FILE = REPORTS_DIR / "financial_report.xlsx"

COLLECTION_REPORT_DIR = REPORTS_DIR / "collection"
COLLECTION_STATUS_JSON_FILE = COLLECTION_REPORT_DIR / "latest_collection_status.json"
COLLECTION_STATUS_MD_FILE = COLLECTION_REPORT_DIR / "latest_collection_status.md"

OPERATIONS_REPORT_DIR = REPORTS_DIR / "operations"
ALERTS_JSON_FILE = OPERATIONS_REPORT_DIR / "alerts.json"
ALERTS_CSV_FILE = OPERATIONS_REPORT_DIR / "alerts.csv"

COVERAGE_REPORT_DIR = REPORTS_DIR / "coverage"
COVERAGE_REPORT_FILE = COVERAGE_REPORT_DIR / "data_coverage_report.csv"
COVERAGE_SUMMARY_FILE = COVERAGE_REPORT_DIR / "data_coverage_summary.json"
COVERAGE_MISSING_DATES_FILE = COVERAGE_REPORT_DIR / "data_coverage_missing_dates.csv"
