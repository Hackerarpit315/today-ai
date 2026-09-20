"""Standalone Planning Engine HTTP route."""

from fastapi import APIRouter

from app.schemas.planning import PlanningRequest, PlanningResponse
from app.services.planning_service import create_plan

router = APIRouter(prefix="/api", tags=["Planning Engine"])


@router.post("/plan", response_model=PlanningResponse)
def create_planning_response(payload: PlanningRequest) -> PlanningResponse:
    """Create a deterministic plan without executing any action."""
    return create_plan(payload)
