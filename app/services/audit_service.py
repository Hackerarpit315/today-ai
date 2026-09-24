from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from app.services.audit.in_memory_repository import InMemoryAuditRepository
from app.schemas.audit import (
    AuditEvent,
    AuditEventCreateRequest,
    AuditEventListRequest,
    AuditEventListResponse,
    AuditEventResponse,
    AuditEventSearchRequest,
    AuditEventRetrieveRequest,
    AuditIntegrityResponse,
)
from app.services.audit.repository import AuditRepository


class AuditService:
    _SECRET_PATTERNS = (
        re.compile(r"(?i)\b(?:password|passwd|otp|api[_-]?key|access[_-]?token|refresh[_-]?token|secret|private[_-]?key)\b\s*[:=]\s*[^\s,;}]+"),
        re.compile(r"(?i)\bauthorization\b\s*[:=]\s*bearer\s+[A-Za-z0-9._~+/=-]{8,}"),
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        re.compile(r"\b(?:sk|pk)_[A-Za-z0-9]{16,}\b"),
    )
    _MAX_METADATA_DEPTH = 6
    _MAX_METADATA_ITEMS = 100
    _MAX_METADATA_STRING = 4000

    def __init__(self, repository: AuditRepository | None = None) -> None:
        self.repository = repository or InMemoryAuditRepository()

    @classmethod
    def _contains_secret(cls, value: Any, depth: int = 0) -> bool:
        if depth > cls._MAX_METADATA_DEPTH:
            return True
        if isinstance(value, str):
            return any(pattern.search(value) for pattern in cls._SECRET_PATTERNS)
        if isinstance(value, dict):
            if len(value) > cls._MAX_METADATA_ITEMS:
                return True
            for key, item in value.items():
                key_text = str(key)
                if re.search(r"(?i)^(password|passwd|otp|api[_-]?key|access[_-]?token|refresh[_-]?token|secret|private[_-]?key)$", key_text):
                    return True
                if cls._contains_secret(item, depth + 1):
                    return True
            return False
        if isinstance(value, (list, tuple)):
            if len(value) > cls._MAX_METADATA_ITEMS:
                return True
            return any(cls._contains_secret(item, depth + 1) for item in value)
        if isinstance(value, (int, float, bool)) or value is None:
            return False
        return True

    @classmethod
    def _validate_metadata(cls, metadata: dict[str, Any]) -> None:
        try:
            encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("Metadata must be JSON-compatible") from exc
        if cls._contains_secret(metadata):
            raise ValueError("Sensitive credential data cannot be stored in audit records")
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("Metadata exceeds the maximum allowed size")
        def oversized(value: Any) -> bool:
            if isinstance(value, str):
                return len(value) > cls._MAX_METADATA_STRING
            if isinstance(value, dict):
                return any(oversized(k) or oversized(v) for k, v in value.items())
            if isinstance(value, (list, tuple)):
                return any(oversized(v) for v in value)
            return False
        if oversized(metadata):
            raise ValueError("Metadata contains an oversized string")

    @classmethod
    def _protected_dict(cls, event: AuditEvent) -> dict[str, Any]:
        data = event.model_dump(mode="json")
        data.pop("integrity_hash", None)
        return data

    @classmethod
    def calculate_integrity_hash(cls, event: AuditEvent) -> str:
        cls._validate_metadata(event.metadata)
        payload = json.dumps(cls._protected_dict(event), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def verify_integrity(cls, event: AuditEvent) -> bool:
        try:
            return cls.calculate_integrity_hash(event) == event.integrity_hash
        except (ValueError, TypeError):
            return False

    def create_event(self, request: AuditEventCreateRequest) -> AuditEventResponse:
        self._validate_metadata(request.metadata)
        # UUID is generated only as an identity; all business-time inputs remain explicit.
        provisional = AuditEvent(
            **request.model_dump(),
            integrity_hash="0" * 64,
        )
        integrity_hash = self.calculate_integrity_hash(provisional)
        event = provisional.model_copy(update={"integrity_hash": integrity_hash})
        created = self.repository.create(event)
        return AuditEventResponse(success=True, status="created", event=created, event_id=created.event_id, reason="Audit event created successfully")

    def retrieve_event(self, request: AuditEventRetrieveRequest) -> AuditEventResponse:
        event = self.repository.get_by_id(request.event_id)
        if event is None:
            return AuditEventResponse(success=False, status="not_found", event_id=request.event_id, reason="Audit event not found")
        return AuditEventResponse(success=True, status="found", event=event, event_id=event.event_id)

    @staticmethod
    def _matches(event: AuditEvent, request: AuditEventListRequest) -> bool:
        checks = (
            (request.request_id, event.request_id),
            (request.correlation_id, event.correlation_id),
            (request.module, event.module),
            (request.event_type, event.event_type),
            (request.status, event.status),
            (request.severity, event.severity),
            (request.actor, event.actor),
            (request.action_id, event.action_id),
            (request.resource_type, event.resource_type),
            (request.resource_id, event.resource_id),
            (request.user_id, event.user_id),
        )
        return all(expected is None or actual == expected for expected, actual in checks)

    def list_events(self, request: AuditEventListRequest) -> AuditEventListResponse:
        all_events = self.repository.all()
        filtered = [e for e in all_events if self._matches(e, request)]
        events = self.repository.list(filtered, ascending=request.ascending, offset=request.offset, limit=request.limit)
        return AuditEventListResponse(success=True, status="listed", events=events, total=len(filtered))

    def search_events(self, request: AuditEventSearchRequest) -> AuditEventListResponse:
        all_events = self.repository.all()
        events = self.repository.search(all_events, request.query, ascending=request.ascending, offset=request.offset, limit=request.limit)
        q = request.query.casefold()
        total = sum(1 for e in all_events if q in e.message.casefold() or q in e.module.value.casefold() or q in e.event_type.value.casefold())
        return AuditEventListResponse(success=True, status="listed", events=events, total=total)

    def count_events(self, request: AuditEventListRequest | None = None) -> int:
        events = self.repository.all()
        if request is not None:
            events = [e for e in events if self._matches(e, request)]
        return self.repository.count(events)

    def verify_event_integrity(self, event_id: UUID) -> AuditIntegrityResponse:
        event = self.repository.get_by_id(event_id)
        if event is None:
            return AuditIntegrityResponse(success=False, event_id=event_id, valid=False, reason="Audit event not found")
        valid = self.verify_integrity(event)
        return AuditIntegrityResponse(success=True, event_id=event_id, valid=valid, reason="Integrity verified" if valid else "Integrity verification failed")
