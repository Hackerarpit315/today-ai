"""Runtime configuration from environment (no secrets)."""

import os

_DEFAULT_MAX_CONTENT_LENGTH = 10_000
_DEFAULT_MAX_REQUEST_BODY_BYTES = 64 * 1024


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = int(raw)
    if value < 1:
        return default
    return value


MAX_CONTENT_LENGTH = _positive_int(
    "TODAY_AI_MAX_CONTENT_LENGTH", _DEFAULT_MAX_CONTENT_LENGTH
)
MAX_REQUEST_BODY_BYTES = _positive_int(
    "TODAY_AI_MAX_REQUEST_BODY_BYTES", _DEFAULT_MAX_REQUEST_BODY_BYTES
)
