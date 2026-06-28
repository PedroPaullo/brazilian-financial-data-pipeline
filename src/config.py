from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
RAW_BCB_DIR = RAW_DATA_DIR / "bcb"
RAW_B3_DIR = RAW_DATA_DIR / "b3"

BCB_SERIES = {
    "selic_daily": {"code": 11, "description": "Taxa Selic diaria", "frequency": "daily"},
    "ipca_monthly": {"code": 433, "description": "IPCA mensal", "frequency": "monthly"},
}

DEFAULT_B3_TICKERS = ["PETR4.SA", "VALE3.SA", "ITUB4.SA"]

OUTPUT_FILES = {
    "selic_daily": RAW_BCB_DIR / "selic_daily.csv",
    "ipca_monthly": RAW_BCB_DIR / "ipca_monthly.csv",
    "stock_prices_daily": RAW_B3_DIR / "stock_prices_daily.csv",
}

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
