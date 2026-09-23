# Module 11 — Execution Verifier

## Purpose

Module 11 verifies whether an execution attempt reported by Module 10 actually has sufficient evidence of success or failure. It is a verifier only: it never executes the requested action.

Core principle:

> Action attempted is not the same as action succeeded.

## Boundaries

This standalone implementation does not modify `app/main.py`, Modules 1–10, or their tests. It makes no n8n, Gmail, Calendar, Telegram, browser, database, or other external calls. It uses no LLM and no machine clock.

## Verification states

- `verified_success` — sufficient action-specific evidence establishes completion.
- `verified_failure` — a controlled failure result establishes that the attempt failed.
- `unknown` — the available evidence is insufficient or contradictory for a success claim.
- `not_attempted` — Module 10 reports that execution was not attempted.
- `blocked` — the action was blocked before execution.

## Verification levels

- `direct` — direct controlled evidence of completion.
- `strong` — strong structured evidence, such as a valid prepared n8n payload.
- `weak` — limited/indirect evidence; it does not become verified success by itself.
- `none` — no useful completion evidence.

## Evidence model

`Evidence` contains:

- `evidence_type`
- `source`
- `reference_id`
- `status`
- `data`
- optional `timestamp`

Evidence is structured data only. Executable/secret-oriented fields such as shell commands, code, passwords, OTPs, private keys, and credentials are rejected.

## Action-specific verification

The verifier has deterministic rules for Module 10 actions:

- `no_op` — a controlled result can be verified directly.
- `dry_run` — successful dry-run completion can be verified, but `external_action_verified` remains false.
- `create_local_note` — requires a valid note identifier or equivalent evidence.
- `create_local_task` — requires a valid task identifier or equivalent evidence.
- `prepare_email_draft` / `prepare_message_draft` — verifies draft preparation only; it never means a message was sent.
- `open_url` — requires explicit browser evidence to claim the browser opened the URL. A prepared URL alone remains `unknown`.
- `record_action` — requires controlled record evidence.
- `n8n_dispatch_preview` — verifies payload preparation only; it never verifies the external workflow.

## Future n8n evidence

Future integrations can pass structured evidence such as an `external_execution` record from n8n. Module 11 currently consumes that evidence but never calls n8n itself.

For example, a future successful external execution could provide a provider reference such as `n8n_exec_123` or `gmail_message_123`. That evidence must be supplied to the verifier; it is never invented by the verifier.

## Failure handling

Malformed schemas are rejected by strict Pydantic models. Failed, blocked, unsupported, unknown, or insufficiently evidenced attempts are represented with structured verification results. Stack traces and implementation details are not exposed by the API route.

## Limitations

A standalone verifier cannot prove an external-world outcome without trustworthy external evidence. In particular, a Module 10 `executed` status is not sufficient by itself for external actions. This module therefore prefers `unknown` over an unsupported success claim.

## API

The standalone route is:

`POST /api/execution/verify`

It is intentionally not registered in `app/main.py` yet.
