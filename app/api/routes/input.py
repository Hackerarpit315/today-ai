"""Input HTTP route."""

from fastapi import APIRouter, Depends, Request

from app.core.security import get_current_principal
from app.schemas.input import InputRequest, InputResponse
from app.services import input_service

router = APIRouter()


@router.post("/api/input", response_model=InputResponse)
def post_input(
    payload: InputRequest,
    request: Request,
    _principal: None = Depends(get_current_principal),
) -> InputResponse:
    result = input_service.accept(payload)
    request.state.request_id = result.request_id
    return result
