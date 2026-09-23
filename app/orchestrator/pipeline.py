"""Deterministic M1 -> M8 orchestration without duplicating module logic."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.core.security import AppError
from app.schemas.context import ContextRequest
from app.schemas.input import InputRequest
from app.schemas.intent import IntentRequest
from app.schemas.planning import PlanningConstraint, PlanningRequest, VerifiedInformation
from app.schemas.priority import PriorityRequest, PriorityStep
from app.schemas.research import ResearchRequest, ResearchSource
from app.schemas.today import TodayRequest, TodayTask
from app.schemas.verification import VerificationRequest, VerificationResearchResult
from app.services import context_service, input_service, intent_service, planning_service
from app.services import priority_service, research_service, today_service, verification_service
from .schemas import PipelineRequest, PipelineResult, StageError


_STAGE_ORDER = ("input", "intent", "context", "research", "verification", "planning", "priority", "today")


def _safe_error(stage: str, exc: Exception) -> StageError:
    if isinstance(exc, ValidationError):
        return StageError(stage=stage, code="validation_error", message="Stage input or output validation failed.")
    if isinstance(exc, AppError):
        return StageError(stage=stage, code=exc.error, message=exc.message)
    return StageError(stage=stage, code="stage_error", message="Stage failed safely.")


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value



class Orchestrator:
    """Run the first deterministic Today AI pipeline.

    The service functions remain owned by Modules 1-8. This class only maps
    their existing contracts into the next module's contract and stops safely
    on the first exception.
    """

    def __init__(self, services: Mapping[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def _service(self, name: str, default: Any) -> Any:
        return self._services.get(name, default)

    def run(self, request: PipelineRequest) -> PipelineResult:
        result = PipelineResult(
            request_id=request.request_id,
            status="success",
            current_stage="input",
        )
        completed: dict[str, Any] = {}

        try:
            # M1: call the existing service for normalization/validation.
            accepted = self._service("input", input_service).accept(
                InputRequest(input_type=request.input_type, content=request.text)
            )
            # M1 owns request-id generation. The integration contract owns
            # correlation, so adapt its validated output to the explicit ID.
            accepted = accepted.model_copy(update={"request_id": str(request.request_id)})
            completed["input"] = accepted.model_dump(mode="json")
            result.stage_results["input"] = completed["input"]

            # M2
            intent = self._service("intent", intent_service).process_intent(
                IntentRequest(
                    request_id=request.request_id,
                    input_type=accepted.input_type,
                    content=accepted.content,
                    status=accepted.status,
                )
            )
            completed["intent"] = intent
            result.intent = _serialize(intent)
            result.stage_results["intent"] = result.intent

            # M3
            context = self._service("context", context_service).process_context(
                ContextRequest(
                    request_id=request.request_id,
                    intent=intent.intent,
                    goal=intent.goal,
                    entities=intent.entities,
                    time_reference=intent.time_reference,
                    confidence=intent.confidence,
                    available_context=request.available_context,
                )
            )
            completed["context"] = context
            result.context = _serialize(context)
            result.stage_results["context"] = result.context

            # M4
            research = self._service("research", research_service).process_research(
                ResearchRequest(
                    request_id=request.request_id,
                    query=intent.goal,
                    intent=intent.intent,
                    goal=intent.goal,
                    entities=intent.entities,
                    sources=request.research_sources,
                )
            )
            completed["research"] = research
            result.research = _serialize(research)
            result.stage_results["research"] = result.research

            # M5: research response omits source content, so join against the
            # exact caller-supplied source objects by source_id.
            sources_by_id = {source.source_id: source for source in request.research_sources}
            verification_items: list[VerificationResearchResult] = []
            for item in research.results:
                source = sources_by_id.get(item.source_id)
                if source is None:
                    continue
                verification_items.append(
                    VerificationResearchResult(
                        source_id=source.source_id,
                        title=source.title,
                        content=source.content,
                        source_type=source.source_type,
                        relevance_score=item.relevance_score,
                    )
                )
            verification = self._service("verification", verification_service).verify_research(
                VerificationRequest(
                    request_id=request.request_id,
                    query=intent.goal,
                    research_results=verification_items,
                )
            )
            completed["verification"] = verification
            result.verification = _serialize(verification)
            result.stage_results["verification"] = result.verification

            # M6: turn verified claims into the module's existing
            # VerifiedInformation contract; no planning logic is duplicated.
            verified_information = [
                VerifiedInformation(key="verified_claim", value=claim, category="fact")
                for claim in verification.verified_claims
            ]
            constraints = [
                PlanningConstraint(key="context_used", value=context.context_used),
                PlanningConstraint(key="research_completed", value=research.research_completed),
                PlanningConstraint(key="verification_status", value=verification.verification_status),
            ]
            planning = self._service("planning", planning_service).create_plan(
                PlanningRequest(
                    request_id=request.request_id,
                    goal=intent.goal,
                    intent=intent.intent,
                    entities=intent.entities,
                    time_reference=intent.time_reference,
                    verified_information=verified_information,
                    constraints=constraints,
                )
            )
            completed["planning"] = planning
            result.planning = _serialize(planning)
            result.stage_results["planning"] = result.planning

            # M7: map the plan into the priority module's existing input
            # contract. Missing optional priority signals intentionally remain
            # absent instead of being invented by the orchestrator.
            priority_steps = [
                PriorityStep(
                    step_id=step.step_id,
                    title=step.title,
                    description=step.description,
                    order=step.order,
                    required=step.required,
                    depends_on=step.depends_on,
                    status=step.status,
                )
                for step in planning.steps
            ]
            priority = self._service("priority", priority_service).prioritize_plan(
                PriorityRequest(
                    request_id=request.request_id,
                    goal=planning.goal,
                    plan_id=planning.plan_id,
                    steps=priority_steps,
                    time_reference=intent.time_reference,
                    priority_reference_time=request.current_datetime,
                )
            )
            completed["priority"] = priority
            result.priority = _serialize(priority)
            result.stage_results["priority"] = result.priority

            # M8: transform M7's prioritized steps into the existing TodayTask
            # contract and pass the explicit current_datetime through unchanged.
            today_tasks = [
                TodayTask(
                    step_id=step.step_id,
                    title=step.title,
                    description=next(
                        (plan_step.description for plan_step in planning.steps if plan_step.step_id == step.step_id),
                        "",
                    ),
                    priority_score=step.priority_score,
                    priority_level=step.priority_level,
                    urgency=step.urgency or "medium",
                    required=step.required,
                    blocked=step.blocked,
                    depends_on=step.depends_on,
                    original_order=step.original_order,
                    status="blocked" if step.blocked else "pending",
                )
                for step in priority.prioritized_steps
            ]
            today = self._service("today", today_service).build_today(
                TodayRequest(
                    request_id=request.request_id,
                    plan_id=planning.plan_id,
                    goal=planning.goal,
                    current_datetime=request.current_datetime,
                    tasks=today_tasks,
                )
            )
            completed["today"] = today
            result.today = _serialize(today)
            result.stage_results["today"] = result.today
            result.current_stage = "today"
            result.status = "success"
            return result

        except Exception as exc:
            # Identify the first stage without exposing implementation details.
            failed_stage = next((stage for stage in _STAGE_ORDER if stage not in completed), "input")
            result.status = "failed"
            result.current_stage = failed_stage
            result.errors = [_safe_error(failed_stage, exc)]
            return result


def run_pipeline(
    text: str,
    *,
    request_id: UUID,
    current_datetime: datetime,
    available_context: list[Any] | None = None,
    research_sources: list[ResearchSource] | None = None,
) -> PipelineResult:
    """Convenience entry point using only explicit context."""

    request = PipelineRequest(
        request_id=request_id,
        text=text,
        current_datetime=current_datetime,
        available_context=available_context or [],
        research_sources=research_sources or [],
    )
    return Orchestrator().run(request)
