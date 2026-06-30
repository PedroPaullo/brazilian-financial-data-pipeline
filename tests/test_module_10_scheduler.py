from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import scheduler


def test_scheduler_import_does_not_start_blocking_loop():
    assert callable(scheduler.create_scheduler)
    assert callable(scheduler.run_full_pipeline)
    assert scheduler.JOB_ID == "brazilian_financial_pipeline"


def test_scheduler_help_shows_run_now_option():
    result = subprocess.run(
        [sys.executable, str(SRC_DIR / "scheduler.py"), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--run-now" in result.stdout


def test_next_business_fire_time_returns_future_business_datetime():
    trigger = CronTrigger(day_of_week="mon-fri", hour=7, minute=0, timezone=scheduler.TIMEZONE_NAME)

    next_fire_time = scheduler._next_business_fire_time(trigger)

    assert next_fire_time is not None
    assert next_fire_time.tzinfo is not None
    assert next_fire_time > datetime.now(scheduler.TIMEZONE)
    assert scheduler.is_brazil_business_day(next_fire_time.date())
