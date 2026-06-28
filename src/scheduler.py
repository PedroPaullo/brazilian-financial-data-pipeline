from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import PROJECT_ROOT
from logger import get_logger

TIMEZONE = "America/Sao_Paulo"
SRC_DIR = Path(__file__).resolve().parent

PIPELINE_STEPS = (
    ("coleta", [sys.executable, str(SRC_DIR / "collect_data.py")]),
    ("validacao", [sys.executable, str(SRC_DIR / "validate_data.py")]),
    ("armazenamento", [sys.executable, str(SRC_DIR / "load_processed_data.py")]),
    ("relatorio", [sys.executable, str(SRC_DIR / "generate_report.py")]),
)

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Executa o pipeline imediatamente e encerra, sem iniciar o agendador.",
    )
    return parser.parse_args()


def run_pipeline():
    logger.info("Iniciando execucao completa do pipeline financeiro.")

    for step_name, command in PIPELINE_STEPS:
        logger.info("Iniciando etapa: %s", step_name)
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
        logger.info("Etapa concluida: %s", step_name)

    logger.info("Pipeline financeiro finalizado com sucesso.")


def create_scheduler():
    scheduler = BlockingScheduler(timezone=TIMEZONE)
    trigger = CronTrigger(day_of_week="mon-fri", hour=7, minute=0, timezone=TIMEZONE)

    scheduler.add_job(
        run_pipeline,
        trigger=trigger,
        id="brazilian_financial_pipeline",
        name="Brazilian Financial Data Pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    return scheduler


def main():
    args = parse_args()

    if args.run_now:
        run_pipeline()
        return

    scheduler = create_scheduler()
    logger.info(
        "Scheduler iniciado. O pipeline sera executado em dias uteis as 07:00 (%s).",
        TIMEZONE,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler encerrado.")


if __name__ == "__main__":
    main()
