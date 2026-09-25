"""Typed contracts for the provider-agnostic LLM layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMRequest(BaseModel):
    """Input supplied to an LLM provider without granting execution authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    user_input: str = Field(..., min_length=1, max_length=10_000)
    current_datetime: datetime
    context: dict[str, Any] | None = None

    @field_validator("user_input")
    @classmethod
    def validate_user_input(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_input must not be empty")
        return value

    @field_validator("current_datetime")
    @classmethod
    def validate_current_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("current_datetime must include timezone information")
        return value


class LLMResponse(BaseModel):
    """Structured intelligence output; it contains no executable action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    intent: str = Field(..., min_length=1, max_length=100)
    goal: str = Field(..., min_length=1, max_length=10_000)
    entities: dict[str, Any]
    time_reference: str | None = Field(default=None, max_length=100)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning_summary: str = Field(..., min_length=1, max_length=2_000)
