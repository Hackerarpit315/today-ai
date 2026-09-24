from __future__ import annotations

import ast
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.persistence.database import get_database_path, initialize_database
from app.persistence.repositories.audit_repository import SQLiteAuditRepository
from app.persistence.repositories.memory_repository import SQLiteMemoryRepository
from app.schemas.audit import (
    AuditEventCreateRequest,
    AuditEventListRequest,
    AuditEventSearchRequest,
)
from app.schemas.memory import (
    MemoryForgetRequest,
    MemoryListRequest,
    MemoryStoreRequest,
    MemoryType,
    MemoryUpdateRequest,
    MemorySource,
    Importance,
)
from app.services.audit_service import AuditService
from app.services.memory_service import MemoryService


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def memory_request(**overrides):
    data = dict(
        user_id="user-1",
        memory_type=MemoryType.preference,
        key="language",
        value="Hindi",
        importance=Importance.medium,
        source=MemorySource.user_explicit,
        current_time=NOW,
    )
    data.update(overrides)
    return MemoryStoreRequest(**data)


def audit_request(**overrides):
    data = dict(
        request_id=UUID("11111111-1111-1111-1111-111111111111"),
        timestamp=NOW,
        module="action",
        event_type="action_executed",
        status="success",
        severity="info",
        actor="module",
        message="Action completed",
        metadata={"adapter": "dry_run"},
        correlation_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    data.update(overrides)
    return AuditEventCreateRequest(**data)


def test_database_initialization_creates_file_and_tables(tmp_path):
    db_path = tmp_path / "nested" / "today_ai.db"
    from app.persistence.database import ensure_database_directory
    assert not db_path.exists()
    import app.persistence.database as database
    # Exercise the configured path without relying on the real project database.
    import os
    old = os.environ.get("TODAY_AI_DB_PATH")
    os.environ["TODAY_AI_DB_PATH"] = str(db_path)
    try:
        result = database.initialize_database()
    finally:
        if old is None:
            os.environ.pop("TODAY_AI_DB_PATH", None)
        else:
            os.environ["TODAY_AI_DB_PATH"] = old
    assert result == db_path
    assert db_path.exists()
    with sqlite3.connect(db_path) as db:
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"schema_migrations", "memories", "audit_events"} <= tables


def test_database_repeated_initialization_is_safe(tmp_path):
    db_path = tmp_path / "today_ai.db"
    from app.persistence.repositories.memory_repository import initialize_database_at
    initialize_database_at(db_path)
    initialize_database_at(db_path)
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 1


def test_database_import_does_not_create_real_default_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TODAY_AI_DB_PATH", raising=False)
    assert not (tmp_path / "data" / "today_ai.db").exists()


def test_database_path_configuration(tmp_path, monkeypatch):
    configured = tmp_path / "configured.db"
    monkeypatch.setenv("TODAY_AI_DB_PATH", str(configured))
    assert get_database_path() == configured


def test_memory_create_and_retrieve_persist_across_instances(tmp_path):
    db_path = tmp_path / "memory.db"
    first = MemoryService(SQLiteMemoryRepository(db_path))
    stored = first.store(memory_request())
    assert stored.success

    second = MemoryService(SQLiteMemoryRepository(db_path))
    fetched = second.retrieve(
        __import__("app.schemas.memory", fromlist=["MemoryRetrieveRequest"]).MemoryRetrieveRequest(
            user_id="user-1", memory_id=stored.memory_id, current_time=NOW
        )
    )
    assert fetched.success
    assert fetched.memory.value == "Hindi"


def test_memory_update_persists_and_preserves_id(tmp_path):
    db_path = tmp_path / "memory.db"
    service = MemoryService(SQLiteMemoryRepository(db_path))
    stored = service.store(memory_request())
    updated = service.update(
        MemoryUpdateRequest(
            user_id="user-1",
            memory_id=stored.memory_id,
            value="English",
            current_time=NOW + timedelta(minutes=1),
        )
    )
    assert updated.success
    assert updated.memory_id == stored.memory_id

    reopened = MemoryService(SQLiteMemoryRepository(db_path))
    fetched = reopened.retrieve(
        __import__("app.schemas.memory", fromlist=["MemoryRetrieveRequest"]).MemoryRetrieveRequest(
            user_id="user-1", memory_id=stored.memory_id, current_time=NOW + timedelta(minutes=1)
        )
    )
    assert fetched.memory.value == "English"
    assert fetched.memory.version == 2


