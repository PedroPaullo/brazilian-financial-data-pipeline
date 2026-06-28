from __future__ import annotations
import argparse
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BCB_SERIES, DEFAULT_B3_TICKERS, OUTPUT_FILES
from collectors.bcb_sgs import fetch_bcb_sgs_series, save_bcb_series_to_csv
from collectors.b3_yfinance import fetch_b3_stock_prices, save_b3_prices_to_csv
from logger import get_logger
from monitoring import finish_pipeline_run, start_pipeline_run

logger = get_logger(__name__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=date.today().strftime("%Y-%m-%d"))
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_B3_TICKERS)
    return parser.parse_args()

def main():
    args = parse_args()
    run_id = start_pipeline_run("collect_data")

    try:
        logger.info("Coletando dados de %s ate %s...", args.start, args.end)

        selic_df = fetch_bcb_sgs_series(BCB_SERIES["selic_daily"]["code"], "selic_daily", args.start, args.end)
        save_bcb_series_to_csv(selic_df, OUTPUT_FILES["selic_daily"])

        ipca_df = fetch_bcb_sgs_series(BCB_SERIES["ipca_monthly"]["code"], "ipca_monthly", args.start, args.end)
        save_bcb_series_to_csv(ipca_df, OUTPUT_FILES["ipca_monthly"])

        stocks_df = fetch_b3_stock_prices(args.tickers, args.start, args.end)
        save_b3_prices_to_csv(stocks_df, OUTPUT_FILES["stock_prices_daily"])

        records_output = len(selic_df) + len(ipca_df) + len(stocks_df)
        finish_pipeline_run(run_id, "SUCCESS", records_output=records_output, errors_count=0)

        logger.info("Selic: %s registros", len(selic_df))
        logger.info("IPCA: %s registros", len(ipca_df))
        logger.info("Acoes: %s registros", len(stocks_df))
        logger.info("Coleta finalizada com sucesso.")
    except Exception as exc:
        finish_pipeline_run(run_id, "FAILED", errors_count=1, error_message=str(exc))
        raise

if __name__ == "__main__":
    main()
