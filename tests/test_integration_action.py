import pytest
from pydantic import ValidationError

from app.schemas.integration_action import (
    IntegrationActionRequest,
    IntegrationActionResponse,
)


def test_integration_action_request_valid():
    request = IntegrationActionRequest(
        user_id="test-user",
        action_type="create_calendar_event",
        parameters={
            "summary": "Test Event",
        },
    )

    assert request.user_id == "test-user"
    assert request.action_type == "create_calendar_event"
    assert request.parameters["summary"] == "Test Event"


def test_integration_action_request_rejects_blank_user_id():
    with pytest.raises(ValidationError):
        IntegrationActionRequest(
            user_id="   ",
            action_type="create_calendar_event",
            parameters={},
        )


def test_integration_action_request_rejects_unknown_action():
    with pytest.raises(ValidationError):
        IntegrationActionRequest(
            user_id="test-user",
            action_type="send_email",
            parameters={},
        )


def test_integration_action_response():
    response = IntegrationActionResponse(
        success=True,
        action_type="create_calendar_event",
        event_id="test-event-id",
        status="confirmed",
        summary="Test Event",
    )

    assert response.success is True
    assert response.event_id == "test-event-id"
    assert response.action_type == "create_calendar_event"