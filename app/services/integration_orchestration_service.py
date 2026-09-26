from __future__ import annotations

from typing import Any

from app.integrations.action_integration import action_integration_service


class IntegrationOrchestrationService:
    """
    Bridges approved Today AI actions to external integrations.

    This service does not perform permission evaluation.
    Permission must already have been granted by the Permission Engine.
    """

    async def execute(
        self,
        *,
        user_id: str,
        action_type: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        if action_type != "create_calendar_event":
            raise ValueError(
                f"Unsupported integration action: {action_type}"
            )

        return await action_integration_service.dispatch(
            user_id=user_id,
            action_type=action_type,
            parameters=parameters,
        )


integration_orchestration_service = IntegrationOrchestrationService()
