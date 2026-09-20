"""Deterministic, non-executing Today Engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.schemas.today import (
    TodayRequest,
    TodayResponse,
    TodaySummary,
    TodayTask,
    TodayTaskStatus,
    TodayTaskView,
)


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _same_local_date(left: datetime, right: datetime) -> bool:
    """Compare calendar dates in the timezone supplied by current_datetime."""
    return left.astimezone(right.tzinfo).date() == right.date()


def _is_completed(task: TodayTask) -> bool:
    return task.status == TodayTaskStatus.completed


def _build_view(
    task: TodayTask,
    *,
    current_datetime: datetime,
    by_id: dict[str, TodayTask],
) -> TodayTaskView:
    deadline_utc = _utc(task.deadline) if task.deadline is not None else None
    current_utc = _utc(current_datetime)
    overdue = bool(deadline_utc is not None and deadline_utc < current_utc and not _is_completed(task))
    due_today = bool(
        task.deadline is not None
        and task.deadline.astimezone(current_datetime.tzinfo).date() == current_datetime.date()
        and not _is_completed(task)
    )
    dependencies_incomplete = any(not _is_completed(by_id[dep]) for dep in task.depends_on)
    blocked = bool(not _is_completed(task) and (task.blocked or dependencies_incomplete))

    if _is_completed(task):
        status = TodayTaskStatus.completed
    elif blocked:
        status = TodayTaskStatus.blocked
    elif overdue:
        status = TodayTaskStatus.overdue
    elif due_today or task.is_today or task.scheduled_date == current_utc.date() or task.required:
        status = TodayTaskStatus.ready
    else:
        status = TodayTaskStatus.pending

    return TodayTaskView(
        step_id=task.step_id,
        title=task.title,
        description=task.description,
        priority_score=task.priority_score,
        priority_level=task.priority_level,
        urgency=task.urgency,
        required=task.required,
        status=status,
        blocked=blocked,
        overdue=overdue,
        due_today=due_today,
        depends_on=list(task.depends_on),
        original_order=task.original_order,
        deadline=task.deadline,
    )


def _is_explicit_today(task: TodayTask, current_datetime: datetime) -> bool:
    today = _utc(current_datetime).date()
    return task.is_today or task.scheduled_date == today


def _base_relevance(task: TodayTask, current_datetime: datetime, by_id: dict[str, TodayTask]) -> bool:
    if _is_completed(task):
        return False
    now = _utc(current_datetime)
    deadline = _utc(task.deadline) if task.deadline else None
    due_today = deadline is not None and deadline.date() == now.date()
    overdue = deadline is not None and deadline < now
    explicit_today = _is_explicit_today(task, current_datetime)
    future_deadline = deadline is not None and deadline.date() > now.date()

    if overdue or due_today or explicit_today:
        return True
    if future_deadline:
        return False

    # A required task without a future deadline is actionable today only when
    # the supplied dependency/blocking signals say it is currently actionable.
    deps_complete = all(_is_completed(by_id[dep]) for dep in task.depends_on)
    return task.required and not task.blocked and deps_complete


def _select_today_tasks(request: TodayRequest) -> set[str]:
    tasks = request.input_tasks
    by_id = {task.step_id: task for task in tasks}
    selected = {
        task.step_id
        for task in tasks
        if _base_relevance(task, request.current_datetime, by_id)
    }

    # If a selected task needs incomplete dependencies, include those dependencies
    # as today's blocking/unblocking work. This is the only case where a clearly
    # future-dated dependency can enter the daily view.
    changed = True
    while changed:
        changed = False
        for step_id in tuple(selected):
            task = by_id[step_id]
            for dep_id in task.depends_on:
                dep = by_id[dep_id]
                if not _is_completed(dep) and dep_id not in selected:
                    selected.add(dep_id)
                    changed = True
    return selected


def _rank_key(view: TodayTaskView) -> tuple:
    # Overdue first, then due today, then score, ready before blocked,
    # required before optional, original plan order, and stable step_id.
    return (
        not view.overdue,
        not view.due_today,
        -view.priority_score,
        view.blocked,
        not view.required,
        view.original_order,
        view.step_id,
    )


def _dependency_aware_order(views: list[TodayTaskView]) -> list[TodayTaskView]:
    by_id = {view.step_id: view for view in views}
    dependents: dict[str, list[str]] = defaultdict(list)
    indegree = {view.step_id: 0 for view in views}
    for view in views:
        for dep in view.depends_on:
            if dep in by_id:
                dependents[dep].append(view.step_id)
                indegree[view.step_id] += 1

    ready = sorted((sid for sid, degree in indegree.items() if degree == 0), key=lambda sid: _rank_key(by_id[sid]))
    ordered: list[TodayTaskView] = []
    while ready:
        current = ready.pop(0)
        ordered.append(by_id[current])
        for dependent in sorted(dependents[current], key=lambda sid: _rank_key(by_id[sid])):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
        ready.sort(key=lambda sid: _rank_key(by_id[sid]))

    # The request validator rejects cycles, so this is defensive only.
    if len(ordered) != len(views):
        remaining = [view for view in views if view.step_id not in {x.step_id for x in ordered}]
        ordered.extend(sorted(remaining, key=_rank_key))
    return ordered


def build_today(request: TodayRequest) -> TodayResponse:
    """Create a daily view without executing, mutating, or externally calling anything."""
    tasks = request.input_tasks
    by_id = {task.step_id: task for task in tasks}
    selected_ids = _select_today_tasks(request)

    today_views: list[TodayTaskView] = []
    completed_views: list[TodayTaskView] = []
    for task in tasks:
        view = _build_view(task, current_datetime=request.current_datetime, by_id=by_id)
        if _is_completed(task):
            # Completed tasks are retained separately when they are relevant to
            # today's view (explicitly today, due today, overdue, or required).
            if (
                _is_explicit_today(task, request.current_datetime)
                or (task.deadline is not None and _same_local_date(task.deadline, request.current_datetime))
                or task.required
            ):
                completed_views.append(view)
        elif task.step_id in selected_ids:
            today_views.append(view)

    today_views = _dependency_aware_order(today_views)
    completed_views.sort(key=lambda item: (item.original_order, item.step_id))

    ready_count = sum(not item.blocked for item in today_views)
    blocked_count = sum(item.blocked for item in today_views)
    overdue_count = sum(item.overdue for item in today_views)
    due_today_count = sum(item.due_today for item in today_views)
    completed_count = len(completed_views)
    high_count = sum(item.priority_level in {"high", "critical"} for item in today_views)
    critical_count = sum(item.priority_level == "critical" for item in today_views)

    if not tasks:
        today_status = "insufficient_information"
    elif not today_views and completed_count == len(tasks):
        today_status = "partially_planned"
    elif not today_views:
        today_status = "partially_planned"
    else:
        today_status = "planned"

    actionable = [item for item in today_views if not item.blocked]
    actionable.sort(key=lambda item: _rank_key(item))
    next_task = actionable[0] if actionable else None

    summary = TodaySummary(
        total_today_tasks=len(today_views),
        ready_count=ready_count,
        blocked_count=blocked_count,
        overdue_count=overdue_count,
        due_today_count=due_today_count,
        completed_count=completed_count,
        high_priority_count=high_count,
        critical_priority_count=critical_count,
    )

    return TodayResponse(
        request_id=request.request_id,
        plan_id=request.plan_id,
        goal=request.goal,
        current_datetime=request.current_datetime,
        today_tasks=today_views,
        completed_tasks=completed_views,
        total_today_tasks=len(today_views),
        ready_count=ready_count,
        blocked_count=blocked_count,
        overdue_count=overdue_count,
        due_today_count=due_today_count,
        completed_count=completed_count,
        high_priority_count=high_count,
        critical_priority_count=critical_count,
        today_status=today_status,
        summary=summary,
        next_task=next_task,
    )
