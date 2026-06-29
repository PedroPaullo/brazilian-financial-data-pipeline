from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import PROJECT_ROOT
from financial_calendar import is_brazil_business_day
from logger import get_logger

TIMEZONE_NAME = "America/Sao_Paulo"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)
JOB_ID = "brazilian_financial_pipeline"
SRC_DIR = Path(__file__).resolve().parent
PIPELINE_START_DATE = "2024-01-01"

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Agenda operacional do Brazilian Financial Data Pipeline.")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Executa uma rodada completa imediatamente antes de iniciar o loop do agendador.",
    )
    return parser.parse_args()


def _today() -> str:
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")


def _run_command(step_name: str, command: list[str]) -> None:
    logger.info("Iniciando etapa %s: %s", step_name, " ".join(command))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    logger.info("Etapa %s concluida.", step_name)


def run_full_pipeline(enforce_business_day: bool = True) -> None:
    execution_end_date = _today()

    if enforce_business_day and not is_brazil_business_day(execution_end_date):
        logger.info("Execucao pulada: %s nao e dia util financeiro.", execution_end_date)
        return

    logger.info("Execucao do pipeline iniciada para o periodo %s a %s.", PIPELINE_START_DATE, execution_end_date)
    collect_command = [
        sys.executable,
        str(SRC_DIR / "collect_data.py"),
        "--start-date",
        PIPELINE_START_DATE,
        "--end-date",
        execution_end_date,
    ]
    pipeline_command = [
        sys.executable,
        str(PROJECT_ROOT / "run_pipeline.py"),
        "--start",
        PIPELINE_START_DATE,
        "--end",
        execution_end_date,
        "--skip-collection",
        "--enable-manifest",
        "--reconcile",
    ]

    try:
        _run_command("collect_data", collect_command)
        _run_command("run_pipeline", pipeline_command)
    except subprocess.CalledProcessError as exc:
        logger.exception("Execucao do pipeline falhou com codigo %s.", exc.returncode)
        raise

    logger.info("Execucao do pipeline finalizada para o periodo %s a %s.", PIPELINE_START_DATE, execution_end_date)


def _next_business_fire_time(trigger: CronTrigger) -> datetime | None:
    previous_fire_time = None
    now = datetime.now(TIMEZONE)
    next_fire_time = trigger.get_next_fire_time(previous_fire_time, now)

    while next_fire_time is not None and not is_brazil_business_day(next_fire_time.date()):
        previous_fire_time = next_fire_time
        next_fire_time = trigger.get_next_fire_time(previous_fire_time, next_fire_time)

    return next_fire_time


def create_scheduler() -> tuple[BlockingScheduler, CronTrigger]:
    scheduler = BlockingScheduler(timezone=TIMEZONE_NAME)
    trigger = CronTrigger(day_of_week="mon-fri", hour=7, minute=0, timezone=TIMEZONE_NAME)

    scheduler.add_job(
        run_full_pipeline,
        trigger=trigger,
        id=JOB_ID,
        name="Brazilian Financial Data Pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler, trigger


def main() -> None:
    args = parse_args()
    scheduler, trigger = create_scheduler()
    next_run_time = _next_business_fire_time(trigger)

    logger.info("Scheduler iniciado em %s.", TIMEZONE_NAME)
    logger.info("Proxima execucao agendada: %s", next_run_time.isoformat() if next_run_time else "indisponivel")

    if args.run_now:
        run_full_pipeline(enforce_business_day=False)
        logger.info("Execucao imediata finalizada. Entrando no loop do agendador.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupcao recebida. Encerrando scheduler.")
        if scheduler.running:
            scheduler.shutdown(wait=False)
        logger.info("Scheduler encerrado.")


if __name__ == "__main__":
    main()
