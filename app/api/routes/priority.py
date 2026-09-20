"""Standalone Priority Engine HTTP route."""

from fastapi import APIRouter

from app.schemas.priority import PriorityRequest, PriorityResponse
from app.services.priority_service import prioritize_plan

router = APIRouter(prefix="/api", tags=["Priority Engine"])


@router.post("/priority", response_model=PriorityResponse)
def create_priority_response(payload: PriorityRequest) -> PriorityResponse:
    """Calculate deterministic priority metadata without executing any action."""
    return prioritize_plan(payload)
