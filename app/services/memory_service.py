from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.persistence.repositories.memory_repository import MemoryRepository
from app.schemas.memory import (
    Importance,
    MemoryForgetRequest,
    MemoryListRequest,
    MemoryOperationResponse,
    MemoryRecord,
    MemoryRetrieveRequest,
    MemoryStatus,
    MemoryStoreRequest,
    MemoryType,
    MemoryUpdateRequest,
    Sensitivity,
)


_SECRET_NAME = re.compile(
    r"(?:^|[_\-\s])(?:password|passwd|otp|api[_-]?key|apikey|access[_-]?token|"
    r"refresh[_-]?token|secret|private[_-]?key)(?:$|[_\-\s])",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?:password|passwd|otp|api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|"
    r"private[_-]?key)\s*[:=]\s*\S+"
    r"|authorization\s*:\s*bearer\s+\S+"
    r"|\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"
    r"|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
    r"|\bsk-[A-Za-z0-9_-]{16,}\b",
    re.IGNORECASE,
)


class InMemoryMemoryRepository(MemoryRepository):
    """Deterministic storage abstraction used until a real database is introduced."""

    def __init__(self) -> None:
        self._records: dict[UUID, MemoryRecord] = {}

    def get(self, memory_id: UUID) -> MemoryRecord | None:
        record = self._records.get(memory_id)
        return deepcopy(record) if record else None

    def save(self, record: MemoryRecord) -> None:
        self._records[record.memory_id] = deepcopy(record)

    def all(self) -> list[MemoryRecord]:
        return [deepcopy(item) for item in self._records.values()]


