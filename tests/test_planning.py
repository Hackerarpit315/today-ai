"""Standalone tests for Module 6 Planning Engine."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes.planning import router
from app.schemas.planning import PlanningRequest
from app.services.planning_service import create_plan

REQUEST_ID = "00000000-0000-0000-0000-000000000006"


def make_request(**overrides):
    payload = {
        "request_id": REQUEST_ID,
        "goal": "Apply for an admission form",
        "intent": "application",
        "entities": {"organization": "Example University"},
        "time_reference": "30 September 2026",
        "verified_information": [
            {"key": "deadline", "value": "30 September 2026", "category": "deadline"},
            {"key": "required_documents", "value": ["Aadhaar", "marksheet"], "category": "requirements"},
            {"key": "application_fee", "value": "500", "category": "fee"},
            {"key": "portal", "value": "https://example.edu/apply", "category": "url"},
        ],
        "constraints": [{"key": "budget", "value": "500"}],
        "available_steps": [],
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_valid_planning_request(client):
    response = client.post("/api/plan", json=make_request())
    assert response.status_code == 200
    body = response.json()
    assert body["planning_status"] == "planned"
    assert body["total_steps"] >= 1


def test_uuid_is_preserved(client):
    response = client.post("/api/plan", json=make_request())
    assert response.json()["request_id"] == REQUEST_ID
    assert UUID(response.json()["request_id"])


def test_goal_validation_rejects_empty_goal():
    with pytest.raises(ValidationError):
        PlanningRequest(**make_request(goal="   "))


def test_intent_validation_rejects_empty_intent():
    with pytest.raises(ValidationError):
        PlanningRequest(**make_request(intent=""))


def test_extra_field_is_rejected(client):
    payload = make_request(unexpected="nope")
    response = client.post("/api/plan", json=payload)
    assert response.status_code == 422


def test_basic_plan_generation(client):
    body = client.post("/api/plan", json=make_request()).json()
    titles = [step["title"] for step in body["steps"]]
    assert "Confirm the requirements" in titles
    assert "Review the completed information" in titles


def test_multiple_steps_have_sequential_orders(client):
    body = client.post("/api/plan", json=make_request()).json()
    assert [step["order"] for step in body["steps"]] == list(range(1, body["total_steps"] + 1))


def test_dependency_creation_for_document_upload(client):
    body = client.post("/api/plan", json=make_request()).json()
    by_title = {step["title"]: step for step in body["steps"]}
    upload = by_title["Upload required documents"]
    collect = by_title["Collect required documents"]
    enter = by_title["Enter applicant information"]
    assert collect["step_id"] in upload["depends_on"]
    assert enter["step_id"] in upload["depends_on"]
    assert upload["status"] == "blocked"


def test_dependency_ordering_is_correct(client):
    body = client.post("/api/plan", json=make_request()).json()
    positions = {step["step_id"]: step["order"] for step in body["steps"]}
    for step in body["steps"]:
        for dependency in step["depends_on"]:
            assert positions[dependency] < step["order"]


def test_required_steps_are_counted(client):
    body = client.post("/api/plan", json=make_request()).json()
    assert body["required_steps"] == sum(step["required"] for step in body["steps"])
    assert body["required_steps"] == body["total_steps"]


def test_optional_step_is_preserved_when_explicitly_supplied(client):
    payload = make_request(
        verified_information=[],
        constraints=[],
        available_steps=[
            {"step_id": "one", "title": "Prepare data", "required": True},
            {"step_id": "two", "title": "Optional review", "required": False, "depends_on": ["one"]},
        ],
    )
    body = client.post("/api/plan", json=payload).json()
    optional = next(step for step in body["steps"] if step["title"] == "Optional review")
    assert optional["required"] is False
    assert body["required_steps"] == 1


def test_deadline_and_constraint_input_is_accepted(client):
    payload = make_request(
        time_reference="before 30 September 2026",
        constraints=[{"key": "location", "value": "Lucknow"}, {"key": "budget", "value": 500}],
    )
    response = client.post("/api/plan", json=payload)
    assert response.status_code == 200
    assert response.json()["planning_confidence"] >= 0.55


def test_insufficient_information_uses_generic_non_invented_plan(client):
    payload = {
        "request_id": REQUEST_ID,
        "goal": "Complete admission process",
        "intent": "complete",
        "entities": {},
        "verified_information": [],
        "constraints": [],
        "available_steps": [],
    }
    body = client.post("/api/plan", json=payload).json()
    assert body["planning_status"] == "partially_planned"
    titles = " ".join(step["title"] for step in body["steps"]).lower()
    assert "aadhaar" not in titles
    assert "₹" not in titles
    assert "http" not in titles


def test_deterministic_output():
    request = PlanningRequest(**make_request())
    first = create_plan(request).model_dump(mode="json")
    second = create_plan(request).model_dump(mode="json")
    assert first == second


def test_confidence_is_bounded(client):
    body = client.post("/api/plan", json=make_request()).json()
    assert 0.0 <= body["planning_confidence"] <= 1.0


def test_empty_verified_information_is_valid(client):
    payload = make_request(verified_information=[])
    response = client.post("/api/plan", json=payload)
    assert response.status_code == 200
    assert response.json()["total_steps"] > 0


def test_multiple_verified_facts_raise_planning_confidence():
    low = PlanningRequest(**make_request(verified_information=[]))
    high = PlanningRequest(**make_request())
    assert create_plan(high).planning_confidence > create_plan(low).planning_confidence


def test_no_invented_facts_in_generic_description(client):
    payload = {
        "request_id": REQUEST_ID,
        "goal": "Organize my project",
        "intent": "organize",
        "entities": {},
        "verified_information": [],
        "constraints": [],
        "available_steps": [],
    }
    body = client.post("/api/plan", json=payload).json()
    combined = " ".join(step["description"] for step in body["steps"]).lower()
    assert "fee" not in combined
    assert "deadline" not in combined
    assert "aadhaar" not in combined


def test_plan_id_is_generated_and_deterministic():
    request = PlanningRequest(**make_request())
    first = create_plan(request).plan_id
    second = create_plan(request).plan_id
    assert first.startswith("plan-")
    assert first == second


def test_response_schema_counts_are_consistent(client):
    body = client.post("/api/plan", json=make_request()).json()
    assert body["total_steps"] == len(body["steps"])
    assert body["required_steps"] <= body["total_steps"]
    assert body["plan_id"]


def test_explicit_steps_and_dependencies_are_preserved(client):
    payload = make_request(
        verified_information=[],
        constraints=[],
        available_steps=[
            {"step_id": "review", "title": "Review", "required": True, "depends_on": ["prepare"]},
            {"step_id": "prepare", "title": "Prepare", "required": True},
        ],
    )
    body = client.post("/api/plan", json=payload).json()
    assert [step["title"] for step in body["steps"]] == ["Prepare", "Review"]
    assert body["steps"][1]["depends_on"] == [body["steps"][0]["step_id"]]


def test_invalid_dependency_does_not_create_external_step(client):
    payload = make_request(
        verified_information=[],
        constraints=[],
        available_steps=[
            {"step_id": "review", "title": "Review", "depends_on": ["missing"]},
        ],
    )
    body = client.post("/api/plan", json=payload).json()
    assert body["steps"][0]["depends_on"] == []
    assert body["steps"][0]["status"] == "ready"


def test_invalid_verified_information_is_rejected(client):
    payload = make_request(
        verified_information=[{"key": "deadline", "value": "tomorrow", "unknown": True}]
    )
    response = client.post("/api/plan", json=payload)
    assert response.status_code == 422


def test_invalid_constraint_structure_is_rejected(client):
    payload = make_request(constraints=[{"key": "budget"}])
    response = client.post("/api/plan", json=payload)
    assert response.status_code == 422


def test_invalid_available_step_structure_is_rejected(client):
    payload = make_request(available_steps=[{"title": "Prepare", "unexpected": True}])
    response = client.post("/api/plan", json=payload)
    assert response.status_code == 422


def test_simple_task_produces_one_meaningful_step(client):
    payload = make_request(
        goal="Go to college",
        intent="task",
        entities={"place": ["college"]},
        time_reference=None,
        verified_information=[],
        constraints=[],
    )
    body = client.post("/api/plan", json=payload).json()
    assert body["total_steps"] == 1
    assert body["steps"][0]["title"] == "Go to college"


def test_tomorrow_task_preserves_time_in_step(client):
    payload = make_request(
        goal="Go to college",
        intent="task",
        entities={"place": ["college"]},
        time_reference="tomorrow",
        verified_information=[],
        constraints=[],
    )
    body = client.post("/api/plan", json=payload).json()
    assert body["total_steps"] == 1
    assert "tomorrow" in body["steps"][0]["description"].lower()


def test_scheduled_call_task_stays_single_step(client):
    payload = make_request(
        goal="Call Rahul",
        intent="task",
        entities={"person": ["Rahul"]},
        time_reference="tomorrow",
        verified_information=[],
        constraints=[],
    )
    body = client.post("/api/plan", json=payload).json()
    assert body["total_steps"] == 1
    assert body["steps"][0]["title"] == "Call Rahul"
    assert "tomorrow" in body["steps"][0]["description"].lower()


def test_genuinely_multi_step_learning_goal_remains_multi_step(client):
    payload = make_request(
        goal="Learn Python",
        intent="task",
        entities={"topic": ["Python"]},
        time_reference=None,
        verified_information=[],
        constraints=[],
    )
    body = client.post("/api/plan", json=payload).json()
    assert body["total_steps"] > 1


def test_existing_application_planning_regression_remains_multi_step(client):
    body = client.post("/api/plan", json=make_request()).json()
    titles = [step["title"] for step in body["steps"]]
    assert body["total_steps"] > 1
    assert "Confirm the requirements" in titles
    assert "Upload required documents" in titles
