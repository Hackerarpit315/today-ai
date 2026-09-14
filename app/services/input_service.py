"""Normalize and accept input. Does not interpret intent."""

from app.core.config import MAX_CONTENT_LENGTH
from app.core.security import AppError
from app.schemas.input import ACCEPTED_INPUT_TYPES, InputRequest, InputResponse
from app.utils.ids import new_request_id


def accept(payload: InputRequest) -> InputResponse:
    content = payload.content.strip()
    if content == "":
        raise AppError("validation_error", "Content must not be empty.", 422)
    if len(content) > MAX_CONTENT_LENGTH:
        raise AppError(
            "payload_too_large",
            "Content exceeds maximum length.",
            413,
        )
    if payload.input_type not in ACCEPTED_INPUT_TYPES:
        raise AppError(
            "unsupported_input_type",
            "Input type is not supported.",
            400,
        )
    return InputResponse(
        request_id=new_request_id(),
        input_type=payload.input_type,
        content=content,
        status="accepted",
    )
