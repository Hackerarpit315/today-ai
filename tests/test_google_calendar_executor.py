import asyncio

from app.integrations.google_calendar import executor as executor_module
from app.integrations.google_calendar.executor import (
    google_calendar_executor,
)


class FakeGoogleCalendarClient:
    async def create_event(
        self,
        user_id: str,
        event: dict,
    ) -> dict:
        return {
            "id": "fake-event-123",
            "status": "confirmed",
            "summary": event["summary"],
        }


def test_google_calendar_create_event(monkeypatch):
    monkeypatch.setattr(
        executor_module.connection_manager,
        "status",
        lambda user_id, provider: executor_module.ConnectionStatus.CONNECTED,
    )

    monkeypatch.setattr(
        executor_module,
        "google_calendar_client",
        FakeGoogleCalendarClient(),
    )

    result = asyncio.run(
        google_calendar_executor.execute(
            user_id="test-user",
            action={
                "type": "calendar.create_event",
                "event": {
                    "summary": "Today AI Connection Manager Test",
                    "description": (
                        "Testing Google Calendar through Connection Manager"
                    ),
                    "start": {
                        "dateTime": "2026-09-28T12:00:00+05:30",
                        "timeZone": "Asia/Kolkata",
                    },
                    "end": {
                        "dateTime": "2026-09-28T12:30:00+05:30",
                        "timeZone": "Asia/Kolkata",
                    },
                },
            },
        )
    )

    assert result["success"] is True
    assert result["action_type"] == "calendar.create_event"
    assert result["event_id"] == "fake-event-123"
    assert result["status"] == "confirmed"
    assert result["summary"] == "Today AI Connection Manager Test"