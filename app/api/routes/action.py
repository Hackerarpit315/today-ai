from fastapi import APIRouter

from app.schemas.action import ActionRequest, ActionResponse
from app.services.action_service import ActionService


router = APIRouter(prefix="/api", tags=["action"])
_service = ActionService()


@router.post("/action", response_model=ActionResponse)
def execute_action(request: ActionRequest) -> ActionResponse:
    return _service.execute(request)
