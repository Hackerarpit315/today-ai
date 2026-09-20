"""Standalone tests for Module 8 Today Engine."""

from datetime import datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes.today import router
from app.schemas.today import TodayRequest
from app.services.today_service import build_today

REQUEST_ID = "00000000-0000-0000-0000-000000000008"
NOW = "2026-09-20T10:30:00+05:30"


def task(step_id="one", title="Prepare", order=1, **kwargs):
    data = {
        "step_id": step_id,
        "title": title,
        "description": "Do the work",
        "priority_score": 70.0,
        "priority_level": "high",
        "urgency": "high",
        "required": True,
        "blocked": False,
        "depends_on": [],
        "original_order": order,
        "status": "pending",
    }
    data.update(kwargs)
    return data


def make_request(**overrides):
    payload = {
        "request_id": REQUEST_ID,
        "plan_id": "plan-008",
        "goal": "Complete today's work",
        "current_datetime": NOW,
        "tasks": [task()],
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_valid_today_request(client):
    response = client.post("/api/today", json=make_request())
    assert response.status_code == 200
    assert response.json()["today_status"] == "planned"


def test_uuid_preservation(client):
    body = client.post("/api/today", json=make_request()).json()
    assert body["request_id"] == REQUEST_ID
    assert UUID(body["request_id"])


def test_plan_id_preservation(client):
    assert client.post("/api/today", json=make_request()).json()["plan_id"] == "plan-008"


def test_goal_preservation(client):
    assert client.post("/api/today", json=make_request()).json()["goal"] == "Complete today's work"


def test_current_datetime_validation():
    request = TodayRequest(**make_request())
    assert request.current_datetime.tzinfo is not None
    assert request.current_datetime.isoformat() == NOW


def test_timezone_aware_datetime_required():
    with pytest.raises(ValidationError, match="timezone"):
        TodayRequest(**make_request(current_datetime="2026-09-20T10:30:00"))


def test_invalid_uuid(client):
    assert client.post("/api/today", json=make_request(request_id="not-a-uuid")).status_code == 422


def test_invalid_datetime(client):
    assert client.post("/api/today", json=make_request(current_datetime="not-a-date")).status_code == 422


def test_extra_field_rejection(client):
    assert client.post("/api/today", json=make_request(unexpected="nope")).status_code == 422


def test_empty_task_list(client):
    body = client.post("/api/today", json=make_request(tasks=[])).json()
    assert body["total_today_tasks"] == 0
    assert body["today_status"] == "insufficient_information"


def test_single_today_task(client):
    body = client.post("/api/today", json=make_request(tasks=[task(is_today=True)])).json()
    assert [x["step_id"] for x in body["today_tasks"]] == ["one"]
    assert body["ready_count"] == 1


def test_multiple_today_tasks(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("one", "One", 1, is_today=True),
        task("two", "Two", 2, is_today=True, priority_score=90, priority_level="critical", urgency="critical"),
    ])).json()
    assert len(body["today_tasks"]) == 2


def test_future_task_exclusion(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("future", "Future", 1, required=False, deadline="2026-09-25T10:30:00+05:30"),
    ])).json()
    assert body["today_tasks"] == []


def test_due_today_detection(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task(deadline="2026-09-20T18:00:00+05:30"),
    ])).json()
    item = body["today_tasks"][0]
    assert item["due_today"] is True
    assert body["due_today_count"] == 1


def test_overdue_detection(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task(deadline="2026-09-20T08:00:00+05:30"),
    ])).json()
    item = body["today_tasks"][0]
    assert item["overdue"] is True
    assert body["overdue_count"] == 1
    assert item["status"] == "overdue"


def test_completed_task_handling(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task(status="completed", is_today=True),
    ])).json()
    assert body["today_tasks"] == []
    assert len(body["completed_tasks"]) == 1
    assert body["completed_tasks"][0]["status"] == "completed"
    assert body["completed_count"] == 1


def test_dependency_handling(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("a", "Collect documents", 1, is_today=True, status="completed"),
        task("b", "Upload documents", 2, is_today=True, depends_on=["a"]),
    ])).json()
    assert [x["step_id"] for x in body["today_tasks"]] == ["b"]
    assert body["today_tasks"][0]["blocked"] is False


def test_blocked_task_detection(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("a", "Collect documents", 1, is_today=True, status="pending"),
        task("b", "Upload documents", 2, is_today=True, depends_on=["a"]),
    ])).json()
    by_id = {x["step_id"]: x for x in body["today_tasks"]}
    assert by_id["b"]["blocked"] is True
    assert by_id["b"]["status"] == "blocked"


def test_ready_task_detection(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("a", "First", 1, is_today=True, status="completed"),
        task("b", "Second", 2, is_today=True, depends_on=["a"]),
    ])).json()
    assert body["today_tasks"][0]["status"] == "ready"
    assert body["ready_count"] == 1


def test_priority_preservation(client):
    original = task(priority_score=91.25, priority_level="critical", urgency="critical", is_today=True)
    body = client.post("/api/today", json=make_request(tasks=[original])).json()
    item = body["today_tasks"][0]
    assert item["priority_score"] == 91.25
    assert item["priority_level"] == "critical"
    assert item["urgency"] == "critical"


