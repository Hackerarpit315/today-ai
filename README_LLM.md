# LLM Intelligence Layer — Phase 2

Phase 2 adds the first real LLM provider behind the Phase 1 provider abstraction.

## Architecture

```text
LLMRequest
    -> LLMProvider
    -> OpenAIProvider
    -> LLMResponse
```

`MockLLMProvider` remains available for deterministic tests. `OpenAIProvider`
implements the same `LLMProvider` interface and is not connected to Actions,
n8n, Gmail, Calendar, Memory, Audit, UI, voice, or `/api/assistant`.

## Configuration

Set these environment variables locally:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_MODEL` defaults to `gpt-4o-mini` if it is not set. No API key is stored
in source code or tests.

## Structured output

The provider requests a structured Pydantic response and validates the returned
fields before constructing the existing `LLMResponse`. The application supplies
`request_id`; the model cannot change request identity.

## Error handling

Missing configuration, SDK problems, API/network failures, timeouts, refusals or
invalid structured output become safe `LLMProviderError` failures. Provider
exceptions and credentials are not copied into application error messages.

## Testing without an API key

The normal test suite uses mocked provider clients. No real OpenAI request is
made by pytest:

```text
python -m pytest tests/test_openai_provider.py -q
python -m pytest -q
```

## Manual real-provider smoke test

Only for local development, after setting `OPENAI_API_KEY`:

```python
from datetime import datetime, timezone
from uuid import uuid4
from app.llm import LLMRequest, OpenAIProvider

request = LLMRequest(
    request_id=uuid4(),
    user_input="Mujhe kal college jana hai.",
    current_datetime=datetime.now(timezone.utc),
)
response = OpenAIProvider().generate(request)
print(response.model_dump())
```

Do not paste API keys into source code, tests, README files, Git commits, or
chat messages. Never commit a real `.env` containing credentials.

## Scope and limitations

Phase 2 connects only the real LLM provider to the existing abstraction. It does
not integrate the provider with the Today AI orchestrator, `/api/assistant`,
Actions, n8n, Gmail, Calendar, browser automation, Memory, Audit, UI, or voice.
Model output remains untrusted structured data and cannot execute code or actions.
