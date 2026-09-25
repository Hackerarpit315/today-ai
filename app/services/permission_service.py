from __future__ import annotations
from datetime import datetime, timezone
from app.schemas.permission import (
    ActionCategory, ApprovalStatus, PermissionDecision, PermissionDecisionType, PermissionRequest,
    PermissionState, Reversibility, RiskLevel,
)

ALIASES = {
    "info": ActionCategory.information, "information": ActionCategory.information,
    "read": ActionCategory.read, "navigation": ActionCategory.navigation,
    "navigate": ActionCategory.navigation, "draft": ActionCategory.draft,
    "draft_email": ActionCategory.draft, "draft_message": ActionCategory.draft,
    "send_email": ActionCategory.communication, "send_message": ActionCategory.communication,
    "send_sms": ActionCategory.communication, "send_whatsapp": ActionCategory.communication,
    "post_publicly": ActionCategory.communication, "communication": ActionCategory.communication,
    "account_change": ActionCategory.account_change, "change_account": ActionCategory.account_change,
    "form_preparation": ActionCategory.form_preparation, "fill_form": ActionCategory.form_preparation,
    "form_submission": ActionCategory.form_submission, "submit_form": ActionCategory.form_submission,
    "financial": ActionCategory.financial, "payment": ActionCategory.financial, "transfer": ActionCategory.financial,
    "purchase": ActionCategory.purchase, "buy": ActionCategory.purchase,
    "deletion": ActionCategory.deletion, "delete": ActionCategory.deletion, "delete_file": ActionCategory.deletion,
    "authentication": ActionCategory.authentication, "login": ActionCategory.authentication,
    "privacy_sensitive": ActionCategory.privacy_sensitive,
    "external_side_effect": ActionCategory.external_side_effect,
}


def classify(action_type: str) -> ActionCategory:
    return ALIASES.get(action_type.strip().lower(), ActionCategory.unknown)


def risk_for(category: ActionCategory, req: PermissionRequest) -> RiskLevel:
    if category in {ActionCategory.financial, ActionCategory.purchase, ActionCategory.deletion}:
        return RiskLevel.critical
    if category is ActionCategory.unknown:
        return RiskLevel.high
    if req.reversibility is Reversibility.irreversible:
        return RiskLevel.critical
    if category in {
        ActionCategory.communication, ActionCategory.account_change,
        ActionCategory.form_submission, ActionCategory.authentication,
        ActionCategory.privacy_sensitive, ActionCategory.external_side_effect,
    }:
        return RiskLevel.high
    if req.external_side_effect:
        return RiskLevel.high
    if req.target_type in {"third_party_account", "financial_institution", "external_service"}:
        return RiskLevel.medium
    if category in {ActionCategory.form_preparation}:
        return RiskLevel.low if req.reversibility is not Reversibility.unknown else RiskLevel.medium
    if category in {ActionCategory.information, ActionCategory.navigation, ActionCategory.read, ActionCategory.draft}:
        return RiskLevel.low
    return RiskLevel.high


def _scope_matches(req: PermissionRequest) -> bool:
    approval = req.approval
    scope = approval.scope if approval else None
    if not approval or not scope or approval.status is not ApprovalStatus.approved:
        return False
    if scope.action_type.lower() != req.action_type.lower():
        return False
    if scope.target is not None and scope.target != req.target:
        return False
    if scope.target_type is not None and scope.target_type != req.target_type:
        return False
    if scope.one_time and approval.action_id != req.action_id:
        return False
    if not scope.one_time and not scope.reusable:
        return False
    if approval.expires_at is not None:
        if req.current_datetime is None:
            return False
        if approval.expires_at <= req.current_datetime:
            return False
    return True


def evaluate(req: PermissionRequest) -> PermissionDecision:
    """Evaluate permission deterministically without executing the requested action."""
    category = classify(req.action_type)
    risk = risk_for(category, req)
    approval = req.approval
    scope = req.permission_scope or (approval.scope if approval else None)

    base = dict(
        request_id=req.request_id,
        action_id=req.action_id,
        action_type=req.action_type,
        action_category=category,
        risk_level=risk,
        permission_required=True,
        permission_state=PermissionState.required,
        approval_valid=False,
        external_side_effect=req.external_side_effect,
        reversibility=req.reversibility,
        permission_scope=scope,
        policy_version=req.policy.policy_version,
    )

    def decision_result(decision: PermissionDecisionType, **overrides) -> PermissionDecision:
        data = base.copy()
        data.update(overrides)
        data["decision"] = decision
        return PermissionDecision(**data)

    if req.approval_status is ApprovalStatus.denied or (approval and approval.status is ApprovalStatus.denied):
        return decision_result(
            PermissionDecisionType.deny,
            permission_state=PermissionState.denied,
            reason="User approval was denied; the action cannot proceed.",
            decision_code="APPROVAL_DENIED",
        )

    if category is ActionCategory.unknown:
        return decision_result(
            PermissionDecisionType.deny,
            permission_state=PermissionState.denied,
            risk_level=RiskLevel.high,
            reason="Unknown action types are denied by the fail-closed permission policy.",
            decision_code="UNKNOWN_ACTION_DENIED",
        )

    if risk is RiskLevel.critical:
        return decision_result(
            PermissionDecisionType.deny,
            permission_state=PermissionState.denied,
            reason="Critical or destructive actions are denied by the permission policy.",
            decision_code="CRITICAL_ACTION_DENIED",
        )

    if risk is RiskLevel.low and req.policy.allow_low_risk_without_approval:
        return decision_result(
            PermissionDecisionType.allow,
            permission_required=False,
            permission_state=PermissionState.not_required,
            reason="The action is low risk and is allowed automatically by policy.",
            decision_code="LOW_RISK_ALLOWED",
        )

    if approval and approval.status is ApprovalStatus.approved:
        if _scope_matches(req):
            return decision_result(
                PermissionDecisionType.allow,
                permission_state=PermissionState.granted,
                approval_valid=True,
                reason="Explicit approval is valid and its scope matches this action.",
                decision_code="APPROVAL_GRANTED",
            )
        if approval.expires_at is not None and req.current_datetime is not None and approval.expires_at <= req.current_datetime:
            return decision_result(
                PermissionDecisionType.require_approval,
                permission_state=PermissionState.expired,
                reason="The supplied approval has expired and cannot authorize this action.",
                decision_code="APPROVAL_EXPIRED",
            )
        return decision_result(
            PermissionDecisionType.require_approval,
            permission_state=PermissionState.invalid,
            reason="Approval was supplied, but its scope does not match this action.",
            decision_code="APPROVAL_SCOPE_MISMATCH",
        )

    return decision_result(
        PermissionDecisionType.require_approval,
        reason="Explicit user approval is required for this action.",
        decision_code="APPROVAL_REQUIRED",
    )
