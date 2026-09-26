
"""Tests for the public assistant application endpoint."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.orchestrator.schemas import PipelineResult, StageError

client = TestClient(app, raise_server_exceptions=False)
ENDPOINT = "/api/assistant"
DT = "2026-09-15T10:00:00+05:30"


def post(payload):
    return client.post(ENDPOINT, json=payload)


def assert_safe_error(response, status=422):
    assert response.status_code == status
    body = response.json()
    blob = str(body)
    assert "Traceback" not in blob
    assert 'File "' not in blob
    return body


def test_valid_request():
    response = post(
        {
            "content": "Mujhe kal college jana hai.",
            "current_datetime": DT,
        }
    )
    assert response.status_code == 200
    body = response.json()
    UUID(body["request_id"])
    assert body["status"] in {"success", "failed"}
    assert "current_stage" in body
    assert "pipeline" in body
    assert "errors" in body


def test_response_structure():
    body = post(
        {
            "content": "hello",
            "current_datetime": DT,
        }
    ).json()

    assert set(body) == {
        "request_id",
        "status",
        "current_stage",
        "pipeline",
        "errors",
    }

    assert set(body["pipeline"]) >= {
        "request_id",
        "status",
        "current_stage",
        "intent",
        "context",
        "research",
        "verification",
        "planning",
        "priority",
        "today",
        "errors",
        "stage_results",
    }


def test_request_id_is_server_generated_and_propagated():
    body = post(
        {
            "content": "hello",
            "current_datetime": DT,
        }
    ).json()

    assert body["request_id"] == body["pipeline"]["request_id"]
    UUID(body["request_id"])


def test_empty_content_rejected():
    assert_safe_error(
        post(
            {
                "content": "",
                "current_datetime": DT,
            }
        )
    )


def test_whitespace_content_rejected():
    assert_safe_error(
        post(
            {
                "content": " \n\t ",
                "current_datetime": DT,
            }
        )
    )


def test_oversized_content_rejected():
    response = post(
        {
            "content": "x" * 10001,
            "current_datetime": DT,
        }
    )
    assert_safe_error(response)


def test_missing_content_rejected():
    assert_safe_error(
        post(
            {
                "current_datetime": DT,
            }
        )
    )


def test_extra_request_field_rejected():
    assert_safe_error(
        post(
            {
                "content": "hello",
                "current_datetime": DT,
                "request_id": "x",
            }
        )
    )


def test_missing_datetime_rejected():
    assert_safe_error(
        post(
            {
                "content": "hello",
            }
        )
    )


def test_timezone_aware_datetime_accepted():
    response = post(
        {
            "content": "hello",
            "current_datetime": "2026-09-15T10:00:00Z",
        }
    )
    assert response.status_code == 200


def test_naive_datetime_rejected():
    assert_safe_error(
        post(
            {
                "content": "hello",
                "current_datetime": "2026-09-15T10:00:00",
            }
        )
    )


def test_invalid_datetime_rejected():
    assert_safe_error(
        post(
            {
                "content": "hello",
                "current_datetime": "not-a-date",
            }
        )
    )


def test_orchestrator_success_is_returned(monkeypatch):
    fake_id = UUID("11111111-1111-4111-8111-111111111111")

    result = PipelineResult(
        request_id=fake_id,
        status="success",
        current_stage="today",
    )

    class FakeOrchestrator:
        def __init__(self, **_kwargs):
            pass

        def run(self, request):
            assert request.request_id != UUID(int=0)
            assert (
                request.current_datetime.isoformat()
                == "2026-09-15T10:00:00+05:30"
            )
            return result

    monkeypatch.setattr(
        "app.api.routes.assistant.Orchestrator",
        FakeOrchestrator,
    )

    body = post(
        {
            "content": "hello",
            "current_datetime": DT,
        }
    ).json()

    assert body["request_id"] == str(fake_id)
    assert body["status"] == "success"
    assert body["current_stage"] == "today"


def test_orchestrator_stage_failure_is_returned_safely(monkeypatch):
    fake_id = UUID("22222222-2222-4222-8222-222222222222")

    result = PipelineResult(
        request_id=fake_id,
        status="failed",
        current_stage="verification",
        errors=[
            StageError(
                stage="verification",
                code="stage_error",
                message="Stage failed safely.",
            )
        ],
    )

    class FakeOrchestrator:
        def __init__(self, **_kwargs):
            pass

        def run(self, request):
            return result

    monkeypatch.setattr(
        "app.api.routes.assistant.Orchestrator",
        FakeOrchestrator,
    )

    response = post(
        {
            "content": "hello",
            "current_datetime": DT,
        }
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "failed"
    assert body["current_stage"] == "verification"
    assert body["errors"][0]["stage"] == "verification"


def test_unexpected_internal_error_is_safe(monkeypatch):
    class BrokenOrchestrator:
        def __init__(self, **_kwargs):
            pass

        def run(self, request):
            raise RuntimeError("secret internal detail")

    monkeypatch.setattr(
        "app.api.routes.assistant.Orchestrator",
        BrokenOrchestrator,
    )

    response = post(
        {
            "content": "hello",
            "current_datetime": DT,
        }
    )

    body = assert_safe_error(response, 500)

    assert body["error"] == "internal_error"
    assert "secret internal detail" not in str(body)


def test_no_stack_trace_on_orchestrator_error(monkeypatch):
    class BrokenOrchestrator:
        def __init__(self, **_kwargs):
            pass

        def run(self, request):
            raise ValueError('File "secret.py", line 1')

    monkeypatch.setattr(
        "app.api.routes.assistant.Orchestrator",
        BrokenOrchestrator,
    )

    body = assert_safe_error(
        post(
            {
                "content": "hello",
                "current_datetime": DT,
            }
        ),
        500,
    )

    assert "Traceback" not in str(body)
    assert 'File "' not in str(body)


def test_existing_module_1_api_still_works():
    response = client.post(
        "/api/input",
        json={
            "input_type": "text",
            "content": "hello",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_existing_module_behavior_unchanged_for_empty_input():
    response = client.post(
        "/api/input",
        json={
            "input_type": "text",
            "content": "",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_same_explicit_context_produces_same_stage_content(monkeypatch):
    fixed_id = UUID("33333333-3333-4333-8333-333333333333")

    class FixedIdOrchestrator:
        def __init__(self, **_kwargs):
            pass

        def run(self, request):
            return PipelineResult(
                request_id=fixed_id,
                status="success",
                current_stage="today",
                stage_results={
                    "input": {
                        "content": request.text,
                    },
                    "today": {
                        "current_datetime": (
                            request.current_datetime.isoformat()
                        ),
                    },
                },
            )

    monkeypatch.setattr(
        "app.api.routes.assistant.Orchestrator",
        FixedIdOrchestrator,
    )

    payload = {
        "content": "same",
        "current_datetime": DT,
    }

    first = post(payload).json()
    second = post(payload).json()

    assert first["pipeline"] == second["pipeline"]


def test_explicit_datetime_reaches_orchestrator(monkeypatch):
    seen = {}

    class InspectingOrchestrator:
        def __init__(self, **_kwargs):
            pass

        def run(self, request):
            seen["dt"] = request.current_datetime

            return PipelineResult(
                request_id=request.request_id,
                status="success",
                current_stage="today",
            )

    monkeypatch.setattr(
        "app.api.routes.assistant.Orchestrator",
        InspectingOrchestrator,
    )

    post(
        {
            "content": "hello",
            "current_datetime": DT,
        }
    )

    assert seen["dt"] == datetime.fromisoformat(DT)


def test_client_cannot_control_request_id(monkeypatch):
    seen = {}

    class InspectingOrchestrator:
        def __init__(self, **_kwargs):
            pass

        def run(self, request):
            seen["id"] = request.request_id

            return PipelineResult(
                request_id=request.request_id,
                status="success",
                current_stage="today",
            )

    monkeypatch.setattr(
        "app.api.routes.assistant.Orchestrator",
        InspectingOrchestrator,
    )

    response = client.post(
        ENDPOINT,
        json={
            "content": "hello",
            "current_datetime": DT,
            "request_id": "44444444-4444-4444-8444-444444444444",
        },
    )

    assert response.status_code == 422
    assert "id" not in seen


def test_malformed_json_rejected():
    response = client.post(
        ENDPOINT,
        content=b"{bad",
        headers={
            "Content-Type": "application/json",
        },
    )

    assert_safe_error(response)


def test_non_json_content_type_rejected():
    response = client.post(
        ENDPOINT,
        content=b"hello",
        headers={
            "Content-Type": "text/plain",
        },
    )

    assert response.status_code in {415, 422}
    assert "Traceback" not in response.text


def test_no_external_network_call_is_used():
    """
    The assistant endpoint must execute normally while the core
    application remains free of accidental external network-client
    dependencies.

    Explicit integration clients are allowed because they are
    intentionally responsible for external communication.

    This intentionally does not monkeypatch socket.socket.connect because
    that can interfere with TestClient/asyncio internals on Windows.
    """
    import ast
    from pathlib import Path

    response = client.post(
        "/api/assistant",
        json={
            "content": "hello",
            "current_datetime": "2026-09-24T08:00:00+05:30",
        },
    )

    assert response.status_code == 200

    project_root = Path(__file__).resolve().parents[1]
    app_root = project_root / "app"

    forbidden_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib.request",
        "urllib3",
        "http.client",
    }

    forbidden_calls = {
        "urlopen",
        "urlretrieve",
        "request",
    }

    allowed_integration_files = {
        "integrations/google_calendar/client.py",
        "integrations/n8n/n8n_client.py",
    }

    violations = []

    for source_file in app_root.rglob("*.py"):
        relative_path = source_file.relative_to(app_root).as_posix()

        # These files are intentionally responsible for external
        # integration/network communication.
        if relative_path in allowed_integration_files:
            continue

        tree = ast.parse(
            source_file.read_text(encoding="utf-8"),
            filename=str(source_file),
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = alias.name.split(".")[0]

                    if (
                        alias.name in forbidden_modules
                        or root_name
                        in {
                            "requests",
                            "httpx",
                            "aiohttp",
                            "urllib3",
                        }
                    ):
                        violations.append(
                            f"{source_file}: external network import "
                            f"'{alias.name}'"
                        )

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""

                if module in forbidden_modules:
                    violations.append(
                        f"{source_file}: external network import "
                        f"'{module}'"
                    )

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in forbidden_calls:
                        violations.append(
                            f"{source_file}: external network call "
                            f"'{node.func.attr}()'"
                        )

    assert not violations, "\n".join(violations)


def test_api_docs_include_assistant_endpoint():
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/assistant" in paths
    assert "post" in paths["/api/assistant"]
