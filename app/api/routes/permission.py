from fastapi import APIRouter
from app.schemas.permission import PermissionDecision, PermissionRequest
from app.services.permission_service import evaluate

router = APIRouter(prefix="/api", tags=["permission"])

@router.post("/permission", response_model=PermissionDecision)
def permission(request: PermissionRequest) -> PermissionDecision:
    return evaluate(request)
