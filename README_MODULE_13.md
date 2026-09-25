# Module 13 — Audit / Log Engine

Standalone, deterministic audit recording and retrieval layer for Today AI.

## Files
- `app/schemas/audit.py`
- `app/services/audit_service.py`
- `app/api/routes/audit.py`
- `app/services/audit/repository.py`
- `app/services/audit/in_memory_repository.py`
- `app/services/audit/__init__.py`
- `app/persistence/repositories/audit_repository.py`
- `tests/test_audit.py`

## Boundary
This module only creates, stores, retrieves, filters, searches, counts, and integrity-checks audit events. It does not execute actions, make permission decisions, call external services, or integrate other modules. `app/main.py` is intentionally unchanged.

## Storage
Audit storage is repository-based. The default `AuditService()` uses the in-memory repository for isolated tests. When the existing persistence configuration enables SQLite (`TODAY_AI_PERSISTENCE=sqlite` or `TODAY_AI_DB_PATH`), the persistence factory uses `SQLiteAuditRepository` and records survive service/repository recreation in the existing `audit_events` table. No second database system is created.

## Event integrity and immutability
Audit events are append-only: the repository exposes creation and retrieval, but no update/delete operation. Each event receives a SHA-256 integrity hash calculated from the protected event fields except `integrity_hash`. Verification recomputes the hash and detects protected-field tampering.

## Security
Credential-like data is rejected before storage, including secrets in structured metadata and audit text fields such as messages/reasons. Rejection messages do not echo the supplied secret. Repository failures are converted to a generic controlled recording error rather than exposing storage/driver details.

## Retrieval
Deterministic retrieval supports request/correlation IDs, module, event type, status, severity, actor, action/resource identifiers, optional user isolation, message/event-type/module search, deterministic timestamp+event-ID ordering, and bounded offset/limit pagination.

## API
The standalone router is under `/api/audit`. It is intentionally not registered in `app/main.py` yet.

## External services
No LLM, external HTTP API, browser, n8n, email, calendar, shell, `eval`, `exec`, or arbitrary subprocess capability is used by Module 13.

## Test
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_audit.py
```