class MemoryService:
    def __init__(self, repository: MemoryRepository | None = None) -> None:
        self.repository = repository or InMemoryMemoryRepository()

    @staticmethod
    def _secret_present(key: str, value: Any) -> bool:
        if _SECRET_NAME.search(key):
            return True
        return bool(_SECRET_VALUE.search(MemoryService._safe_text(value)))

    @staticmethod
    def _safe_text(value: Any) -> str:
        # Only used for pattern detection; never returned to callers.
        if isinstance(value, dict):
            return " ".join(
                f"{MemoryService._safe_text(k)} {MemoryService._safe_text(v)}"
                for k, v in value.items()
            )
        if isinstance(value, (list, tuple, set)):
            return " ".join(MemoryService._safe_text(v) for v in value)
        return str(value)

    @staticmethod
    def _expired(record: MemoryRecord, current_time: datetime) -> bool:
        return record.expires_at is not None and current_time >= record.expires_at

    @staticmethod
    def _priority(record: MemoryRecord) -> tuple[int, float, str]:
        rank = {
            Importance.critical: 4,
            Importance.high: 3,
            Importance.medium: 2,
            Importance.low: 1,
        }[record.importance]
        return (-rank, -record.updated_at.timestamp(), str(record.memory_id))

    @staticmethod
    def _generic_rejection(operation: str) -> MemoryOperationResponse:
        return MemoryOperationResponse(
            operation=operation,
            status="rejected",
            success=False,
            reason="Sensitive credential data cannot be stored",
        )

    def _active_candidates(
        self, request: MemoryStoreRequest
    ) -> list[MemoryRecord]:
        matches = []
        for record in self.repository.all():
            if record.user_id != request.user_id:
                continue
            if record.memory_type != request.memory_type or record.key != request.key:
                continue
            if record.status != MemoryStatus.active:
                continue
            if self._expired(record, request.current_time):
                continue
            matches.append(record)
        return matches

    def store(self, request: MemoryStoreRequest) -> MemoryOperationResponse:
        if self._secret_present(request.key, request.value):
            return self._generic_rejection("store")

        for record in self._active_candidates(request):
            if record.value == request.value:
                return MemoryOperationResponse(
                    operation="store",
                    status="duplicate",
                    success=True,
                    reason="Identical active memory already exists",
                    memory_id=record.memory_id,
                    memory=record,
                )
            return MemoryOperationResponse(
                operation="store",
                status="conflict",
                success=False,
                reason="Existing memory conflicts with the new value",
                memory_id=record.memory_id,
            )

        if request.expires_at is not None and request.expires_at <= request.current_time:
            status = MemoryStatus.expired
        else:
            status = MemoryStatus.active

        record = MemoryRecord(
            memory_id=uuid4(),
            user_id=request.user_id,
            memory_type=request.memory_type,
            key=request.key,
            value=deepcopy(request.value),
            importance=request.importance,
            sensitivity=request.sensitivity,
            status=status,
            source=request.source,
            created_at=request.current_time,
            updated_at=request.current_time,
            expires_at=request.expires_at,
            version=1,
        )
        self.repository.save(record)
        return MemoryOperationResponse(
            operation="store",
            status="stored",
            success=True,
            reason="Memory stored successfully",
            memory_id=record.memory_id,
            memory=record,
        )

    def retrieve(self, request: MemoryRetrieveRequest) -> MemoryOperationResponse:
        record = self.repository.get(request.memory_id)
        if record is None or record.user_id != request.user_id:
            return MemoryOperationResponse(
                operation="retrieve",
                status="not_found",
                success=False,
                reason="Memory not found",
                memory_id=request.memory_id,
            )
        if record.status == MemoryStatus.forgotten:
            return MemoryOperationResponse(
                operation="retrieve",
                status="not_found",
                success=False,
                reason="Memory not found",
                memory_id=request.memory_id,
            )
        if self._expired(record, request.current_time):
            record.status = MemoryStatus.expired
            self.repository.save(record)
            return MemoryOperationResponse(
                operation="retrieve",
                status="expired",
                success=False,
                reason="Memory is expired",
                memory_id=request.memory_id,
            )
        if record.status != MemoryStatus.active:
            return MemoryOperationResponse(
                operation="retrieve",
                status="not_found",
                success=False,
                reason="Memory is not active",
                memory_id=request.memory_id,
            )
        return MemoryOperationResponse(
            operation="retrieve",
            status="found",
            success=True,
            reason="Memory retrieved successfully",
            memory_id=record.memory_id,
            memory=record,
        )

    def list(self, request: MemoryListRequest) -> MemoryOperationResponse:
        records = []
        for record in self.repository.all():
            if record.user_id != request.user_id:
                continue
            if record.status == MemoryStatus.forgotten:
                continue
            if self._expired(record, request.current_time):
                record.status = MemoryStatus.expired
                self.repository.save(record)
            if record.status == MemoryStatus.expired:
                continue
            if request.status is not None and record.status != request.status:
                continue
            if request.memory_type is not None and record.memory_type != request.memory_type:
                continue
            if request.key is not None and record.key != request.key:
                continue
            if request.query is not None:
                q = request.query.casefold()
                haystack = f"{record.key} {self._safe_text(record.value)}".casefold()
                if q not in haystack:
                    continue
            records.append(record)

        records.sort(key=self._priority)
        return MemoryOperationResponse(
            operation="list",
            status="listed",
            success=True,
            reason="Memories listed successfully",
            memories=records,
        )

    def update(self, request: MemoryUpdateRequest) -> MemoryOperationResponse:
        if self._secret_present("", request.value):
            return self._generic_rejection("update")

        record = self.repository.get(request.memory_id)
        if record is None or record.user_id != request.user_id:
            return MemoryOperationResponse(
                operation="update",
                status="not_found",
                success=False,
                reason="Memory not found",
                memory_id=request.memory_id,
            )
        if record.status == MemoryStatus.forgotten:
            return MemoryOperationResponse(
                operation="update",
                status="not_found",
                success=False,
                reason="Memory not found",
                memory_id=request.memory_id,
            )
        if self._expired(record, request.current_time):
            record.status = MemoryStatus.expired
            self.repository.save(record)
            return MemoryOperationResponse(
                operation="update",
                status="expired",
                success=False,
                reason="Memory is expired",
                memory_id=request.memory_id,
            )
        if record.status != MemoryStatus.active:
            return MemoryOperationResponse(
                operation="update",
                status="not_found",
                success=False,
                reason="Memory is not active",
                memory_id=request.memory_id,
            )

        # Re-check conflicts if the new value would collide with another active record.
        for other in self.repository.all():
            if other.memory_id == record.memory_id:
                continue
            if (
                other.user_id == record.user_id
                and other.memory_type == record.memory_type
                and other.key == record.key
                and other.status == MemoryStatus.active
                and not self._expired(other, request.current_time)
            ):
                if other.value == request.value:
                    return MemoryOperationResponse(
                        operation="update",
                        status="duplicate",
                        success=True,
                        reason="Identical active memory already exists",
                        memory_id=other.memory_id,
                        memory=other,
                    )
                return MemoryOperationResponse(
                    operation="update",
                    status="conflict",
                    success=False,
                    reason="Updated value conflicts with an existing memory",
                    memory_id=other.memory_id,
                )

        record.value = deepcopy(request.value)
        if request.importance is not None:
            record.importance = request.importance
        if request.sensitivity is not None:
            record.sensitivity = request.sensitivity
        record.expires_at = request.expires_at
        record.updated_at = request.current_time
        record.version += 1
        if record.expires_at is not None and record.expires_at <= request.current_time:
            record.status = MemoryStatus.expired
        self.repository.save(record)

        return MemoryOperationResponse(
            operation="update",
            status="updated",
            success=True,
            reason="Memory updated successfully",
            memory_id=record.memory_id,
            memory=record,
        )

    def forget(self, request: MemoryForgetRequest) -> MemoryOperationResponse:
        record = self.repository.get(request.memory_id)
        if record is None or record.user_id != request.user_id:
            return MemoryOperationResponse(
                operation="forget",
                status="not_found",
                success=False,
                reason="Memory not found",
                memory_id=request.memory_id,
            )
        if record.status == MemoryStatus.forgotten:
            return MemoryOperationResponse(
                operation="forget",
                status="already_forgotten",
                success=True,
                reason="Memory is already forgotten",
                memory_id=record.memory_id,
            )
        record.status = MemoryStatus.forgotten
        record.updated_at = request.current_time
        record.version += 1
        self.repository.save(record)
        return MemoryOperationResponse(
            operation="forget",
            status="forgotten",
            success=True,
            reason="Memory marked as forgotten",
            memory_id=record.memory_id,
        )
