"""Standalone Verification Engine HTTP route."""

from fastapi import APIRouter

from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.verification_service import verify_research

router = APIRouter(prefix="/api", tags=["Verification Engine"])


@router.post("/verification", response_model=VerificationResponse)
def create_verification(payload: VerificationRequest) -> VerificationResponse:
    """Verify consistency of explicitly supplied research results."""
    return verify_research(payload)
