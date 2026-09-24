from __future__ import annotations

import json
import importlib

sqlite3 = importlib.import_module("sqlite3")
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.schemas.audit import AuditEvent
from app.persistence.connection import connect
from app.persistence.database import get_database_path
from app.persistence.repositories.memory_repository import initialize_database_at


from app.services.audit.repository import AuditRepository


def _uuid(value):
    return UUID(value) if value else None


def _event_from_row(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        event_id=UUID(row["event_id"]),
        request_id=UUID(row["request_id"]),
        timestamp=datetime.fromisoformat(row["timestamp"]),
        module=row["module"],
        event_type=row["event_type"],
        status=row["status"],
        severity=row["severity"],
        actor=row["actor"],
        action_id=_uuid(row["action_id"]),
        resource_type=row["resource_type"],
        resource_id=_uuid(row["resource_id"]),
        message=row["message"],
        metadata=json.loads(row["metadata_json"]),
        correlation_id=UUID(row["correlation_id"]),
        parent_event_id=_uuid(row["parent_event_id"]),
        user_id=_uuid(row["user_id"]),
        error_code=row["error_code"],
        reason=row["reason"],
        duration_ms=row["duration_ms"],
        ip_hash=row["ip_hash"],
        policy_version=row["policy_version"],
        integrity_hash=row["integrity_hash"],
    )


class SQLiteAuditRepository(AuditRepository):
    """Append-only application repository backed by SQLite."""

    def __init__(self, database_path=None) -> None:
        self.database_path = database_path or get_database_path()
        initialize_database_at(self.database_path)

    def create(self, event: AuditEvent) -> AuditEvent:
        with connect(self.database_path) as db:
            try:
                db.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, request_id, timestamp, module, event_type,
                        status, severity, actor, action_id, resource_type,
                        resource_id, message, metadata_json, correlation_id,
                        parent_event_id, user_id, error_code, reason,
                        duration_ms, ip_hash, policy_version, integrity_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(event.event_id), str(event.request_id), event.timestamp.isoformat(),
                        event.module.value, event.event_type.value, event.status.value,
                        event.severity.value, event.actor.value,
                        str(event.action_id) if event.action_id else None,
                        event.resource_type,
                        str(event.resource_id) if event.resource_id else None,
                        event.message,
                        json.dumps(event.metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                        str(event.correlation_id),
                        str(event.parent_event_id) if event.parent_event_id else None,
                        str(event.user_id) if event.user_id else None,
                        event.error_code, event.reason, event.duration_ms,
                        event.ip_hash, event.policy_version, event.integrity_hash,
                    ),
                )
                db.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError("Audit event already exists") from exc
        return event.model_copy(deep=True)

    def get_by_id(self, event_id: UUID) -> AuditEvent | None:
        with connect(self.database_path) as db:
            row = db.execute(
                "SELECT * FROM audit_events WHERE event_id = ?",
                (str(event_id),),
            ).fetchone()
        return _event_from_row(row) if row else None

    def all(self) -> list[AuditEvent]:
        with connect(self.database_path) as db:
            rows = db.execute(
                "SELECT * FROM audit_events ORDER BY timestamp, event_id"
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    @staticmethod
    def _ordered(events, ascending):
        return sorted(events, key=lambda e: (e.timestamp, e.event_id), reverse=not ascending)

    def list(self, events, *, ascending, offset, limit):
        ordered = self._ordered(events, ascending)
        return [e.model_copy(deep=True) for e in ordered[offset:offset + limit]]

    def search(self, events, query, *, ascending, offset, limit):
        q = query.casefold()
        matched = [
            e for e in events
            if q in e.message.casefold()
            or q in e.module.value.casefold()
            or q in e.event_type.value.casefold()
        ]
        return self.list(matched, ascending=ascending, offset=offset, limit=limit)

    def count(self, events):
        return len(events)
