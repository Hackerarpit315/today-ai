from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.schemas.action import ActionRequest, ActionResponse
from app.schemas.permission import PermissionRequest, PermissionDecision
from app.services.action_service import ActionService
from app.services.permission_service import evaluate


class OrchestrationService:
    """
    Coordinates Permission Engine and Action Engine.

    This layer does not replace or modify either module.
    It only passes the output of Permission Engine into
    Action Engine in the expected schema.
    """

    def __init__(self) -> None:
        self._action_service = ActionService()

    def execute(
        self,
        *,
        permission_request: PermissionRequest,
        parameters: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> ActionResponse:
        parameters = parameters or {}

        # Module 9: Permission Engine
        permission: PermissionDecision = evaluate(permission_request)

        # Build Module 10 input from Module 9 output.
        action_request = ActionRequest(
            request_id=permission.request_id,
            action_id=UUID(permission.action_id),
            action_type=permission.action_type,
            action_category=permission.action_category.value,
            risk_level=permission.risk_level.value,
            permission_required=permission.permission_required,
            permission_decision=permission.decision,
            permission_state=permission.permission_state.value,
            approval_valid=permission.approval_valid,
            external_side_effect=permission.external_side_effect,
            reversibility=permission.reversibility.value,
            permission_scope=(
                permission.permission_scope.model_dump()
                if permission.permission_scope is not None
                else None
            ),
            requested_scope=(
                permission.permission_scope.model_dump()
                if permission.permission_scope is not None
                else None
            ),
            parameters=parameters,
            dry_run=dry_run,
        )

        # Module 10: Action Engine
        return self._action_service.execute(action_request)


orchestration_service = OrchestrationService()