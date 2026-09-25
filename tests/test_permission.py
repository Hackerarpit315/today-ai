from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.permission import (
    ApprovalStatus,
    PermissionDecisionType,
    PermissionRequest,
    PermissionState,
    Reversibility,
    RiskLevel,
)
from app.services.permission_service import evaluate

RID = "123e4567-e89b-12d3-a456-426614174000"


def req(**kw):
    data = {
        "request_id": RID,
        "action_id": "act-1",
        "action_type": "read",
        "description": "Read public information",
        "reversibility": "reversible",
    }
    data.update(kw)
    return PermissionRequest.model_validate(data)


def approval(
    action_id="act-1",
    action_type="send_email",
    target="alice@example.com",
    target_type="another_person",
    one_time=True,
    reusable=False,
    expires_at=None,
):
    return {
        "status": "approved",
        "action_id": action_id,
        "scope": {
            "scope_type": "action",
            "action_type": action_type,
            "target": target,
            "target_type": target_type,
            "one_time": one_time,
            "reusable": reusable,
        },
        "expires_at": expires_at,
    }


def test_valid_request():
    assert evaluate(req()).action_category.value == "read"


def test_uuid_preserved():
    assert evaluate(req()).request_id == UUID(RID)


def test_action_id_preserved():
    assert evaluate(req()).action_id == "act-1"


def test_empty_action_validation():
    with pytest.raises(ValidationError):
        req(action_id="")


def test_invalid_uuid():
    with pytest.raises(ValidationError):
        req(request_id="bad")


def test_extra_field_rejected():
    with pytest.raises(ValidationError):
        req(extra="x")


def test_low_risk_is_allowed_automatically():
    d = evaluate(req())
    assert d.decision is PermissionDecisionType.allow
    assert d.permission_state is PermissionState.not_required
    assert not d.permission_required
    assert d.risk_level is RiskLevel.low


def test_low_risk_policy_can_disable_auto_allow():
    d = evaluate(req(policy={"allow_low_risk_without_approval": False}))
    assert d.decision is PermissionDecisionType.require_approval
    assert d.permission_state is PermissionState.required


def test_medium_risk_requires_approval():
    d = evaluate(req(target_type="third_party_account"))
    assert d.risk_level is RiskLevel.medium
    assert d.decision is PermissionDecisionType.require_approval
    assert d.permission_required


def test_high_risk_requires_approval():
    d = evaluate(req(action_type="send_email"))
    assert d.risk_level is RiskLevel.high
    assert d.decision is PermissionDecisionType.require_approval
    assert d.permission_required


def test_communication_requires_approval():
    assert evaluate(req(action_type="send_message")).decision is PermissionDecisionType.require_approval


def test_form_submission_requires_approval():
    assert evaluate(req(action_type="submit_form")).decision is PermissionDecisionType.require_approval


def test_account_change_requires_approval():
    assert evaluate(req(action_type="account_change")).decision is PermissionDecisionType.require_approval


def test_privacy_sensitive_requires_approval():
    assert evaluate(req(action_type="privacy_sensitive")).decision is PermissionDecisionType.require_approval


def test_information_is_low_risk():
    d = evaluate(req(action_type="information"))
    assert d.action_category.value == "information"
    assert d.decision is PermissionDecisionType.allow


def test_navigation_is_low_risk():
    assert evaluate(req(action_type="navigation")).decision is PermissionDecisionType.allow


def test_draft_is_low_risk():
    assert evaluate(req(action_type="draft_email")).decision is PermissionDecisionType.allow


def test_unknown_action_fails_closed():
    d = evaluate(req(action_type="something_unrecognized"))
    assert d.action_category.value == "unknown"
    assert d.risk_level is RiskLevel.high
    assert d.decision is PermissionDecisionType.deny
    assert d.permission_state is PermissionState.denied


def test_deletion_is_denied():
    d = evaluate(req(action_type="delete_file"))
    assert d.risk_level is RiskLevel.critical
    assert d.decision is PermissionDecisionType.deny
    assert d.permission_state is PermissionState.denied


def test_financial_is_critical_and_denied():
    d = evaluate(req(action_type="payment"))
    assert d.risk_level is RiskLevel.critical
    assert d.decision is PermissionDecisionType.deny


def test_purchase_is_critical_and_denied():
    d = evaluate(req(action_type="purchase"))
    assert d.risk_level is RiskLevel.critical
    assert d.decision is PermissionDecisionType.deny


def test_irreversible_action_is_critical_and_denied():
    d = evaluate(req(action_type="read", reversibility="irreversible"))
    assert d.risk_level is RiskLevel.critical
    assert d.decision is PermissionDecisionType.deny


def test_external_side_effect_is_high_risk():
    d = evaluate(req(external_side_effect=True))
    assert d.risk_level is RiskLevel.high
    assert d.decision is PermissionDecisionType.require_approval


