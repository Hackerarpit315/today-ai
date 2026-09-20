"""Strict Pydantic contracts for the standalone Today Engine (Module 8)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value.strip()


class TodayTaskStatus(str, Enum):
    pending = "pending"
    blocked = "blocked"
    ready = "ready"
    overdue = "overdue"
    completed = "completed"


class PriorityLevel(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class UrgencyLevel(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TodayTask(BaseModel):
    """A caller-supplied prioritized plan task; no priority is recalculated."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    step_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(default="", max_length=2_000)
    priority_score: float = Field(..., ge=0.0, le=100.0)
    priority_level: PriorityLevel
    urgency: UrgencyLevel
    required: bool
    blocked: bool = False
    depends_on: list[str] = Field(default_factory=list, max_length=50)
    original_order: int = Field(..., ge=1)
    status: TodayTaskStatus = TodayTaskStatus.pending
    deadline: datetime | None = None
    is_today: bool = False
    scheduled_date: date | None = None

    _validate_step_id = field_validator("step_id")(_non_empty)
    _validate_title = field_validator("title")(_non_empty)
    _validate_description = field_validator("description")(_non_empty)

    @field_validator("depends_on")
    @classmethod
    def validate_dependencies(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
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


class TodayRequest(BaseModel):
    """Strict, deterministic input contract for daily task selection."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    request_id: UUID
    plan_id: str = Field(..., min_length=1, max_length=128)
    goal: str = Field(..., min_length=1, max_length=2_000)
    current_datetime: datetime
    tasks: list[TodayTask] | None = Field(default=None, max_length=200)
    prioritized_steps: list[TodayTask] | None = Field(default=None, max_length=200)
    constraints: list[str] | dict[str, str] | None = None

    _validate_plan_id = field_validator("plan_id")(_non_empty)
    _validate_goal = field_validator("goal")(_non_empty)

    @field_validator("current_datetime")
    @classmethod
    def validate_current_datetime_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("current_datetime must include timezone information")
        return value

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            return [_non_empty(item) for item in value]
        return {_non_empty(k): _non_empty(v) for k, v in value.items()}

    @model_validator(mode="after")
    def validate_task_source_and_graph(self) -> "TodayRequest":
        if self.tasks is not None and self.prioritized_steps is not None:
            raise ValueError("provide only one of tasks or prioritized_steps")
        supplied = self.tasks if self.tasks is not None else self.prioritized_steps
        if supplied is None:
            raise ValueError("tasks or prioritized_steps is required")

        ids = [task.step_id for task in supplied]
        if len(ids) != len(set(ids)):
            raise ValueError("step_id values must be unique")
        id_set = set(ids)
        for task in supplied:
            if task.step_id in task.depends_on:
                raise ValueError("a task cannot depend on itself")
            unknown = [dep for dep in task.depends_on if dep not in id_set]
            if unknown:
                raise ValueError(f"unknown dependency: {unknown[0]}")

        # Reject dependency cycles so ordering is always deterministic and valid.
        graph = {task.step_id: set(task.depends_on) for task in supplied}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("dependency graph contains a cycle")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
        return self

    @property
    def input_tasks(self) -> list[TodayTask]:
        """Return the normalized task list regardless of input field name."""
        return self.tasks if self.tasks is not None else self.prioritized_steps or []


class TodayTaskView(BaseModel):
    """Task representation returned in the Today view."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    step_id: str
    title: str
    description: str
    priority_score: float = Field(..., ge=0.0, le=100.0)
    priority_level: PriorityLevel
    urgency: UrgencyLevel
    required: bool
    status: TodayTaskStatus
    blocked: bool
    overdue: bool
    due_today: bool
    depends_on: list[str]
    original_order: int
    deadline: datetime | None = None


class TodaySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_today_tasks: int = Field(..., ge=0)
    ready_count: int = Field(..., ge=0)
    blocked_count: int = Field(..., ge=0)
    overdue_count: int = Field(..., ge=0)
    due_today_count: int = Field(..., ge=0)
    completed_count: int = Field(..., ge=0)
    high_priority_count: int = Field(..., ge=0)
    critical_priority_count: int = Field(..., ge=0)


class TodayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    request_id: UUID
    plan_id: str
    goal: str
    current_datetime: datetime
    today_tasks: list[TodayTaskView]
    completed_tasks: list[TodayTaskView] = Field(default_factory=list)
    total_today_tasks: int = Field(..., ge=0)
    ready_count: int = Field(..., ge=0)
    blocked_count: int = Field(..., ge=0)
    overdue_count: int = Field(..., ge=0)
    due_today_count: int = Field(..., ge=0)
    completed_count: int = Field(..., ge=0)
    high_priority_count: int = Field(..., ge=0)
    critical_priority_count: int = Field(..., ge=0)
    today_status: str = Field(..., pattern=r"^(planned|partially_planned|insufficient_information)$")
    summary: TodaySummary
    next_task: TodayTaskView | None = None
