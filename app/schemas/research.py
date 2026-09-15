"""Pydantic schemas for the standalone Research Engine."""

from typing import Any
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class ResearchSource(BaseModel):
    """A research source explicitly supplied to the Research Engine."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=500)
    url: AnyHttpUrl
    content: str = Field(..., min_length=1, max_length=50_000)
    source_type: str = Field(..., min_length=1, max_length=64)
    published_at: str | None = Field(default=None, max_length=128)


class ResearchRequest(BaseModel):
    """Input contract for deterministic research over supplied sources."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    query: str = Field(..., min_length=1, max_length=1_000)
    intent: str = Field(..., min_length=1, max_length=256)
    goal: str = Field(..., min_length=1, max_length=5_000)
    entities: dict[str, Any] = Field(default_factory=dict, max_length=100)
    sources: list[ResearchSource] = Field(default_factory=list, max_length=1_000)


class ResearchResult(BaseModel):
    """One relevant supplied source and its deterministic relevance data."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    url: AnyHttpUrl
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    matched_terms: list[str]


class ResearchResponse(BaseModel):
    """Output contract for the standalone Research Engine."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    query: str
    results: list[ResearchResult]
    sources_found: int = Field(..., ge=0)
    research_completed: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
