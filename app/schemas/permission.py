from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ApprovalStatus(str, Enum):
    not_provided = "not_provided"
    approved = "approved"
    denied = "denied"

class PermissionState(str, Enum):
    not_required = "not_required"
    required = "required"
    granted = "granted"
    denied = "denied"
    expired = "expired"
    invalid = "invalid"
    pending = "pending"

class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class Reversibility(str, Enum):
    reversible = "reversible"
    partially_reversible = "partially_reversible"
    irreversible = "irreversible"
    unknown = "unknown"

class ActionCategory(str, Enum):
    information = "information"
    navigation = "navigation"
    read = "read"
    draft = "draft"
    communication = "communication"
    account_change = "account_change"
    form_preparation = "form_preparation"
    form_submission = "form_submission"
    financial = "financial"
    purchase = "purchase"
    deletion = "deletion"
    authentication = "authentication"
    privacy_sensitive = "privacy_sensitive"
    external_side_effect = "external_side_effect"
    unknown = "unknown"

class PermissionScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_type: str = Field(min_length=1, max_length=64)
    action_type: str = Field(min_length=1, max_length=128)
    target: str | None = Field(default=None, min_length=1, max_length=500)
    target_type: str | None = Field(default=None, min_length=1, max_length=64)
    one_time: bool = True
    reusable: bool = False

    @field_validator("scope_type", "action_type", "target", "target_type", mode="before")
    @classmethod
    def strip_strings(cls, v: Any):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("must not be empty")
        return v

class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ApprovalStatus = ApprovalStatus.not_provided
    permission_id: str | None = Field(default=None, min_length=1, max_length=128)
    action_id: str | None = Field(default=None, min_length=1, max_length=128)
    scope: PermissionScope | None = None
    expires_at: datetime | None = None

    @field_validator("permission_id", "action_id", mode="before")
    @classmethod
    def strip_ids(cls, v: Any):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("must not be empty")
        return v

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, v):
        if v is not None and v.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        return v

class PermissionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_low_risk_without_approval: bool = False
    allow_medium_risk_without_approval: bool = False
    policy_version: str = Field(default="permission-policy-v1", min_length=1, max_length=64)

class PermissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    action_id: str = Field(min_length=1, max_length=128)
    action_type: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2000)
    target: str | None = Field(default=None, min_length=1, max_length=500)
    target_type: str | None = Field(default=None, min_length=1, max_length=64)
    external_side_effect: bool = False
    reversibility: Reversibility = Reversibility.unknown
    approval_status: ApprovalStatus = ApprovalStatus.not_provided
    approval: Approval | None = None
    permission_scope: PermissionScope | None = None
    policy: PermissionPolicy = Field(default_factory=PermissionPolicy)
    current_datetime: datetime | None = None

    @field_validator("action_id", "action_type", "description", "target", "target_type", mode="before")
    @classmethod
    def strip_text(cls, v: Any):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("must not be empty")
        return v

    @field_validator("current_datetime")
    @classmethod
    def aware_current_time(cls, v):
        if v is not None and v.tzinfo is None:
            raise ValueError("current_datetime must be timezone-aware")
        return v

class PermissionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    action_id: str
    action_type: str
    action_category: ActionCategory
    risk_level: RiskLevel
    permission_required: bool
    permission_state: PermissionState
    approval_valid: bool
    external_side_effect: bool
    reversibility: Reversibility
    permission_scope: PermissionScope | None
    reason: str
    policy_version: str
    decision_code: str
