"""Deterministic, non-executing Priority Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.priority import (
    PriorityRequest,
    PriorityResponse,
    PrioritizedStep,
    ScoreBreakdown,
)

URGENCY_SCORES = {
    "critical": 100.0,
    "high": 75.0,
    "medium": 50.0,
    "low": 25.0,
}
WEIGHTS = {
    "urgency": 0.30,
    "deadline": 0.25,
    "required": 0.20,
    "dependency": 0.15,
    "importance": 0.10,
}


def _deadline_score(deadline: datetime | None, reference: datetime | None) -> float:
    """Return a fixed score from deadline proximity; no reference means neutral."""
    if deadline is None or reference is None:
        return 50.0
    delta_hours = (deadline.astimezone(timezone.utc) - reference.astimezone(timezone.utc)).total_seconds() / 3600
    if delta_hours <= 0:
        return 100.0
    if delta_hours <= 24:
        return 80.0
    if delta_hours <= 72:
        return 60.0
    if delta_hours <= 168:
        return 40.0
    return 20.0


def _dependency_scores(request: PriorityRequest) -> dict[str, float]:
    """Score readiness plus deterministic downstream blocking impact."""
    by_id = {step.step_id: step for step in request.steps}
    downstream_count = {step.step_id: 0 for step in request.steps}
    for step in request.steps:
        for dep in step.depends_on:
            downstream_count[dep] += 1

    max_downstream = max(downstream_count.values(), default=0)
    scores: dict[str, float] = {}
    for step in request.steps:
        unresolved = any(by_id[dep].status not in {"completed", "ready"} for dep in step.depends_on)
        readiness = 0.0 if unresolved else 60.0
        blocking = 40.0 * (downstream_count[step.step_id] / max_downstream) if max_downstream else 0.0
        scores[step.step_id] = round(readiness + blocking, 6)
    return scores


def _level(score: float) -> str:
    if score >= 90.0:
        return "critical"
    if score >= 70.0:
        return "high"
    if score >= 40.0:
        return "medium"
    return "low"


def _confidence(request: PriorityRequest) -> float:
    """Confidence measures completeness of priority signals, not correctness."""
    signals = 0
    total = len(request.steps) * 3  # urgency, deadline, importance
    for step in request.steps:
        signals += step.urgency is not None
        signals += step.deadline is not None
        signals += step.importance is not None
    if request.priority_reference_time is None:
        # Deadline signals cannot be used for proximity without a supplied reference.
        total += len(request.steps)
    else:
        total += 0
    base = signals / total if total else 0.0
    structural = 0.20 if any(step.depends_on for step in request.steps) else 0.10
    return round(min(1.0, 0.70 * base + structural), 6)


def prioritize_plan(request: PriorityRequest) -> PriorityResponse:
    """Calculate deterministic priority metadata without modifying or executing the plan."""
    dependency_scores = _dependency_scores(request)
    prioritized: list[PrioritizedStep] = []

    for step in request.steps:
        urgency_score = URGENCY_SCORES[step.urgency] if step.urgency else 50.0
        deadline_score = _deadline_score(step.deadline, request.priority_reference_time)
        required_score = 100.0 if step.required else 0.0
        importance_score = step.importance if step.importance is not None else 50.0
        dependency_score = dependency_scores[step.step_id]

        final = (
            urgency_score * WEIGHTS["urgency"]
            + deadline_score * WEIGHTS["deadline"]
            + required_score * WEIGHTS["required"]
            + dependency_score * WEIGHTS["dependency"]
            + importance_score * WEIGHTS["importance"]
        )
        final = round(max(0.0, min(100.0, final)), 6)

        blocked = any(
            next(s for s in request.steps if s.step_id == dep).status != "completed"
            for dep in step.depends_on
        )

        prioritized.append(
            PrioritizedStep(
                step_id=step.step_id,
                title=step.title,
                priority_score=final,
                priority_level=_level(final),
                urgency=step.urgency,
                required=step.required,
                blocked=blocked,
                depends_on=list(step.depends_on),
                original_order=step.order,
                score_breakdown=ScoreBreakdown(
                    urgency_score=round(urgency_score, 6),
                    deadline_score=round(deadline_score, 6),
                    required_score=round(required_score, 6),
                    dependency_score=round(dependency_score, 6),
                    importance_score=round(importance_score, 6),
                    final_score=final,
                ),
            )
        )

    # Deterministic tie-breaking: score, readiness, required, original order, step_id.
    by_id = {step.step_id: step for step in request.steps}
    prioritized.sort(
        key=lambda item: (
            -item.priority_score,
            item.blocked,
            not item.required,
            item.original_order,
            item.step_id,
        )
    )

    counts = {level: sum(item.priority_level == level for item in prioritized) for level in ("critical", "high", "medium", "low")}
    explicit_signal_count = sum(
        step.urgency is not None or step.deadline is not None or step.importance is not None
        for step in request.steps
    )
    if explicit_signal_count == 0:
        status = "partially_prioritized"
    else:
        status = "prioritized"

    return PriorityResponse(
        request_id=request.request_id,
        plan_id=request.plan_id,
        goal=request.goal,
        prioritized_steps=prioritized,
        total_steps=len(prioritized),
        critical_count=counts["critical"],
        high_count=counts["high"],
        medium_count=counts["medium"],
        low_count=counts["low"],
        priority_status=status,
        priority_confidence=_confidence(request),
    )
