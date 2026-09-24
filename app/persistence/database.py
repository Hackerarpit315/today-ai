from __future__ import annotations

import os
from pathlib import Path


DEFAULT_DB_PATH = Path("data") / "today_ai.db"
DB_ENV_VAR = "TODAY_AI_DB_PATH"


def get_database_path() -> Path:
    """Return the configured SQLite path without creating files or directories."""
    configured = os.environ.get(DB_ENV_VAR)
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / DEFAULT_DB_PATH


def ensure_database_directory(path: Path) -> None:
    """Create only the parent directory needed by the configured database."""
    path.parent.mkdir(parents=True, exist_ok=True)


def initialize_database() -> Path:
    """Create the local database and required tables if they do not exist."""
    path = get_database_path()
    ensure_database_directory(path)

    from app.persistence.connection import connect
    from app.persistence.migrations import apply_migrations

    with connect(path) as connection:
        apply_migrations(connection)
    return path
