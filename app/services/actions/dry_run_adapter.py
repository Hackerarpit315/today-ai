from __future__ import annotations

from typing import Any

from app.schemas.action import ActionRequest
from app.services.actions.base_adapter import ActionAdapter


class DryRunAdapter(ActionAdapter):
    name = "dry_run"

    def execute(self, request: ActionRequest) -> dict[str, Any]:
        return {
            "operation": "dry_run",
            "would_execute": True,
            "action_type": request.action_type,
            "parameters": request.parameters,
            "side_effect_performed": False,
        }
