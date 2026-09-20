"""Standalone tests for Module 7 Priority Engine."""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes.priority import router
from app.schemas.priority import PriorityRequest
from app.services.priority_service import prioritize_plan

REQUEST_ID = "00000000-0000-0000-0000-000000000007"
REF = "2026-09-20T12:00:00+00:00"


def step(step_id="one", title="Prepare", order=1, **kwargs):
    data = {
        "step_id": step_id,
        "title": title,
        "order": order,
        "required": True,
        "depends_on": [],
        "status": "ready",
    }
    data.update(kwargs)
    return data


def make_request(**overrides):
    payload = {
        "request_id": REQUEST_ID,
        "goal": "Complete an admission application",
        "plan_id": "plan-007",
        "steps": [
            step("one", "Prepare documents", 1, urgency="high", importance=70),
            step("two", "Review application", 2, depends_on=["one"], urgency="medium", importance=60),
        ],
        "time_reference": "tomorrow",
        "constraints": ["budget limited"],
        "priority_reference_time": REF,
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_valid_priority_request(client):
    response = client.post("/api/priority", json=make_request())
    assert response.status_code == 200
    assert response.json()["priority_status"] == "prioritized"


def test_uuid_preservation(client):
    body = client.post("/api/priority", json=make_request()).json()
    assert body["request_id"] == REQUEST_ID
    assert UUID(body["request_id"])


def test_plan_id_preservation(client):
    body = client.post("/api/priority", json=make_request()).json()
    assert body["plan_id"] == "plan-007"


def test_goal_preservation(client):
    body = client.post("/api/priority", json=make_request()).json()
    assert body["goal"] == "Complete an admission application"


def test_empty_goal_validation():
    with pytest.raises(ValidationError):
        PriorityRequest(**make_request(goal="   "))


def test_invalid_uuid(client):
    response = client.post("/api/priority", json=make_request(request_id="not-a-uuid"))
    assert response.status_code == 422


def test_extra_field_rejection(client):
    response = client.post("/api/priority", json=make_request(unexpected="nope"))
    assert response.status_code == 422


def test_single_step_priority(client):
    payload = make_request(steps=[step()])
    body = client.post("/api/priority", json=payload).json()
    assert body["total_steps"] == 1
    assert body["prioritized_steps"][0]["step_id"] == "one"


def test_multiple_step_priority(client):
    body = client.post("/api/priority", json=make_request()).json()
    assert len(body["prioritized_steps"]) == 2
    assert body["total_steps"] == 2


def test_deterministic_scoring():
    request = PriorityRequest(**make_request())
    first = prioritize_plan(request).model_dump(mode="json")
    second = prioritize_plan(request).model_dump(mode="json")
    assert first == second


def test_score_range_0_to_100(client):
    body = client.post("/api/priority", json=make_request()).json()
    for item in body["prioritized_steps"]:
        assert 0.0 <= item["priority_score"] <= 100.0
        assert 0.0 <= item["score_breakdown"]["final_score"] <= 100.0


def test_priority_level_mapping():
    from app.services.priority_service import _level
    assert _level(90.0) == "critical"
    assert _level(89.999) == "high"
    assert _level(70.0) == "high"
    assert _level(69.999) == "medium"
    assert _level(40.0) == "medium"
    assert _level(39.999) == "low"
    assert _level(0.0) == "low"


def test_critical_priority(client):
    payload = make_request(
        steps=[step("critical", "Urgent", 1, urgency="critical", importance=100,
                    deadline="2026-09-20T12:00:00+00:00")]
    )
    item = client.post("/api/priority", json=payload).json()["prioritized_steps"][0]
    assert item["priority_level"] == "critical"


def test_high_priority(client):
    payload = make_request(
        steps=[step("high", "Important", 1, urgency="high", importance=80)]
    )
    item = client.post("/api/priority", json=payload).json()["prioritized_steps"][0]
    assert item["priority_level"] == "high"


def test_medium_priority(client):
    payload = make_request(
        steps=[step("medium", "Normal", 1, urgency="medium", required=False, importance=50)]
    )
    item = client.post("/api/priority", json=payload).json()["prioritized_steps"][0]
    assert item["priority_level"] == "medium"


def test_low_priority(client):
    payload = make_request(
        steps=[step("low", "Optional", 1, urgency="low", required=False, importance=0)]
    )
    item = client.post("/api/priority", json=payload).json()["prioritized_steps"][0]
    assert item["priority_level"] == "low"


def test_required_vs_optional_behavior():
    required = PriorityRequest(**make_request(
        steps=[step("req", "Required", 1, urgency="medium", required=True, importance=50)]
    ))
    optional = PriorityRequest(**make_request(
        steps=[step("opt", "Optional", 1, urgency="medium", required=False, importance=50)]
    ))
    assert prioritize_plan(required).prioritized_steps[0].priority_score > prioritize_plan(optional).prioritized_steps[0].priority_score


def test_urgency_handling():
    low = PriorityRequest(**make_request(steps=[step(urgency="low", importance=50)]))
    critical = PriorityRequest(**make_request(steps=[step(urgency="critical", importance=50)]))
    assert prioritize_plan(critical).prioritized_steps[0].score_breakdown.urgency_score == 100.0
    assert prioritize_plan(low).prioritized_steps[0].score_breakdown.urgency_score == 25.0


def test_deadline_handling():
    payload = make_request(steps=[step(
        deadline="2026-09-20T13:00:00+00:00", importance=50
    )])
    item = prioritize_plan(PriorityRequest(**payload)).prioritized_steps[0]
    assert item.score_breakdown.deadline_score == 80.0


def test_no_deadline_behavior():
    item = prioritize_plan(PriorityRequest(**make_request(
        steps=[step(importance=50)]
    ))).prioritized_steps[0]
    assert item.score_breakdown.deadline_score == 50.0


def test_dependency_handling():
    payload = make_request(steps=[
        step("a", "First", 1, status="completed"),
        step("b", "Second", 2, depends_on=["a"], status="ready"),
    ])
    result = prioritize_plan(PriorityRequest(**payload))
    by_id = {x.step_id: x for x in result.prioritized_steps}
    assert by_id["b"].depends_on == ["a"]
    assert by_id["b"].blocked is False


def test_blocked_task_handling():
    payload = make_request(steps=[
        step("a", "First", 1, status="pending"),
        step("b", "Second", 2, depends_on=["a"], status="pending"),
    ])
    result = prioritize_plan(PriorityRequest(**payload))
    by_id = {x.step_id: x for x in result.prioritized_steps}
    assert by_id["b"].blocked is True
    assert by_id["b"].priority_score >= 0


def test_dependency_based_tie_breaking():
    payload = make_request(steps=[
        step("dep-a", "A", 1, status="pending"),
        step("dep-b", "B", 2, status="completed"),
        step(
            "blocked", "Blocked", 3, status="pending",
            depends_on=["dep-a"], importance=59,
        ),
        step(
            "ready", "Ready", 4, status="pending",
            depends_on=["dep-b"], importance=50,
        ),
    ])
    # The explicit importance difference offsets the dependency-score difference,
    # producing a score tie that must be resolved by readiness.
    result = prioritize_plan(PriorityRequest(**payload))
    positions = {item.step_id: index for index, item in enumerate(result.prioritized_steps)}
    assert positions["ready"] < positions["blocked"]


def test_original_order_tie_breaking():
    payload = make_request(steps=[
        step("first", "First", 5, urgency="medium", importance=50),
        step("second", "Second", 6, urgency="medium", importance=50),
    ])
    result = prioritize_plan(PriorityRequest(**payload))
    assert [x.step_id for x in result.prioritized_steps] == ["first", "second"]


def test_no_invented_information():
    payload = {
        "request_id": REQUEST_ID,
        "goal": "Organize my project",
        "plan_id": "plan-plain",
        "steps": [step()],
    }
    result = prioritize_plan(PriorityRequest(**payload))
    item = result.prioritized_steps[0]
    assert item.urgency is None
    assert item.score_breakdown.urgency_score == 50.0
    assert item.score_breakdown.deadline_score == 50.0
    assert item.score_breakdown.importance_score == 50.0
    assert result.priority_status == "partially_prioritized"


def test_empty_steps_rejected():
    with pytest.raises(ValidationError):
        PriorityRequest(**make_request(steps=[]))


def test_malformed_steps_rejected(client):
    response = client.post("/api/priority", json=make_request(
        steps=[{"step_id": "x", "title": "Missing required fields"}]
    ))
    assert response.status_code == 422


def test_multiple_dependencies():
    payload = make_request(steps=[
        step("a", "A", 1, status="completed"),
        step("b", "B", 2, status="completed"),
        step("c", "C", 3, depends_on=["a", "b"], status="ready"),
    ])
    result = prioritize_plan(PriorityRequest(**payload))
    c = next(x for x in result.prioritized_steps if x.step_id == "c")
    assert c.depends_on == ["a", "b"]
    assert c.blocked is False


def test_score_breakdown_is_exposed(client):
    item = client.post("/api/priority", json=make_request()).json()["prioritized_steps"][0]
    breakdown = item["score_breakdown"]
    assert set(breakdown) == {
        "urgency_score", "deadline_score", "required_score",
        "dependency_score", "importance_score", "final_score",
    }


def test_confidence_bounds(client):
    body = client.post("/api/priority", json=make_request()).json()
    assert 0.0 <= body["priority_confidence"] <= 1.0


def test_duplicate_step_ids_rejected():
    with pytest.raises(ValidationError):
        PriorityRequest(**make_request(steps=[
            step("dup", "One", 1),
            step("dup", "Two", 2),
        ]))


def test_unknown_dependency_rejected():
    with pytest.raises(ValidationError):
        PriorityRequest(**make_request(steps=[
            step("one", "One", 1, depends_on=["missing"]),
        ]))


def test_self_dependency_rejected():
    with pytest.raises(ValidationError):
        PriorityRequest(**make_request(steps=[
            step("one", "One", 1, depends_on=["one"]),
        ]))


def test_invalid_importance_rejected():
    with pytest.raises(ValidationError):
        PriorityRequest(**make_request(steps=[step(importance=101)]))


def test_naive_deadline_rejected():
    with pytest.raises(ValidationError):
        PriorityRequest(**make_request(steps=[step(deadline="2026-09-21T12:00:00")]))


def test_counts_are_consistent(client):
    body = client.post("/api/priority", json=make_request()).json()
    counts = sum(body[f"{level}_count"] for level in ("critical", "high", "medium", "low"))
    assert counts == body["total_steps"]


def test_request_schema_extra_field_inside_step_rejected(client):
    response = client.post("/api/priority", json=make_request(
        steps=[step(unexpected="x")]
    ))
    assert response.status_code == 422


def test_reference_time_is_required_for_deadline_proximity():
    with_ref = PriorityRequest(**make_request(
        steps=[step(deadline="2026-09-20T13:00:00+00:00")]
    ))
    without_ref = PriorityRequest(**make_request(
        priority_reference_time=None,
        steps=[step(deadline="2026-09-20T13:00:00+00:00")]
    ))
    a = prioritize_plan(with_ref).prioritized_steps[0].score_breakdown.deadline_score
    b = prioritize_plan(without_ref).prioritized_steps[0].score_breakdown.deadline_score
    assert a == 80.0
    assert b == 50.0
