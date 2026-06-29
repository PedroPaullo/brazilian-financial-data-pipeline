from __future__ import annotations

import re
import sqlite3
from pathlib import Path

VIEWS_SQL_FILE = Path(__file__).resolve().parent / "views.sql"
CREATE_VIEW_PATTERN = re.compile(r"CREATE\s+VIEW\s+([A-Za-z0-9_]+)\s+AS", re.IGNORECASE)


def _view_statements(sql_text: str) -> list[tuple[str, str]]:
    statements: list[tuple[str, str]] = []
    for statement in [chunk.strip() for chunk in sql_text.split(";") if chunk.strip()]:
        match = CREATE_VIEW_PATTERN.search(statement)
        if not match:
            continue
        statements.append((match.group(1), statement))
    return statements


def load_intelligence_views(database_file: Path | str) -> dict[str, int]:
    database_path = Path(database_file)
    sql_text = VIEWS_SQL_FILE.read_text(encoding="utf-8")
    statements = _view_statements(sql_text)

    if not statements:
        raise ValueError(f"Nenhuma view encontrada em {VIEWS_SQL_FILE}")

    counts: dict[str, int] = {}
    with sqlite3.connect(database_path) as conn:
        for view_name, statement in statements:
            conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            conn.execute(statement)
            counts[view_name] = int(conn.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0])
        conn.commit()

    return counts
