from __future__ import annotations

import ast
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.llm import LLMProvider, LLMProviderError, LLMRequest, LLMResponse, MockLLMProvider, OpenAIProvider


CURRENT = datetime(2026, 9, 25, 8, 20, tzinfo=timezone.utc)


def make_request(text: str = "Mujhe kal college jana hai.") -> LLMRequest:
    return LLMRequest(request_id=uuid4(), user_input=text, current_datetime=CURRENT)


class FakeResponse:
    def __init__(self, parsed):
        self.output_parsed = parsed


class FakeResponses:
    def __init__(self, parsed=None, error=None):
        self.parsed = parsed
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeResponse(self.parsed)


class FakeClient:
    def __init__(self, parsed=None, error=None):
        self.responses = FakeResponses(parsed=parsed, error=error)


def valid_model_output():
    return {
        "intent": "task",
        "goal": "Go to college",
        "entities": {},
        "time_reference": "tomorrow",
        "confidence": 0.95,
        "reasoning_summary": "The user expressed a future task.",
    }


def test_provider_implements_interface():
    assert issubclass(OpenAIProvider, LLMProvider)
    assert isinstance(OpenAIProvider(api_key="test-key", client=FakeClient(valid_model_output())).generate(make_request()), LLMResponse)


def test_missing_api_key_fails_safely(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIProvider(client=FakeClient(valid_model_output()))
    with pytest.raises(LLMProviderError, match="OPENAI_API_KEY is not configured"):
        provider.generate(make_request())


def test_api_client_invocation_is_correct():
    client = FakeClient(valid_model_output())
    provider = OpenAIProvider(api_key="test-key", model="test-model", client=client)
    provider.generate(make_request())
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["text_format"].__name__ == "_StructuredModelOutput"
    assert call["input"][1]["content"] == "Mujhe kal college jana hai."


def test_request_id_is_preserved():
    request_id = uuid4()
    request = LLMRequest(request_id=request_id, user_input="hello", current_datetime=CURRENT)
    response = OpenAIProvider(api_key="test-key", client=FakeClient(valid_model_output())).generate(request)
    assert response.request_id == request_id


def test_valid_structured_output_becomes_llm_response():
    response = OpenAIProvider(api_key="test-key", client=FakeClient(valid_model_output())).generate(make_request())
    assert response.intent == "task"
    assert response.goal == "Go to college"
    assert response.entities == {}
    assert response.time_reference == "tomorrow"
    assert response.confidence == 0.95


def test_malformed_model_output_is_rejected():
    malformed = {"intent": "task", "goal": "x"}
    with pytest.raises(LLMProviderError, match="invalid structured output"):
        OpenAIProvider(api_key="test-key", client=FakeClient(malformed)).generate(make_request())


def test_invalid_confidence_is_rejected():
    invalid = valid_model_output()
    invalid["confidence"] = 1.5
    with pytest.raises(LLMProviderError, match="invalid structured output"):
        OpenAIProvider(api_key="test-key", client=FakeClient(invalid)).generate(make_request())


def test_provider_api_failure_is_safe():
    secret = "sk-test-secret-that-must-not-leak"
    client = FakeClient(error=RuntimeError(f"upstream failed with {secret}"))
    with pytest.raises(LLMProviderError) as exc_info:
        OpenAIProvider(api_key=secret, client=client).generate(make_request())
    assert str(exc_info.value) == "OpenAI provider request failed"
    assert secret not in str(exc_info.value)


def test_timeout_is_safe():
    client = FakeClient(error=TimeoutError("simulated timeout"))
    with pytest.raises(LLMProviderError, match="OpenAI provider request failed"):
        OpenAIProvider(api_key="test-key", client=client).generate(make_request())


def test_api_key_is_not_hardcoded():
    source = Path(__file__).resolve().parents[1] / "app" / "llm" / "openai_provider.py"
    text = source.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "OPENAI_API_KEY" in text


def test_no_shell_subprocess_eval_or_exec():
    source = Path(__file__).resolve().parents[1] / "app" / "llm" / "openai_provider.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    forbidden_modules = {"subprocess", "os.system", "commands"}
    forbidden_calls = {"system", "popen", "eval", "exec", "compile"}
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules or alias.name.split(".")[0] == "subprocess":
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "subprocess":
            violations.append(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
            violations.append(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_calls:
            violations.append(node.func.attr)
    assert not violations, violations


def test_existing_mock_provider_still_works():
    response = MockLLMProvider().generate(make_request())
    assert response.intent == "task"
    assert response.goal == "Go to college"
