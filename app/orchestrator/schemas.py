"""Strict schemas for the first Today AI integration pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.context import ContextItem
from app.schemas.research import ResearchSource


class PipelineRequest(BaseModel):
    """Explicit input/context required by the M1 -> M8 pipeline."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    text: str = Field(..., min_length=0, max_length=10_000)
    current_datetime: datetime
    input_type: Literal["text"] = "text"
    available_context: list[ContextItem] = Field(default_factory=list, max_length=1_000)
    research_sources: list[ResearchSource] = Field(default_factory=list, max_length=1_000)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return value

    @field_validator("current_datetime")
    @classmethod
    def validate_current_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("current_datetime must include timezone information")
        return value


class StageError(BaseModel):
    """Safe, user-facing description of one failed pipeline stage."""

    model_config = ConfigDict(extra="forbid")

    stage: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=500)


class PipelineResult(BaseModel):
    """Structured result containing every completed stage and safe errors."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    status: Literal["success", "failed"]
    current_stage: str = Field(..., min_length=1, max_length=64)
    intent: Any | None = None
    context: Any | None = None
    research: Any | None = None
    verification: Any | None = None
    planning: Any | None = None
    priority: Any | None = None
    today: Any | None = None
    errors: list[StageError] = Field(default_factory=list, max_length=20)
    stage_results: dict[str, Any] = Field(default_factory=dict, max_length=20)
