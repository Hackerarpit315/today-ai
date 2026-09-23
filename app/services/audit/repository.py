from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.audit import AuditEvent


class AuditRepository(ABC):
    @abstractmethod
    def create(self, event: AuditEvent) -> AuditEvent: ...

    @abstractmethod
    def get_by_id(self, event_id: UUID) -> AuditEvent | None: ...

    @abstractmethod
    def list(self, events: list[AuditEvent], *, ascending: bool, offset: int, limit: int) -> list[AuditEvent]: ...

    @abstractmethod
    def search(self, events: list[AuditEvent], query: str, *, ascending: bool, offset: int, limit: int) -> list[AuditEvent]: ...

    @abstractmethod
    def count(self, events: list[AuditEvent]) -> int: ...
