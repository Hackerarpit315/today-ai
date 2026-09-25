# Module 14 — Security Engine

Standalone deterministic security-control layer for Today AI.

## Existing implementation found

The uploaded project already contained a Module 14 implementation in:

- `app/schemas/security.py`
- `app/services/security_service.py`
- `app/api/routes/security.py`
- `app/services/security/__init__.py`
- `tests/test_security.py`

This refinement preserves that architecture rather than creating a duplicate security subsystem.

## Boundary

- `app/main.py` is unchanged.
- Modules 1–13 are not modified by Module 14.
- M14 does not execute actions or commands.
- No `eval()`, `exec()`, `os.system()`, subprocess execution, browser automation, n8n execution, email sending, calendar modification, or external network calls.
- M14 does not grant permissions. It only evaluates security policy against the authorization context supplied by the caller.
- M10 remains responsible for execution and M11 remains responsible for execution verification.

## Security controls

- Secret and credential detection for passwords, OTPs, API keys, access/refresh tokens, bearer tokens, JWT-like values, authorization values, and private-key markers.
- Command-injection, shell, script-injection, `eval`/`exec`-style, and path-traversal pattern detection.
- HTTP/HTTPS-only URL validation with embedded-credential and control-character rejection.
- Deterministic payload size, metadata size, nesting, and JSON-compatibility limits.
- Data-exposure detection for credential-like, email, phone, and payment-card-like values.
- Deterministic action-risk classification.
- Fail-closed authorization handling: `DENY` blocks, `REQUIRE_APPROVAL` produces `review_required`, contradictory authorization blocks, and missing authorization context does not become `allow`.
- Stable policy version `1.0` and deterministic threat ordering.
- Strict Pydantic request/response models with extra-field rejection.

## M13 audit integration

M14 provides `build_security_audit_event()` to convert a security decision into a secret-free `AuditEventCreateRequest` using the existing Module 13 audit schema.

The helper requires an explicit timestamp and does not persist anything itself. Callers can pass the resulting request to the existing `AuditService`/repository, including the existing SQLite repository, without introducing another database.

Security audit events use the existing `security_event` event type and contain only structured security-decision metadata. Detected secrets are never copied into the event.

## API

- `POST /api/security/check`
- `POST /api/security/url`
- `POST /api/security/action`

The router remains intentionally unregistered in `app/main.py`.

## Persistence

M14 does not create a database or persistence layer. Security events reuse the existing M13 Audit/Log Engine and its repository architecture when persistence is requested by a caller.

## Limitations

Detection is heuristic and rule based. Regex/pattern detection cannot provide complete security coverage and can have false positives or false negatives. URL validation checks syntax and allowed schemes; it does not establish that a destination is trustworthy. Absence of a detected threat is not a guarantee of safety. Authentication/session identity is not invented by M14 because the current project exposes only a placeholder principal and does not provide an authenticated security context.

## Verification

Focused M14 tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_security.py
```

The refined source snapshot was verified with 82 focused M14 tests, 72 M13 audit tests, 35 persistence tests, and 776 tests across the full suite.
