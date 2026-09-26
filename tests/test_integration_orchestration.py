import asyncio

from app.services.integration_orchestration_service import (
    integration_orchestration_service,
)


def test_create_calendar_event_integration_orchestration(monkeypatch):
    captured = {}

    async def fake_dispatch(
        *,
        user_id,
        action_type,
        parameters,
    ):
        captured["user_id"] = user_id
        captured["action_type"] = action_type
        captured["parameters"] = parameters

        return {
            "success": True,
            "action_type": "calendar.create_event",
            "event_id": "integration-test-event",
            "status": "confirmed",
            "summary": parameters["summary"],
        }

    monkeypatch.setattr(
        "app.services.integration_orchestration_service"
        ".action_integration_service.dispatch",
        fake_dispatch,
    )

    result = asyncio.run(
        integration_orchestration_service.execute(
            user_id="test-user",
            action_type="create_calendar_event",
            parameters={
                "summary": "Integration Orchestration Test",
                "description": "Testing integration orchestration",
                "start": {
                    "dateTime": "2026-10-01T12:00:00+05:30",
                    "timeZone": "Asia/Kolkata",
                },
                "end": {
                    "dateTime": "2026-10-01T12:30:00+05:30",
                    "timeZone": "Asia/Kolkata",
                },
            },
        )
    )

    assert captured["user_id"] == "test-user"
    assert captured["action_type"] == "create_calendar_event"
    assert captured["parameters"]["summary"] == "Integration Orchestration Test"

    assert result["success"] is True
    assert result["event_id"] == "integration-test-event"
    assert result["action_type"] == "calendar.create_event"


def test_unsupported_integration_action_is_rejected():
    try:
        asyncio.run(
            integration_orchestration_service.execute(
                user_id="test-user",
                action_type="send_email",
                parameters={},
            )
        )
    except ValueError as exc:
        assert str(exc) == "Unsupported integration action: send_email"
    else:
        raise AssertionError("Unsupported integration action was accepted")
