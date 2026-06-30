from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from database import postgres_loader


def test_load_to_postgres_function_exists_with_expected_signature():
    signature = inspect.signature(postgres_loader.load_to_postgres)

    assert list(signature.parameters) == ["database_url", "sqlite_database_file", "schema_file"]
    assert signature.parameters["database_url"].default is inspect._empty
    assert signature.parameters["sqlite_database_file"].default == postgres_loader.PROCESSED_DB_FILE
    assert signature.parameters["schema_file"].default == postgres_loader.POSTGRES_SCHEMA_FILE


def test_default_postgres_connection_string_is_parseable():
    parsed = urlparse(postgres_loader.DEFAULT_POSTGRES_URL)

    assert parsed.scheme == "postgresql"
    assert parsed.username == "pipeline_user"
    assert parsed.password == "pipeline_pass"
    assert parsed.hostname == "localhost"
    assert parsed.port == 5432
    assert parsed.path == "/financial_pipeline"


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL") or os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Real PostgreSQL validation requires DATABASE_URL and RUN_POSTGRES_INTEGRATION=1.",
)
def test_load_to_postgres_real_connection_opt_in():
    sqlite_database_file = Path(os.getenv("SQLITE_DATABASE_FILE", PROJECT_ROOT / "data" / "processed" / "financial_data.db"))
    if not sqlite_database_file.exists():
        pytest.skip(f"SQLite database not found: {sqlite_database_file}")

    counts = postgres_loader.load_to_postgres(
        os.environ["DATABASE_URL"],
        sqlite_database_file=sqlite_database_file,
    )

    assert counts["fact_bcb_series_values"] > 0
    assert counts["fact_b3_stock_prices"] > 0
