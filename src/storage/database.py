from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    backend: str
    database_url: str | None = None


def get_database_backend(value: str | None = None) -> str:
    return (value or os.getenv("DB_BACKEND") or os.getenv("DATABASE_BACKEND") or "sqlite").lower()


def get_database_url(value: str | None = None) -> str | None:
    return value or os.getenv("DATABASE_URL")


def is_postgres_enabled(backend: str | None = None) -> bool:
    return get_database_backend(backend) == "postgres"


def validate_database_config(backend: str | None = None, database_url: str | None = None) -> DatabaseConfig:
    resolved_backend = get_database_backend(backend)
    resolved_url = get_database_url(database_url)
    if resolved_backend not in {"sqlite", "postgres"}:
        raise ValueError("database_backend deve ser 'sqlite' ou 'postgres'.")
    if resolved_backend == "postgres" and not resolved_url:
        raise ValueError("PostgreSQL opcional exige DATABASE_URL ou --database-url.")
    return DatabaseConfig(backend=resolved_backend, database_url=resolved_url)


def create_engine_or_connection(backend: str | None = None, database_url: str | None = None):
    config = validate_database_config(backend, database_url)
    if config.backend == "sqlite":
        return None
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError("PostgreSQL opcional requer SQLAlchemy. Instale requirements-postgres.txt.") from exc
    return create_engine(config.database_url)
