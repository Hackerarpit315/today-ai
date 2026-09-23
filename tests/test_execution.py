from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.execution import Evidence, ExecutionRequest
from app.services.execution_service import ExecutionService


R = UUID("11111111-1111-4111-8111-111111111111")
A = UUID("22222222-2222-4222-8222-222222222222")


def req(action_type, *, attempted=True, status="executed", result=None, evidence=None,
        dry_run=False, external=False, category="information", expected="completed"):
    return ExecutionRequest(
        request_id=R,
        action_id=A,
        action_type=action_type,
        action_category=category,
        execution_attempted=attempted,
        execution_status=status,
        adapter="local",
        dry_run=dry_run,
        external_side_effect=external,
        expected_outcome=expected,
        execution_result=result or {},
        evidence=evidence or [],
    )


def ev(t, source="local_adapter", ref=None, status="created", data=None):
    return Evidence(evidence_type=t, source=source, reference_id=ref, status=status, data=data or {})


@pytest.fixture
def service():
    return ExecutionService()


def test_successful_local_note_with_id(service):
    r = service.verify(req("create_local_note", result={"status": "created", "note_id": "note_123"}))
    assert r.verification_status == "verified_success"
    assert r.verification_level == "direct"
    assert r.verified_reference == "note_123"


def test_successful_local_note_with_evidence_id(service):
    r = service.verify(req("create_local_note", result={"status": "created"}, evidence=[ev("local_record", ref="note_123", data={"note_id": "note_123"})]))
    assert r.verification_status == "verified_success"


def test_local_note_without_id_is_unknown(service):
    r = service.verify(req("create_local_note", result={"status": "created"}))
    assert r.verification_status == "unknown"


def test_failed_local_note(service):
    r = service.verify(req("create_local_note", status="failed", result={"error_code": "ADAPTER_ERROR"}))
    assert r.verification_status == "verified_failure"


def test_successful_local_task_with_id(service):
    r = service.verify(req("create_local_task", result={"status": "created", "task_id": "task_1"}))
    assert r.verification_status == "verified_success"


def test_failed_local_task(service):
    r = service.verify(req("create_local_task", status="failed", result={"error_code": "X"}))
    assert r.verification_status == "verified_failure"


def test_successful_email_draft_with_id(service):
    r = service.verify(req("prepare_email_draft", category="communication", result={"status": "draft_prepared", "draft_id": "draft_1"}))
    assert r.verification_status == "verified_success"
    assert r.external_action_verified is False


def test_email_draft_without_id_unknown(service):
    r = service.verify(req("prepare_email_draft", category="communication", result={"status": "draft_prepared"}))
    assert r.verification_status == "unknown"


def test_successful_message_draft(service):
    r = service.verify(req("prepare_message_draft", category="communication", result={"status": "draft_prepared", "draft_id": "msgdraft_1"}))
    assert r.verification_status == "verified_success"


def test_message_draft_without_evidence(service):
    r = service.verify(req("prepare_message_draft", category="communication", result={"status": "draft_prepared"}))
    assert r.verification_status == "unknown"


def test_successful_no_op(service):
    r = service.verify(req("no_op", result={"operation": "no_op", "message": "No operation performed."}))
    assert r.verification_status == "verified_success"


def test_no_op_without_controlled_result_is_unknown(service):
    r = service.verify(req("no_op", result={}))
    assert r.verification_status == "unknown"


def test_successful_dry_run(service):
    r = service.verify(req("dry_run", status="would_execute", dry_run=True, result={"would_execute": True, "side_effect_performed": False, "operation": "dry_run"}))
    assert r.verification_status == "verified_success"


def test_dry_run_not_external_success(service):
    r = service.verify(req("dry_run", status="would_execute", dry_run=True, external=True, result={"would_execute": True, "side_effect_performed": False}))
    assert r.verified is True
    assert r.external_action_verified is False


def test_url_prepared_without_browser_evidence_is_unknown(service):
    r = service.verify(req("open_url", category="navigation", result={"operation": "open_url", "status": "prepared", "url": "https://example.com"}))
    assert r.verification_status == "unknown"
    assert r.external_action_verified is False


def test_url_with_actual_browser_evidence(service):
    evidence = ev("browser_execution", source="controlled_browser", ref="browser_1", status="opened")
    r = service.verify(req("open_url", category="navigation", result={"status": "prepared"}, evidence=[evidence]))
    assert r.verification_status == "verified_success"
    assert r.external_action_verified is True


def test_n8n_dispatch_preview(service):
    result = {"operation": "n8n_dispatch_preview", "status": "preview", "network_call_performed": False, "payload": {"action_id": str(A)}}
    r = service.verify(req("n8n_dispatch_preview", category="external_side_effect", result=result))
    assert r.verification_status == "verified_success"
    assert r.verification_level == "strong"


def test_n8n_preview_not_external_success(service):
    result = {"operation": "n8n_dispatch_preview", "network_call_performed": False, "payload": {"x": 1}}
    r = service.verify(req("n8n_dispatch_preview", category="external_side_effect", external=True, result=result))
    assert r.external_action_verified is False


def test_future_n8n_success_evidence(service):
    evidence = ev("external_execution", source="n8n", ref="n8n_exec_123", status="success", data={"provider": "n8n"})
    # Preview action remains preview-only even if external evidence is supplied.
    r = service.verify(req("n8n_dispatch_preview", category="external_side_effect", result={"operation": "n8n_dispatch_preview", "network_call_performed": False, "payload": {}}, evidence=[evidence]))
    assert r.external_action_verified is False


