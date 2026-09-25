from uuid import UUID
import pytest
from pydantic import ValidationError
from app.schemas.permission import PermissionRequest, PermissionState, RiskLevel, Reversibility, ApprovalStatus
from app.services.permission_service import evaluate

RID = "123e4567-e89b-12d3-a456-426614174000"

def req(**kw):
    data = {"request_id": RID, "action_id": "act-1", "action_type": "read", "description": "Read public information", "reversibility": "reversible"}
    data.update(kw)
    return PermissionRequest.model_validate(data)

def approval(action_id="act-1", action_type="send_email", target="alice@example.com", target_type="another_person", one_time=True, reusable=False):
    return {"status":"approved", "action_id":action_id, "scope":{"scope_type":"action","action_type":action_type,"target":target,"target_type":target_type,"one_time":one_time,"reusable":reusable}}

def test_valid_request(): assert evaluate(req()).action_category.value == "read"
def test_default_decision_requires_approval(): assert evaluate(req()).decision == "REQUIRE_APPROVAL"
def test_uuid_preserved(): assert evaluate(req()).request_id == UUID(RID)
def test_action_id_preserved(): assert evaluate(req()).action_id == "act-1"
def test_empty_action_validation():
    with pytest.raises(ValidationError): req(action_id="")
def test_invalid_uuid():
    with pytest.raises(ValidationError): req(request_id="bad")
def test_extra_field_rejected():
    with pytest.raises(ValidationError): req(extra="x")
def test_low_risk(): assert evaluate(req()).risk_level is RiskLevel.low
def test_medium_risk(): assert evaluate(req(target_type="third_party_account")).risk_level is RiskLevel.medium
def test_high_risk(): assert evaluate(req(action_type="send_email")).risk_level is RiskLevel.high
def test_critical_risk(): assert evaluate(req(action_type="payment")).risk_level is RiskLevel.critical
def test_information_action(): assert evaluate(req(action_type="information")).action_category.value == "information"
def test_navigation_action(): assert evaluate(req(action_type="navigation")).action_category.value == "navigation"
def test_draft_communication(): assert evaluate(req(action_type="draft_email")).action_category.value == "draft"
def test_sending_communication(): assert evaluate(req(action_type="send_email")).permission_required
def test_form_preparation(): assert evaluate(req(action_type="fill_form")).action_category.value == "form_preparation"
def test_form_submission(): assert evaluate(req(action_type="submit_form")).permission_required
def test_financial(): assert evaluate(req(action_type="payment")).risk_level is RiskLevel.critical
def test_deletion(): assert evaluate(req(action_type="delete_file")).risk_level is RiskLevel.critical
def test_account_change(): assert evaluate(req(action_type="account_change")).permission_required
def test_privacy_sensitive(): assert evaluate(req(action_type="privacy_sensitive")).permission_required
def test_unknown_action():
    d=evaluate(req(action_type="something_unrecognized")); assert d.action_category.value=="unknown" and d.risk_level is RiskLevel.high and d.permission_state is PermissionState.required
def test_no_approval():
    d=evaluate(req(action_type="send_email")); assert d.permission_state is PermissionState.required and not d.approval_valid
def test_valid_approval():
    d=evaluate(req(action_type="send_email", target="alice@example.com", target_type="another_person", approval=approval())); assert d.permission_state is PermissionState.granted and d.approval_valid and d.decision == "ALLOW"
def test_invalid_approval_status_mismatch():
    d=evaluate(req(action_type="send_email", approval={"status":"approved","action_id":"act-1","scope":{"scope_type":"action","action_type":"read","one_time":True,"reusable":False}})); assert d.permission_state is PermissionState.invalid
def test_denied_approval():
    d=evaluate(req(action_type="send_email", approval_status="denied")); assert d.permission_state is PermissionState.denied
def test_scope_mismatch():
    d=evaluate(req(action_type="send_email", approval=approval(target="bob@example.com"), target="alice@example.com")); assert d.permission_state is PermissionState.invalid
def test_one_time_permission():
    d=evaluate(req(action_type="send_email", approval=approval(action_id="other"))); assert d.permission_state is PermissionState.invalid
def test_reusable_permission():
    d=evaluate(req(action_type="send_email", target="alice@example.com", target_type="another_person", approval=approval(one_time=False,reusable=True))); assert d.permission_state is PermissionState.granted
def test_external_side_effect(): assert evaluate(req(external_side_effect=True)).risk_level is RiskLevel.high
def test_reversibility(): assert evaluate(req(action_type="read", reversibility="irreversible")).risk_level is RiskLevel.critical
def test_unknown_reversibility_conservative(): assert evaluate(req(action_type="form_preparation", reversibility="unknown")).risk_level is RiskLevel.medium
def test_third_party_target(): assert evaluate(req(target_type="third_party_account")).risk_level is RiskLevel.medium
def test_own_target(): assert evaluate(req(target_type="user_local_data")).risk_level is RiskLevel.low
def test_critical_approved():
    d=evaluate(req(action_type="payment", target="bank", target_type="financial_institution", approval=approval(action_type="payment",target="bank",target_type="financial_institution"))); assert d.permission_state is PermissionState.granted
def test_critical_denied(): assert evaluate(req(action_type="payment", approval_status="denied")).permission_state is PermissionState.denied
def test_unrelated_approval():
    d=evaluate(req(action_type="payment", approval=approval(action_type="send_email"))); assert d.permission_state is PermissionState.invalid
def test_malformed_scope():
    with pytest.raises(ValidationError): req(action_type="send_email", approval={"status":"approved","scope":{"scope_type":"","action_type":"send_email","one_time":True,"reusable":False}})
def test_missing_target_allowed_but_conservative_scope():
    d=evaluate(req(action_type="send_email")); assert d.permission_state is PermissionState.required
def test_permission_consistency():
    d=evaluate(req(action_type="payment")); assert not (d.permission_required and not d.approval_valid and d.permission_state is PermissionState.granted)
def test_reason_generated(): assert evaluate(req(action_type="payment")).reason
def test_deterministic_repeated():
    r=req(action_type="send_email"); assert evaluate(r).model_dump() == evaluate(r).model_dump()
def test_low_policy_can_allow():
    d=evaluate(req(policy={"allow_low_risk_without_approval":True})); assert not d.permission_required and d.permission_state is PermissionState.not_required and d.decision == "ALLOW"
def test_denied_never_granted():
    d=evaluate(req(action_type="send_email", approval_status="denied", approval=approval())); assert d.permission_state is PermissionState.denied and not d.approval_valid
