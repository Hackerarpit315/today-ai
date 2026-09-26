from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


IntegrationActionType = Literal[
    "create_calendar_event",
]


class IntegrationActionRequest(BaseModel):
    """Request contract for an approved external integration action."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1, max_length=256)
    action_type: IntegrationActionType
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("user_id must not be empty")

        return value


class IntegrationActionResponse(BaseModel):
    """Stable response contract for an external integration action."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    action_type: str
    event_id: str | None = None
    status: str | None = None
    summary: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)