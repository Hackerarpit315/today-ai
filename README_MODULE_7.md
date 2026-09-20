# Module 7 — Priority Engine

## 1. What Module 7 does

The Priority Engine receives an existing structured plan and calculates deterministic priority metadata for every step. It answers **"What should be done first?"** without executing, modifying, or completing any task.

The module is standalone. Its router is intentionally **not** registered in `app/main.py` during this phase.

## 2. Why Priority is separate from Planning

Planning determines **which steps are needed and their dependency order**. Priority determines **which existing steps deserve attention first**. Module 7 does not redesign the plan or invent new steps.

## 3. Input schema

`PriorityRequest` contains:

- `request_id`: UUID
- `goal`: non-empty string
- `plan_id`: non-empty string
- `steps`: one or more strict plan steps
- `time_reference`: optional descriptive time reference
- `constraints`: optional list or string dictionary
- `priority_reference_time`: optional timezone-aware timestamp used only for deterministic deadline proximity

Each step contains:

- `step_id`, `title`, `description`, `order`
- `required`
- `depends_on`
- `status`
- optional `urgency` (`critical`, `high`, `medium`, `low`)
- optional timezone-aware `deadline`
- optional `importance` from 0 to 100

All schemas use `ConfigDict(extra="forbid")`. Step IDs are unique and dependencies must refer to existing steps.

## 4. Output schema

The response preserves:

- `request_id`
- `plan_id`
- `goal`

It returns ordered `prioritized_steps`, counts for each priority level, `priority_status`, and deterministic `priority_confidence`.

Each prioritized step preserves its identity and includes:

- priority score and level
- urgency
- required flag
- blocked flag
- dependencies
- original order
- transparent score breakdown

## 5. Priority factors

The score uses five supplied/derived factors:

| Factor | Weight |
|---|---:|
| Urgency | 30% |
| Deadline proximity | 25% |
| Required status | 20% |
| Dependency / blocking impact | 15% |
| Importance | 10% |

No factor is guessed when it is absent. Neutral values are used where required.

## 6. Priority formula

Each component is normalized to 0–100:

`final_score = 0.30*urgency + 0.25*deadline + 0.20*required + 0.15*dependency + 0.10*importance`

The final score is clamped to 0–100 and rounded deterministically.

Neutral defaults:

- missing urgency → 50
- missing deadline or missing reference time → 50
- required → 100; optional → 0
- missing importance → 50

## 7. Urgency mapping

- `critical` → 100
- `high` → 75
- `medium` → 50
- `low` → 25

No urgency is invented when the field is absent.

## 8. Deadline handling

Deadline proximity is calculated only when both a step deadline and `priority_reference_time` are supplied. Both must be timezone-aware.

- overdue / due now → 100
- within 24 hours → 80
- within 72 hours → 60
- within 7 days → 40
- more than 7 days away → 20

Without an explicit deadline or reference time, the deadline component is neutral (50). The module never reads the current clock or internet data.

## 9. Required / optional handling

Required steps receive 100 for the required component. Optional steps receive 0. Required status therefore matters, but it does not automatically determine the final ranking.

## 10. Dependency handling

Dependency score combines readiness and downstream blocking impact:

- ready contribution: 60 when all dependencies are completed/ready, otherwise 0
- blocking contribution: up to 40 based on the number of direct downstream steps relative to the most blocking step in the plan

This means a prerequisite that blocks several steps can receive additional priority.

## 11. Blocked task handling

A step is `blocked=true` when it has a dependency whose status is not `completed`. A blocked step still receives a score based on its own signals; blocked status is not used to erase its priority score.

Priority and execution readiness are separate concepts.

## 12. Priority level thresholds

- 90–100 → `critical`
- 70–89.999999 → `high`
- 40–69.999999 → `medium`
- 0–39.999999 → `low`

The boundaries are fixed and deterministic.

## 13. Tie-breaking rules

After descending priority score, ties are resolved by:

1. dependency readiness (`blocked=false` first)
2. required status (required first)
3. original plan order (ascending)
4. `step_id` (ascending)

No randomness is used.

## 14. Insufficient-information behavior

The engine never invents urgency, deadlines, or importance.

If no explicit urgency, deadline, or importance is supplied, the result is still deterministic but `priority_status` is `partially_prioritized`. Explicit priority signals produce `prioritized`.

## 15. Determinism

The same validated input produces the same output. The implementation uses no LLM, ML model, random values, external API, web search, database, Supabase, n8n, or current internet data.

`priority_confidence` is a deterministic measure of signal completeness, not the probability that a priority is objectively correct.

## 16. Limitations

- Deadline proximity requires an explicit reference timestamp; the engine does not use the current time.
- Natural-language deadlines are not interpreted by this module.
- Importance must be supplied as a numeric 0–100 value when available.
- The engine does not infer real-world urgency from task wording.
- It does not execute, notify, schedule, browse, pay, or mark work complete.

## 17. Why external services are disabled

This module is intentionally a pure priority calculation component. External services would make its behavior less isolated and could introduce nondeterminism, side effects, or execution responsibilities that belong to later modules.

## 18. How to run tests

From the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_priority.py
```

The router can be tested independently by creating a small FastAPI app and calling `app.include_router` on `app.api.routes.priority.router`. It is not globally registered yet.
