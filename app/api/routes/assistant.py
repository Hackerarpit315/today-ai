"""Public application endpoint backed by the existing M1 -> M8 orchestrator."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter

from app.llm.factory import create_llm_provider
from app.orchestrator.pipeline import Orchestrator
from app.orchestrator.schemas import PipelineRequest
from app.schemas.assistant import AssistantRequest, AssistantResponse

router = APIRouter(prefix="/api", tags=["assistant"])


@router.post("/assistant", response_model=AssistantResponse)
def assistant(request: AssistantRequest) -> AssistantResponse:
    """Accept a user request, run the existing orchestrator, and expose its result."""
    request_id = uuid4()
    llm_provider = create_llm_provider()
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
