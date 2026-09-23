# Module 15 — JARVIS UI / Voice Layer

Standalone presentation and conversation layer for Today AI. It provides deterministic in-memory sessions, immutable messages, safe presentation validation, structured assistant responses, system/UI state, future voice interfaces, and a mock backend.

## Boundary
- Does not modify or register in `app/main.py`.
- Does not execute actions or approve permissions.
- Does not replace Module 14 security authority.
- No LLM, network, database, SQLite, Redis, Supabase, n8n, or external voice service.

## Session/history
Sessions belong to one `user_id`. Closed and paused sessions reject new messages. History is capped deterministically; newest messages are retained and older non-system messages are removed first. No arbitrary update/delete operations are exposed for messages.

## Voice
`VoiceInputProvider.transcribe(audio_reference)` and `VoiceOutputProvider.synthesize(text)` are interfaces only. Mock providers return placeholders; no microphone/audio service is used.

## Backend
`ConversationBackend` is the future integration boundary. `MockConversationBackend` returns the deterministic message `Aapka request receive ho gaya.` and never claims external execution.

## Frontend
A lightweight plain HTML/CSS/JS JARVIS-style frontend is included. It is a static presentation artifact and does not require external assets or network access.

## Security/presentation limits
Basic secret-pattern rejection prevents obvious passwords, OTPs, API keys, tokens, bearer tokens and private-key blocks from being stored through the conversation service. Module 14 remains authoritative. This layer does not claim complete security.

## Test
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ui.py
```
