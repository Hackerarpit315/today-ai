import asyncio

from app.integrations.action_integration import action_integration_service


def test_create_calendar_event_mapping(monkeypatch):
    captured = {}

    async def fake_send_action_to_n8n(action):
        captured["action"] = action
        return {
            "success": True,
            "action_type": "calendar.create_event",
            "event_id": "test-event-id",
            "status": "confirmed",
            "summary": "Bridge Unit Test",
        }

    monkeypatch.setattr(
        "app.integrations.action_integration.send_action_to_n8n",
        fake_send_action_to_n8n,
    )

    result = asyncio.run(
        action_integration_service.dispatch(
            user_id="test-user",
            action_type="create_calendar_event",
            parameters={
                "summary": "Bridge Unit Test",
                "description": "Testing Action Integration mapping",
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

    assert captured["action"]["type"] == "calendar.create_event"
    assert captured["action"]["event"]["summary"] == "Bridge Unit Test"
    assert captured["action"]["event"]["description"] == "Testing Action Integration mapping"
    assert captured["action"]["event"]["start"]["dateTime"] == "2026-10-01T12:00:00+05:30"
    assert captured["action"]["event"]["end"]["dateTime"] == "2026-10-01T12:30:00+05:30"

    assert result["success"] is True
    assert result["event_id"] == "test-event-id"