def test_deterministic_ordering(client):
    tasks = [
        task("low", "Low", 3, is_today=True, priority_score=20, priority_level="low", urgency="low", required=False),
        task("high", "High", 2, is_today=True, priority_score=90, priority_level="critical", urgency="critical"),
        task("due", "Due", 1, deadline="2026-09-20T23:00:00+05:30", priority_score=40, priority_level="medium", urgency="medium"),
        task("late", "Late", 4, deadline="2026-09-19T23:00:00+05:30", priority_score=30, priority_level="low", urgency="low", required=False),
    ]
    first = client.post("/api/today", json=make_request(tasks=tasks)).json()
    second = client.post("/api/today", json=make_request(tasks=tasks)).json()
    assert first == second
    assert [x["step_id"] for x in first["today_tasks"]] == ["late", "due", "high", "low"]


def test_dependency_aware_ordering(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("b", "B", 1, is_today=True, depends_on=["a"], priority_score=100, priority_level="critical", urgency="critical"),
        task("a", "A", 2, is_today=True, priority_score=10, priority_level="low", urgency="low"),
    ])).json()
    assert [x["step_id"] for x in body["today_tasks"]] == ["a", "b"]


def test_required_vs_optional_behavior(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("required", "Required", 1, required=True),
        task("optional", "Optional", 2, required=False),
    ])).json()
    assert [x["step_id"] for x in body["today_tasks"]] == ["required"]


def test_today_summary_counts(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("overdue", "Overdue", 1, deadline="2026-09-19T10:00:00+05:30", priority_score=95, priority_level="critical", urgency="critical"),
        task("due", "Due", 2, deadline="2026-09-20T18:00:00+05:30", priority_score=80, priority_level="high", urgency="high"),
        task("dep", "Dependency", 3, status="pending", is_today=True, priority_score=20, priority_level="low", urgency="low"),
        task("blocked", "Blocked", 4, is_today=True, depends_on=["dep"], priority_score=90, priority_level="critical", urgency="critical"),
    ])).json()
    assert body["total_today_tasks"] == 4
    assert body["ready_count"] == 3
    assert body["blocked_count"] == 1
    assert body["overdue_count"] == 1
    assert body["due_today_count"] == 1
    assert body["high_priority_count"] == 3
    assert body["critical_priority_count"] == 2


def test_no_invented_deadline_or_task_information(client):
    body = client.post("/api/today", json=make_request(tasks=[task(is_today=True, deadline=None)])).json()
    item = body["today_tasks"][0]
    assert item["deadline"] is None
    assert item["step_id"] == "one"
    assert item["title"] == "Prepare"


def test_multiple_dependencies(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("a", "A", 1, status="completed"),
        task("b", "B", 2, status="pending"),
        task("c", "C", 3, is_today=True, depends_on=["a", "b"]),
    ])).json()
    by_id = {x["step_id"]: x for x in body["today_tasks"]}
    assert by_id["c"]["blocked"] is True
    assert "b" in by_id["c"]["depends_on"]


def test_mixed_overdue_due_today_and_future(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("overdue", "Overdue", 1, required=False, deadline="2026-09-19T12:00:00+05:30"),
        task("today", "Today", 2, required=False, deadline="2026-09-20T12:00:00+05:30"),
        task("future", "Future", 3, required=False, deadline="2026-09-21T12:00:00+05:30"),
    ])).json()
    assert [x["step_id"] for x in body["today_tasks"]] == ["overdue", "today"]


def test_no_actionable_tasks(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("future", "Future", 1, required=False, deadline="2026-09-25T10:00:00+05:30"),
        task("optional", "Optional", 2, required=False),
    ])).json()
    assert body["today_tasks"] == []
    assert body["next_task"] is None
    assert body["today_status"] == "partially_planned"


def test_all_tasks_completed(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("a", "A", 1, status="completed", is_today=True),
        task("b", "B", 2, status="completed", is_today=True),
    ])).json()
    assert body["today_tasks"] == []
    assert body["completed_count"] == 2
    assert body["next_task"] is None


def test_blocked_high_priority_task(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("dep", "Dependency", 1, is_today=True),
        task("critical", "Critical", 2, is_today=True, depends_on=["dep"], priority_score=100, priority_level="critical", urgency="critical"),
    ])).json()
    item = next(x for x in body["today_tasks"] if x["step_id"] == "critical")
    assert item["blocked"] is True
    assert body["next_task"]["step_id"] == "dep"


def test_next_task_selection(client):
    body = client.post("/api/today", json=make_request(tasks=[
        task("optional", "Optional", 1, required=False, is_today=True, priority_score=95, priority_level="critical", urgency="critical"),
        task("overdue", "Overdue", 2, required=False, deadline="2026-09-19T10:00:00+05:30", priority_score=70, priority_level="high", urgency="high"),
    ])).json()
    assert body["next_task"]["step_id"] == "overdue"


def test_insufficient_information_for_empty_input():
    request = TodayRequest(**make_request(tasks=[]))
    result = build_today(request)
    assert result.today_status == "insufficient_information"
    assert result.next_task is None


def test_deterministic_repeated_execution():
    request = TodayRequest(**make_request(tasks=[
        task("a", "A", 1, is_today=True),
        task("b", "B", 2, is_today=True, depends_on=["a"]),
    ]))
    first = build_today(request).model_dump(mode="json")
    second = build_today(request).model_dump(mode="json")
    assert first == second


def test_unknown_dependency_rejected():
    with pytest.raises(ValidationError, match="unknown dependency"):
        TodayRequest(**make_request(tasks=[task(depends_on=["does-not-exist"])]))


def test_dependency_cycle_rejected():
    with pytest.raises(ValidationError, match="cycle"):
        TodayRequest(**make_request(tasks=[
            task("a", "A", 1, depends_on=["b"]),
            task("b", "B", 2, depends_on=["a"]),
        ]))
