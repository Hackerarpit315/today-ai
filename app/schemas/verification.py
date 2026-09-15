"""Pydantic schemas for the standalone Verification Engine."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


class VerificationResearchResult(BaseModel):
    """A research result supplied by the Research Engine or another caller."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1, max_length=50_000)
    source_type: str = Field(..., min_length=1, max_length=64)
    relevance_score: float = Field(..., ge=0.0, le=1.0)

    _validate_title = field_validator("title")(_non_empty)
    _validate_content = field_validator("content")(_non_empty)
    _validate_source_type = field_validator("source_type")(_non_empty)
    _validate_source_id = field_validator("source_id")(_non_empty)


class VerificationRequest(BaseModel):
    """Input contract for deterministic verification of supplied evidence."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    query: str = Field(..., min_length=1, max_length=1_000)
    research_results: list[VerificationResearchResult] = Field(
        ..., max_length=1_000
    )

    _validate_query = field_validator("query")(_non_empty)


class VerificationResponse(BaseModel):
    """Output contract for the standalone Verification Engine."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    verified: bool
    conflict_detected: bool
    verification_status: str
    verified_claims: list[str]
    conflicting_claims: list[str]
    insufficient_claims: list[str]
    supporting_sources: list[str]
    conflicting_sources: list[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
