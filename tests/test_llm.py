from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.llm import LLMProvider, LLMRequest, LLMResponse, MockLLMProvider


CURRENT = datetime(2026, 9, 24, 18, 39, tzinfo=timezone.utc)


def make_request(text: str = "Mujhe kal college jana hai.") -> LLMRequest:
    return LLMRequest(request_id=uuid4(), user_input=text, current_datetime=CURRENT)


def test_valid_request():
    request = make_request()
    assert request.user_input == "Mujhe kal college jana hai."
    assert request.current_datetime.tzinfo is not None


def test_timezone_aware_datetime_required():
    with pytest.raises(ValidationError):
        LLMRequest(
            request_id=uuid4(),
            user_input="hello",
            current_datetime=datetime(2026, 9, 24, 10, 0),
        )


def test_deterministic_mock_response():
    request = make_request()
    provider = MockLLMProvider()
    first = provider.generate(request)
    second = provider.generate(request)
    assert first == second
    assert first.intent == "task"
    assert first.goal == "Go to college"
    assert first.time_reference == "tomorrow"
    assert first.confidence == 0.95


def test_request_id_is_preserved():
    request_id = uuid4()
    response = MockLLMProvider().generate(
        LLMRequest(
            request_id=request_id,
            user_input="hello",
            current_datetime=CURRENT,
        )
    )
    assert response.request_id == request_id


def test_structured_response_validation():
    response = LLMResponse(
        request_id=uuid4(),
        intent="task",
        goal="Go to college",
        entities={},
        time_reference="tomorrow",
        confidence=0.95,
        reasoning_summary="The user expressed a future task.",
    )
    assert response.model_dump()["entities"] == {}


def test_confidence_range_is_enforced():
    with pytest.raises(ValidationError):
        LLMResponse(
            request_id=uuid4(),
            intent="task",
            goal="test",
            entities={},
            confidence=1.1,
            reasoning_summary="test",
        )
    with pytest.raises(ValidationError):
        LLMResponse(
            request_id=uuid4(),
            intent="task",
            goal="test",
            entities={},
            confidence=-0.1,
            reasoning_summary="test",
        )


def test_malformed_input_rejected():
    with pytest.raises(ValidationError):
        LLMRequest(
            request_id=uuid4(),
            user_input="   ",
            current_datetime=CURRENT,
        )
    with pytest.raises(ValidationError):
        LLMRequest(
            request_id=uuid4(),
            user_input="hello",
            current_datetime=CURRENT,
            unexpected=True,
        )


def test_no_external_network_or_ai_sdk_dependencies():
    llm_root = Path(__file__).resolve().parents[1] / "app" / "llm"
    forbidden_roots = {
        "requests", "httpx", "aiohttp", "urllib3", "openai", "anthropic",
        "google", "langchain", "langgraph",
    }
    forbidden_calls = {"urlopen", "request", "system", "popen", "eval", "exec"}
    violations: list[str] = []

    for source_file in llm_root.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_roots:
                        violations.append(f"{source_file}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in forbidden_roots:
                    violations.append(f"{source_file}: import {node.module}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden_calls:
                    violations.append(f"{source_file}: call {node.func.attr}()")

    assert not violations, "\n".join(violations)


def test_no_dynamic_execution_constructs():
    llm_root = Path(__file__).resolve().parents[1] / "app" / "llm"
    violations: list[str] = []
    for source_file in llm_root.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "compile"}:
                violations.append(f"{source_file}: {node.func.id}()")
    assert not violations, "\n".join(violations)


def test_provider_interface_behavior():
    assert issubclass(MockLLMProvider, LLMProvider)
    assert LLMProvider.generate.__isabstractmethod__ is True
    provider = MockLLMProvider()
    assert isinstance(provider.generate(make_request()), LLMResponse)
