from __future__ import annotations

from uuid import UUID, uuid5

from app.schemas.action import ActionRequest, ActionResponse
from app.services.actions.base_adapter import ActionAdapter
from app.services.actions.dry_run_adapter import DryRunAdapter
from app.services.actions.local_adapter import LocalActionAdapter
from app.services.actions.n8n_adapter import N8NActionAdapter


_NAMESPACE = UUID("6f0c9a0a-3b84-4bb5-91c7-0f9e4a4f1b72")

_EXECUTABLE_LOCAL = {
    "no_op",
    "dry_run",
    "create_local_note",
    "create_local_task",
    "prepare_email_draft",
    "prepare_message_draft",
    "open_url",
    "record_action",
}
_SUPPORTED_TYPES = _EXECUTABLE_LOCAL | {"n8n_dispatch_preview"}
_FUTURE_UNSUPPORTED = {
    "send_email",
    "send_message",
    "create_calendar_event",
    "telegram_message",
    "external_api_call",
}


class ActionService:
    def execute(self, request: ActionRequest) -> ActionResponse:
        execution_id = uuid5(_NAMESPACE, f"{request.request_id}:{request.action_id}")

        blocked_reason = self._permission_block_reason(request)
        if blocked_reason:
            return self._response(
                request, execution_id, status="blocked", attempted=False,
                executed=False, blocked=True, adapter="none",
                result={}, reason=blocked_reason,
            )

        parameter_error = self._validate_parameters(request)
        if parameter_error:
            return self._response(
                request, execution_id, status="failed", attempted=False,
                executed=False, blocked=False, adapter="validation",
                result={}, reason=parameter_error,
            )

        if request.action_type not in _SUPPORTED_TYPES:
            status = "unsupported" if request.action_type in _FUTURE_UNSUPPORTED else "unsupported"
            return self._response(
                request, execution_id, status=status, attempted=False,
                executed=False, blocked=False, adapter="none",
                result={}, reason="action type is not executable in Module 10",
            )

        if request.dry_run or request.action_type == "dry_run":
            adapter: ActionAdapter = DryRunAdapter()
        elif request.action_type == "n8n_dispatch_preview":
            adapter = N8NActionAdapter()
        else:
            adapter = LocalActionAdapter()

        try:
            result = adapter.execute(request)
        except NotImplementedError as exc:
            return self._response(
                request, execution_id, status="unsupported", attempted=True,
                executed=False, blocked=False, adapter=adapter.name,
                result={}, reason=str(exc),
            )
        except (ValueError, KeyError) as exc:
            return self._response(
                request, execution_id, status="failed", attempted=True,
                executed=False, blocked=False, adapter=adapter.name,
                result={}, reason=str(exc),
            )
        except Exception:
            # Deliberately do not expose stack traces or implementation details.
            return self._response(
                request, execution_id, status="failed", attempted=True,
                executed=False, blocked=False, adapter=adapter.name,
                result={}, reason="controlled adapter failure",
            )

        would_execute = bool(result.get("would_execute"))
        if would_execute:
            status = "would_execute"
            executed = False
        else:
            status = "executed"
            executed = True

        return self._response(
            request, execution_id, status=status, attempted=True,
            executed=executed, blocked=False, adapter=adapter.name,
            result=result, reason="action adapter completed successfully",
        )

    @staticmethod
    def _permission_block_reason(request: ActionRequest) -> str | None:
        if not request.permission_required:
            return None
        if request.permission_state != "granted":
            return f"permission is not granted: {request.permission_state}"
        if not request.approval_valid:
            return "permission approval is not valid"
        if not ActionService._scope_matches(request):
            return "requested permission scope does not match granted scope"
        return None

    @staticmethod
    def _scope_matches(request: ActionRequest) -> bool:
        granted = request.permission_scope
        requested = request.requested_scope
        if granted is None or requested is None:
            return False

        if granted.scope_type != requested.scope_type:
            return False
        if granted.action_type and granted.action_type != requested.action_type:
            return False
        if granted.target and granted.target != requested.target:
            return False
        if granted.target_type and granted.target_type != requested.target_type:
            return False

        if granted.scope_type == "one_time":
            if not granted.one_time or not requested.one_time:
                return False
            # One-time scope must be explicitly tied to this request's action.
            # The action id is carried by the action request, not inside scope.
            return granted.action_type == request.action_type

        return True

    @staticmethod
    def _validate_parameters(request: ActionRequest) -> str | None:
        p = request.parameters

        def required(*keys: str) -> str | None:
            missing = [k for k in keys if k not in p]
            if missing:
                return f"missing required parameter(s): {', '.join(missing)}"
            return None

        if request.action_type == "create_local_note":
            err = required("title", "content")
            if err:
                return err
            if not all(isinstance(p[k], str) and p[k].strip() for k in ("title", "content")):
                return "title and content must be non-empty strings"

        elif request.action_type == "create_local_task":
            err = required("title")
            if err:
                return err
            if not isinstance(p["title"], str) or not p["title"].strip():
                return "title must be a non-empty string"
            if "description" in p and not isinstance(p["description"], str):
                return "description must be a string"

        elif request.action_type == "prepare_email_draft":
            err = required("recipient", "subject", "body")
            if err:
                return err
            if not all(isinstance(p[k], str) and p[k].strip() for k in ("recipient", "subject", "body")):
                return "recipient, subject and body must be non-empty strings"

        elif request.action_type == "prepare_message_draft":
            err = required("recipient", "body")
            if err:
                return err
            if not all(isinstance(p[k], str) and p[k].strip() for k in ("recipient", "body")):
                return "recipient and body must be non-empty strings"

        elif request.action_type == "open_url":
            err = required("url")
            if err:
                return err
            if not isinstance(p["url"], str):
                return "url must be a string"
            from urllib.parse import urlparse
            parsed = urlparse(p["url"])
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
                return "only valid http:// or https:// URLs are allowed"

        return None

    @staticmethod
    def _response(request, execution_id, *, status, attempted, executed,
                   blocked, adapter, result, reason):
        return ActionResponse(
            request_id=request.request_id,
            action_id=request.action_id,
            action_type=request.action_type,
            status=status,
            execution_attempted=attempted,
            executed=executed,
            blocked=blocked,
            result=result,
            reason=reason,
            adapter=adapter,
            external_side_effect=request.external_side_effect,
            reversibility=request.reversibility,
            execution_id=execution_id,
        )
