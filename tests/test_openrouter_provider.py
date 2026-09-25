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


CURRENT = datetime(
    2026,
    9,
    25,
    8,
    20,
    tzinfo=timezone.utc,
)


def make_request() -> LLMRequest:
    return LLMRequest(
        request_id=uuid4(),
        user_input="Mujhe kal college jana hai.",
        current_datetime=CURRENT,
    )


class FakeMessage:
    def __init__(
        self,
        parsed=None,
        content=None,
    ):
        self.parsed = parsed
        self.content = content


class FakeChoice:
    def __init__(
        self,
        parsed=None,
        content=None,
    ):
        self.message = FakeMessage(
            parsed=parsed,
            content=content,
        )


class FakeResponse:
    def __init__(
        self,
        parsed=None,
        content=None,
    ):
        self.choices = [
            FakeChoice(
                parsed=parsed,
                content=content,
            )
        ]


class FakeCompletions:
    def __init__(
        self,
        parsed=None,
        content=None,
        error=None,
    ):
        self.parsed = parsed
        self.content = content
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)

        if self.error:
            raise self.error

        return FakeResponse(
            parsed=self.parsed,
            content=self.content,
        )


class FakeChat:
    def __init__(
        self,
        parsed=None,
        content=None,
        error=None,
    ):
        self.completions = FakeCompletions(
            parsed=parsed,
            content=content,
            error=error,
        )


class FakeClient:
    def __init__(
        self,
        parsed=None,
        content=None,
        error=None,
    ):
        self.chat = FakeChat(
            parsed=parsed,
            content=content,
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
        "reasoning_summary": (
            "The user expressed a future task."
        ),
    }


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv(
        "OPENROUTER_API_KEY",
        raising=False,
    )

    provider = OpenRouterProvider(
        client=FakeClient(
            parsed=valid_output()
        )
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
        client=FakeClient(
            parsed=valid_output()
        )
    )

    assert provider._api_key == "test-key"


def test_custom_api_key():
    provider = OpenRouterProvider(
        api_key="custom-test-key",
        client=FakeClient(
            parsed=valid_output()
        ),
    )

    assert provider._api_key == "custom-test-key"


def test_default_model():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=valid_output()
        ),
    )

    assert provider._model == DEFAULT_OPENROUTER_MODEL
    assert provider._model == "openrouter/free"


def test_custom_model():
    provider = OpenRouterProvider(
        api_key="test-key",
        model="custom/model",
        client=FakeClient(
            parsed=valid_output()
        ),
    )

    assert provider._model == "custom/model"


def test_default_base_url():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=valid_output()
        ),
    )

    assert provider._base_url == OPENROUTER_BASE_URL


def test_successful_response():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=valid_output()
        ),
    )

    response = provider.generate(
        make_request()
    )

    assert isinstance(
        response,
        LLMResponse,
    )

    assert response.intent == "task"

    assert response.goal == "Go to college"

    assert response.entities == {
        "place": ["college"]
    }

    assert response.time_reference == "tomorrow"

    assert response.confidence == 0.95


def test_request_id_preserved():
    request = make_request()

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=valid_output()
        ),
    )

    response = provider.generate(request)

    assert response.request_id == request.request_id


def test_request_construction():
    client = FakeClient(
        parsed=valid_output()
    )

    provider = OpenRouterProvider(
        api_key="test-key",
        model="test-model",
        client=client,
    )

    provider.generate(
        make_request()
    )

    call = client.chat.completions.calls[0]

    assert call["model"] == "test-model"

    assert (
        call["response_format"]
        is _StructuredModelOutput
    )

    assert len(
        call["messages"]
    ) == 2

    assert call["messages"][1]["content"] == (
        "Mujhe kal college jana hai."
    )


def test_invalid_structured_response():
    invalid = valid_output()

    invalid["confidence"] = 2.0

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=invalid
        ),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="invalid structured output",
    ):
        provider.generate(
            make_request()
        )


def test_api_failure():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            error=RuntimeError(
                "simulated API failure"
            )
        ),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="OpenRouter provider request failed",
    ):
        provider.generate(
            make_request()
        )


def test_missing_structured_output():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=None,
            content=None,
        ),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="no structured result",
    ):
        provider.generate(
            make_request()
        )


def test_llm_response_validation():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=valid_output()
        ),
    )

    response = provider.generate(
        make_request()
    )

    validated = LLMResponse.model_validate(
        response.model_dump()
    )

    assert validated == response


def test_structured_schema_forbids_extra_properties():
    schema = (
        _StructuredModelOutput
        .model_json_schema()
    )

    assert (
        schema["additionalProperties"]
        is False
    )

    entities_ref = (
        schema["properties"]
        ["entities"]
        ["$ref"]
    )

    entities_name = (
        entities_ref.split("/")[-1]
    )

    entities_schema = (
        schema["$defs"]
        [entities_name]
    )

    assert (
        entities_schema["additionalProperties"]
        is False
    )


