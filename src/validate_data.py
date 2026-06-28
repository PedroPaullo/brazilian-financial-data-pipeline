from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OUTPUT_FILES, VALIDATION_DB_FILE, VALIDATION_OUTPUT_FILES
from validators.load_raw_to_sqlite import load_raw_files_to_sqlite
from validators.quality_checks import run_quality_checks, save_validation_outputs
from logger import get_logger
from monitoring import finish_pipeline_run, start_pipeline_run

logger = get_logger(__name__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selic-file", default=str(OUTPUT_FILES["selic_daily"]))
    parser.add_argument("--ipca-file", default=str(OUTPUT_FILES["ipca_monthly"]))
    parser.add_argument("--usd-ptax-file", default=str(OUTPUT_FILES["usd_brl_ptax_sell_daily"]))
    parser.add_argument("--cdi-file", default=str(OUTPUT_FILES["cdi_daily"]))
    parser.add_argument("--stocks-file", default=str(OUTPUT_FILES["stock_prices_daily"]))
    parser.add_argument("--database-file", default=str(VALIDATION_DB_FILE))
    return parser.parse_args()

def main():
    args = parse_args()
    run_id = start_pipeline_run("validate_data")

    try:
        logger.info("Iniciando Modulo 2 - Validacao de dados")

        loaded_rows = load_raw_files_to_sqlite(
            selic_file=Path(args.selic_file),
            ipca_file=Path(args.ipca_file),
            stocks_file=Path(args.stocks_file),
            database_file=Path(args.database_file),
            extra_bcb_files=[Path(args.usd_ptax_file), Path(args.cdi_file)],
        )

        logger.info("Registros carregados no SQLite:")
        for table, count in loaded_rows.items():
            logger.info("  %s: %s linhas", table, count)

        results_df, gaps_df, summary = run_quality_checks(Path(args.database_file))

        save_validation_outputs(
            results_df=results_df,
            gaps_df=gaps_df,
            summary=summary,
            quality_results_file=VALIDATION_OUTPUT_FILES["quality_results"],
            quality_summary_file=VALIDATION_OUTPUT_FILES["quality_summary"],
            date_gaps_detail_file=VALIDATION_OUTPUT_FILES["date_gaps_detail"],
        )

        logger.info("=" * 60)
        logger.info("RESUMO DA VALIDACAO - MODULO 2")
        logger.info("=" * 60)
        logger.info("Status geral : %s", summary["overall_status"])
        logger.info("Total checks : %s", summary["total_checks"])
        logger.info("PASS         : %s", summary["pass"])
        logger.info("WARN         : %s", summary["warn"])
        logger.info("FAIL         : %s", summary["fail"])
        logger.info("=" * 60)

        status = "FAILED" if summary["fail"] > 0 else "SUCCESS"
        finish_pipeline_run(
            run_id,
            status,
            records_input=sum(loaded_rows.values()),
            records_output=int(summary["total_checks"]),
            warnings_count=int(summary["warn"]),
            errors_count=int(summary["fail"]),
        )

        if summary["fail"] > 0:
            logger.error("Validacao concluida COM FALHAS.")
            raise SystemExit(1)

        logger.info("Validacao concluida sem falhas criticas.")
    except SystemExit:
        raise
    except Exception as exc:
        finish_pipeline_run(run_id, "FAILED", errors_count=1, error_message=str(exc))
        raise

if __name__ == "__main__":
    main()
