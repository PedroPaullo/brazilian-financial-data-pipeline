from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from monitoring import (
    finish_pipeline_run,
    refresh_source_freshness_from_processed_db,
    start_pipeline_run,
    upsert_source_freshness,
)


def main():
    database_file = PROJECT_ROOT / "data" / "operations" / "test_pipeline_operations.db"
    if database_file.exists():
        database_file.unlink()

    run_id = start_pipeline_run("test_module", database_file=database_file)
    finish_pipeline_run(
        run_id,
        "SUCCESS",
        records_input=10,
        records_output=8,
        warnings_count=1,
        errors_count=0,
        database_file=database_file,
    )
    upsert_source_freshness(
        source_name="TEST_SOURCE",
        dataset_name="test_dataset",
        last_available_date="2024-12-31",
        expected_frequency="daily",
        records_count=8,
        database_file=database_file,
    )
    refresh_source_freshness_from_processed_db(
        processed_db_file=PROJECT_ROOT / "data" / "processed" / "financial_data.db",
        operations_db_file=database_file,
    )

    with sqlite3.connect(database_file) as conn:
        run_row = conn.execute(
            "SELECT module_name, status, records_input, records_output FROM pipeline_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        freshness_row = conn.execute(
            """
            SELECT source_name, dataset_name, records_count
            FROM source_freshness
            WHERE source_name = 'TEST_SOURCE' AND dataset_name = 'test_dataset'
            """
        ).fetchone()
        freshness_count = conn.execute("SELECT COUNT(*) FROM source_freshness").fetchone()[0]

    assert run_row == ("test_module", "SUCCESS", 10, 8)
    assert freshness_row == ("TEST_SOURCE", "test_dataset", 8)
    assert freshness_count >= 11

    print("\nTeste do Modulo 5 concluido com sucesso.")


if __name__ == "__main__":
    main()
