# Today AI — Integration / Orchestrator Phase

## Scope

This integration layer connects the existing Modules 1–8 without rewriting their business logic:

1. Input
2. Intent
3. Context
4. Research
5. Verification
6. Planning
7. Priority
8. Today

Modules 9–15 are intentionally not integrated in this phase.

## Created files

- `app/orchestrator/__init__.py`
- `app/orchestrator/schemas.py`
- `app/orchestrator/pipeline.py`
- `tests/test_orchestrator.py`
- `README_INTEGRATION.md`

## Explicit context

The pipeline requires:

- an explicit `request_id`
- user text
- a timezone-aware `current_datetime`
- optional explicitly supplied context items
- optional explicitly supplied research sources

No machine clock is read by the orchestrator.

## Error behavior

The pipeline stops at the first failing stage. Completed stage results remain available, later stages are not called, and a bounded structured error is returned without a stack trace.

## Research boundary

The Research Engine is called only with caller-supplied sources. The orchestrator does not browse, fetch URLs, or make HTTP requests.

## Execution boundary

No actions are executed. Modules 9–15 are not called.

## Testing

Integration tests: 38.

Target command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The supplied project archive used for validation contains one pre-existing failure in `tests/test_input.py` caused by the existing `OpenAI` organization name being matched by that test's forbidden-string scan. The orchestrator itself passes all 38 integration tests and does not introduce that string or modify the existing module.

## Limitations

- Priority signals such as urgency, deadlines, and importance are not invented when Modules 6 does not provide them.
- Verification only evaluates the evidence returned from the explicitly supplied research sources.
- This is an integration layer, not production readiness or full application integration.
