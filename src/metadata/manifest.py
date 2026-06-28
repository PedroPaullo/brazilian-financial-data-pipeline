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

from config import PROJECT_ROOT

MANIFEST_RUNS_DIR = PROJECT_ROOT / "data" / "manifests" / "runs"
MANIFEST_DATASETS_DIR = PROJECT_ROOT / "data" / "manifests" / "datasets"


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


def write_run_manifest(manifest: dict[str, Any], path: Path | None = None) -> Path:
    MANIFEST_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = path or manifest_path_for_run(str(manifest["run_id"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=4)
    return output_path


def load_run_manifest(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_latest_manifest(directory: Path = MANIFEST_RUNS_DIR) -> dict[str, Any] | None:
    if not directory.exists():
        return None
    manifests = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        return None
    return load_run_manifest(manifests[0])
