from uuid import UUID, uuid4, uuid5

import pytest
from pydantic import ValidationError

from app.schemas.action import ActionRequest
from app.services.action_service import ActionService


service = ActionService()
REQ = UUID("11111111-1111-1111-1111-111111111111")
ACTION = UUID("22222222-2222-2222-2222-222222222222")


def scope(action_type="create_local_note", target=None, scope_type="action"):
    return {
        "scope_type": scope_type,
        "action_type": action_type,
        "target": target,
        "target_type": None,
        "one_time": scope_type == "one_time",
        "reusable": scope_type != "one_time",
    }


def make(action_type="no_op", **overrides):
    base = dict(
        request_id=REQ,
        action_id=ACTION,
        action_type=action_type,
        action_category="information",
        risk_level="low",
        permission_required=False,
        permission_state="not_required",
        approval_valid=False,
        external_side_effect=False,
        reversibility="reversible",
        permission_scope=None,
        requested_scope=None,
        parameters={},
        dry_run=False,
    )
    base.update(overrides)
    return ActionRequest(**base)


def granted(action_type="create_local_note", **overrides):
    s = scope(action_type=action_type)
    base = dict(
        permission_required=True,
        permission_state="granted",
        approval_valid=True,
        permission_scope=s,
        requested_scope=s,
    )
    base.update(overrides)
    return make(action_type=action_type, **base)


def test_valid_no_op():
    r = service.execute(make())
    assert r.status == "executed"
    assert r.executed is True


def test_valid_dry_run():
    r = service.execute(make(dry_run=True))
    assert r.status == "would_execute"
    assert r.executed is False


def test_permission_not_required():
    r = service.execute(make())
    assert r.blocked is False


def test_permission_granted():
    r = service.execute(granted(parameters={"title": "x", "content": "y"}))
    assert r.status == "executed"


@pytest.mark.parametrize("state", ["required", "denied", "expired", "invalid", "pending"])
def test_permission_states_block(state):
    r = service.execute(granted(permission_state=state))
    assert r.status == "blocked"
    assert r.blocked is True


def test_missing_approval_blocks():
    r = service.execute(granted(approval_valid=False))
    assert r.status == "blocked"


def test_valid_permission_scope():
    r = service.execute(granted(parameters={"title": "x", "content": "y"}))
    assert r.status == "executed"


def test_scope_mismatch_blocks():
    s = scope("create_local_note")
    requested = scope("create_local_task")
    r = service.execute(granted(permission_scope=s, requested_scope=requested))
    assert r.status == "blocked"


def test_missing_scope_blocks_when_permission_required():
    r = service.execute(granted(permission_scope=None, requested_scope=None))
    assert r.status == "blocked"


def test_unknown_action_type_rejected_by_schema():
    with pytest.raises(ValidationError):
        make(action_type="run_shell_command")


def test_future_known_action_is_unsupported():
    r = service.execute(make(action_type="send_email"))
    assert r.status == "unsupported"


def test_missing_note_parameters():
    r = service.execute(make("create_local_note"))
    assert r.status == "failed"


def test_invalid_note_parameters():
    r = service.execute(make("create_local_note", parameters={"title": 1, "content": "x"}))
    assert r.status == "failed"


def test_create_local_note():
    r = service.execute(make("create_local_note", parameters={"title": "College", "content": "Go tomorrow"}))
    assert r.status == "executed"
    assert r.result["status"] == "created"


def test_create_local_task():
    r = service.execute(make("create_local_task", parameters={"title": "Study", "description": "Math"}))
    assert r.status == "executed"


def test_prepare_email_draft():
    p = {"recipient": "professor@example.com", "subject": "Leave", "body": "I will be absent."}
    r = service.execute(make("prepare_email_draft", parameters=p, action_category="communication", risk_level="high"))
    assert r.result["status"] == "draft_prepared"


def test_prepare_message_draft():
    p = {"recipient": "friend", "body": "See you tomorrow"}
    r = service.execute(make("prepare_message_draft", parameters=p, action_category="communication", risk_level="high"))
    assert r.result["status"] == "draft_prepared"


def test_email_draft_does_not_send():
    p = {"recipient": "a@example.com", "subject": "Hi", "body": "Hello"}
    r = service.execute(make("prepare_email_draft", parameters=p))
    assert r.result["operation"] == "prepare_email_draft"
    assert "send" not in r.result


def test_message_draft_does_not_send():
    p = {"recipient": "a", "body": "Hello"}
    r = service.execute(make("prepare_message_draft", parameters=p))
    assert r.result["operation"] == "prepare_message_draft"


@pytest.mark.parametrize("url", ["http://example.com", "https://example.com/path?q=1"])
def test_valid_http_urls(url):
    r = service.execute(make("open_url", parameters={"url": url}, action_category="navigation"))
    assert r.status == "executed"
    assert r.result["url"] == url


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "data:text/plain,hello", "vbscript:msgbox(1)"])
def test_unsafe_urls_rejected(url):
    r = service.execute(make("open_url", parameters={"url": url}, action_category="navigation"))
    assert r.status == "failed"