def test_memory_forget_is_persisted_without_physical_delete(tmp_path):
    db_path = tmp_path / "memory.db"
    service = MemoryService(SQLiteMemoryRepository(db_path))
    stored = service.store(memory_request())
    result = service.forget(
        MemoryForgetRequest(
            user_id="user-1", memory_id=stored.memory_id, current_time=NOW + timedelta(minutes=1)
        )
    )
    assert result.success

    reopened_repo = SQLiteMemoryRepository(db_path)
    raw = reopened_repo.get(stored.memory_id)
    assert raw is not None
    assert raw.status.value == "forgotten"


def test_memory_list_is_deterministic_and_user_isolated(tmp_path):
    db_path = tmp_path / "memory.db"
    service = MemoryService(SQLiteMemoryRepository(db_path))
    service.store(memory_request(key="low", value="1", importance=Importance.low))
    service.store(memory_request(key="high", value="2", importance=Importance.high))
    service.store(memory_request(user_id="user-2", key="other", value="3"))
    result = service.list(
        MemoryListRequest(user_id="user-1", current_time=NOW)
    )
    assert [m.key for m in result.memories] == ["high", "low"]


def test_memory_expiry_persists_status(tmp_path):
    db_path = tmp_path / "memory.db"
    service = MemoryService(SQLiteMemoryRepository(db_path))
    stored = service.store(
        memory_request(expires_at=NOW + timedelta(minutes=1))
    )
    result = service.retrieve(
        __import__("app.schemas.memory", fromlist=["MemoryRetrieveRequest"]).MemoryRetrieveRequest(
            user_id="user-1",
            memory_id=stored.memory_id,
            current_time=NOW + timedelta(minutes=2),
        )
    )
    assert result.status == "expired"
    raw = SQLiteMemoryRepository(db_path).get(stored.memory_id)
    assert raw.status.value == "expired"


def test_memory_secret_is_not_stored(tmp_path):
    db_path = tmp_path / "memory.db"
    service = MemoryService(SQLiteMemoryRepository(db_path))
    result = service.store(memory_request(key="api_key", value="secret-value"))
    assert result.status == "rejected"
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0


def test_memory_json_round_trip(tmp_path):
    db_path = tmp_path / "memory.db"
    service = MemoryService(SQLiteMemoryRepository(db_path))
    value = {"topic": "AI", "items": ["a", "b"]}
    stored = service.store(memory_request(key="structured", value=value))
    fetched = MemoryService(SQLiteMemoryRepository(db_path)).retrieve(
        __import__("app.schemas.memory", fromlist=["MemoryRetrieveRequest"]).MemoryRetrieveRequest(
            user_id="user-1", memory_id=stored.memory_id, current_time=NOW
        )
    )
    assert fetched.memory.value == value


def test_memory_invalid_non_json_value_is_handled_without_silent_failure(tmp_path):
    db_path = tmp_path / "memory.db"
    repo = SQLiteMemoryRepository(db_path)
    record = memory_request(value=object())
    # Pydantic accepts Any, but SQLite persistence must explicitly reject it.
    with pytest.raises(ValueError, match="JSON-compatible"):
        MemoryService(repo).store(record)


def test_audit_append_and_retrieve_persist_across_instances(tmp_path):
    db_path = tmp_path / "audit.db"
    first = AuditService(SQLiteAuditRepository(db_path))
    created = first.create_event(audit_request())
    assert created.success

    second = AuditService(SQLiteAuditRepository(db_path))
    fetched = second.retrieve_event(
        __import__("app.schemas.audit", fromlist=["AuditEventRetrieveRequest"]).AuditEventRetrieveRequest(
            event_id=created.event_id
        )
    )
    assert fetched.success
    assert fetched.event.message == "Action completed"


def test_audit_append_only_duplicate_is_rejected(tmp_path):
    db_path = tmp_path / "audit.db"
    repo = SQLiteAuditRepository(db_path)
    event = AuditService(repo).create_event(audit_request()).event
    with pytest.raises(ValueError, match="already exists"):
        repo.create(event)


