"""Strict Pydantic schemas for the standalone Priority Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value.strip()


class UrgencyLevel(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class StepStatus(str, Enum):
    pending = "pending"
    blocked = "blocked"
    ready = "ready"
    completed = "completed"


class PriorityStep(BaseModel):
    """Input plan step used only for priority calculation."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    step_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(default="", max_length=2_000)
    order: int = Field(..., ge=1)
    required: bool
    depends_on: list[str] = Field(default_factory=list, max_length=50)
    status: StepStatus = StepStatus.pending
    urgency: UrgencyLevel | None = None
    deadline: datetime | None = None
    importance: float | None = Field(default=None, ge=0.0, le=100.0)

    _validate_step_id = field_validator("step_id")(_non_empty)
    _validate_title = field_validator("title")(_non_empty)

    @field_validator("depends_on")
    @classmethod
    def validate_dependencies(cls, value: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for item in value:
            item = _non_empty(item)
            if item in seen:
                raise ValueError("depends_on must not contain duplicates")
            seen.add(item)
            cleaned.append(item)
        return cleaned

    @field_validator("deadline")
    @classmethod
    def validate_deadline_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("deadline must include timezone information")
        return value


class PriorityRequest(BaseModel):
    """Standalone input contract for deterministic priority calculation."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    request_id: UUID
    goal: str = Field(..., min_length=1, max_length=2_000)
    plan_id: str = Field(..., min_length=1, max_length=128)
    steps: list[PriorityStep] = Field(..., min_length=1, max_length=200)
    time_reference: str | None = Field(default=None, max_length=300)
    constraints: list[str] | dict[str, str] | None = None
    priority_reference_time: datetime | None = None

    _validate_goal = field_validator("goal")(_non_empty)
    _validate_plan_id = field_validator("plan_id")(_non_empty)

    @field_validator("time_reference")
    @classmethod
    def validate_time_reference(cls, value: str | None) -> str | None:
        return _non_empty(value) if value is not None else None

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            cleaned = [_non_empty(item) for item in value]
            return cleaned
        return {_non_empty(k): _non_empty(v) for k, v in value.items()}

    @field_validator("priority_reference_time")
    @classmethod
    def validate_reference_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("priority_reference_time must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_step_graph(self) -> "PriorityRequest":
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step_id values must be unique")
        id_set = set(ids)
        for step in self.steps:
            if step.step_id in step.depends_on:
                raise ValueError("a step cannot depend on itself")
            unknown = [dep for dep in step.depends_on if dep not in id_set]
            if unknown:
                raise ValueError(f"unknown dependency: {unknown[0]}")
        if self.priority_reference_time is not None:
            ref = self.priority_reference_time
            assert ref is not None
            for step in self.steps:
                if step.deadline is not None:
                    # Compare only after normalizing both aware datetimes to UTC.
                    if step.deadline.tzinfo is None:
                        raise ValueError("deadline must include timezone information")
                    _ = step.deadline.astimezone(timezone.utc) - ref.astimezone(timezone.utc)
        return self


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urgency_score: float = Field(..., ge=0.0, le=100.0)
    deadline_score: float = Field(..., ge=0.0, le=100.0)
    required_score: float = Field(..., ge=0.0, le=100.0)
    dependency_score: float = Field(..., ge=0.0, le=100.0)
    importance_score: float = Field(..., ge=0.0, le=100.0)
    final_score: float = Field(..., ge=0.0, le=100.0)


class PrioritizedStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    priority_score: float = Field(..., ge=0.0, le=100.0)
    priority_level: str = Field(..., pattern=r"^(critical|high|medium|low)$")
    urgency: UrgencyLevel | None = None
    required: bool
    blocked: bool
    depends_on: list[str] = Field(default_factory=list, max_length=50)
    original_order: int = Field(..., ge=1)
    score_breakdown: ScoreBreakdown


class PriorityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    plan_id: str
    goal: str
    prioritized_steps: list[PrioritizedStep]
    total_steps: int = Field(..., ge=0)
    critical_count: int = Field(..., ge=0)
    high_count: int = Field(..., ge=0)
    medium_count: int = Field(..., ge=0)
    low_count: int = Field(..., ge=0)
    priority_status: str = Field(
        ..., pattern=r"^(prioritized|partially_prioritized|insufficient_information)$"
    )
    priority_confidence: float = Field(..., ge=0.0, le=1.0)
