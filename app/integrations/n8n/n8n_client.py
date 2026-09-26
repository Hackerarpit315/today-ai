import json
import os
from typing import Any
from urllib.request import Request, urlopen


def get_n8n_webhook_url() -> str:
    value = os.getenv("N8N_ACTION_WEBHOOK_URL", "").strip()
    if not value:
        raise RuntimeError("N8N_ACTION_WEBHOOK_URL is not configured")
    return value


async def send_action_to_n8n(
    action: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "action": action,
    }

    request = Request(
        get_n8n_webhook_url(),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
        },
    )

    with urlopen(request, timeout=20.0) as response:
        body = response.read()

    if not body:
        return {}

    return json.loads(body)