def test_no_approval_requires_approval():
    d = evaluate(req(action_type="send_email"))
    assert d.permission_state is PermissionState.required
    assert not d.approval_valid
    assert d.decision is PermissionDecisionType.require_approval


def test_valid_approval_allows_high_risk_action():
    d = evaluate(
        req(
            action_type="send_email",
            target="alice@example.com",
            target_type="another_person",
            approval=approval(),
        )
    )
    assert d.decision is PermissionDecisionType.allow
    assert d.permission_state is PermissionState.granted
    assert d.approval_valid


def test_scope_mismatch_requires_new_approval():
    d = evaluate(
        req(
            action_type="send_email",
            target="alice@example.com",
            approval=approval(target="bob@example.com"),
        )
    )
    assert d.decision is PermissionDecisionType.require_approval
    assert d.permission_state is PermissionState.invalid
    assert not d.approval_valid


def test_action_id_mismatch_requires_new_approval():
    d = evaluate(req(action_type="send_email", approval=approval(action_id="other")))
    assert d.decision is PermissionDecisionType.require_approval
    assert d.permission_state is PermissionState.invalid


def test_action_type_mismatch_requires_new_approval():
    d = evaluate(req(action_type="send_email", approval=approval(action_type="read")))
    assert d.decision is PermissionDecisionType.require_approval
    assert d.permission_state is PermissionState.invalid


def test_reusable_approval_can_allow_matching_action():
    d = evaluate(
        req(
            action_type="send_email",
            target="alice@example.com",
            target_type="another_person",
            approval=approval(one_time=False, reusable=True),
        )
    )
    assert d.decision is PermissionDecisionType.allow
    assert d.permission_state is PermissionState.granted


def test_expired_approval_requires_new_approval():
    now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    d = evaluate(
        req(
            action_type="send_email",
            target="alice@example.com",
            target_type="another_person",
            current_datetime=now,
            approval=approval(expires_at="2026-09-25T11:59:00+00:00"),
        )
    )
    assert d.decision is PermissionDecisionType.require_approval
    assert d.permission_state is PermissionState.expired


def test_denied_approval_is_terminal():
    d = evaluate(
        req(
            action_type="send_email",
            approval_status="denied",
            approval=approval(),
        )
    )
    assert d.decision is PermissionDecisionType.deny
    assert d.permission_state is PermissionState.denied
    assert not d.approval_valid


def test_critical_action_cannot_be_authorized_by_approval():
    d = evaluate(
        req(
            action_type="payment",
            target="bank",
            target_type="financial_institution",
            approval=approval(
                action_type="payment",
                target="bank",
                target_type="financial_institution",
            ),
        )
    )
    assert d.decision is PermissionDecisionType.deny
    assert d.permission_state is PermissionState.denied
    assert not d.approval_valid


def test_unknown_action_cannot_be_authorized_by_approval():
    d = evaluate(req(action_type="unknown_action", approval=approval(action_type="unknown_action")))
    assert d.decision is PermissionDecisionType.deny
    assert d.permission_state is PermissionState.denied


def test_request_id_is_preserved_for_allow():
    assert evaluate(req()).request_id == UUID(RID)


def test_request_id_is_preserved_for_approval_required():
    assert evaluate(req(action_type="send_email")).request_id == UUID(RID)


def test_request_id_is_preserved_for_deny():
    assert evaluate(req(action_type="delete_file")).request_id == UUID(RID)


def test_reason_is_always_present():
    for action_type in ("read", "send_email", "delete_file", "unknown_action"):
        assert evaluate(req(action_type=action_type)).reason


def test_decision_is_always_explicit():
    for action_type in ("read", "send_email", "delete_file", "unknown_action"):
        assert evaluate(req(action_type=action_type)).decision in {
            PermissionDecisionType.allow,
            PermissionDecisionType.require_approval,
            PermissionDecisionType.deny,
        }


def test_permission_decision_rejects_extra_fields():
    d = evaluate(req())
    with pytest.raises(ValidationError):
        d.model_copy(update={"extra": "x"}).model_validate(d.model_dump() | {"extra": "x"})


def test_permission_is_deterministic():
    request = req(action_type="send_email")
    assert evaluate(request).model_dump() == evaluate(request).model_dump()


def test_no_action_execution_contract():
    d = evaluate(req(action_type="send_email"))
    assert not hasattr(d, "execution_id")
    assert not hasattr(d, "executed")
    assert not hasattr(d, "result")


def test_policy_version_is_preserved():
    d = evaluate(req(policy={"policy_version": "permission-policy-test-v2"}))
    assert d.policy_version == "permission-policy-test-v2"


def test_malformed_scope_is_rejected():
    with pytest.raises(ValidationError):
        req(
            action_type="send_email",
            approval={
                "status": "approved",
                "scope": {
                    "scope_type": "",
                    "action_type": "send_email",
                    "one_time": True,
                    "reusable": False,
                },
            },
        )
