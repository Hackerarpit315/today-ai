# Module 6 — Planning Engine

## 1. What Module 6 does

The Planning Engine converts a structured goal plus supplied verified information into an ordered, dependency-aware plan. It answers **what needs to be done and in what order**.

It produces a plan only. It does not execute the plan.

## 2. Why Planning is separate from Research

Research finds relevant information. Planning turns the information already supplied to it into steps. Keeping these responsibilities separate makes the planner deterministic and independently testable.

## 3. Why Planning is separate from Verification

Module 5 is responsible for checking consistency of supplied evidence. Module 6 treats `verified_information` as input data and does not independently verify it or claim real-world truth.

## 4. Input schema

`PlanningRequest` contains:

- `request_id`
- `goal`
- `intent`
- `entities`
- optional `time_reference`
- `verified_information`
- optional `constraints`
- optional `available_steps`

All models use strict `ConfigDict(extra="forbid")` validation.

## 5. Output schema

`PlanningResponse` contains:

- `request_id`
- `goal`
- deterministic `plan_id`
- ordered `steps`
- `total_steps`
- `required_steps`
- `planning_confidence`
- `planning_status`

## 6. Step structure

Each step contains:

- `step_id`
- `title`
- `description`
- `order`
- `required`
- `depends_on`
- `status`

Statuses are `ready`, `blocked`, or `pending`. The initial implementation marks dependency-free steps as `ready` and dependent steps as `blocked`; no status is updated by real-world execution.

## 7. Dependency logic

Dependencies are represented using step IDs. The service performs deterministic topological ordering. If a dependency cycle is supplied, a deterministic original-order fallback prevents non-termination; the planner still does not execute anything.

## 8. Ordering logic

Domain-aware rule templates cover common admission/application, booking, purchase, and research goals. The generic fallback uses requirements → information gathering → main-task preparation → review. Explicit dependencies always take priority over template order.

## 9. Required/optional logic

Explicit `available_steps` preserve their supplied `required` value. Inferred steps are conservative and required by default. The planner does not invent domain-specific requirements. Supplied optional information is preserved as optional input metadata.

## 10. Constraint handling

Constraints and `time_reference` are preserved as planner inputs and affect deterministic planning confidence. The planner does not invent deadlines, budgets, locations, documents, URLs, or policies.

## 11. Confidence calculation

`planning_confidence` is an explainable deterministic score. It increases when the request contains supplied verified information, constraints/time references, or explicit steps. It is a planning-quality signal, not a probability that the plan will succeed in the real world.

## 12. Insufficient-information behavior

When a goal lacks domain-specific information, the planner uses only generic high-level preparation steps. It does not invent specific documents, fees, deadlines, websites, or policies. Requests with no specific signal are marked `partially_planned` rather than pretending the plan is fully informed.

## 13. Limitations

This initial implementation is rule-based. It does not understand arbitrary natural-language dependencies, execute actions, or perform semantic/LLM planning. Complex domains may need additional deterministic templates later.

## 14. Why external services are disabled

Module 6 intentionally has no web, HTTP, browser, n8n, OpenAI, LLM, database, Supabase, notification, payment, calendar, or autonomous-action access. This keeps the module deterministic and independently testable.

## 15. How to run tests

From the project root:

```text
.\\.venv\\Scripts\\python.exe -m pytest -q tests/test_planning.py
```

The standalone route is `POST /api/plan`, but it is intentionally not registered in `app/main.py` yet.
