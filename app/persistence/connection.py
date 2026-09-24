from __future__ import annotations

import importlib

sqlite3 = importlib.import_module("sqlite3")
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with safe row access and foreign keys enabled."""
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
