from __future__ import annotations

from typing import Any

from app.integrations.n8n.n8n_client import send_action_to_n8n


class ActionIntegrationService:
    async def dispatch(
        self,
        user_id: str,
        action_type: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        if action_type != "create_calendar_event":
            raise ValueError(
                f"Unsupported integration action: {action_type}"
            )

        event = {
            "summary": parameters.get("summary"),
            "description": parameters.get("description", ""),
            "start": parameters.get("start"),
            "end": parameters.get("end"),
        }

        if (
            not isinstance(event["summary"], str)
            or not event["summary"].strip()
        ):
            raise ValueError(
                "Calendar event summary is required"
            )

        if not isinstance(event["start"], dict):
            raise ValueError(
                "Calendar event start is required"
            )

        if not isinstance(event["end"], dict):
            raise ValueError(
                "Calendar event end is required"
            )

        action = {
            "type": "calendar.create_event",
            "event": event,
        }

        return await send_action_to_n8n(action)


action_integration_service = ActionIntegrationService()
