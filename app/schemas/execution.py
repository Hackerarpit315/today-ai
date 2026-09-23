from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

ExecutionStatus = Literal[
    "executed",
    "success",
    "failed",
    "unknown",
    "blocked",
    "would_execute",
    "not_attempted",
    "unsupported",
    "not_configured",
]

VerificationStatus = Literal[
    "verified_success",
    "verified_failure",
    "unknown",
    "not_attempted",
    "blocked",
]

VerificationLevel = Literal["direct", "strong", "weak", "none"]


_FORBIDDEN_KEYS = {
    "command", "cmd", "shell", "powershell", "script", "code", "eval", "exec",
    "executable", "subprocess", "os_system", "private_key", "password", "otp",
    "token", "secret", "credential", "webhook_url",
}


def _validate_safe_data(value: Any) -> None:
    """Reject obviously executable/secret-bearing evidence structures."""
    if callable(value):
        raise ValueError("callable values are not allowed")
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ValueError(f"unsafe field: {key}")
            _validate_safe_data(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_safe_data(child)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: str
    source: str
    reference_id: str | None = None
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None

    @field_validator("evidence_type", "source", "status")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("evidence fields must not be blank")
        return value.strip()

    @field_validator("reference_id", "timestamp")
    @classmethod
    def optional_non_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("optional evidence strings must not be blank")
        return value

    @field_validator("data")
    @classmethod
    def safe_data(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_safe_data(value)
        return value


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    action_id: UUID
    action_type: ActionType
    action_category: ActionCategory
    execution_attempted: bool
    execution_status: ExecutionStatus
    adapter: str
    dry_run: bool = False
    external_side_effect: bool
    expected_outcome: str
    execution_result: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)

    @field_validator("adapter", "expected_outcome")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()

    @field_validator("execution_result")
    @classmethod
    def safe_execution_result(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_safe_data(value)
        return value


class ExecutionVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    action_id: UUID
    action_type: ActionType
    verification_status: VerificationStatus
    verification_level: VerificationLevel
    verified: bool
    external_action_verified: bool
    expected_outcome: str
    observed_outcome: str
    evidence_used: list[Evidence] = Field(default_factory=list)
    reason: str
    verification_id: UUID
    verified_reference: str | None = None
    policy_version: str = "execution-verification-v1"
