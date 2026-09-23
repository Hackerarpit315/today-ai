from __future__ import annotations

from typing import Any
from uuid import UUID, uuid5

from app.schemas.execution import (
    Evidence,
    ExecutionRequest,
    ExecutionVerificationResponse,
)


_NAMESPACE = UUID("d4a6d8c8-7b25-4fcb-a1e5-0a5f2b6c9d31")
_SUPPORTED_ACTIONS = {
    "no_op",
    "dry_run",
    "create_local_note",
    "create_local_task",
    "prepare_email_draft",
    "prepare_message_draft",
    "open_url",
    "record_action",
    "n8n_dispatch_preview",
}


class ExecutionService:
    """Deterministic, read-only verifier for Module 10 execution results."""

    def verify(self, request: ExecutionRequest) -> ExecutionVerificationResponse:
        verification_id = uuid5(
            _NAMESPACE,
            f"{request.request_id}:{request.action_id}:{request.execution_status}:{request.execution_result}:{request.evidence}",
        )

        if not request.execution_attempted:
            return self._response(
                request,
                verification_id,
                "not_attempted",
                "none",
                False,
                False,
                "execution was not attempted",
                "not_attempted",
                [],
                None,
            )

        if request.execution_status == "blocked" or self._result_status(request) == "blocked":
            return self._response(
                request,
                verification_id,
                "blocked",
                "none",
                False,
                False,
                "execution was blocked; no action completion is verified",
                "blocked",
                self._relevant_evidence(request),
                None,
            )

        if request.action_type not in _SUPPORTED_ACTIONS:
            return self._response(
                request,
                verification_id,
                "unknown",
                "none",
                False,
                False,
                "action type is not supported by the standalone verifier",
                "unsupported",
                self._relevant_evidence(request),
                None,
            )

        if request.execution_status in {"failed", "not_configured", "unsupported"}:
            return self._response(
                request,
                verification_id,
                "verified_failure",
                "direct",
                True,
                False,
                "execution result explicitly reports controlled failure",
                "failed",
                self._relevant_evidence(request),
                self._first_reference(request),
            )

        if request.execution_status == "unknown":
            return self._response(
                request,
                verification_id,
                "unknown",
                "none",
                False,
                False,
                "execution status is unknown and does not establish completion",
                "unknown",
                self._relevant_evidence(request),
                None,
            )

        if request.action_type == "open_url":
            return self._verify_open_url(request, verification_id)
        if request.action_type == "n8n_dispatch_preview":
            return self._verify_n8n_preview(request, verification_id)
        if request.dry_run or request.action_type == "dry_run":
            return self._verify_dry_run(request, verification_id)
        if request.action_type == "no_op":
            return self._verify_no_op(request, verification_id)
        if request.action_type in {"create_local_note", "create_local_task"}:
            return self._verify_local_record(request, verification_id)
        if request.action_type in {"prepare_email_draft", "prepare_message_draft"}:
            return self._verify_draft(request, verification_id)
        if request.action_type == "record_action":
            return self._verify_record_action(request, verification_id)

        return self._response(
            request, verification_id, "unknown", "none", False, False,
            "no verification rule matched", "unknown", self._relevant_evidence(request), None,
        )

    def _verify_no_op(self, request: ExecutionRequest, verification_id: UUID):
        if self._controlled_success(request):
            return self._response(
                request, verification_id, "verified_success", "direct", True, False,
                "controlled no-op completed successfully", "completed",
                self._relevant_evidence(request), self._first_reference(request),
            )
        return self._unknown(request, verification_id, "no-op lacks sufficient controlled completion evidence")

    def _verify_dry_run(self, request: ExecutionRequest, verification_id: UUID):
        if self._controlled_dry_run(request):
            return self._response(
                request, verification_id, "verified_success", "direct", True, False,
                "dry-run operation completed; no external action was verified", "dry_run_completed",
                self._relevant_evidence(request), self._first_reference(request),
            )
        return self._unknown(request, verification_id, "dry-run result does not prove completion")

    def _verify_local_record(self, request: ExecutionRequest, verification_id: UUID):
        key = "note_id" if request.action_type == "create_local_note" else "task_id"
        evidence = self._find_evidence_with_id(request, key)
        result_id = request.execution_result.get(key)
        if self._valid_id(result_id) or evidence is not None:
            reference = str(result_id or evidence.reference_id or evidence.data.get(key))
            return self._response(
                request, verification_id, "verified_success", "direct", True, False,
                f"{request.action_type} has controlled identifier evidence", "created",
                self._relevant_evidence(request), reference,
            )
        if self._result_status(request) in {"created", "executed", "success"}:
            return self._unknown(request, verification_id, f"{request.action_type} reports success but has no valid identifier evidence")
        return self._unknown(request, verification_id, f"insufficient evidence for {request.action_type}")

    def _verify_draft(self, request: ExecutionRequest, verification_id: UUID):
        evidence = self._find_evidence_with_id(request, "draft_id")
        result_id = request.execution_result.get("draft_id")
        if not result_id and isinstance(request.execution_result.get("draft"), dict):
            result_id = request.execution_result["draft"].get("draft_id")
        if self._valid_id(result_id) or evidence is not None:
            reference = str(result_id or evidence.reference_id or evidence.data.get("draft_id"))
            return self._response(
                request, verification_id, "verified_success", "direct", True, False,
                "draft was successfully prepared; sending was not verified", "draft_prepared",
                self._relevant_evidence(request), reference,
            )
        return self._unknown(request, verification_id, "draft reports completion but no draft identifier evidence exists")

    def _verify_open_url(self, request: ExecutionRequest, verification_id: UUID):
        browser = self._find_browser_success(request)
        if browser:
            return self._response(
                request, verification_id, "verified_success", "direct", True, True,
                "browser evidence confirms the URL was opened", "browser_opened",
                [browser], browser.reference_id,
            )
        return self._response(
            request, verification_id, "unknown", "weak" if request.execution_result else "none",
            False, False,
            "URL request was prepared, but no browser execution evidence was supplied",
            "url_prepared", self._relevant_evidence(request), None,
        )

    def _verify_n8n_preview(self, request: ExecutionRequest, verification_id: UUID):
        result = request.execution_result
        prepared = (
            result.get("operation") == "n8n_dispatch_preview"
            and result.get("network_call_performed") is False
            and isinstance(result.get("payload"), dict)
        )
        evidence = self._find_evidence(request, "n8n_dispatch_preview", {"preview", "prepared", "success"})
        if prepared or evidence:
            reference = (evidence.reference_id if evidence else None)
            return self._response(
                request, verification_id, "verified_success", "strong", True, False,
                "n8n dispatch payload was prepared; no external action was verified",
                "dispatch_preview_prepared", self._relevant_evidence(request), reference,
            )
        return self._unknown(request, verification_id, "n8n preview lacks sufficient payload evidence")

    def _verify_record_action(self, request: ExecutionRequest, verification_id: UUID):
        evidence = self._find_evidence(request, "local_record", {"created", "recorded", "success"})
        result_status = self._result_status(request)
        record = request.execution_result.get("record")
        if evidence or (result_status == "recorded_in_memory" and isinstance(record, dict) and record):
            return self._response(
                request, verification_id, "verified_success", "direct", True, False,
                "controlled action record evidence confirms completion", "recorded",
                self._relevant_evidence(request), self._first_reference(request),
            )
        return self._unknown(request, verification_id, "record action lacks sufficient controlled evidence")

    @staticmethod
    def _controlled_success(request: ExecutionRequest) -> bool:
        result = request.execution_result
        status = str(result.get("status", "")).lower()
        operation = str(result.get("operation", "")).lower()
        return request.execution_status in {"executed", "success"} and (
            status in {"", "executed", "success", "completed"}
            and bool(operation or result or request.evidence)
        )

    @staticmethod
    def _controlled_dry_run(request: ExecutionRequest) -> bool:
        result = request.execution_result
        return (
            request.execution_status in {"executed", "success", "would_execute"}
            and result.get("would_execute") is True
            and result.get("side_effect_performed") is False
        )

    @staticmethod
    def _result_status(request: ExecutionRequest) -> str:
        return str(request.execution_result.get("status", "")).lower()

    @staticmethod
    def _valid_id(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _relevant_evidence(request: ExecutionRequest) -> list[Evidence]:
        return list(request.evidence)

    @staticmethod
    def _first_reference(request: ExecutionRequest) -> str | None:
        for evidence in request.evidence:
            if evidence.reference_id:
                return evidence.reference_id
        return None

    @staticmethod
    def _find_evidence_with_id(request: ExecutionRequest, key: str) -> Evidence | None:
        for evidence in request.evidence:
            # Prefer action-specific structured identifiers. A generic reference
            # alone is not enough to prove that the evidence belongs to this
            # action (for example, a task ID must not verify a note).
            if evidence.status.lower() not in {"created", "success", "prepared", "recorded"}:
                continue
            if evidence.data.get(key):
                return evidence
        return None

    @staticmethod
    def _find_evidence(request: ExecutionRequest, evidence_type: str, statuses: set[str]) -> Evidence | None:
        for evidence in request.evidence:
            if evidence.evidence_type == evidence_type and evidence.status.lower() in statuses:
                return evidence
        return None

    @staticmethod
    def _find_browser_success(request: ExecutionRequest) -> Evidence | None:
        for evidence in request.evidence:
            if evidence.evidence_type == "browser_execution" and evidence.status.lower() in {"opened", "success"}:
                return evidence
        return None

    def _unknown(self, request: ExecutionRequest, verification_id: UUID, reason: str):
        return self._response(
            request, verification_id, "unknown", "none", False, False,
            reason, "insufficient_evidence", self._relevant_evidence(request), None,
        )

    @staticmethod
    def _response(
        request: ExecutionRequest,
        verification_id: UUID,
        status: str,
        level: str,
        verified: bool,
        external_verified: bool,
        reason: str,
        observed: str,
        evidence: list[Evidence],
        reference: str | None,
    ) -> ExecutionVerificationResponse:
        return ExecutionVerificationResponse(
            request_id=request.request_id,
            action_id=request.action_id,
            action_type=request.action_type,
            verification_status=status,
            verification_level=level,
            verified=verified,
            external_action_verified=external_verified,
            expected_outcome=request.expected_outcome,
            observed_outcome=observed,
            evidence_used=evidence,
            reason=reason,
            verification_id=verification_id,
            verified_reference=reference,
        )
