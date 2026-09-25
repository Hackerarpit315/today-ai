"""Tests for application-level LLM provider integration."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.routes.assistant import assistant
from app.llm.factory import (
    LLMProviderConfigurationError,
    create_llm_provider,
)
from app.llm.mock_provider import MockLLMProvider
from app.llm.openai_provider import OpenAIProvider, LLMProviderError
from app.llm.openrouter_provider import OpenRouterProvider, OpenRouterProviderError
from app.llm.schemas import LLMRequest
from app.main import app
from app.orchestrator.pipeline import Orchestrator

DT = datetime(2026, 9, 24, 8, tzinfo=timezone.utc)


def test_default_provider_is_mock(monkeypatch):
    monkeypatch.delenv("TODAY_AI_LLM_PROVIDER", raising=False)
    assert isinstance(create_llm_provider(), MockLLMProvider)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("mock", MockLLMProvider),
        ("openrouter", OpenRouterProvider),
        ("openai", OpenAIProvider),
    ],
)
def test_explicit_provider_selection(monkeypatch, name, expected):
    monkeypatch.setenv("TODAY_AI_LLM_PROVIDER", name)
    assert isinstance(create_llm_provider(), expected)


def test_invalid_provider_configuration_is_safe(monkeypatch):
    monkeypatch.setenv("TODAY_AI_LLM_PROVIDER", "secret-provider")
    with pytest.raises(LLMProviderConfigurationError, match="Unsupported LLM provider"):
        create_llm_provider()


def test_missing_openrouter_key_is_safe(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = create_llm_provider("openrouter")
    with pytest.raises(OpenRouterProviderError) as exc:
        provider.generate(
            LLMRequest(
                request_id=UUID("11111111-1111-4111-8111-111111111111"),
                user_input="hello",
                current_datetime=DT,
            )
        )
    assert str(exc.value) == "OPENROUTER_API_KEY is not configured"
    assert "sk-" not in str(exc.value).lower()


def test_missing_openai_key_is_safe(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = create_llm_provider("openai")
    with pytest.raises(LLMProviderError) as exc:
        provider.generate(
            LLMRequest(
                request_id=UUID("11111111-1111-4111-8111-111111111111"),
                user_input="hello",
                current_datetime=DT,
            )
        )
    assert str(exc.value) == "OPENAI_API_KEY is not configured"
    assert "sk-" not in str(exc.value).lower()


def test_assistant_defaults_to_mock_and_remains_backward_compatible(monkeypatch):
    monkeypatch.delenv("TODAY_AI_LLM_PROVIDER", raising=False)
    client = TestClient(app)
    response = client.post(
        "/api/assistant",
        json={
            "content": "Mujhe kal college jana hai.",
            "current_datetime": "2026-09-24T08:00:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["pipeline"]["intent"]["intent"] == "task"


def test_explicit_openrouter_is_injected_without_network_in_test(monkeypatch):
    calls = []

    class FakeProvider:
        def generate(self, request):
            calls.append(request)
            return type(
                "R",
                (),
                {
                    "request_id": request.request_id,
                    "intent": "information",
                    "goal": "Explain cybersecurity",
                    "entities": {},
                    "time_reference": None,
                    "confidence": 0.9,
                },
            )()

    monkeypatch.setenv("TODAY_AI_LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(
        "app.api.routes.assistant.create_llm_provider",
        lambda: FakeProvider(),
    )
    client = TestClient(app)
    response = client.post(
        "/api/assistant",
        json={
            "content": "Explain cybersecurity.",
            "current_datetime": "2026-09-24T08:00:00+00:00",
        },
    )
    assert response.status_code == 200
    assert response.json()["pipeline"]["intent"]["intent"] == "information"
    assert len(calls) == 1


def test_provider_failure_is_safe_and_does_not_execute_action(monkeypatch):
    class FailingProvider:
        def generate(self, request):
            raise OpenRouterProviderError("provider failure")

    monkeypatch.setattr(
        "app.api.routes.assistant.create_llm_provider",
        lambda: FailingProvider(),
    )
    client = TestClient(app)
    response = client.post(
        "/api/assistant",
        json={
            "content": "send an email",
            "current_datetime": "2026-09-24T08:00:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["current_stage"] == "intent"
    assert "provider failure" not in str(body)
    assert "action" not in str(body).lower()


def test_provider_failure_does_not_reach_deterministic_later_stages():
    calls = []

    class FailingProvider:
        def generate(self, request):
            calls.append("llm")
            raise OpenRouterProviderError("failure")

    result = Orchestrator(llm_provider=FailingProvider()).run(
        __import__("app.orchestrator.schemas", fromlist=["PipelineRequest"]).PipelineRequest(
            request_id=UUID("33333333-3333-4333-8333-333333333333"),
            text="execute something",
            current_datetime=DT,
        )
    )
    assert result.status == "failed"
    assert result.current_stage == "intent"
    assert list(result.stage_results) == ["input"]
    assert calls == ["llm"]


def test_no_api_key_is_returned_by_assistant_configuration_error(monkeypatch):
    monkeypatch.setenv("TODAY_AI_LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = TestClient(app)
    response = client.post(
        "/api/assistant",
        json={
            "content": "hello",
            "current_datetime": "2026-09-24T08:00:00+00:00",
        },
    )
    assert response.status_code == 200
    blob = response.text.lower()
    body = response.json()
    assert body["status"] == "failed"
    assert body["current_stage"] == "intent"
    assert "openrouter_api_key" not in blob
    assert "sk-" not in blob
    assert "api_key" not in blob


def test_orchestrator_accepts_injected_provider_without_changing_default_pipeline():
    class FakeProvider:
        def generate(self, request):
            return type(
                "R",
                (),
                {
                    "request_id": request.request_id,
                    "intent": "task",
                    "goal": "Prepare application",
                    "entities": {},
                    "time_reference": "tomorrow",
                    "confidence": 0.9,
                },
            )()

    result = Orchestrator(llm_provider=FakeProvider()).run(
        __import__("app.orchestrator.schemas", fromlist=["PipelineRequest"]).PipelineRequest(
            request_id=UUID("22222222-2222-4222-8222-222222222222"),
            text="prepare my application",
            current_datetime=DT,
        )
    )
    assert result.status == "success"
    assert result.intent["intent"] == "task"
    assert "action" not in result.stage_results
