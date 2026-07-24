from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from uvicorn import Config, Server

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = PROJECT_ROOT / "data" / "processed" / "financial_data.db"


def run_initial_pipeline() -> None:
    if DATABASE_FILE.exists():
        return
    start_date = os.getenv("PIPELINE_START_DATE", "2024-01-01")
    command = [sys.executable, str(PROJECT_ROOT / "collect_data.py"), "--start-date", start_date, "--end-date", time.strftime("%Y-%m-%d")]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    subprocess.run([sys.executable, str(PROJECT_ROOT / "run_pipeline.py"), "--skip-collection", "--enable-manifest", "--reconcile"], cwd=PROJECT_ROOT, check=True)


def start_scheduler() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(PROJECT_ROOT / "src" / "scheduler.py")], cwd=PROJECT_ROOT)


def main() -> None:
    run_initial_pipeline()
    scheduler = start_scheduler()
    try:
        config = Config("src.api:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info")
        Server(config).run()
    finally:
        scheduler.terminate()


if __name__ == "__main__":
    main()
