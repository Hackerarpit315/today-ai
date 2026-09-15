"""Standalone tests for Module 4 — Research Engine."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.research import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

REQUEST_ID = "00000000-0000-0000-0000-000000000001"


def source(
    source_id: str,
    title: str,
    content: str,
    source_type: str = "article",
) -> dict:
    return {
        "source_id": source_id,
        "title": title,
        "url": f"https://example.com/{source_id}",
        "content": content,
        "source_type": source_type,
    }


def base_request(sources: list[dict]) -> dict:
    return {
        "request_id": REQUEST_ID,
        "query": "AKTU admission form deadline",
        "intent": "research",
        "goal": "Find the AKTU admission form deadline",
        "entities": {"organization": "AKTU"},
        "sources": sources,
    }


def test_valid_research_request():
    response = client.post(
        "/api/research",
        json=base_request(
            [source("source-1", "AKTU Admission Form Deadline",
                    "AKTU admission form deadline and application dates.",
                    "official")]
        ),
    )

    assert response.status_code == 200
    assert response.json()["research_completed"] is True


def test_relevant_source_is_returned():
    response = client.post(
        "/api/research",
        json=base_request(
            [
                source(
                    "source-1",
                    "AKTU Admission Form Deadline",
                    "AKTU admission form deadline and application dates.",
                    "official",
                ),
                source("source-2", "Weather Report",
                       "Today's weather forecast.", "general"),
            ]
        ),
    )

    assert [item["source_id"] for item in response.json()["results"]] == ["source-1"]


def test_irrelevant_source_is_excluded():
    response = client.post(
        "/api/research",
        json=base_request(
            [source("source-2", "Weather Report", "Today's weather forecast.")]
        ),
    )

    body = response.json()
    assert body["results"] == []
    assert body["sources_found"] == 0
    assert body["confidence"] == 0.0


def test_higher_relevance_source_comes_first():
    response = client.post(
        "/api/research",
        json=base_request(
            [
                source("low", "AKTU admission", "AKTU admission information."),
                source(
                    "high",
                    "AKTU admission form deadline",
                    "AKTU admission form deadline application dates.",
                ),
            ]
        ),
    )

    results = response.json()["results"]
    assert results[0]["source_id"] == "high"
    assert results[0]["relevance_score"] > results[1]["relevance_score"]


def test_equal_relevance_preserves_original_order():
    response = client.post(
        "/api/research",
        json=base_request(
            [
                source("first", "AKTU admission", "Information about admission."),
                source("second", "AKTU admission", "Information about admission."),
            ]
        ),
    )

    results = response.json()["results"]
    assert [item["source_id"] for item in results] == ["first", "second"]


def test_matched_terms_are_returned_correctly():
    response = client.post(
        "/api/research",
        json=base_request(
            [
                source(
                    "source-1",
                    "AKTU Admission Form Deadline",
                    "AKTU admission form deadline and application dates.",
                    "official",
                )
            ]
        ),
    )

    matched = set(response.json()["results"][0]["matched_terms"])
    assert {"aktu", "admission", "form", "deadline"}.issubset(matched)


def test_relevance_score_stays_between_zero_and_one():
    response = client.post(
        "/api/research",
        json=base_request(
            [source("source-1", "AKTU admission form deadline",
                    "AKTU admission form deadline application dates.")]
        ),
    )

    for result in response.json()["results"]:
        assert 0.0 <= result["relevance_score"] <= 1.0


def test_confidence_stays_between_zero_and_one():
    response = client.post(
        "/api/research",
        json=base_request(
            [
                source("one", "AKTU admission", "AKTU admission"),
                source("two", "AKTU deadline", "AKTU deadline"),
                source("three", "AKTU form", "AKTU form"),
                source("four", "AKTU application", "AKTU application"),
            ]
        ),
    )

    confidence = response.json()["confidence"]
    assert 0.0 <= confidence <= 1.0
    assert confidence == 1.0


def test_empty_source_list_is_handled_correctly():
    response = client.post("/api/research", json=base_request([]))

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["sources_found"] == 0
    assert response.json()["research_completed"] is True
    assert response.json()["confidence"] == 0.0


def test_request_id_is_preserved():
    request_id = "11111111-1111-1111-1111-111111111111"
    payload = base_request(
        [source("source-1", "AKTU deadline", "AKTU deadline")]
    )
    payload["request_id"] = request_id

    response = client.post("/api/research", json=payload)

    assert response.status_code == 200
    assert UUID(response.json()["request_id"]) == UUID(request_id)


def test_invalid_request_is_rejected():
    payload = base_request([source("source-1", "AKTU", "AKTU")])
    payload["request_id"] = "not-a-uuid"

    response = client.post("/api/research", json=payload)

    assert response.status_code == 422


def test_extra_unexpected_fields_are_rejected():
    payload = base_request([source("source-1", "AKTU", "AKTU")])
    payload["unexpected"] = "not allowed"

    response = client.post("/api/research", json=payload)

    assert response.status_code == 422


def test_source_extra_fields_are_rejected():
    payload = base_request([source("source-1", "AKTU", "AKTU")])
    payload["sources"][0]["unexpected"] = "not allowed"

    response = client.post("/api/research", json=payload)

    assert response.status_code == 422


def test_invalid_url_is_rejected():
    payload = base_request([source("source-1", "AKTU", "AKTU")])
    payload["sources"][0]["url"] = "not-a-url"

    response = client.post("/api/research", json=payload)

    assert response.status_code == 422


def test_short_tokens_do_not_match():
    payload = base_request(
        [source("source-1", "AKTU", "Form", "official")]
    )
    payload["query"] = "AKTU"
    payload["intent"] = "research"
    payload["goal"] = "Find it"

    response = client.post("/api/research", json=payload)

    assert response.status_code == 200
    assert response.json()["results"][0]["matched_terms"] == ["aktu"]
