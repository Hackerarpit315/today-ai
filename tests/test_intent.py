from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.intent import router as intent_router


app = FastAPI()
app.include_router(intent_router)

client = TestClient(app)


def accepted(content):
    return {
        "request_id": str(uuid4()),
        "input_type": "text",
        "content": content,
        "status": "accepted",
    }


def test_task():
    r = client.post("/api/intent", json=accepted("Mujhe kal college jana hai"))
    assert r.status_code == 200
    assert r.json()["intent"] == "task"
    assert r.json()["time_reference"] == "tomorrow"


def test_question():
    r = client.post("/api/intent", json=accepted("What is an API?"))
    assert r.status_code == 200
    assert r.json()["intent"] == "question"


def test_research():
    r = client.post(
        "/api/intent",
        json=accepted("Research AKTU admission deadline"),
    )
    assert r.status_code == 200
    assert r.json()["intent"] == "research"


def test_reminder():
    r = client.post(
        "/api/intent",
        json=accepted("Remind me tomorrow at 10 am"),
    )
    assert r.status_code == 200
    assert r.json()["intent"] == "reminder"


def test_command():
    r = client.post("/api/intent", json=accepted("Open GitHub"))
    assert r.status_code == 200
    assert r.json()["intent"] == "command"


def test_unknown():
    r = client.post("/api/intent", json=accepted("Hello Today AI"))
    assert r.status_code == 200
    assert r.json()["intent"] == "unknown"


def test_request_id_preserved():
    payload = accepted("Mujhe assignment complete karna hai")
    rid = payload["request_id"]

    r = client.post("/api/intent", json=payload)

    assert r.status_code == 200
    assert r.json()["request_id"] == rid


def test_confidence_range():
    r = client.post("/api/intent", json=accepted("Mujhe college jana hai"))

    assert r.status_code == 200
    assert 0 <= r.json()["confidence"] <= 1


def test_extra_fields_rejected():
    payload = accepted("Mujhe college jana hai")
    payload["extra"] = "not allowed"

    r = client.post("/api/intent", json=payload)

    assert r.status_code == 422