def test_audit_filtering_and_search(tmp_path):
    db_path = tmp_path / "audit.db"
    service = AuditService(SQLiteAuditRepository(db_path))
    service.create_event(audit_request(message="Permission checked"))
    service.create_event(audit_request(module="memory", event_type="memory_stored", message="Memory saved"))

    filtered = service.list_events(AuditEventListRequest(module="memory"))
    assert filtered.total == 1

    searched = service.search_events(AuditEventSearchRequest(query="permission"))
    assert searched.total == 1


def test_audit_pagination_and_deterministic_ordering(tmp_path):
    db_path = tmp_path / "audit.db"
    service = AuditService(SQLiteAuditRepository(db_path))
    for i in range(5):
        service.create_event(audit_request(timestamp=NOW + timedelta(seconds=i), message=f"event {i}"))
    result = service.list_events(AuditEventListRequest(limit=2, offset=1))
    assert len(result.events) == 2
    assert result.total == 5


def test_audit_integrity_hash_survives_round_trip(tmp_path):
    db_path = tmp_path / "audit.db"
    service = AuditService(SQLiteAuditRepository(db_path))
    event = service.create_event(audit_request()).event
    reopened = AuditService(SQLiteAuditRepository(db_path))
    fetched = reopened.retrieve_event(
        __import__("app.schemas.audit", fromlist=["AuditEventRetrieveRequest"]).AuditEventRetrieveRequest(
            event_id=event.event_id
        )
    ).event
    assert fetched.integrity_hash == event.integrity_hash
    assert reopened.verify_integrity(fetched) is True


def test_audit_tampering_is_detected_after_retrieval(tmp_path):
    db_path = tmp_path / "audit.db"
    service = AuditService(SQLiteAuditRepository(db_path))
    event = service.create_event(audit_request()).event
    tampered = event.model_copy(update={"message": "tampered"})
    assert service.verify_integrity(tampered) is False


def test_audit_secret_is_not_stored(tmp_path):
    db_path = tmp_path / "audit.db"
    service = AuditService(SQLiteAuditRepository(db_path))
    with pytest.raises(ValueError):
        service.create_event(audit_request(metadata={"api_key": "secret-value"}))
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 0


def test_audit_user_isolation(tmp_path):
    db_path = tmp_path / "audit.db"
    service = AuditService(SQLiteAuditRepository(db_path))
    user1 = uuid4()
    user2 = uuid4()
    service.create_event(audit_request(user_id=user1))
    service.create_event(audit_request(user_id=user2))
    result = service.list_events(AuditEventListRequest(user_id=user1))
    assert result.total == 1
    assert result.events[0].user_id == user1


def test_parameterized_sql_is_used():
    for path in [
        Path("app/persistence/repositories/memory_repository.py"),
        Path("app/persistence/repositories/audit_repository.py"),
    ]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        sql_literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        assert not any("SELECT * FROM memories WHERE memory_id = '"
                       in value for value in sql_literals)
        assert not any("SELECT * FROM audit_events WHERE event_id = '"
                       in value for value in sql_literals)


def test_invalid_database_path_does_not_get_silently_swallowed(tmp_path):
    bad_path = tmp_path / "existing-directory"
    bad_path.mkdir()
    with pytest.raises(sqlite3.Error):
        SQLiteMemoryRepository(bad_path)


def test_in_memory_memory_repository_still_works():
    service = MemoryService()
    result = service.store(memory_request())
    assert result.success


def test_in_memory_audit_repository_still_works():
    service = AuditService()
    result = service.create_event(audit_request())
    assert result.success


def test_assistant_api_still_works():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/assistant",
        json={
            "content": "hello",
            "current_datetime": "2026-09-24T08:00:00+05:30",
        },
    )
    assert response.status_code == 200


def test_persistence_has_no_external_network_calls():
    root = Path(__file__).resolve().parents[1] / "app" / "persistence"
    forbidden = {"requests", "httpx", "aiohttp", "urllib3", "urllib.request"}
    violations = []
    for source in root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden:
                        violations.append(f"{source}: {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module in forbidden or node.module.split(".")[0] in forbidden:
                    violations.append(f"{source}: {node.module}")
    assert not violations, "\n".join(violations)


def test_no_secrets_in_persistence_source():
    root = Path(__file__).resolve().parents[1] / "app" / "persistence"
    text = "\n".join(p.read_text(encoding="utf-8").lower() for p in root.rglob("*.py"))
    assert "api_key =" not in text
    assert "password =" not in text
    assert "secret =" not in text