def test_arbitrary_command_rejected():
    with pytest.raises(ValidationError):
        make(parameters={"command": "whoami"})


def test_arbitrary_code_rejected():
    with pytest.raises(ValidationError):
        make(parameters={"code": "__import__('os').system('whoami')"})


def test_n8n_dispatch_preview():
    r = service.execute(make(
        "n8n_dispatch_preview",
        action_category="external_side_effect",
        risk_level="high",
        parameters={"recipient": "professor@example.com", "subject": "Leave", "body": "Absent"},
    ))
    assert r.status == "executed"
    assert r.adapter == "n8n"
    assert r.result["network_call_performed"] is False


def test_n8n_network_call_is_not_performed():
    r = service.execute(make("n8n_dispatch_preview"))
    assert r.result["network_call_performed"] is False
    assert r.result["would_dispatch"] is True


def test_n8n_adapter_controlled_preview_result():
    r = service.execute(make("n8n_dispatch_preview"))
    assert r.result["status"] == "preview"


def test_dry_run_does_not_perform_side_effect():
    p = {"title": "x", "content": "y"}
    r = service.execute(make("create_local_note", parameters=p, dry_run=True))
    assert r.status == "would_execute"
    assert r.result["side_effect_performed"] is False


def test_adapter_failure_handling():
    # Missing required local parameter is converted into a safe failed response.
    r = service.execute(make("prepare_email_draft", parameters={"recipient": "x"}))
    assert r.status == "failed"
    assert r.execution_attempted is False


def test_deterministic_repeated_execution():
    request = make("create_local_note", parameters={"title": "x", "content": "y"})
    a = service.execute(request)
    b = service.execute(request)
    assert a.model_dump() == b.model_dump()


def test_request_id_preserved():
    r = service.execute(make())
    assert r.request_id == REQ


def test_execution_id_is_uuid_and_stable():
    r = service.execute(make())
    assert isinstance(r.execution_id, UUID)
    assert r.execution_id == service.execute(make()).execution_id


def test_unknown_schema_fields_rejected():
    with pytest.raises(ValidationError):
        make(extra_field="reject")


def test_malformed_input_rejected():
    with pytest.raises(ValidationError):
        ActionRequest(
            request_id="not-a-uuid",
            action_id=str(ACTION),
            action_type="no_op",
            action_category="information",
            risk_level="low",
            permission_required=False,
            permission_state="not_required",
            approval_valid=False,
            external_side_effect=False,
            reversibility="reversible",
            parameters={},
        )


def test_safe_error_handling_for_invalid_url():
    r = service.execute(make("open_url", parameters={"url": "http:///bad"}))
    assert r.status == "failed"
    assert "traceback" not in r.reason.lower()


def test_record_action_is_in_memory():
    r = service.execute(make("record_action"))
    assert r.status == "executed"
    assert r.result["status"] == "recorded_in_memory"


def test_no_real_browser_launch():
    r = service.execute(make("open_url", parameters={"url": "https://example.com"}))
    assert r.result["operation"] == "open_url"
    assert r.result["status"] == "prepared"


def test_one_time_scope_requires_one_time_flags():
    s = scope("create_local_note", scope_type="one_time")
    s["one_time"] = False
    r = service.execute(granted(permission_scope=s, requested_scope=s))
    assert r.status == "blocked"


def test_external_action_can_be_permission_checked():
    s = scope("send_email", target="professor@example.com")
    r = service.execute(make(
        "send_email",
        permission_required=True,
        permission_state="granted",
        approval_valid=True,
        permission_scope=s,
        requested_scope=s,
        action_category="communication",
        risk_level="high",
        external_side_effect=True,
    ))
    assert r.status == "unsupported"


def test_permission_check_happens_before_adapter_selection():
    r = service.execute(make(
        "n8n_dispatch_preview",
        permission_required=True,
        permission_state="denied",
        approval_valid=False,
        action_category="external_side_effect",
        risk_level="high",
        external_side_effect=True,
    ))
    assert r.status == "blocked"
    assert r.adapter == "none"


def test_dry_run_can_block_before_simulation():
    r = service.execute(make(
        "n8n_dispatch_preview",
        permission_required=True,
        permission_state="required",
        approval_valid=False,
        dry_run=True,
    ))
    assert r.status == "blocked"


def test_response_contains_required_execution_flags():
    r = service.execute(make())
    data = r.model_dump()
    for key in ["execution_attempted", "executed", "blocked", "result", "reason", "adapter", "execution_id"]:
        assert key in data


def test_no_op_has_no_external_side_effect():
    r = service.execute(make())
    assert r.external_side_effect is False


def test_drafts_are_not_external_side_effects():
    p = {"recipient": "a@example.com", "subject": "x", "body": "y"}
    r = service.execute(make("prepare_email_draft", parameters=p))
    assert r.external_side_effect is False
