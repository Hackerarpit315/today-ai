from uuid import uuid4

from app.schemas.permission import PermissionRequest
from app.services.orchestration_service import OrchestrationService


def test_orchestration_permission_to_action():
    request_id = uuid4()
    action_id = str(uuid4())

    permission_request = PermissionRequest(
        request_id=request_id,
        action_id=action_id,
        action_type="create_local_note",
        description="Create a local note",
        external_side_effect=False,
        current_datetime=None,
    )

    service = OrchestrationService()

    response = service.execute(
        permission_request=permission_request,
        parameters={
            "title": "Orchestration Test",
            "content": "Permission to Action integration test",
        },
    )

    assert response.request_id == request_id
    assert str(response.action_id) == action_id
    assert response.action_type == "create_local_note"
    assert response.status == "blocked"
    assert response.blocked is True
    assert response.execution_attempted is False


def test_orchestration_allowed_action_executes():
    request_id = uuid4()
    action_id = str(uuid4())

    permission_request = PermissionRequest(
        request_id=request_id,
        action_id=action_id,
        action_type="create_local_note",
        description="Create an approved local note",
        target="local_note",
        target_type="user_local_data",
        external_side_effect=False,
        reversibility="reversible",
        approval={
            "status": "approved",
            "action_id": action_id,
            "scope": {
                "scope_type": "action",
                "action_type": "create_local_note",
                "target": "local_note",
                "target_type": "user_local_data",
                "one_time": True,
                "reusable": False,
            },
        },
    )

    service = OrchestrationService()

    response = service.execute(
        permission_request=permission_request,
        parameters={
            "title": "Approved Orchestration Test",
            "content": "Allowed execution path",
        },
    )

    assert response.request_id == request_id
    assert str(response.action_id) == action_id
    assert response.action_type == "create_local_note"
    assert response.blocked is False
    assert response.execution_attempted is True
    assert response.executed is True
    assert response.status == "executed"
