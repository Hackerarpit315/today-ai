"""Strict Pydantic schemas for the standalone Planning Engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value.strip()


class VerifiedInformation(BaseModel):
    """A piece of already-verified information supplied to the planner."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=128)
    value: Any
    category: str = Field(default="fact", min_length=1, max_length=64)
    required: bool | None = None

    _validate_key = field_validator("key")( _non_empty)
    _validate_category = field_validator("category")(_non_empty)


class PlanningConstraint(BaseModel):
    """A constraint that the planner must preserve without inventing facts."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=128)
    value: Any

    _validate_key = field_validator("key")(_non_empty)


class AvailableStep(BaseModel):
    """An optional caller-supplied step template."""

    model_config = ConfigDict(extra="forbid")

    step_id: str | None = Field(default=None, min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(default="", max_length=2_000)
    required: bool = True
    depends_on: list[str] = Field(default_factory=list, max_length=50)

    _validate_title = field_validator("title")(_non_empty)


class PlanningRequest(BaseModel):
    """Input contract for deterministic plan generation."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    goal: str = Field(..., min_length=1, max_length=2_000)
    intent: str = Field(..., min_length=1, max_length=128)
    entities: dict[str, Any] = Field(default_factory=dict, max_length=100)
    time_reference: str | None = Field(default=None, max_length=300)
    verified_information: list[VerifiedInformation] = Field(default_factory=list, max_length=500)
    constraints: list[PlanningConstraint] = Field(default_factory=list, max_length=100)
    available_steps: list[AvailableStep] = Field(default_factory=list, max_length=100)

    _validate_goal = field_validator("goal")( _non_empty)
    _validate_intent = field_validator("intent")(_non_empty)


class PlanStep(BaseModel):
    """A single non-executing plan step."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(default="", max_length=2_000)
    order: int = Field(..., ge=1)
    required: bool
    depends_on: list[str] = Field(default_factory=list, max_length=50)
    status: str = Field(..., pattern=r"^(pending|blocked|ready)$")


class PlanningResponse(BaseModel):
    """Output contract for the standalone Planning Engine."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    goal: str
    plan_id: str = Field(..., min_length=1, max_length=128)
    steps: list[PlanStep] = Field(default_factory=list, max_length=200)
    total_steps: int = Field(..., ge=0)
    required_steps: int = Field(..., ge=0)
    planning_confidence: float = Field(..., ge=0.0, le=1.0)
    planning_status: str = Field(
        ..., pattern=r"^(planned|partially_planned|insufficient_information)$"
    )
