from fastapi import APIRouter

from app.schemas.execution import ExecutionRequest, ExecutionVerificationResponse
from app.services.execution_service import ExecutionService


router = APIRouter(prefix="/api/execution", tags=["execution-verification"])
_service = ExecutionService()


@router.post("/verify", response_model=ExecutionVerificationResponse)
def verify_execution(request: ExecutionRequest) -> ExecutionVerificationResponse:
    return _service.verify(request)
