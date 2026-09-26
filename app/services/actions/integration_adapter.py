from __future__ import annotations

import asyncio
from typing import Any

from app.schemas.action import ActionRequest
from app.services.actions.base_adapter import ActionAdapter
from app.services.integration_orchestration_service import (
    integration_orchestration_service,
)


class IntegrationActionAdapter(ActionAdapter):
    name = "integration"

    def execute(self, request: ActionRequest) -> dict[str, Any]:
        if request.action_type != "create_calendar_event":
            raise NotImplementedError(
                f"integration adapter does not support {request.action_type}"
            )

        return asyncio.run(
            integration_orchestration_service.execute(
                user_id=str(request.request_id),
                action_type=request.action_type,
                parameters=request.parameters,
            )
        )