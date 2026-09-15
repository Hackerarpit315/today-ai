"""Standalone tests for Module 3 Context Engine."""

from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.context import router as context_router


# Intentionally do not import app.main: Module 3 must be independently testable.
app = FastAPI()
app.include_router(context_router)
client = TestClient(app)


def make_payload(**overrides):
    payload = {
        "request_id": str(uuid4()),
        "intent": "task",
        "goal": "Complete Python assignment",
        "entities": {},
        "time_reference": None,
        "confidence": 0.9,
        "available_context": [],
    }
    payload.update(overrides)
    return payload


def context(context_id, content, context_type="note", tags=None):
    return {
        "context_id": context_id,
        "content": content,
        "context_type": context_type,
        "tags": tags or [],
    }


def test_relevant_context_is_selected():
    payload = make_payload(
        available_context=[
            context("c1", "Python assignment is due tomorrow"),
            context("c2", "Buy vegetables"),
        ]
    )

    response = client.post("/api/context", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert [item["context_id"] for item in body["relevant_context"]] == ["c1"]
    assert body["context_used"] is True


def test_irrelevant_context_is_excluded():
    payload = make_payload(
        intent="study",
        goal="Study networking",
        available_context=[context("c1", "Buy vegetables")],
    )

    response = client.post("/api/context", json=payload)

    assert response.status_code == 200
    assert response.json()["relevant_context"] == []
    assert response.json()["context_used"] is False


def test_higher_relevance_gets_higher_priority():
    payload = make_payload(
        available_context=[
            context("low", "Python notes"),
            context("high", "Complete Python assignment before Python exam"),
        ]
    )

    response = client.post("/api/context", json=payload)

    assert response.status_code == 200
    assert [item["context_id"] for item in response.json()["relevant_context"]] == [
        "high",
        "low",
    ]


def test_equal_relevance_preserves_original_order():
    payload = make_payload(
        available_context=[
            context("first", "Python notes"),
            context("second", "Python tutorial"),
            context("third", "Python book"),
        ]
    )

    response = client.post("/api/context", json=payload)

    assert response.status_code == 200
    assert [item["context_id"] for item in response.json()["relevant_context"]] == [
        "first",
        "second",
        "third",
    ]


def test_empty_available_context_works_correctly():
    response = client.post("/api/context", json=make_payload(available_context=[]))

    assert response.status_code == 200
    assert response.json()["relevant_context"] == []
    assert response.json()["context_used"] is False
    assert response.json()["confidence"] == 0.0


def test_request_id_is_preserved():
    request_id = str(uuid4())

    response = client.post(
        "/api/context", json=make_payload(request_id=request_id)
    )

    assert response.status_code == 200
    assert response.json()["request_id"] == request_id
    UUID(response.json()["request_id"])


def test_confidence_remains_between_zero_and_one():
    payload = make_payload(
        confidence=0.25,
        available_context=[context("c1", "Python assignment")],
    )

    response = client.post("/api/context", json=payload)

    assert response.status_code == 200
    assert 0.0 <= response.json()["confidence"] <= 1.0


def test_invalid_confidence_is_rejected():
    for value in (-0.01, 1.01):
        response = client.post(
            "/api/context", json=make_payload(confidence=value)
        )
        assert response.status_code == 422


def test_unexpected_fields_are_rejected():
    payload = make_payload(extra="not allowed")

    response = client.post("/api/context", json=payload)

    assert response.status_code == 422


def test_same_input_produces_exactly_the_same_output():
    request_id = str(uuid4())
    payload = make_payload(
        request_id=request_id,
        available_context=[
            context("c1", "Python assignment is due tomorrow"),
            context("c2", "Buy vegetables"),
        ],
    )

    first = client.post("/api/context", json=payload)
    second = client.post("/api/context", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
