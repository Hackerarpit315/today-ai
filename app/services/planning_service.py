"""Deterministic, side-effect-free Planning Engine."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from app.schemas.planning import (
    AvailableStep,
    PlanStep,
    PlanningRequest,
    PlanningResponse,
)

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
        "from", "has", "have", "how", "in", "into", "is", "it", "of", "on", "or",
        "the", "this", "to", "what", "when", "where", "which", "with", "you",
    }
)


@dataclass(frozen=True)
class _StepDraft:
    key: str
    title: str
    description: str
    required: bool
    depends_on_keys: tuple[str, ...] = ()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_PATTERN.findall(text.casefold())
        if len(token) > 2 and token not in _STOP_WORDS
    }


def _value_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {value[key]}" for key in sorted(value))
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value)
    return str(value)


def _has_any(tokens: set[str], *words: str) -> bool:
    return bool(tokens.intersection(words))


def _information_keys(payload: PlanningRequest) -> set[str]:
    keys: set[str] = set()
    for item in payload.verified_information:
        keys.update(_tokens(item.key))
        keys.update(_tokens(_value_text(item.value)))
    return keys


def _constraint_text(payload: PlanningRequest) -> str:
    parts = [f"{item.key}: {_value_text(item.value)}" for item in payload.constraints]
    if payload.time_reference:
        parts.append(f"time_reference: {payload.time_reference}")
    return "; ".join(parts)


_MULTI_STEP_ACTIONS = frozenset(
    {
        "learn", "study", "prepare", "master", "build", "develop",
        "organize", "implement", "migrate", "launch", "improve",
        "practice", "train", "plan",
    }
)
_SIMPLE_TASK_INTENTS = frozenset({"task", "reminder", "command"})


def _is_multi_step_goal(payload: PlanningRequest, tokens: set[str]) -> bool:
    """Identify broad outcome-oriented goals without depending on a domain-specific example."""
    if tokens.intersection(_MULTI_STEP_ACTIONS):
        return True
    if payload.time_reference and any(
        marker in payload.time_reference.casefold()
        for marker in ("day", "days", "week", "weeks", "month", "months")
    ) and len(tokens) >= 3:
        return True
    return False


def _simple_task_draft(payload: PlanningRequest) -> _StepDraft:
    """Represent a directly actionable task as one non-executing step."""
    title = payload.goal.strip().rstrip(".!?")
    description = "Complete the task described by the goal without executing it."
    if payload.time_reference:
        description = f"Complete this task at the requested time: {payload.time_reference}."
    return _StepDraft("simple-task", title, description, True)


def _explicit_steps(payload: PlanningRequest) -> list[_StepDraft]:
    drafts: list[_StepDraft] = []
    for index, step in enumerate(payload.available_steps, start=1):
        key = step.step_id or f"custom-{index}"
        drafts.append(
            _StepDraft(
                key=key,
                title=step.title,
                description=step.description,
                required=step.required,
                depends_on_keys=tuple(step.depends_on),
            )
        )
    return drafts


def _derive_steps(payload: PlanningRequest) -> list[_StepDraft]:
    """Create a minimal plan from goal, intent and supplied information."""
    tokens = _tokens(f"{payload.goal} {payload.intent}")
    info_keys = _information_keys(payload)
    drafts: list[_StepDraft] = []

    has_documents = _has_any(
        info_keys,
        "document", "documents", "aadhaar", "passport", "certificate", "marksheet",
        "id", "proof", "photo", "signature", "upload",
    )
    has_portal = _has_any(info_keys, "url", "portal", "website", "link")
    is_admission = _has_any(tokens, "admission", "application", "apply", "form", "enroll", "registration")
    is_booking = _has_any(tokens, "book", "booking", "reserve", "reservation")
    is_purchase = _has_any(tokens, "buy", "purchase", "order", "shopping")
    is_research = _has_any(tokens, "research", "compare", "find", "investigate", "analyze")

    # Direct task/reminder/command goals are represented as one actionable
    # planning step unless the structured goal clearly describes a broader
    # outcome that naturally requires multiple stages.
    if payload.intent.casefold() in _SIMPLE_TASK_INTENTS and not _is_multi_step_goal(payload, tokens):
        return [_simple_task_draft(payload)]

    if is_admission:
        drafts.extend(
            [
                _StepDraft("confirm-requirements", "Confirm the requirements", "Review the supplied requirements and constraints before starting.", True),
                _StepDraft("collect-documents", "Collect required documents", "Gather the documents identified by the supplied information.", True, ("confirm-requirements",)),
            ]
        )
        if has_portal or "portal" in tokens or "website" in tokens:
            drafts.append(_StepDraft("open-portal", "Open the application portal", "Use the supplied portal information when it is available.", True, ("confirm-requirements",)))
        drafts.append(_StepDraft("enter-information", "Enter applicant information", "Prepare the required information for the application form.", True, ("confirm-requirements",)))
        if has_documents:
            drafts.append(_StepDraft("upload-documents", "Upload required documents", "Prepare and upload the supplied required documents.", True, ("collect-documents", "enter-information")))
            review_deps = ("enter-information", "upload-documents")
        else:
            review_deps = ("enter-information",)
        drafts.append(_StepDraft("review", "Review the completed information", "Check the prepared application for missing or inconsistent information.", True, review_deps))
        drafts.append(_StepDraft("prepare-submission", "Prepare for final submission", "Make the application ready for the final submission action without executing it.", True, ("review",)))
        return drafts

    if is_booking:
        return [
            _StepDraft("confirm-details", "Confirm booking requirements", "Review the supplied booking details, constraints, and timing.", True),
            _StepDraft("select-option", "Select the required option", "Choose the option that satisfies the supplied goal and constraints.", True, ("confirm-details",)),
            _StepDraft("review", "Review the booking details", "Check the selected option and supplied details before confirmation.", True, ("select-option",)),
            _StepDraft("prepare-confirmation", "Prepare for confirmation", "Make the booking ready for the final confirmation action without executing it.", True, ("review",)),
        ]

    if is_purchase:
        return [
            _StepDraft("confirm-requirements", "Confirm purchase requirements", "Review the supplied product, budget, and other constraints.", True),
            _StepDraft("select-item", "Select the required item", "Choose an item that satisfies the supplied requirements.", True, ("confirm-requirements",)),
            _StepDraft("review", "Review the purchase details", "Check the selected item and supplied purchase information.", True, ("select-item",)),
            _StepDraft("prepare-order", "Prepare the order", "Prepare the order for the final action without placing it.", True, ("review",)),
        ]

    if is_research:
        return [
            _StepDraft("define-question", "Define the research question", "Clarify the supplied goal and constraints before reviewing evidence.", True),
            _StepDraft("review-evidence", "Review the supplied evidence", "Review the information already supplied to the planner.", True, ("define-question",)),
            _StepDraft("compare-findings", "Compare the relevant findings", "Compare the supplied findings against the goal.", True, ("review-evidence",)),
            _StepDraft("prepare-result", "Prepare the research result", "Prepare a structured result without performing additional research.", True, ("compare-findings",)),
        ]

    # Generic fallback: never invent domain-specific facts.
    return [
        _StepDraft("identify-requirements", "Identify the required requirements", "Determine what information or prerequisites are needed for the supplied goal.", True),
        _StepDraft("gather-information", "Gather the required information", "Collect the information already identified as necessary.", True, ("identify-requirements",)),
        _StepDraft("perform-main-task", "Prepare the main task", "Prepare the main task described by the goal without executing an external action.", True, ("gather-information",)),
        _StepDraft("review", "Review the prepared plan", "Check the prepared work against the supplied goal and constraints.", True, ("perform-main-task",)),
    ]


def _order_drafts(drafts: list[_StepDraft]) -> list[_StepDraft]:
    """Topologically order steps while preserving original order for ties."""
    by_key = {draft.key: draft for draft in drafts}
    original_index = {draft.key: index for index, draft in enumerate(drafts)}
    normalized: dict[str, tuple[str, ...]] = {}
    for draft in drafts:
        normalized[draft.key] = tuple(dep for dep in draft.depends_on_keys if dep in by_key and dep != draft.key)

    ordered: list[_StepDraft] = []
    remaining = set(by_key)
    while remaining:
        ready = [
            key for key in remaining
            if all(dep not in remaining for dep in normalized[key])
        ]
        if not ready:
            # Deterministic cycle fallback: preserve original order and break the cycle.
            key = min(remaining, key=lambda item: original_index[item])
            ready = [key]
        ready.sort(key=lambda item: original_index[item])
        for key in ready:
            ordered.append(by_key[key])
            remaining.remove(key)
    return ordered


def _plan_id(payload: PlanningRequest) -> str:
    canonical = payload.model_dump(mode="json")
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"plan-{digest}"


def _confidence(payload: PlanningRequest, step_count: int) -> float:
    """Calculate transparent deterministic planning confidence."""
    if step_count == 0:
        return 0.0
    score = 0.45
    if payload.verified_information:
        score += min(0.25, 0.05 * len(payload.verified_information))
    if payload.constraints or payload.time_reference:
        score += 0.10
    if payload.available_steps:
        score += 0.15
    if len(payload.verified_information) >= 2:
        score += 0.05
    return round(min(1.0, max(0.0, score)), 6)


def create_plan(payload: PlanningRequest) -> PlanningResponse:
    """Generate a deterministic, non-executing plan."""
    drafts = _explicit_steps(payload) if payload.available_steps else _derive_steps(payload)
    drafts = _order_drafts(drafts)

    key_to_id = {draft.key: f"step-{index:03d}" for index, draft in enumerate(drafts, start=1)}
    steps: list[PlanStep] = []
    for index, draft in enumerate(drafts, start=1):
        dependencies = [key_to_id[dep] for dep in draft.depends_on_keys if dep in key_to_id]
        status = "ready" if not dependencies else "blocked"
        steps.append(
            PlanStep(
                step_id=key_to_id[draft.key],
                title=draft.title,
                description=draft.description,
                order=index,
                required=draft.required,
                depends_on=dependencies,
                status=status,
            )
        )

    required_steps = sum(1 for step in steps if step.required)
    has_specific_signal = bool(
        payload.verified_information
        or payload.constraints
        or payload.time_reference
        or payload.available_steps
        or _has_any(_tokens(f"{payload.goal} {payload.intent}"), "admission", "application", "booking", "purchase", "research", "compare")
    )
    if not has_specific_signal:
        planning_status = "partially_planned"
    elif payload.available_steps or payload.verified_information or payload.constraints:
        planning_status = "planned"
    else:
        planning_status = "partially_planned"

    return PlanningResponse(
        request_id=payload.request_id,
        goal=payload.goal,
        plan_id=_plan_id(payload),
        steps=steps,
        total_steps=len(steps),
        required_steps=required_steps,
        planning_confidence=_confidence(payload, len(steps)),
        planning_status=planning_status,
    )
