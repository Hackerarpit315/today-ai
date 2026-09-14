# Today AI — Module 1 (Input Layer)

HTTP API that receives, validates, normalizes, identifies, and returns user input. It does **not** interpret intent, call an LLM, store data, or authenticate.

## Setup

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```text
uvicorn app.main:app --reload
```

`POST /api/input` with JSON:

```json
{ "input_type": "text", "content": "Mujhe kal 10 baje reminder laga dena." }
```

Success response includes a server-generated `request_id`, the normalized `content`, `input_type`, and `status: "accepted"`.

Module 1 accepts `input_type` `text` only. Known types `url`, `image`, `file`, and `voice_transcript` return 400. Unknown types return 422.

## Limits (environment)

| Variable | Default |
|---|---|
| `TODAY_AI_MAX_CONTENT_LENGTH` | 10000 characters |
| `TODAY_AI_MAX_REQUEST_BODY_BYTES` | 65536 bytes |

Oversized content and bodies are rejected (413), never truncated. Requests must use `Content-Type: application/json` (415 otherwise).

## Tests

```text
pytest
```

## Security notes

All input is treated as untrusted data. The service does not execute input, call outbound HTTP, or persist content. Logs include method, path, status, and `request_id` only — not raw content. Auth is not implemented; `get_current_principal` is a no-op dependency slot for a later module.