def test_future_n8n_failure_evidence(service):
    evidence = ev("external_execution", source="n8n", ref="n8n_exec_123", status="failed")
    r = service.verify(req("n8n_dispatch_preview", category="external_side_effect", result={}, evidence=[evidence]))
    assert r.verification_status == "unknown"


def test_execution_not_attempted(service):
    r = service.verify(req("create_local_note", attempted=False, status="not_attempted"))
    assert r.verification_status == "not_attempted"
    assert r.verified is False


def test_action_blocked(service):
    r = service.verify(req("create_local_note", status="blocked", result={"status": "blocked"}))
    assert r.verification_status == "blocked"


def test_execution_status_failed(service):
    r = service.verify(req("record_action", status="failed", result={"error_code": "FAIL"}))
    assert r.verification_status == "verified_failure"


def test_execution_status_unknown(service):
    r = service.verify(req("record_action", status="unknown", result={}))
    assert r.verification_status == "unknown"


def test_missing_evidence_for_record(service):
    r = service.verify(req("record_action", result={"operation": "record_action"}))
    assert r.verification_status == "unknown"


def test_valid_record_action(service):
    r = service.verify(req("record_action", result={"status": "recorded_in_memory", "record": {"action_id": str(A)}}))
    assert r.verification_status == "verified_success"


def test_invalid_evidence_blank_source():
    with pytest.raises(ValidationError):
        Evidence(evidence_type="local_record", source="", status="created")


def test_mismatched_action_type_evidence_is_unknown(service):
    evidence = ev("local_record", ref="task_1", status="created", data={"task_id": "task_1"})
    r = service.verify(req("create_local_note", result={"status": "created"}, evidence=[evidence]))
    assert r.verification_status == "unknown"
    assert r.verified is False


def test_unknown_action_type_rejected_by_schema():
    with pytest.raises(ValidationError):
        req("delete_everything")


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        ExecutionRequest(
            request_id=R, action_id=A, action_type="no_op", action_category="information",
            execution_attempted=True, execution_status="executed", adapter="local",
            external_side_effect=False, expected_outcome="completed", unexpected="x",
        )


def test_malformed_uuid_rejected():
    with pytest.raises(ValidationError):
        ExecutionRequest(
            request_id="bad", action_id=A, action_type="no_op", action_category="information",
            execution_attempted=True, execution_status="executed", adapter="local",
            external_side_effect=False, expected_outcome="completed",
        )


def test_unsafe_evidence_field_rejected():
    with pytest.raises(ValidationError):
        Evidence(evidence_type="local_record", source="test", status="created", data={"command": "rm -rf /"})


def test_verification_is_deterministic(service):
    request = req("create_local_note", result={"status": "created", "note_id": "note_1"})
    first = service.verify(request)
    second = service.verify(request)
    assert first.model_dump() == second.model_dump()


def test_request_id_preserved(service):
    r = service.verify(req("no_op", result={"operation": "no_op"}))
    assert r.request_id == R


def test_action_id_preserved(service):
    r = service.verify(req("no_op", result={"operation": "no_op"}))
    assert r.action_id == A


def test_verification_id_deterministic(service):
    request = req("no_op", result={"operation": "no_op"})
    assert service.verify(request).verification_id == service.verify(request).verification_id


def test_failed_status_takes_precedence_over_success_evidence(service):
    evidence = ev("local_record", ref="note_1", status="created")
    r = service.verify(req("create_local_note", status="failed", result={"error_code": "X"}, evidence=[evidence]))
    assert r.verification_status == "verified_failure"


def test_blocked_result_takes_precedence(service):
    r = service.verify(req("no_op", result={"status": "blocked", "operation": "no_op"}))
    assert r.verification_status == "blocked"


def test_insufficient_evidence_never_claims_success(service):
    r = service.verify(req("create_local_task", result={"status": "executed"}))
    assert r.verification_status == "unknown"
    assert r.verified is False


def test_email_draft_does_not_mean_email_sent(service):
    r = service.verify(req("prepare_email_draft", category="communication", result={"status": "draft_prepared", "draft_id": "d1"}))
    assert r.verification_status == "verified_success"
    assert r.external_action_verified is False


def test_message_draft_does_not_mean_message_sent(service):
    r = service.verify(req("prepare_message_draft", category="communication", result={"status": "draft_prepared", "draft_id": "d1"}))
    assert r.external_action_verified is False


def test_n8n_preview_requires_no_network_call(service):
    result = {"operation": "n8n_dispatch_preview", "network_call_performed": False, "payload": {"action_type": "send_email"}}
    r = service.verify(req("n8n_dispatch_preview", category="external_side_effect", result=result))
    assert r.verification_status == "verified_success"
    assert r.external_action_verified is False


def test_timestamp_is_optional():
    e = Evidence(evidence_type="local_record", source="local", status="created")
    assert e.timestamp is None


def test_evidence_is_preserved_in_response(service):
    evidence = ev("local_record", ref="note_1", status="created")
    r = service.verify(req("create_local_note", result={}, evidence=[evidence]))
    assert len(r.evidence_used) == 1
    assert r.evidence_used[0].reference_id == "note_1"


def test_observed_outcome_is_structured(service):
    r = service.verify(req("no_op", result={"operation": "no_op"}))
    assert r.observed_outcome == "completed"


def test_policy_version_present(service):
    r = service.verify(req("no_op", result={"operation": "no_op"}))
    assert r.policy_version == "execution-verification-v1"