def test_parsed_structured_response():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=valid_output()
        ),
    )

    response = provider.generate(
        make_request()
    )

    assert response.intent == "task"

    assert response.goal == (
        "Go to college"
    )

    assert response.entities == {
        "place": ["college"]
    }


def test_content_structured_response_fallback():
    content = """
{
  "intent": "task",
  "goal": "Go to college",
  "entities": {
    "person": [],
    "place": ["college"],
    "organization": [],
    "date": ["kal"],
    "time": [],
    "topic": ["college"]
  },
  "time_reference": "tomorrow",
  "confidence": 0.95,
  "reasoning_summary": "The user expressed a future task."
}
"""

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            content=content
        ),
    )

    response = provider.generate(
        make_request()
    )

    assert response.intent == "task"

    assert response.goal == (
        "Go to college"
    )

    assert response.entities == {
        "place": ["college"],
        "date": ["kal"],
        "topic": ["college"],
    }

    assert (
        response.time_reference
        == "tomorrow"
    )


def test_content_structured_response_code_fence():
    content = """```json
{
  "intent": "task",
  "goal": "Go to college",
  "entities": {
    "person": [],
    "place": ["college"],
    "organization": [],
    "date": [],
    "time": [],
    "topic": []
  },
  "time_reference": "tomorrow",
  "confidence": 0.95,
  "reasoning_summary": "Future task."
}
```"""

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            content=content
        ),
    )

    response = provider.generate(
        make_request()
    )

    assert response.intent == "task"


def test_invalid_content_structured_output():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            content="not valid json"
        ),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="invalid structured output",
    ):
        provider.generate(
            make_request()
        )


def test_missing_content_structured_output():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=None,
            content=None,
        ),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="no structured result",
    ):
        provider.generate(
            make_request()
        )


def test_content_schema_validation():
    invalid = valid_output()
    invalid["confidence"] = 2.0

    import json

    content = json.dumps(
        invalid
    )

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            content=content
        ),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="invalid structured output",
    ):
        provider.generate(
            make_request()
        )


@pytest.mark.parametrize(
    (
        "user_input",
        "expected_intent",
    ),
    [
        (
            "Mujhe kal college jana hai.",
            "task",
        ),
        (
            "Mujhe assignment complete karna hai.",
            "task",
        ),
        (
            "Kal mujhe doctor ke paas jana hai.",
            "task",
        ),
        (
            "College kab khulta hai?",
            "information",
        ),
        (
            "College ke baare mein batao.",
            "information",
        ),
        (
            "What is the admission process?",
            "information",
        ),
        (
            "Rahul ko kal call karna hai.",
            "task",
        ),
    ],
)
def test_representative_intents(
    user_input,
    expected_intent,
):
    output = valid_output()
    output["intent"] = expected_intent

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=output
        ),
    )

    request = make_request()

    request = request.model_copy(
        update={
            "user_input": user_input
        }
    )

    response = provider.generate(
        request
    )

    assert (
        response.intent
        == expected_intent
    )


def test_mujhe_is_not_person_entity():
    output = valid_output()

    output["intent"] = "task"

    output["entities"] = {
        "person": [],
        "place": ["college"],
        "organization": [],
        "date": ["kal"],
        "time": [],
        "topic": ["college"],
    }

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=output
        ),
    )

    response = provider.generate(
        make_request()
    )

    assert response.intent == "task"

    assert "Mujhe" not in (
        response.entities.get(
            "person",
            [],
        )
    )


def test_rahul_can_be_person_entity():
    output = valid_output()

    output["intent"] = "task"

    output["entities"] = {
        "person": ["Rahul"],
        "place": [],
        "organization": [],
        "date": ["kal"],
        "time": [],
        "topic": [],
    }

    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            parsed=output
        ),
    )

    request = make_request()

    request = request.model_copy(
        update={
            "user_input": (
                "Rahul ko kal call karna hai."
            )
        }
    )

    response = provider.generate(
        request
    )

    assert response.intent == "task"

    assert response.entities[
        "person"
    ] == ["Rahul"]


def test_system_prompt_contains_semantic_intent_rules():
    client = FakeClient(
        parsed=valid_output()
    )

    provider = OpenRouterProvider(
        api_key="test-key",
        client=client,
    )

    provider.generate(
        make_request()
    )

    call = (
        client
        .chat
        .completions
        .calls[0]
    )

    system_prompt = (
        call["messages"][0]["content"]
    )

    assert (
        "Mujhe kal college jana hai."
        in system_prompt
    )

    assert '"task"' in system_prompt

    assert (
        '"information"'
        in system_prompt
    )

    assert "Mujhe" in system_prompt

    assert (
        "ordinary pronouns"
        in system_prompt
    )

    assert (
        "complete message"
        in system_prompt
    )

    assert (
        "execute actions"
        in system_prompt
    )


def test_provider_exception():
    provider = OpenRouterProvider(
        api_key="test-key",
        client=FakeClient(
            error=RuntimeError(
                "simulated API failure"
            )
        ),
    )

    with pytest.raises(
        OpenRouterProviderError,
        match="OpenRouter provider request failed",
    ):
        provider.generate(
            make_request()
        )