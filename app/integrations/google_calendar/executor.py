from typing import Any

from app.integrations.connections.manager import connection_manager
from app.integrations.connections.models import ConnectionStatus
from app.integrations.google_calendar.client import google_calendar_client


class GoogleCalendarExecutor:
    async def execute(
        self,
        user_id: str,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        action_type = action.get("type")

        if action_type != "calendar.create_event":
            raise ValueError(
                f"Unsupported calendar action: {action_type}"
            )

        connection_status = connection_manager.status(
            user_id=user_id,
            provider="google",
        )

        if connection_status != ConnectionStatus.CONNECTED:
            raise ValueError(
                "Google account is not connected"
            )

        event = action.get("event")

        if not isinstance(event, dict):
            raise ValueError(
                "Calendar action requires an event object"
            )

        result = await google_calendar_client.create_event(
            user_id=user_id,
            event=event,
        )

        return {
            "success": True,
            "action_type": action_type,
            "event_id": result.get("id"),
            "status": result.get("status"),
            "summary": result.get("summary"),
        }


google_calendar_executor = GoogleCalendarExecutor()