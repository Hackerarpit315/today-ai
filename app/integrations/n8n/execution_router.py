from typing import Any

from app.integrations.google_calendar.executor import (
    google_calendar_executor,
)


async def execute_external_action(
    user_id: str,
    action: dict[str, Any],
) -> dict[str, Any]:
    action_type = action.get("type")

    if action_type == "calendar.create_event":
        return await google_calendar_executor.execute(
            user_id=user_id,
            action=action,
        )

    raise ValueError(
        f"Unsupported external action: {action_type}"
    )