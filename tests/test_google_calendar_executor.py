import asyncio

from app.integrations.google_calendar.executor import (
    google_calendar_executor,
)


def test_google_calendar_create_event():
    result = asyncio.run(
        google_calendar_executor.execute(
            user_id="test-user",
            action={
                "type": "calendar.create_event",
                "event": {
                    "summary": "Today AI Connection Manager Test",
                    "description": "Testing Google Calendar through Connection Manager",
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
    assert result["event_id"]
    assert result["status"] == "confirmed"
    assert result["summary"] == "Today AI Connection Manager Test"