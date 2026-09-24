from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter

from app.schemas.memory import (
    MemoryForgetRequest,
    MemoryListRequest,
    MemoryRetrieveRequest,
    MemoryStoreRequest,
    MemoryUpdateRequest,
)
from app.persistence.factory import create_memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryRouteRequest:
    """Route request envelope is intentionally assembled from strict operation schemas."""


@router.post("")
def memory_operation(payload: dict[str, Any]) -> Any:
    """Dispatch a structured memory operation without executing external actions."""
    operation = payload.get("operation")
    data = payload.get("data")
    if not isinstance(operation, str) or not isinstance(data, dict):
        return {
            "operation": str(operation) if operation is not None else "",
            "status": "invalid",
            "success": False,
            "reason": "operation and data are required",
        }

    models = {
        "store": MemoryStoreRequest,
        "retrieve": MemoryRetrieveRequest,
        "update": MemoryUpdateRequest,
        "forget": MemoryForgetRequest,
        "list": MemoryListRequest,
    }
    model = models.get(operation)
    if model is None:
        return {
            "operation": operation,
            "status": "invalid",
            "success": False,
            "reason": "Unsupported memory operation",
        }

    request = model.model_validate(data)
    service = create_memory_service()
    service_method = getattr(service, operation)
    return service_method(request)
