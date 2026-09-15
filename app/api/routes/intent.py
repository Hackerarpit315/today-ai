from fastapi import APIRouter
from app.schemas.intent import IntentRequest, IntentResponse
from app.services.intent_service import process_intent

router = APIRouter(prefix="/api", tags=["Intent Engine"])

@router.post("/intent", response_model=IntentResponse)
def create_intent(payload: IntentRequest) -> IntentResponse:
    return process_intent(payload)
