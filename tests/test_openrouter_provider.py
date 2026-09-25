from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.llm.openrouter_provider import (
    DEFAULT_OPENROUTER_MODEL,
    OPENROUTER_BASE_URL,
    OpenRouterProvider,
    OpenRouterProviderError,
    _StructuredModelOutput,
)
from app.llm.schemas import LLMRequest, LLMResponse


CURRENT = datetime(2026, 9, 25, 8, 20, tzinfo=timezone.utc)


def make_request() -> LLMRequest:
    return LLMRequest(
        request_id=uuid4(),
        user_input="Mujhe kal college jana hai.",
        current_datetime=CURRENT,
    )


class FakeMessage:
    def __init__(self, parsed):
        self.parsed = parsed


class FakeChoice:
    def __init__(self, parsed):
        self.message = FakeMessage(parsed)


class FakeResponse:
    def __init__(self, parsed):
        self.choices = [FakeChoice(parsed)]


class FakeCompletions:
    def __init__(self, parsed=None, error=None):
        self.parsed = parsed
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)

        if self.error:
            raise self.error

        return FakeResponse(self.parsed)


class FakeChat:
    def __init__(self, parsed=None, error=None):
        self.completions = FakeCompletions(
            parsed=parsed,
            error=error,
        )


class FakeClient:
    def __init__(self, parsed=None, error=None):
        self.chat = FakeChat(
            parsed=parsed,
            error=error,
        )


def valid_output():
    return {
        "intent": "task",
        "goal": "Go to college",
        "entities": {
            "person": [],
            "place": ["college"],
            "organization": [],
            "date": [],
            "time": [],
            "topic": [],
        },
        "time_reference": "tomorrow",
        "confidence": 0.95,
        "reasoning_summary": "The user expressed a future task.",
    }


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv(
        "OPENROUTER_API_KEY",
        raising=False,
    )

    provider = OpenRouterProvider(
        client=FakeClient(valid_output())
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="OPENROUTER_API_KEY is not configured",
    ):
        provider.generate(make_request())


def test_environment_api_key(monkeypatch):
    monkeypatch.setenv(
        "OPENROUTER_API_KEY",
        "test-key",
    )

    provider = OpenRouterProvider(
        client=FakeClient(valid_output())
    )

    assert provider._api_key == "test-key"


def test_custom_api_key():
    provider = OpenRouterProvider(
        api_key="custom-test-key",
        client=FakeClient(valid_output()),
    )

    assert provider._api_key == "custom-test-key"


def test_default_model():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(valid_output()),
    )

    assert provider._model == DEFAULT_OPENROUTER_MODEL
    assert provider._model == "openrouter/free"


def test_custom_model():
    provider = OpenRouterProvider(
        api_key="test-key",
        model="custom/model",
        client=FakeClient(valid_output()),
    )

    assert provider._model == "custom/model"


def test_default_base_url():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(valid_output()),
    )

    assert provider._base_url == OPENROUTER_BASE_URL


def test_successful_response():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(valid_output()),
    )

    response = provider.generate(make_request())

    assert isinstance(response, LLMResponse)
    assert response.intent == "task"
    assert response.goal == "Go to college"
    assert response.entities == {"place": ["college"]}
    assert response.time_reference == "tomorrow"
    assert response.confidence == 0.95


def test_request_id_preserved():
    request = make_request()

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(valid_output()),
    )

    response = provider.generate(request)

    assert response.request_id == request.request_id


def test_request_construction():
    client = FakeClient(valid_output())

    provider = OpenRouterProvider(
        api_key="test-key",
        model="test-model",
        client=client,
    )

    provider.generate(make_request())

    call = client.chat.completions.calls[0]

    assert call["model"] == "test-model"
    assert call["response_format"] is _StructuredModelOutput
    assert len(call["messages"]) == 2
    assert call["messages"][1]["content"] == (
        "Mujhe kal college jana hai."
    )


def test_invalid_structured_response():
    invalid = valid_output()
    invalid["confidence"] = 2.0

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(invalid),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="invalid structured output",
    ):
        provider.generate(make_request())


def test_api_failure():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            error=RuntimeError("simulated API failure")
        ),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="OpenRouter provider request failed",
    ):
        provider.generate(make_request())


def test_missing_structured_output():
    class EmptyClient:
        class Chat:
            class Completions:
                def parse(self, **kwargs):
                    class Response:
                        choices = []

                    return Response()

            completions = Completions()

        chat = Chat()

    provider = OpenRouterProvider(
        api_key="test-key",
        client=EmptyClient(),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="no choices",
    ):
        provider.generate(make_request())


def test_llm_response_validation():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(valid_output()),
    )

    response = provider.generate(make_request())

    validated = LLMResponse.model_validate(
        response.model_dump()
    )

    assert validated == response


def test_structured_schema_forbids_extra_properties():
    schema = _StructuredModelOutput.model_json_schema()

    assert schema["additionalProperties"] is False

    entities_ref = schema["properties"]["entities"]["$ref"]
    entities_name = entities_ref.split("/")[-1]

    entities_schema = schema["$defs"][entities_name]

    assert entities_schema["additionalProperties"] is False