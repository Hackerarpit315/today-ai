from __future__ import annotations

import ast
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.api.routes import audit as audit_route
from app.api.routes import memory as memory_route
from fastapi.testclient import TestClient
from app.main import app
from app.persistence.database import get_database_path, initialize_database
from app.persistence.factory import create_audit_service, create_memory_service
from app.persistence.repositories.audit_repository import SQLiteAuditRepository
from app.persistence.repositories.memory_repository import SQLiteMemoryRepository
from app.schemas.audit import AuditEventCreateRequest
from app.schemas.memory import MemoryStoreRequest, MemoryRetrieveRequest, MemoryType, Importance, Sensitivity
from app.services.audit_service import AuditService
from app.services.memory_service import MemoryService

NOW = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)


def memory_request(**overrides):
    data = {
        "user_id": "activation-user",
        "memory_type": MemoryType.preference,
        "key": "language",
        "value": "Hindi",
        "importance": Importance.medium,
        "sensitivity": Sensitivity.normal,
        "source": "user_explicit",
        "current_time": NOW,
    }
    data.update(overrides)
    return MemoryStoreRequest(**data)


def audit_request(**overrides):
    data = {
        "request_id": uuid4(),
        "timestamp": NOW,
        "module": "audit",
        "event_type": "memory_stored",
        "status": "success",
        "severity": "info",
        "actor": "module",
        "message": "Persistence activation verification",
        "metadata": {"test": "activation"},
        "correlation_id": uuid4(),
    }
    data.update(overrides)
    return AuditEventCreateRequest(**data)


def test_database_initialization_is_explicit_and_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "nested" / "activation.db"
    monkeypatch.setenv("TODAY_AI_DB_PATH", str(db_path))

    assert not db_path.exists()
    assert get_database_path() == db_path
    assert initialize_database() == db_path
    assert db_path.exists()
    assert initialize_database() == db_path

    with sqlite3.connect(db_path) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"schema_migrations", "memories", "audit_events"}.issubset(tables)


def test_memory_real_service_persists_across_service_recreation(tmp_path, monkeypatch):
    db_path = tmp_path / "memory.db"
    monkeypatch.setenv("TODAY_AI_DB_PATH", str(db_path))
    monkeypatch.setenv("TODAY_AI_PERSISTENCE", "sqlite")

    first = create_memory_service()
    stored = first.store(memory_request())
    assert stored.success

    second = create_memory_service()
    retrieved = second.retrieve(
        MemoryRetrieveRequest(
            user_id="activation-user",
            memory_id=stored.memory_id,
            current_time=NOW,
        )
    )
    assert retrieved.success
    assert retrieved.memory.value == "Hindi"
    assert retrieved.memory.memory_id == stored.memory_id


def test_memory_api_route_uses_sqlite_when_persistence_enabled(tmp_path, monkeypatch):
    db_path = tmp_path / "memory-api.db"
    monkeypatch.setenv("TODAY_AI_DB_PATH", str(db_path))
    monkeypatch.setenv("TODAY_AI_PERSISTENCE", "sqlite")

    response = memory_route.memory_operation({
        "operation": "store",
        "data": {
            "user_id": "api-user",
            "memory_type": "preference",
            "key": "theme",
            "value": "dark",
            "importance": "medium",
            "sensitivity": "normal",
            "source": "user_explicit",
            "current_time": "2026-09-15T10:00:00+00:00",
        },
    })
    assert response.success
    memory_id = response.memory_id

    # A fresh service instance reads the application-route-created record from SQLite.
    fresh = create_memory_service()
    retrieved = fresh.retrieve(
        MemoryRetrieveRequest(
            user_id="api-user",
            memory_id=memory_id,
            current_time=NOW,
        )
    )
    assert retrieved.success
    assert retrieved.memory.value == "dark"


def test_audit_real_service_persists_across_service_recreation(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv("TODAY_AI_DB_PATH", str(db_path))
    monkeypatch.setenv("TODAY_AI_PERSISTENCE", "sqlite")

    first = create_audit_service()
    created = first.create_event(audit_request())
    assert created.success

    second = create_audit_service()
    fetched = second.retrieve_event(
        __import__("app.schemas.audit", fromlist=["AuditEventRetrieveRequest"]).AuditEventRetrieveRequest(
            event_id=created.event_id
        )
    )
    assert fetched.success
    assert fetched.event.message == "Persistence activation verification"
    assert second.verify_event_integrity(fetched.event_id).valid is True


def test_audit_api_route_uses_sqlite_when_persistence_enabled(tmp_path, monkeypatch):
    db_path = tmp_path / "audit-api.db"
    monkeypatch.setenv("TODAY_AI_DB_PATH", str(db_path))
    monkeypatch.setenv("TODAY_AI_PERSISTENCE", "sqlite")

    response = audit_route.create_audit_event(audit_request())
    assert response.success
    event_id = response.event_id

    fresh = create_audit_service()
    fetched = fresh.retrieve_event(
        __import__("app.schemas.audit", fromlist=["AuditEventRetrieveRequest"]).AuditEventRetrieveRequest(
            event_id=event_id
        )
    )
    assert fetched.success
    assert fetched.event.message == "Persistence activation verification"


def test_audit_persistence_preserves_search_filter_and_pagination(tmp_path, monkeypatch):
    db_path = tmp_path / "audit-query.db"
    monkeypatch.setenv("TODAY_AI_DB_PATH", str(db_path))
    monkeypatch.setenv("TODAY_AI_PERSISTENCE", "sqlite")

    service = create_audit_service()
    for index in range(3):
        service.create_event(
            audit_request(
                timestamp=NOW.replace(minute=index),
                message=f"activation event {index}",
                module="memory" if index < 2 else "audit",
            )
        )

    from app.schemas.audit import AuditEventListRequest, AuditEventSearchRequest
    filtered = service.list_events(AuditEventListRequest(module="memory"))
    assert filtered.total == 2
    page = service.list_events(AuditEventListRequest(limit=1, offset=1))
    assert len(page.events) == 1
    searched = service.search_events(AuditEventSearchRequest(query="activation event 2"))
    assert searched.total == 1


def test_assistant_api_still_works_with_persistence_enabled(tmp_path, monkeypatch):
    db_path = tmp_path / "assistant.db"
    monkeypatch.setenv("TODAY_AI_DB_PATH", str(db_path))
    monkeypatch.setenv("TODAY_AI_PERSISTENCE", "sqlite")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/assistant",
        json={
            "content": "Mujhe kal college jana hai.",
            "current_datetime": "2026-09-15T10:00:00+05:30",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_persistence_source_has_no_external_network_or_dynamic_execution():
    root = Path(__file__).resolve().parents[1] / "app" / "persistence"
    forbidden_imports = {"requests", "httpx", "aiohttp", "urllib3", "urllib.request"}
    forbidden_calls = {"urlopen", "request", "urlretrieve", "system", "popen", "eval", "exec"}
    violations = []
    for source in root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_imports:
                        violations.append(f"{source}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in forbidden_imports:
                    violations.append(f"{source}: from {node.module}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in forbidden_calls:
                    violations.append(f"{source}: {node.func.id}()")
    assert not violations, "\n".join(violations)
