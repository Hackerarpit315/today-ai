"""Standalone Context Engine HTTP route."""

from fastapi import APIRouter

from app.schemas.context import ContextRequest, ContextResponse
from app.services.context_service import process_context

router = APIRouter(prefix="/api", tags=["Context Engine"])


@router.post("/context", response_model=ContextResponse)
def create_context(payload: ContextRequest) -> ContextResponse:
    """Return only the explicitly supplied context relevant to the request."""
    return process_context(payload)
