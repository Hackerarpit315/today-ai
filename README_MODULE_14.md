# Module 14 — Security Engine

Standalone deterministic security-control layer for Today AI.

## Boundary
- No `app/main.py` changes.
- No integration with Modules 1–13.
- No action execution, shell execution, network requests, browser automation, LLM, database, n8n, or external APIs.
- Decisions mean **passed the implemented security policy**, not guaranteed safety.

## Implemented
- Secret/credential detection without returning detected values.
- HTTP/HTTPS-only URL validation, URL length and embedded-credential checks.
- Heuristic command, script, and path-traversal detection.
- Deterministic payload/resource limits.
- Pattern-based email, phone and card-like data-exposure detection.
- Deterministic action-risk classification and independent permission/security policy checks.
- Request UUID/schema validation through strict Pydantic models.
- Safe sanitization only for content that is not security-sensitive; unsafe transformations are blocked.
- Stable policy version `1.0` and deterministic threat ordering.

## API
- `POST /api/security/check`
- `POST /api/security/url`
- `POST /api/security/action`

The router is intentionally not registered in `app/main.py` yet.

## Limitations
Rule/regex detection is heuristic. Data-exposure detection is pattern based. URL validation does not establish that a destination is trustworthy. Absence of a detected threat is not a guarantee of safety. Some command/script patterns can produce false positives or false negatives.

## Test
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_security.py
```
