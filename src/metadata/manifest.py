from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from artifact_retention import prune_artifacts, today_stamp
from config import PROJECT_ROOT

MANIFEST_DIR = PROJECT_ROOT / "data" / "manifests"
MANIFEST_LATEST_FILE = MANIFEST_DIR / "latest.json"
MANIFEST_DAILY_DIR = MANIFEST_DIR / "daily"
MANIFEST_RUNS_DIR = MANIFEST_DIR / "runs"
MANIFEST_DATASETS_DIR = MANIFEST_DIR / "datasets"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_run_id(prefix: str = "pipeline") -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{prefix}_{uuid.uuid4().hex[:8]}"


def get_git_commit(project_root: Path = PROJECT_ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def calculate_file_checksum(path: Path) -> str | None:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def calculate_dataframe_checksum(df: pd.DataFrame) -> str:
    if df.empty:
        return hashlib.sha256(b"empty").hexdigest()
    csv_text = df.sort_index(axis=1).to_csv(index=False)
    return hashlib.sha256(csv_text.encode("utf-8")).hexdigest()


def calculate_schema_hash(df: pd.DataFrame) -> str:
    schema = "|".join(f"{column}:{dtype}" for column, dtype in df.dtypes.astype(str).items())
    return hashlib.sha256(schema.encode("utf-8")).hexdigest()


def build_file_metadata(path: Path) -> dict[str, Any]:
    path = Path(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "file_size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
        "checksum": calculate_file_checksum(path),
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S") if path.exists() and path.is_file() else None,
    }


def create_run_manifest(
    run_id: str,
    command: str,
    parameters: dict[str, Any],
    database_backend: str = "sqlite",
    sources_enabled: list[str] | None = None,
    sources_skipped: list[str] | None = None,
    date_range: dict[str, str] | None = None,
    input_files: list[Path] | None = None,
    output_files: list[Path] | None = None,
    datasets_created: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    status: str = "RUNNING",
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "started_at": started_at or now_text(),
        "finished_at": finished_at,
        "status": status,
        "git_commit": get_git_commit(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "command": command,
        "parameters": parameters,
        "database_backend": database_backend,
        "sources_enabled": sources_enabled or [],
        "sources_skipped": sources_skipped or [],
        "datasets_created": datasets_created or [],
        "row_counts": {item.get("dataset_name"): item.get("row_count") for item in datasets_created or []},
        "date_range": date_range or {},
        "input_files": [build_file_metadata(path) for path in input_files or []],
        "output_files": [build_file_metadata(path) for path in output_files or []],
        "checksums": {},
        "warnings": warnings or [],
        "errors": errors or [],
    }


def manifest_path_for_run(run_id: str, directory: Path = MANIFEST_RUNS_DIR) -> Path:
    return directory / f"{run_id}.json"


def manifest_path_for_day(stamp: str | None = None, directory: Path = MANIFEST_DAILY_DIR) -> Path:
    return directory / f"{stamp or today_stamp()}.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=4)


def write_run_manifest(
    manifest: dict[str, Any],
    path: Path | None = None,
    archive_runs: bool = False,
    retention_days: int | None = None,
    base_dir: Path | None = None,
) -> Path:
    if path is not None:
        _write_json(path, manifest)
        return path

    manifest_dir = Path(base_dir) if base_dir else MANIFEST_DIR
    latest_path = manifest_dir / "latest.json"
    daily_dir = manifest_dir / "daily"
    runs_dir = manifest_dir / "runs"
    datasets_dir = manifest_dir / "datasets"

    for directory in [daily_dir, datasets_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    _write_json(latest_path, manifest)
    _write_json(manifest_path_for_day(directory=daily_dir), manifest)

    if archive_runs:
        _write_json(manifest_path_for_run(str(manifest["run_id"]), directory=runs_dir), manifest)

    prune_artifacts([daily_dir, runs_dir], retention_days=retention_days)
    return latest_path


def load_run_manifest(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_latest_manifest(directory: Path = MANIFEST_DIR) -> dict[str, Any] | None:
    latest_path = Path(directory) / "latest.json"
    if latest_path.exists():
        return load_run_manifest(latest_path)
    runs_directory = Path(directory) / "runs" if Path(directory).name != "runs" else Path(directory)
    if not runs_directory.exists():
        return None
    manifests = sorted(runs_directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        return None
    return load_run_manifest(manifests[0])
