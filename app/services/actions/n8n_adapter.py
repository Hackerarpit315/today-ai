from __future__ import annotations

from typing import Any

from app.schemas.action import ActionRequest
from app.services.actions.base_adapter import ActionAdapter


class N8NActionAdapter(ActionAdapter):
    """
    Future n8n contract only.

    This adapter deliberately performs no HTTP request and has no webhook URL
    or credentials. It returns the exact payload that a future implementation
    would dispatch to an n8n webhook.
    """

    name = "n8n"

    def execute(self, request: ActionRequest) -> dict[str, Any]:
        payload = {
            "action_id": str(request.action_id),
            "action_type": request.action_type,
            "action_category": request.action_category,
            "parameters": request.parameters,
        }
        return {
            "operation": "n8n_dispatch_preview",
            "status": "preview",
            "would_dispatch": True,
            "network_call_performed": False,
            "payload": payload,
        }
