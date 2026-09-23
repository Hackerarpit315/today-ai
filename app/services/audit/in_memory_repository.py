from __future__ import annotations

from uuid import UUID

from app.schemas.audit import AuditEvent
from app.services.audit.repository import AuditRepository


class InMemoryAuditRepository(AuditRepository):
    def __init__(self) -> None:
        self._events: dict[UUID, AuditEvent] = {}

    def create(self, event: AuditEvent) -> AuditEvent:
        if event.event_id in self._events:
            raise ValueError("Audit event already exists")
        self._events[event.event_id] = event.model_copy(deep=True)
        return event.model_copy(deep=True)

    def get_by_id(self, event_id: UUID) -> AuditEvent | None:
        event = self._events.get(event_id)
        return event.model_copy(deep=True) if event else None

    @staticmethod
    def _ordered(events: list[AuditEvent], ascending: bool) -> list[AuditEvent]:
        return sorted(events, key=lambda e: (e.timestamp, e.event_id), reverse=not ascending)

    def list(self, events: list[AuditEvent], *, ascending: bool, offset: int, limit: int) -> list[AuditEvent]:
        ordered = self._ordered(events, ascending)
        return [e.model_copy(deep=True) for e in ordered[offset : offset + limit]]

    def search(self, events: list[AuditEvent], query: str, *, ascending: bool, offset: int, limit: int) -> list[AuditEvent]:
        q = query.casefold()
        matched = [e for e in events if q in e.message.casefold() or q in e.module.value.casefold() or q in e.event_type.value.casefold()]
        return self.list(matched, ascending=ascending, offset=offset, limit=limit)

    def count(self, events: list[AuditEvent]) -> int:
        return len(events)
