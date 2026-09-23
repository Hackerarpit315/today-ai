from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModuleName(str, Enum):
    input = "input"
    intent = "intent"
    context = "context"
    research = "research"
    verification = "verification"
    planning = "planning"
    priority = "priority"
    today = "today"
    permission = "permission"
    action = "action"
    execution = "execution"
    memory = "memory"
    audit = "audit"
    security = "security"
    ui = "ui"


class EventType(str, Enum):
    request_received = "request_received"
    intent_created = "intent_created"
    context_selected = "context_selected"
    research_completed = "research_completed"
    verification_completed = "verification_completed"
    plan_created = "plan_created"
    priority_calculated = "priority_calculated"
    today_generated = "today_generated"
    permission_checked = "permission_checked"
    permission_granted = "permission_granted"
    permission_denied = "permission_denied"
    action_requested = "action_requested"
    action_blocked = "action_blocked"
    action_executed = "action_executed"
    execution_verified = "execution_verified"
    memory_stored = "memory_stored"
    memory_retrieved = "memory_retrieved"
    memory_updated = "memory_updated"
    memory_forgotten = "memory_forgotten"
    error = "error"
    warning = "warning"
    security_event = "security_event"


class AuditStatus(str, Enum):
    success = "success"
    failure = "failure"
    blocked = "blocked"
    pending = "pending"
    unknown = "unknown"
    skipped = "skipped"


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ActorType(str, Enum):
    system = "system"
    user = "user"
    module = "module"
    external_service = "external_service"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuditEvent(StrictModel):
    event_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    timestamp: datetime
    module: ModuleName
    event_type: EventType
    status: AuditStatus
    severity: Severity
    actor: ActorType
    action_id: UUID | None = None
    resource_type: str | None = Field(default=None, min_length=1, max_length=100)
    resource_id: UUID | None = None
    message: str = Field(min_length=1, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID
    parent_event_id: UUID | None = None
    user_id: UUID | None = None
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    ip_hash: str | None = Field(default=None, min_length=1, max_length=256)
    policy_version: str | None = Field(default=None, min_length=1, max_length=100)
    integrity_hash: str

    @field_validator("timestamp")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class AuditEventCreateRequest(StrictModel):
    request_id: UUID
    timestamp: datetime
    module: ModuleName
    event_type: EventType
    status: AuditStatus
    severity: Severity
    actor: ActorType
    action_id: UUID | None = None
    resource_type: str | None = Field(default=None, min_length=1, max_length=100)
    resource_id: UUID | None = None
    message: str = Field(min_length=1, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID
    parent_event_id: UUID | None = None
    user_id: UUID | None = None
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    ip_hash: str | None = Field(default=None, min_length=1, max_length=256)
    policy_version: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("timestamp")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class AuditEventRetrieveRequest(StrictModel):
    event_id: UUID


class AuditEventListRequest(StrictModel):
    request_id: UUID | None = None
    correlation_id: UUID | None = None
    module: ModuleName | None = None
    event_type: EventType | None = None
    status: AuditStatus | None = None
    severity: Severity | None = None
    actor: ActorType | None = None
    action_id: UUID | None = None
    resource_type: str | None = Field(default=None, min_length=1, max_length=100)
    resource_id: UUID | None = None
    user_id: UUID | None = None
    ascending: bool = True
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class AuditEventSearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    ascending: bool = True


class AuditEventResponse(StrictModel):
    success: bool
    status: Literal["created", "found", "not_found", "rejected"]
    event: AuditEvent | None = None
    event_id: UUID | None = None
    reason: str | None = None


class AuditEventListResponse(StrictModel):
    success: bool
    status: Literal["listed"]
    events: list[AuditEvent]
    total: int


class AuditIntegrityResponse(StrictModel):
    success: bool
    event_id: UUID
    valid: bool
    reason: str
