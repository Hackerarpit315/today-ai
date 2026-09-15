"""Standalone Research Engine HTTP route."""

from fastapi import APIRouter

from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.research_service import process_research

router = APIRouter(prefix="/api", tags=["Research Engine"])


@router.post("/research", response_model=ResearchResponse)
def create_research(payload: ResearchRequest) -> ResearchResponse:
    """Rank explicitly supplied research sources."""
    return process_research(payload)
