from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

POLICY_VERSION = "1.0"

class SecurityCheckType(str, Enum):
    secret_detection = "secret_detection"
    credential_detection = "credential_detection"
    url_validation = "url_validation"
    input_validation = "input_validation"
    command_injection_detection = "command_injection_detection"
    script_injection_detection = "script_injection_detection"
    path_traversal_detection = "path_traversal_detection"
    suspicious_payload_detection = "suspicious_payload_detection"
    data_exposure_detection = "data_exposure_detection"
    action_safety_check = "action_safety_check"
    permission_policy_check = "permission_policy_check"
    request_integrity_check = "request_integrity_check"

class SecurityDecisionType(str, Enum):
    allow = "allow"
    block = "block"
    review_required = "review_required"
    sanitize = "sanitize"

class RiskLevel(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class ThreatType(str, Enum):
    none = "none"
    secret_exposure = "secret_exposure"
    credential_exposure = "credential_exposure"
    malicious_url = "malicious_url"
    command_injection = "command_injection"
    script_injection = "script_injection"
    path_traversal = "path_traversal"
    oversized_payload = "oversized_payload"
    suspicious_payload = "suspicious_payload"
    data_exposure = "data_exposure"
    unsafe_action = "unsafe_action"
    invalid_request = "invalid_request"
    unknown_threat = "unknown_threat"

class ActionCategory(str, Enum):
    information = "information"
    navigation = "navigation"
    read = "read"
    draft = "draft"
    communication = "communication"
    account_change = "account_change"
    form_submission = "form_submission"
    financial = "financial"
    purchase = "purchase"
    deletion = "deletion"
    authentication = "authentication"
    privacy_sensitive = "privacy_sensitive"
    external_side_effect = "external_side_effect"
    unknown = "unknown"

class SecurityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    check_types: list[SecurityCheckType] = Field(default_factory=lambda: [SecurityCheckType.secret_detection, SecurityCheckType.credential_detection, SecurityCheckType.input_validation, SecurityCheckType.command_injection_detection, SecurityCheckType.script_injection_detection, SecurityCheckType.path_traversal_detection, SecurityCheckType.suspicious_payload_detection, SecurityCheckType.data_exposure_detection, SecurityCheckType.request_integrity_check])
    policy_version: str = POLICY_VERSION
    sanitize: bool = False

    @field_validator("content")
    @classmethod
    def content_string(cls, v: str) -> str:
        return v

    @field_validator("policy_version")
    @classmethod
    def policy(cls, v: str) -> str:
        if v != POLICY_VERSION:
            raise ValueError("unsupported policy version")
        return v

class URLSecurityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    url: str
    policy_version: str = POLICY_VERSION

    @field_validator("policy_version")
    @classmethod
    def policy(cls, v: str) -> str:
        if v != POLICY_VERSION:
            raise ValueError("unsupported policy version")
        return v

class ActionSecurityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    action_id: UUID | None = None
    action_category: ActionCategory
    content: str = ""
    permission_granted: bool = False
    permission_decision: Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"] | None = None
    credential_handling: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    policy_version: str = POLICY_VERSION

    @field_validator("policy_version")
    @classmethod
    def policy(cls, v: str) -> str:
        if v != POLICY_VERSION:
            raise ValueError("unsupported policy version")
        return v

class SecurityPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    permission_granted: bool
    permission_decision: Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"] | None = None
    action_category: ActionCategory
    credential_handling: bool = False
    policy_version: str = POLICY_VERSION

    @field_validator("policy_version")
    @classmethod
    def policy(cls, v: str) -> str:
        if v != POLICY_VERSION:
            raise ValueError("unsupported policy version")
        return v

class SecurityCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    check_type: SecurityCheckType
    passed: bool
    risk_level: RiskLevel
    threat_type: ThreatType
    reason: str

class SecurityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    security_check_id: UUID
    request_id: UUID
    decision: SecurityDecisionType
    risk_level: RiskLevel
    threat_detected: bool
    threat_types: list[ThreatType]
    blocked: bool
    reason: str
    policy_version: str
    checks_performed: list[SecurityCheckType]
    results: list[SecurityCheckResult] = Field(default_factory=list)

    @field_validator("policy_version")
    @classmethod
    def policy(cls, v: str) -> str:
        if v != POLICY_VERSION:
            raise ValueError("unsupported policy version")
        return v
