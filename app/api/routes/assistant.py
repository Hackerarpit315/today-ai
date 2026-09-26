"""Public application endpoint backed by the existing M1 -> M8 orchestrator."""

from __future__ import annotations

import os
from uuid import uuid4

from fastapi import APIRouter

from app.llm.factory import create_llm_provider
from app.llm.provider import LLMProvider
from app.orchestrator.pipeline import Orchestrator
from app.orchestrator.schemas import PipelineRequest
from app.schemas.assistant import AssistantRequest, AssistantResponse


router = APIRouter(prefix="/api", tags=["assistant"])


def _get_llm_provider() -> LLMProvider | None:
    """Return an LLM provider only when explicitly configured.

    When TODAY_AI_LLM_PROVIDER is not set, the assistant uses the
    deterministic orchestrator without an external LLM.

    The factory is intentionally called without arguments so existing
    tests can monkeypatch create_llm_provider with a zero-argument
    function.
    """
    provider = os.getenv("TODAY_AI_LLM_PROVIDER")

    if provider is None or not provider.strip():
        return None

    return create_llm_provider()


@router.post("/assistant", response_model=AssistantResponse)
def assistant(request: AssistantRequest) -> AssistantResponse:
    """Accept a user request, run the existing orchestrator, and expose its result."""
    request_id = uuid4()

    llm_provider = _get_llm_provider()

    pipeline_result = Orchestrator(
        llm_provider=llm_provider,
    ).run(
        PipelineRequest(
            request_id=request_id,
            text=request.content,
            current_datetime=request.current_datetime,
        )
    )

    return AssistantResponse(
        request_id=pipeline_result.request_id,
        status=pipeline_result.status,
        current_stage=pipeline_result.current_stage,
        pipeline=pipeline_result.model_dump(mode="json"),
        errors=pipeline_result.errors,
    )