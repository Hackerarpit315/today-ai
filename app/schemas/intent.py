from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class IntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    input_type: str
    content: str = Field(min_length=1)
    status: str

class IntentResponse(BaseModel):
    request_id: UUID
    intent: str
    goal: str
    entities: dict[str, Any]
    time_reference: str | None
    confidence: float = Field(ge=0.0, le=1.0)
