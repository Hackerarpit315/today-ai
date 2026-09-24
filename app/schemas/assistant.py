"""Public request/response schemas for the Today AI assistant API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.orchestrator.schemas import StageError


class AssistantRequest(BaseModel):
    """Strict public input for the application assistant endpoint."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1, max_length=10_000)
    current_datetime: datetime

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be empty")
        return value

    @field_validator("current_datetime")
    @classmethod
    def validate_current_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("current_datetime must include timezone information")
        return value


class AssistantResponse(BaseModel):
    """Stable public envelope around the existing orchestrator result."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    status: Literal["success", "failed"]
    current_stage: str
    pipeline: dict[str, Any]
    errors: list[StageError] = Field(default_factory=list)
