"""Input layer request, response, and error models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


KNOWN_INPUT_TYPES = frozenset(
    {"text", "url", "image", "file", "voice_transcript"}
)
ACCEPTED_INPUT_TYPES = frozenset({"text"})


class InputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_type: str
    content: str = Field(..., min_length=0)

    @field_validator("input_type")
    @classmethod
    def input_type_must_be_known(cls, value: str) -> str:
        if value not in KNOWN_INPUT_TYPES:
            raise ValueError("Unknown input_type.")
        return value


class InputResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    input_type: str
    content: str
    status: Literal["accepted"]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
    status: int
