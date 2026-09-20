# Module 8 — Today Engine

## 1. What Module 8 does

The Today Engine converts an already-prioritized task list into a deterministic daily execution view. It selects relevant tasks, marks them ready or blocked, preserves priority metadata, orders the selected tasks, and calculates a daily summary.

It **does not execute tasks**.

## 2. Why Today Engine is separate from Priority Engine

Module 7 answers **how important a task is**. Module 8 answers **whether that task belongs in today's view and what order the daily view should use**. Module 8 never recalculates `priority_score`, `priority_level`, or `urgency`.

## 3. Input schema

`TodayRequest` contains:

- `request_id`: UUID
- `plan_id`: non-empty string
- `goal`: non-empty string
- `current_datetime`: timezone-aware datetime
- exactly one of `tasks` or `prioritized_steps`: a list of prioritized task records (an empty list is valid)
- optional `constraints`

Each task contains `step_id`, `title`, `description`, `priority_score` (0–100), `priority_level`, `urgency`, `required`, `blocked`, `depends_on`, `original_order`, `status`, and optional `deadline`. Explicit Today signals are represented by `is_today` and/or `scheduled_date`.

All schemas use `ConfigDict(extra="forbid")`.

## 4. Output schema

`TodayResponse` preserves `request_id`, `plan_id`, `goal`, and `current_datetime`, then returns:

- `today_tasks`
- `completed_tasks`
- `total_today_tasks`
- `ready_count`
- `blocked_count`
- `overdue_count`
- `due_today_count`
- `completed_count`
- `high_priority_count`
- `critical_priority_count`
- `today_status`
- `summary`
- optional `next_task`

Each Today task preserves identity, description, priority data, dependency data, original order, and deadline while adding `overdue`, `due_today`, `blocked`, and derived daily `status`.

## 5. Current datetime handling

The caller must provide `current_datetime`. It must be timezone-aware. The service never calls the machine clock. Instant comparisons normalize aware datetimes to UTC. Calendar-date checks use the timezone supplied by `current_datetime`, so “today” means the caller’s explicit current calendar date.

## 6. Today task selection rules

An incomplete task is selected when at least one of these supplied signals applies:

1. its deadline is overdue;
2. its deadline falls on the calendar date represented by `current_datetime`;
3. `is_today` is true;
4. `scheduled_date` equals today's UTC calendar date;
5. it is required, has no future deadline, is not explicitly blocked, and all dependencies are completed.

A clearly future-dated task is excluded unless it is an incomplete dependency required to unblock an already-selected Today task.

No task or deadline is invented.

## 7. Future task handling

A clearly future-deadline task normally remains outside `today_tasks`. It remains in the supplied plan and is not deleted or modified.

## 8. Overdue task handling

An incomplete task is overdue when its timezone-normalized deadline is before `current_datetime`. It remains visible in the Today view and receives `overdue=true`. An overdue task is not automatically completed.

## 9. Due-today handling

An incomplete task whose deadline has the same calendar date as `current_datetime` in the `current_datetime` timezone receives `due_today=true` and is eligible for the Today view.

## 10. Completed task handling

A task with input status `completed` is never an active Today task. When it is explicitly Today-relevant (for example, `is_today`, today's deadline, or required), it can appear in `completed_tasks` with status preserved as `completed`.

## 11. Dependency handling

Dependencies are validated for uniqueness, existence, self-dependency, and cycles. An incomplete dependency makes the dependent task blocked. A selected task's incomplete dependencies are added to the daily view so the dependency chain is visible; this is the only mechanism that can pull a clearly future-dated dependency into Today.

## 12. Ready/blocked state

A non-completed Today task is blocked when its explicit `blocked` flag is true or at least one dependency is incomplete. Otherwise it is ready. The derived status is `blocked`, `overdue`, or `ready` as applicable. Overdue is also exposed independently through `overdue=true`.

## 13. Ordering algorithm

The service first computes a deterministic ranking key:

1. overdue tasks first;
2. due-today tasks next;
3. higher `priority_score` first;
4. ready tasks before blocked tasks;
5. required tasks before optional tasks;
6. lower `original_order` first;
7. `step_id` as final tie-breaker.

Then it applies a deterministic topological ordering. An incomplete dependency that is itself in `today_tasks` must appear before its dependent, regardless of the ordinary ranking key.

## 14. Priority preservation

Module 8 never recalculates priority. It copies the supplied `priority_score`, `priority_level`, and `urgency` exactly.

## 15. Summary calculation

Counts are calculated directly from the final daily view. `ready_count` counts Today tasks that are not blocked; `blocked_count` counts blocked Today tasks; overdue and due-today counts use their respective flags. High-priority count includes `high` and `critical`; critical count includes only `critical`.

## 16. Next-task logic

When implemented, `next_task` is selected from non-blocked Today tasks. The deterministic preference is overdue, then due today, then higher priority, then earlier plan order, with `step_id` as the final tie-breaker. If there is no actionable task, `next_task` is `null`.

## 17. Insufficient-information behavior

An empty task list produces `today_status="insufficient_information"`. A non-empty plan with no Today tasks produces `partially_planned`. When Today tasks can be safely classified, the status is `planned`.

## 18. Determinism

There is no random value, machine-clock access, LLM, ML model, external data, database, API, browser, n8n, OpenAI, or Supabase call. The same request produces the same response.

## 19. Limitations

This initial implementation cannot infer unstated schedules, estimate workload, invent deadlines, execute actions, or resolve ambiguous natural-language constraints. Instant comparison is performed in UTC, while calendar-date comparison uses the explicit `current_datetime` timezone.

## 20. Why external services are disabled

Module 8 is deliberately a pure daily-selection component. Keeping it free of external services makes tests reproducible and prevents a planning/view layer from accidentally performing actions.

## 21. How to run tests

From the project root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_today.py
```

The standalone router is available from `app/api/routes/today.py` at `POST /api/today`, but it is intentionally **not registered in `app/main.py` yet**.
