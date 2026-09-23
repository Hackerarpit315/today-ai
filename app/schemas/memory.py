from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class MemoryType(str, Enum):
    preference = "preference"
    profile = "profile"
    goal = "goal"
    project = "project"
    task_context = "task_context"
    instruction = "instruction"
    routine = "routine"
    fact = "fact"
    temporary = "temporary"
    unknown = "unknown"


class Importance(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Sensitivity(str, Enum):
    normal = "normal"
    sensitive = "sensitive"
    highly_sensitive = "highly_sensitive"


class MemoryStatus(str, Enum):
    active = "active"
    archived = "archived"
    expired = "expired"
    forgotten = "forgotten"


class MemorySource(str, Enum):
    user_explicit = "user_explicit"
    user_conversation = "user_conversation"
    system = "system"
    imported = "imported"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _nonempty(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


class MemoryRecord(StrictModel):
    memory_id: UUID
    user_id: StrictStr
    memory_type: MemoryType
    key: StrictStr
    value: Any
    importance: Importance
    sensitivity: Sensitivity
    status: MemoryStatus
    source: MemorySource
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    version: int = Field(ge=1)

    @field_validator("user_id", "key")
    @classmethod
    def validate_nonempty(cls, value: str) -> str:
        return _nonempty(value)

    @field_validator("created_at", "updated_at", "expires_at")
    @classmethod
    def validate_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value):
        return value


class MemoryStoreRequest(StrictModel):
    user_id: str
    memory_type: MemoryType
    key: str
    value: Any
    importance: Importance = Importance.medium
    sensitivity: Sensitivity = Sensitivity.normal
    source: MemorySource
    expires_at: Optional[datetime] = None
    current_time: datetime

    @field_validator("user_id", "key")
    @classmethod
    def validate_nonempty(cls, value: str) -> str:
        return _nonempty(value)

    @field_validator("current_time", "expires_at")
    @classmethod
    def validate_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class MemoryRetrieveRequest(StrictModel):
    user_id: StrictStr
    memory_id: UUID
    current_time: datetime

    @field_validator("user_id")
    @classmethod
    def validate_nonempty(cls, value: str) -> str:
        return _nonempty(value)

    @field_validator("current_time")
    @classmethod
    def validate_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class MemoryUpdateRequest(StrictModel):
    user_id: StrictStr
    memory_id: UUID
    value: Any
    current_time: datetime
    importance: Optional[Importance] = None
    sensitivity: Optional[Sensitivity] = None
    expires_at: Optional[datetime] = None

    @field_validator("user_id")
    @classmethod
    def validate_nonempty(cls, value: str) -> str:
        return _nonempty(value)

    @field_validator("current_time", "expires_at")
    @classmethod
    def validate_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class MemoryForgetRequest(StrictModel):
    user_id: StrictStr
    memory_id: UUID
    current_time: datetime

    @field_validator("user_id")
    @classmethod
    def validate_nonempty(cls, value: str) -> str:
        return _nonempty(value)

    @field_validator("current_time")
    @classmethod
    def validate_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class MemoryListRequest(StrictModel):
    user_id: StrictStr
    memory_type: Optional[MemoryType] = None
    key: Optional[str] = None
    status: Optional[MemoryStatus] = None
    query: Optional[str] = None
    current_time: datetime

    @field_validator("user_id")
    @classmethod
    def validate_nonempty(cls, value: str) -> str:
        return _nonempty(value)

    @field_validator("key", "query")
    @classmethod
    def validate_optional_text(cls, value):
        if value is None:
            return value
        return value.strip() or None

    @field_validator("current_time")
    @classmethod
    def validate_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class MemoryOperationResponse(StrictModel):
    operation: str
    status: str
    success: bool
    reason: str
    memory_id: Optional[UUID] = None
    memory: Optional[MemoryRecord] = None
    memories: list[MemoryRecord] = Field(default_factory=list)
