from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alerts import generate_operational_alerts
from config import (
    ALERTS_CSV_FILE,
    ALERTS_JSON_FILE,
    FINANCIAL_REPORT_FILE,
    OUTPUT_FILES,
    PROJECT_ROOT,
    PROCESSED_DB_FILE,
    VALIDATION_DB_FILE,
    VALIDATION_OUTPUT_FILES,
)
from logger import get_logger
from monitoring import finish_pipeline_run, record_data_artifact, start_pipeline_run

SRC_DIR = Path(__file__).resolve().parent
logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--skip-collection", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument(
        "--modules",
        nargs="+",
        choices=["collect", "validate", "load", "report", "alerts"],
        help="Executa apenas os modulos informados, na ordem fornecida.",
    )
    return parser.parse_args()


def _default_steps(args) -> list[str]:
    if args.modules:
        return args.modules

    steps = ["collect", "validate", "load", "report", "alerts"]
    if args.skip_collection:
        steps.remove("collect")
    if args.skip_report:
        steps.remove("report")
    return steps


def _command_for_step(step: str, args) -> list[str]:
    commands = {
        "collect": [sys.executable, str(SRC_DIR / "collect_data.py"), "--start", args.start, "--end", args.end],
        "validate": [sys.executable, str(SRC_DIR / "validate_data.py")],
        "load": [sys.executable, str(SRC_DIR / "load_processed_data.py")],
        "report": [sys.executable, str(SRC_DIR / "generate_report.py")],
        "alerts": [sys.executable, str(SRC_DIR / "alerts.py")],
    }
    return commands[step]


def _record_standard_artifacts(run_id: int | None = None) -> None:
    for series_name, output_file in OUTPUT_FILES.items():
        record_data_artifact("raw_csv", output_file, series_name, status="CREATED" if output_file.exists() else "MISSING", run_id=run_id)

    record_data_artifact("validation_db", VALIDATION_DB_FILE, "validation", status="CREATED" if VALIDATION_DB_FILE.exists() else "MISSING", run_id=run_id)
    record_data_artifact("processed_db", PROCESSED_DB_FILE, "processed", status="CREATED" if PROCESSED_DB_FILE.exists() else "MISSING", run_id=run_id)
    record_data_artifact("excel_report", FINANCIAL_REPORT_FILE, "financial_report", status="CREATED" if FINANCIAL_REPORT_FILE.exists() else "MISSING", run_id=run_id)

    for artifact_name, artifact_path in VALIDATION_OUTPUT_FILES.items():
        record_data_artifact("validation_report", artifact_path, artifact_name, status="CREATED" if artifact_path.exists() else "MISSING", run_id=run_id)

    record_data_artifact("alerts_json", ALERTS_JSON_FILE, "operational_alerts", status="CREATED" if ALERTS_JSON_FILE.exists() else "MISSING", run_id=run_id)
    record_data_artifact("alerts_csv", ALERTS_CSV_FILE, "operational_alerts", status="CREATED" if ALERTS_CSV_FILE.exists() else "MISSING", run_id=run_id)


def run_pipeline(args) -> int:
    run_id = start_pipeline_run("run_pipeline")
    steps = _default_steps(args)
    logger.info("Iniciando run_pipeline com etapas: %s", ", ".join(steps))

    try:
        for step in steps:
            command = _command_for_step(step, args)
            logger.info("Executando etapa %s", step)
            subprocess.run(command, cwd=PROJECT_ROOT, check=True)
            logger.info("Etapa %s concluida", step)

        if "alerts" not in steps:
            generate_operational_alerts()

        _record_standard_artifacts(run_id)
        finish_pipeline_run(run_id, "SUCCESS", errors_count=0)
        logger.info("run_pipeline concluido com sucesso.")
        return 0
    except subprocess.CalledProcessError as exc:
        finish_pipeline_run(run_id, "FAILED", errors_count=1, error_message=str(exc))
        logger.error("run_pipeline falhou na etapa: %s", exc)
        return 1
    except Exception as exc:
        finish_pipeline_run(run_id, "FAILED", errors_count=1, error_message=str(exc))
        logger.error("run_pipeline falhou: %s", exc)
        return 1


def main() -> None:
    raise SystemExit(run_pipeline(parse_args()))


if __name__ == "__main__":
    main()
