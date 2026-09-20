"""Standalone Today Engine HTTP route; intentionally not registered globally yet."""

from fastapi import APIRouter

from app.schemas.today import TodayRequest, TodayResponse
from app.services.today_service import build_today

router = APIRouter(prefix="/api", tags=["Today Engine"])


@router.post("/today", response_model=TodayResponse)
def create_today_response(payload: TodayRequest) -> TodayResponse:
    """Build a deterministic Today view without executing any task."""
    return build_today(payload)
