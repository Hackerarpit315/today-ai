# Module 10 — Action Engine

Module 10 executes only actions that have already passed the Module 9 permission decision.

## Boundaries

- No LLM/OpenAI/Gemini/Claude.
- No browser automation.
- No external API calls.
- No database/Supabase.
- No real n8n webhook.
- No shell/subprocess/eval/exec.
- No real email, messaging, calendar, payment, or destructive system operation.

## Adapters

- `LocalActionAdapter`: controlled local/in-memory representations and draft preparation.
- `DryRunAdapter`: validates/dispatches a preview without performing side effects.
- `N8NActionAdapter`: future contract only. It returns the payload that would be sent to n8n and explicitly reports that no network call occurred.

## API

`POST /api/action`

The route is standalone and is intentionally not registered in `app/main.py` yet.

## Permission gate

When `permission_required` is true, execution requires:

1. `permission_state == "granted"`
2. `approval_valid == true`
3. `permission_scope` and `requested_scope` to match

Otherwise the request is blocked before adapter selection.

## Execution identity

`execution_id` is a deterministic UUID derived from `request_id` and `action_id`. This keeps standalone tests reproducible.

## Future architecture

Module 10 → n8n adapter → future n8n webhook → external services → Module 11 verification.

The current implementation does not make the external hop.
