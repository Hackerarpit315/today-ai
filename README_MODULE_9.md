# Module 9 — Permission Engine

## 1. Purpose
Module 9 deterministically decides whether an intended action requires explicit user authorization. It never executes actions.

## 2. Separation from Action Engine
Permission is policy; execution belongs to Module 10. Module 9 does not know how an action is performed.

## 3. Philosophy
Consequential actions are denied-by-default until a valid, scoped approval exists. Silence, pending approval, or an unrelated approval is never treated as authorization.

## 4. Categories
Supported categories: information, navigation, read, draft, communication, account_change, form_preparation, form_submission, financial, purchase, deletion, authentication, privacy_sensitive, external_side_effect, unknown.

## 5. Risk levels
Information/navigation/read/draft are low when non-external. Explicit external targets can make otherwise low actions medium. Communication, account changes, submissions, authentication, privacy-sensitive and external side effects are high. Financial, purchase, deletion, and irreversible actions are critical. Unknown actions are high.

## 6. Permission states
`not_required`, `required`, `granted`, `denied`, `expired`, `invalid`, `pending`.

## 7. Scope
A scope includes action type and optional target/target type. One-time approvals are bound to `action_id`. Reusable approvals must explicitly set `reusable=true` and `one_time=false`.

## 8. Approval validation
An approved permission is valid only when its action type and supplied scope match the request. One-time approvals also require the exact action ID. Expired approvals are invalid/expired. Denials always remain denied.

## 9. External side effects
Sending, submitting, changing accounts, publishing, and other externally consequential actions require approval unless an explicit trusted policy permits them.

## 10. Reversibility
Supported values are reversible, partially_reversible, irreversible, and unknown. Irreversible actions are critical. Unknown reversibility is handled conservatively.

## 11. Financial actions
Payments, purchases, transfers, subscriptions, refunds, and financial account changes require explicit permission and are critical by default.

## 12. Communication
Drafting is distinct from sending. Sending email/SMS/WhatsApp or posting publicly is high risk and requires explicit approval by default.

## 13. Forms
Preparing/filling a form is distinct from submitting it. Submission is an external side effect and requires explicit approval.

## 14. Deletion
Deletion is critical and requires explicit approval.

## 15. Authentication
Authentication actions are classified conservatively. This module never stores, requests, exposes, or processes passwords, OTPs, private keys, or other secrets.

## 16. Privacy-sensitive actions
Explicit privacy-sensitive actions require permission unless an exact trusted policy allows them.

## 17. Unknown actions
Unknown action types produce `unknown`, high risk, permission required, and cannot be silently allowed.

## 18. Decision logic
Classification -> risk -> policy requirement -> approval validation -> final state. Low/medium bypass is possible only through the explicitly supplied policy.

## 19. Consistency
A required action with invalid/missing approval is never granted. A denied approval is denied. Unknown actions are never `not_required`.

## 20. Determinism
No LLM, OpenAI, external API, database, web, randomness, or system clock is used. Optional approval expiry is evaluated only against caller-supplied timezone-aware `current_datetime`.

## 21. API
Standalone router: `POST /api/permission` in `app/api/routes/permission.py`. It is intentionally not registered in `app/main.py` yet.

## 22. Limitations
This is a policy decision component, not an operating-system permission manager, identity provider, secret store, or execution engine. Integration with Module 10 is intentionally deferred.

## 23. Tests
Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_permission.py
```

The tests are isolated and do not require Modules 1–8 or the complete application to start.
