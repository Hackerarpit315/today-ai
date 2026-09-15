"""Standalone tests for Module 5 — Verification Engine."""

from copy import deepcopy
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.verification import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

REQUEST_ID = "00000000-0000-0000-0000-000000000001"


def result(source_id: str, content: str, relevance_score: float = 1.0) -> dict:
    return {
        "source_id": source_id,
        "title": f"Source {source_id}",
        "content": content,
        "source_type": "article",
        "relevance_score": relevance_score,
    }


def payload(results: list[dict]) -> dict:
    return {
        "request_id": REQUEST_ID,
        "query": "AKTU admission form deadline and application fee",
        "research_results": results,
    }


def test_valid_verification_request():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("one", "Application deadline is 30 September 2026."),
                result("two", "Applications close on 30 September 2026."),
            ]
        ),
    )
    assert response.status_code == 200
    assert response.json()["verification_status"] == "verified"


def test_uuid_is_preserved():
    body = payload([result("one", "Application deadline is 30 September 2026.")])
    body["request_id"] = "11111111-1111-1111-1111-111111111111"
    response = client.post("/api/verification", json=body)
    assert response.status_code == 200
    assert UUID(response.json()["request_id"]) == UUID(body["request_id"])


def test_multiple_agreeing_sources_are_verified():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("one", "Application fee is Rs 500."),
                result("two", "The application fee is Rs 500."),
            ]
        ),
    )
    body = response.json()
    assert body["verified"] is True
    assert body["conflict_detected"] is False
    assert body["supporting_sources"] == ["one", "two"]


def test_conflicting_dates_are_detected():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("one", "Application deadline is 30 September 2026."),
                result("two", "Application deadline is 15 October 2026."),
            ]
        ),
    )
    body = response.json()
    assert body["verified"] is False
    assert body["conflict_detected"] is True
    assert body["verification_status"] == "conflicting"


def test_conflicting_numbers_are_detected():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("one", "The examination has 100 questions."),
                result("two", "The examination has 120 questions."),
            ]
        ),
    )
    assert response.json()["conflict_detected"] is True


def test_conflicting_fees_are_detected():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("one", "Application fee is Rs 500."),
                result("two", "Application fee is Rs 1000."),
            ]
        ),
    )
    assert response.json()["verification_status"] == "conflicting"


def test_conflicting_deadlines_are_detected():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("one", "Applications close on 30 September 2026."),
                result("two", "Applications close on 15 October 2026."),
            ]
        ),
    )
    body = response.json()
    assert body["conflict_detected"] is True
    assert set(body["conflicting_sources"]) == {"one", "two"}


def test_insufficient_evidence_for_single_factual_source():
    response = client.post(
        "/api/verification",
        json=payload([result("one", "Application deadline is 30 September 2026.")]),
    )
    body = response.json()
    assert body["verified"] is False
    assert body["verification_status"] == "insufficient_evidence"
    assert body["insufficient_claims"]


def test_single_source_without_extractable_fact_is_unverified_or_insufficient():
    response = client.post(
        "/api/verification",
        json=payload([result("one", "The admission process is available online.")]),
    )
    body = response.json()
    assert body["verified"] is False
    assert body["verification_status"] in {"insufficient_evidence", "unverified"}


def test_irrelevant_zero_relevance_source_is_ignored():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("irrelevant", "Application deadline is 1 January 2030.", 0.0),
                result("one", "Application deadline is 30 September 2026.", 1.0),
                result("two", "Application deadline is 30 September 2026.", 0.8),
            ]
        ),
    )
    body = response.json()
    assert body["verified"] is True
    assert "irrelevant" not in body["supporting_sources"]
    assert "irrelevant" not in body["conflicting_sources"]


def test_relevance_score_is_accepted_and_does_not_mean_truth():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("high", "Application fee is Rs 500.", 1.0),
                result("low", "Application fee is Rs 1000.", 0.1),
            ]
        ),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["conflict_detected"] is True


def test_output_is_deterministic():
    body = payload(
        [
            result("one", "Application deadline is 30 September 2026."),
            result("two", "Application deadline is 30 September 2026."),
        ]
    )
    first = client.post("/api/verification", json=body).json()
    second = client.post("/api/verification", json=deepcopy(body)).json()
    assert first == second


def test_confidence_stays_between_zero_and_one():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("one", "Application fee is Rs 500."),
                result("two", "Application fee is Rs 500."),
                result("three", "Application fee is Rs 500."),
            ]
        ),
    )
    confidence = response.json()["confidence"]
    assert 0.0 <= confidence <= 1.0


def test_extra_request_field_is_rejected():
    body = payload([result("one", "Application fee is Rs 500.")])
    body["unexpected"] = "not allowed"
    response = client.post("/api/verification", json=body)
    assert response.status_code == 422


def test_extra_research_result_field_is_rejected():
    body = payload([result("one", "Application fee is Rs 500.")])
    body["research_results"][0]["unexpected"] = "not allowed"
    response = client.post("/api/verification", json=body)
    assert response.status_code == 422


def test_invalid_uuid_is_rejected():
    body = payload([result("one", "Application fee is Rs 500.")])
    body["request_id"] = "not-a-uuid"
    response = client.post("/api/verification", json=body)
    assert response.status_code == 422


def test_empty_query_is_rejected():
    body = payload([result("one", "Application fee is Rs 500.")])
    body["query"] = "   "
    response = client.post("/api/verification", json=body)
    assert response.status_code == 422


def test_empty_source_content_is_rejected():
    body = payload([result("one", "Application fee is Rs 500.")])
    body["research_results"][0]["content"] = "   "
    response = client.post("/api/verification", json=body)
    assert response.status_code == 422


def test_invalid_relevance_score_is_rejected():
    body = payload([result("one", "Application fee is Rs 500.", 1.5)])
    response = client.post("/api/verification", json=body)
    assert response.status_code == 422


def test_multiple_claims_can_be_verified_together():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result(
                    "one",
                    "Application fee is Rs 500. Application deadline is 30 September 2026.",
                ),
                result(
                    "two",
                    "The application fee is Rs 500. Applications close on 30 September 2026.",
                ),
            ]
        ),
    )
    body = response.json()
    assert body["verified"] is True
    assert len(body["verified_claims"]) == 2


def test_equivalent_wording_with_same_date_agrees():
    response = client.post(
        "/api/verification",
        json=payload(
            [
                result("one", "Application deadline is 30 September 2026."),
                result("two", "Applications close on September 30, 2026."),
            ]
        ),
    )
    body = response.json()
    assert body["verified"] is True
    assert body["conflict_detected"] is False
