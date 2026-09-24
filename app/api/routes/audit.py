from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas.audit import (
    ActorType, AuditEventCreateRequest, AuditEventListRequest, AuditEventListResponse,
    AuditEventResponse, AuditEventSearchRequest, AuditEventRetrieveRequest, AuditIntegrityResponse,
    AuditStatus, EventType, ModuleName, Severity,
)
from app.persistence.factory import create_audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.post("", response_model=AuditEventResponse)
def create_audit_event(request: AuditEventCreateRequest) -> AuditEventResponse:
    try:
        return create_audit_service().create_event(request)
    except ValueError as exc:
        return AuditEventResponse(success=False, status="rejected", reason=str(exc))

@router.get("/search", response_model=AuditEventListResponse)
def search_audit_events(query: str = Query(min_length=1, max_length=500), ascending: bool = True, limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0)) -> AuditEventListResponse:
    return create_audit_service().search_events(AuditEventSearchRequest(query=query, ascending=ascending, limit=limit, offset=offset))

@router.get("/{event_id}/integrity", response_model=AuditIntegrityResponse)
def audit_integrity(event_id: UUID) -> AuditIntegrityResponse:
    return create_audit_service().verify_event_integrity(event_id)

@router.get("/{event_id}", response_model=AuditEventResponse)
def get_audit_event(event_id: UUID) -> AuditEventResponse:
    return create_audit_service().retrieve_event(AuditEventRetrieveRequest(event_id=event_id))

@router.get("", response_model=AuditEventListResponse)
def list_audit_events(
    request_id: UUID | None = None, correlation_id: UUID | None = None, module: ModuleName | None = None,
    event_type: EventType | None = None, status: AuditStatus | None = None, severity: Severity | None = None,
    actor: ActorType | None = None, action_id: UUID | None = None, resource_type: str | None = None,
    resource_id: UUID | None = None, user_id: UUID | None = None, ascending: bool = True,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
) -> AuditEventListResponse:
    request = AuditEventListRequest(
        request_id=request_id, correlation_id=correlation_id, module=module, event_type=event_type, status=status,
        severity=severity, actor=actor, action_id=action_id, resource_type=resource_type, resource_id=resource_id,
        user_id=user_id, ascending=ascending, limit=limit, offset=offset,
    )
    return create_audit_service().list_events(request)
