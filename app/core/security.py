"""Safe error types, JSON-only gate, body size limit, and future auth hook."""

from __future__ import annotations

import json
import logging
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import MAX_REQUEST_BODY_BYTES

logger = logging.getLogger("today_ai")


class AppError(Exception):
    def __init__(self, error: str, message: str, status: int) -> None:
        self.error = error
        self.message = message
        self.status = status
        super().__init__(message)


def error_body(error: str, message: str, status: int) -> dict[str, Any]:
    return {"error": error, "message": message, "status": status}


def get_current_principal() -> None:
    """Placeholder auth dependency. Module 1 does not authenticate."""
    return None


def _header_map(scope: Scope) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        headers[raw_name.decode("latin-1").lower()] = raw_value.decode("latin-1")
    return headers


def _is_json_content_type(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json"


class JsonOnlyMiddleware:
    """Reject non-JSON Content-Type on methods that send a body."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        if method in {"POST", "PUT", "PATCH"}:
            content_type = _header_map(scope).get("content-type", "")
            if not _is_json_content_type(content_type):
                await _send_json(
                    send,
                    415,
                    error_body(
                        "unsupported_media_type",
                        "Content-Type must be application/json.",
                        415,
                    ),
                )
                return

        await self.app(scope, receive, send)


class BodySizeLimitMiddleware:
    """Reject request bodies larger than MAX_REQUEST_BODY_BYTES."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _header_map(scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await _send_json(
                        send,
                        413,
                        error_body(
                            "payload_too_large",
                            "Request body is too large.",
                            413,
                        ),
                    )
                    return
            except ValueError:
                pass

        body = bytearray()
        too_large = False
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            if chunk:
                if len(body) + len(chunk) > self.max_bytes:
                    too_large = True
                    break
                body.extend(chunk)
            if not message.get("more_body", False):
                break

        if too_large:
            await _send_json(
                send,
                413,
                error_body(
                    "payload_too_large",
                    "Request body is too large.",
                    413,
                ),
            )
            return

        captured = bytes(body)
        sent = False

        async def replay_receive() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": captured, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)


class AccessLogMiddleware:
    """Log method, path, status, and request_id — never raw content."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_holder = {"code": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message.get("status", 0)
            await send(message)

        await self.app(scope, receive, send_wrapper)

        path = scope.get("path", "")
        method = scope.get("method", "")
        state = scope.get("state")
        request_id = "-"
        if isinstance(state, dict):
            request_id = state.get("request_id", "-") or "-"
        elif state is not None:
            request_id = getattr(state, "request_id", "-") or "-"
        logger.info("%s %s %s %s", method, path, status_holder["code"], request_id)


async def _send_json(send: Send, status: int, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": raw})
