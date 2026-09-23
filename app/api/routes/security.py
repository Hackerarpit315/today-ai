from fastapi import APIRouter
from app.schemas.security import ActionSecurityRequest, SecurityCheckRequest, URLSecurityRequest
from app.services.security_service import action_check, check_request, check_url

router = APIRouter(prefix="/api/security", tags=["security"])

@router.post("/check")
def security_check(request: SecurityCheckRequest):
    return check_request(request)

@router.post("/url")
def security_url(request: URLSecurityRequest):
    return check_url(request)

@router.post("/action")
def security_action(request: ActionSecurityRequest):
    return action_check(request)
