"""Schemas for the standalone Context Engine."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContextItem(BaseModel):
    """A piece of explicitly supplied context available to the engine."""

    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(..., min_length=1, max_length=128)
    content: str = Field(..., min_length=1, max_length=10_000)
    context_type: str = Field(..., min_length=1, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=50)


class ContextRequest(BaseModel):
    """Input contract for Context Engine selection."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    intent: str = Field(..., min_length=1, max_length=128)
    goal: str = Field(..., min_length=1, max_length=10_000)
    entities: dict[str, Any] = Field(default_factory=dict)
    time_reference: str | None = Field(default=None, max_length=128)
    confidence: float = Field(..., ge=0.0, le=1.0)
    available_context: list[ContextItem] = Field(default_factory=list, max_length=1_000)


class ContextResponse(BaseModel):
    """Output contract for Context Engine selection."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    relevant_context: list[ContextItem]
    context_used: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
