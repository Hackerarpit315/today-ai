from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


RiskLevel = Literal["low", "medium", "high", "critical"]
PermissionDecision = Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"]
PermissionState = Literal[
    "not_required", "required", "granted", "denied", "expired", "invalid", "pending"
]
Reversibility = Literal["reversible", "partially_reversible", "irreversible", "unknown"]
ScopeType = Literal[
    "action", "action_type", "specific_target", "session", "one_time", "recurring"
]
ActionCategory = Literal[
    "information",
    "navigation",
    "read",
    "communication",
    "account_change",
    "form_preparation",
    "form_submission",
    "financial",
    "purchase",
    "deletion",
    "authentication",
    "privacy_sensitive",
    "external_side_effect",
    "unknown",
]

# The first group is executable in this module. The second group is accepted
# as known future action types so the service can return "unsupported" rather
# than treating a known future capability as an unknown input.
ActionType = Literal[
    "no_op",
    "dry_run",
    "create_local_note",
    "create_local_task",
    "prepare_email_draft",
    "prepare_message_draft",
    "open_url",
    "record_action",
    "n8n_dispatch_preview",
    "send_email",
    "send_message",
    "create_calendar_event",
    "telegram_message",
    "external_api_call",
]

_FORBIDDEN_PARAMETER_KEYS = {
    "command", "cmd", "shell", "powershell", "script", "code", "eval", "exec",
    "executable", "subprocess", "os_system", "private_key", "password", "otp",
    "token", "secret", "credential",
}


class PermissionScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: ScopeType
    action_type: str | None = None
    target: str | None = None
    target_type: str | None = None
    one_time: bool = False
    reusable: bool = False

    @field_validator("action_type", "target", "target_type")
    @classmethod
    def reject_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("scope strings must not be blank")
        return value


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    action_id: UUID
    action_type: ActionType
    action_category: ActionCategory
    risk_level: RiskLevel
    permission_required: bool
    permission_decision: PermissionDecision | None = None
    permission_state: PermissionState
    approval_valid: bool
    external_side_effect: bool
    reversibility: Reversibility
    permission_scope: PermissionScope | None = None
    requested_scope: PermissionScope | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False

    @field_validator("parameters")
    @classmethod
    def safe_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                for key, child in obj.items():
                    if str(key).lower() in _FORBIDDEN_PARAMETER_KEYS:
                        raise ValueError(f"unsafe parameter key: {key}")
                    walk(child)
            elif isinstance(obj, list):
                for child in obj:
                    walk(child)
        walk(value)
        return value


class ActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    action_id: UUID
    action_type: ActionType
    status: Literal[
        "blocked", "would_execute", "executed", "failed", "unsupported", "not_configured"
    ]
    execution_attempted: bool
    executed: bool
    blocked: bool
    result: dict[str, Any] = Field(default_factory=dict)
    reason: str
    adapter: str
    external_side_effect: bool
    reversibility: Reversibility
    execution_id: UUID
