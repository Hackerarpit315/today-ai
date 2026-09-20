from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.schemas.action import ActionRequest
from app.services.actions.base_adapter import ActionAdapter


class LocalActionAdapter(ActionAdapter):
    name = "local"

    def execute(self, request: ActionRequest) -> dict[str, Any]:
        p = request.parameters

        if request.action_type == "no_op":
            return {"operation": "no_op", "message": "No operation performed."}

        if request.action_type == "create_local_note":
            return {
                "operation": "create_local_note",
                "status": "created",
                "note": {"title": p["title"], "content": p["content"]},
            }

        if request.action_type == "create_local_task":
            return {
                "operation": "create_local_task",
                "status": "created",
                "task": {
                    "title": p["title"],
                    "description": p.get("description", ""),
                },
            }

        if request.action_type == "prepare_email_draft":
            return {
                "operation": "prepare_email_draft",
                "status": "draft_prepared",
                "draft": {
                    "recipient": p["recipient"],
                    "subject": p["subject"],
                    "body": p["body"],
                },
            }

        if request.action_type == "prepare_message_draft":
            return {
                "operation": "prepare_message_draft",
                "status": "draft_prepared",
                "draft": {
                    "recipient": p["recipient"],
                    "body": p["body"],
                },
            }

        if request.action_type == "open_url":
            url = p["url"]
            parsed = urlparse(url)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
                raise ValueError("only valid http:// or https:// URLs are allowed")
            return {"operation": "open_url", "status": "prepared", "url": url}

        if request.action_type == "record_action":
            return {
                "operation": "record_action",
                "status": "recorded_in_memory",
                "record": {
                    "action_id": str(request.action_id),
                    "action_type": request.action_type,
                },
            }

        raise NotImplementedError(f"local adapter does not support {request.action_type}")
