# Module 12 — Memory Engine

Module 12 provides deterministic, structured memory management for Today AI.

## Scope

- Store, retrieve, update, forget, and list memory records.
- In-memory repository only.
- Strict Pydantic schemas.
- UUID memory IDs.
- Explicit timezone-aware `current_time`; no machine-clock business logic.
- Deterministic secret/credential rejection.
- User isolation.
- Duplicate and conflict detection.
- Expiration and temporary-memory handling.
- Versioning on updates/forget operations.

## Security boundary

This module does not execute external actions and does not call databases, Supabase,
n8n, browsers, Gmail, Calendar, external APIs, LLMs, shells, PowerShell, `eval`,
or `exec`. Credential-like data is rejected without returning the submitted secret.

## Files

- `app/schemas/memory.py`
- `app/services/memory_service.py`
- `app/api/routes/memory.py`
- `tests/test_memory.py`

The router is not registered in `app/main.py` yet.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_memory.py
```

## Future architecture

The repository is intentionally an interface-compatible in-memory layer so a later
SQLite/PostgreSQL/Supabase implementation can replace storage without moving memory
business rules into the API route.
