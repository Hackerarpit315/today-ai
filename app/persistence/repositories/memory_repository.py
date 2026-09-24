from __future__ import annotations

import json
import importlib

sqlite3 = importlib.import_module("sqlite3")
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from app.schemas.memory import MemoryRecord
from app.persistence.connection import connect
from app.persistence.database import get_database_path, initialize_database


class MemoryRepository(ABC):
    """Repository contract shared by in-memory and SQLite memory storage."""

    @abstractmethod
    def get(self, memory_id: UUID) -> MemoryRecord | None: ...

    @abstractmethod
    def save(self, record: MemoryRecord) -> None: ...

    @abstractmethod
    def all(self) -> list[MemoryRecord]: ...


def _json_value(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Memory value must be JSON-compatible for SQLite persistence") from exc


def _record_from_row(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        memory_id=UUID(row["memory_id"]),
        user_id=row["user_id"],
        memory_type=row["memory_type"],
        key=row["key"],
        value=json.loads(row["value_json"]),
        importance=row["importance"],
        sensitivity=row["sensitivity"],
        status=row["status"],
        source=row["source"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        version=row["version"],
    )


class SQLiteMemoryRepository(MemoryRepository):
    """SQLite implementation of the existing M12 repository contract."""

    def __init__(self, database_path=None) -> None:
        self.database_path = database_path or get_database_path()
        initialize_database_at(self.database_path)

    def get(self, memory_id: UUID) -> MemoryRecord | None:
        with connect(self.database_path) as db:
            row = db.execute(
                "SELECT * FROM memories WHERE memory_id = ?",
                (str(memory_id),),
            ).fetchone()
        return _record_from_row(row) if row else None

    def save(self, record: MemoryRecord) -> None:
        value_json = _json_value(deepcopy(record.value))
        with connect(self.database_path) as db:
            db.execute(
                """
                INSERT INTO memories (
                    memory_id, user_id, memory_type, key, value_json,
                    importance, sensitivity, status, source,
                    created_at, updated_at, expires_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    memory_type=excluded.memory_type,
                    key=excluded.key,
                    value_json=excluded.value_json,
                    importance=excluded.importance,
                    sensitivity=excluded.sensitivity,
                    status=excluded.status,
                    source=excluded.source,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    expires_at=excluded.expires_at,
                    version=excluded.version
                """,
                (
                    str(record.memory_id),
                    record.user_id,
                    record.memory_type.value,
                    record.key,
                    value_json,
                    record.importance.value,
                    record.sensitivity.value,
                    record.status.value,
                    record.source.value,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.expires_at.isoformat() if record.expires_at else None,
                    record.version,
                ),
            )
            db.commit()

    def all(self) -> list[MemoryRecord]:
        with connect(self.database_path) as db:
            rows = db.execute(
                "SELECT * FROM memories ORDER BY memory_id"
            ).fetchall()
        return [_record_from_row(row) for row in rows]


def initialize_database_at(path) -> None:
    from app.persistence.database import ensure_database_directory
    from app.persistence.migrations import apply_migrations

    ensure_database_directory(path)
    with connect(path) as db:
        apply_migrations(db)
