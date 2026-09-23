# Module 13 — Audit / Log Engine

Standalone, deterministic audit recording and retrieval layer for Today AI.

## Files
- `app/schemas/audit.py`
- `app/services/audit_service.py`
- `app/api/routes/audit.py`
- `app/services/audit/repository.py`
- `app/services/audit/in_memory_repository.py`
- `app/services/audit/__init__.py`
- `tests/test_audit.py`

## Boundary
This module only creates, stores, retrieves, filters, searches, counts, and integrity-checks audit events. It does not execute actions, call external services, modify `app/main.py`, or integrate other modules.

## Storage
An in-memory repository is used. No database, Redis, SQLite, Supabase, filesystem persistence, or cloud storage is used.

## Security
Credential-like data is rejected before storage. Audit messages and metadata are never intended to carry passwords, OTPs, API keys, access/refresh tokens, private keys, or bearer credentials.

## Integrity
Each immutable event gets a SHA-256 integrity hash calculated from all protected event fields except `integrity_hash`. Verification recomputes the hash and detects protected-field tampering.

## API
The standalone router is under `/api/audit`. It is intentionally not registered in `app/main.py`.

## Test
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_audit.py
```
