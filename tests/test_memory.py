from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.memory import (
    Importance,
    MemoryListRequest,
    MemoryRetrieveRequest,
    MemoryStoreRequest,
    MemoryType,
    Sensitivity,
)
from app.services.memory_service import MemoryService

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(hours=1)


def req(**overrides):
    data = dict(
        user_id="user-1",
        memory_type=MemoryType.preference,
        key="preferred_language",
        value="Hindi",
        importance=Importance.medium,
        sensitivity=Sensitivity.normal,
        source="user_explicit",
        current_time=NOW,
    )
    data.update(overrides)
    return MemoryStoreRequest(**data)


def retrieve(service, memory_id, user="user-1", now=LATER):
    from app.schemas.memory import MemoryRetrieveRequest
    return service.retrieve(
        MemoryRetrieveRequest(user_id=user, memory_id=memory_id, current_time=now)
    )


def test_valid_memory_creation():
    result = MemoryService().store(req())
    assert result.success and result.status == "stored"
    assert result.memory.key == "preferred_language"


def test_memory_id_generation():
    result = MemoryService().store(req())
    assert isinstance(result.memory.memory_id, UUID)


def test_timestamp_creation():
    result = MemoryService().store(req())
    assert result.memory.created_at == NOW
    assert result.memory.updated_at == NOW


def test_version_starts_at_one():
    result = MemoryService().store(req())
    assert result.memory.version == 1


@pytest.mark.parametrize(
    "memory_type",
    [
        MemoryType.preference,
        MemoryType.profile,
        MemoryType.goal,
        MemoryType.project,
        MemoryType.task_context,
        MemoryType.routine,
    ],
)
def test_supported_memory_types(memory_type):
    result = MemoryService().store(req(memory_type=memory_type, key=f"k-{memory_type.value}"))
    assert result.success


def test_temporary_memory():
    result = MemoryService().store(req(memory_type=MemoryType.temporary, key="session_note"))
    assert result.memory.memory_type == MemoryType.temporary


def test_expiration():
    service = MemoryService()
    result = service.store(req(expires_at=NOW + timedelta(minutes=30)))
    found = retrieve(service, result.memory_id, now=NOW + timedelta(minutes=31))
    assert found.status == "expired"
    assert found.success is False


def test_retrieve_existing_memory():
    service = MemoryService()
    stored = service.store(req())
    found = retrieve(service, stored.memory_id)
    assert found.success and found.status == "found"


def test_retrieve_missing_memory():
    from uuid import uuid4
    from app.schemas.memory import MemoryRetrieveRequest
    result = MemoryService().retrieve(
        MemoryRetrieveRequest(user_id="user-1", memory_id=uuid4(), current_time=NOW)
    )
    assert result.status == "not_found"


def test_list_memories():
    service = MemoryService()
    service.store(req())
    service.store(req(key="theme", value="dark"))
    result = service.list(
        MemoryListRequest(user_id="user-1", current_time=LATER)
    )
    assert len(result.memories) == 2


def test_filter_by_user_id():
    service = MemoryService()
    service.store(req())
    service.store(req(user_id="user-2", key="x", value="y"))
    result = service.list(MemoryListRequest(user_id="user-1", current_time=LATER))
    assert len(result.memories) == 1
    assert result.memories[0].user_id == "user-1"


def test_filter_by_memory_type():
    service = MemoryService()
    service.store(req())
    service.store(req(memory_type=MemoryType.goal, key="goal", value="learn"))
    result = service.list(
        MemoryListRequest(user_id="user-1", memory_type=MemoryType.goal, current_time=LATER)
    )
    assert len(result.memories) == 1


def test_filter_by_key():
    service = MemoryService()
    service.store(req())
    service.store(req(key="theme", value="dark"))
    result = service.list(
        MemoryListRequest(user_id="user-1", key="theme", current_time=LATER)
    )
    assert [m.key for m in result.memories] == ["theme"]


def test_user_isolation():
    service = MemoryService()
    stored = service.store(req())
    assert retrieve(service, stored.memory_id, user="user-2").status == "not_found"


def test_update_memory():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryUpdateRequest
    updated = service.update(
        MemoryUpdateRequest(
            user_id="user-1",
            memory_id=stored.memory_id,
            value="English",
            current_time=LATER,
        )
    )
    assert updated.success and updated.memory.value == "English"


def test_version_increment():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryUpdateRequest
    updated = service.update(
        MemoryUpdateRequest(user_id="user-1", memory_id=stored.memory_id, value="English", current_time=LATER)
    )
    assert updated.memory.version == 2
    assert updated.memory.created_at == NOW
    assert updated.memory.updated_at == LATER


def test_forget_memory():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryForgetRequest
    result = service.forget(
        MemoryForgetRequest(user_id="user-1", memory_id=stored.memory_id, current_time=LATER)
    )
    assert result.status == "forgotten"


def test_forgotten_memory_exclusion():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryForgetRequest
    service.forget(
        MemoryForgetRequest(user_id="user-1", memory_id=stored.memory_id, current_time=LATER)
    )
    assert retrieve(service, stored.memory_id).status == "not_found"
    assert service.list(MemoryListRequest(user_id="user-1", current_time=LATER)).memories == []


def test_duplicate_detection():
    service = MemoryService()
    first = service.store(req())
    second = service.store(req())
    assert second.status == "duplicate"
    assert second.memory_id == first.memory_id


def test_conflicting_memory_detection():
    service = MemoryService()
    service.store(req())
    result = service.store(req(value="English"))
    assert result.status == "conflict"
    assert result.success is False


def test_importance_validation():
    with pytest.raises(ValidationError):
        req(importance="urgent")


def test_sensitivity_validation():
    with pytest.raises(ValidationError):
        req(sensitivity="secret")


@pytest.mark.parametrize(
    "key,value",
    [
        ("password", "do-not-store"),
        ("passwd", "do-not-store"),
        ("api_key", "do-not-store"),
        ("access_token", "do-not-store"),
        ("refresh_token", "do-not-store"),
        ("private_key", "do-not-store"),
        ("credential", "authorization: bearer abcdefghijklmnop"),
    ],
)
def test_secret_rejection(key, value):
    result = MemoryService().store(req(key=key, value=value))
    assert result.status == "rejected"
    assert "do-not-store" not in result.reason
    assert "abcdef" not in result.reason


def test_otp_rejection():
    result = MemoryService().store(req(key="login_otp", value="123456"))
    assert result.status == "rejected"


def test_authorization_token_rejection():
    result = MemoryService().store(
        req(key="session", value="Bearer abcdefghijklmnopQRST")
    )
    assert result.status == "rejected"


def test_deterministic_ordering():
    service = MemoryService()
    service.store(req(key="low", value="1", importance=Importance.low))
    service.store(req(key="high", value="2", importance=Importance.high))
    service.store(req(key="critical", value="3", importance=Importance.critical))
    result = service.list(MemoryListRequest(user_id="user-1", current_time=LATER))
    assert [m.importance for m in result.memories] == [
        Importance.critical, Importance.high, Importance.low
    ]


def test_schema_extra_field_rejection():
    with pytest.raises(ValidationError):
        req(unexpected="value")


def test_invalid_uuid_rejection():
    from app.schemas.memory import MemoryRetrieveRequest
    with pytest.raises(ValidationError):
        MemoryRetrieveRequest(user_id="user-1", memory_id="not-a-uuid", current_time=NOW)


def test_invalid_timestamp_rejection():
    with pytest.raises(ValidationError):
        MemoryRetrieveRequest(
            user_id="user-1",
            memory_id="00000000-0000-0000-0000-000000000001",
            current_time="2026-01-01T12:00:00",
        )


def test_expired_memory_excluded_from_list():
    service = MemoryService()
    service.store(req(expires_at=NOW + timedelta(minutes=1)))
    result = service.list(MemoryListRequest(user_id="user-1", current_time=LATER))
    assert result.memories == []


def test_temporary_memory_expiry_behavior():
    service = MemoryService()
    stored = service.store(
        req(
            memory_type=MemoryType.temporary,
            key="temporary_context",
            value="short-lived",
            expires_at=NOW + timedelta(minutes=1),
        )
    )
    assert retrieve(service, stored.memory_id, now=NOW + timedelta(minutes=2)).status == "expired"


def test_repeated_operations_have_same_logical_result():
    service = MemoryService()
    first = service.store(req())
    second = service.store(req())
    assert second.status == "duplicate"
    assert second.memory_id == first.memory_id


def test_source_is_preserved():
    result = MemoryService().store(req(source="imported"))
    assert result.memory.source.value == "imported"


def test_sensitive_non_secret_value_is_allowed():
    result = MemoryService().store(
        req(key="medical_note", value="private preference", sensitivity=Sensitivity.sensitive)
    )
    assert result.success
    assert result.memory.sensitivity == Sensitivity.sensitive


def test_highly_sensitive_non_credential_value_is_allowed():
    result = MemoryService().store(
        req(key="important_context", value="do not share casually", sensitivity=Sensitivity.highly_sensitive)
    )
    assert result.success


def test_update_rechecks_secret_detection():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryUpdateRequest
    result = service.update(
        MemoryUpdateRequest(
            user_id="user-1",
            memory_id=stored.memory_id,
            value="password=hidden",
            current_time=LATER,
        )
    )
    assert result.status == "rejected"


def test_forget_does_not_physically_delete_record():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryForgetRequest
    service.forget(
        MemoryForgetRequest(user_id="user-1", memory_id=stored.memory_id, current_time=LATER)
    )
    raw = service.repository.get(stored.memory_id)
    assert raw is not None
    assert raw.status.value == "forgotten"


def test_archived_memory_not_returned_as_active():
    service = MemoryService()
    stored = service.store(req())
    record = service.repository.get(stored.memory_id)
    record.status = "archived"
    service.repository.save(record)
    assert retrieve(service, stored.memory_id).status == "not_found"


def test_list_query_matching():
    service = MemoryService()
    service.store(req(key="language", value="Hindi"))
    service.store(req(key="theme", value="dark"))
    result = service.list(
        MemoryListRequest(user_id="user-1", query="hindi", current_time=LATER)
    )
    assert len(result.memories) == 1
    assert result.memories[0].key == "language"


def test_expiring_store_is_not_active():
    result = MemoryService().store(req(expires_at=NOW))
    assert result.memory.status.value == "expired"


def test_update_expiring_value_marks_expired():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryUpdateRequest
    result = service.update(
        MemoryUpdateRequest(
            user_id="user-1",
            memory_id=stored.memory_id,
            value="English",
            expires_at=NOW,
            current_time=LATER,
        )
    )
    assert result.memory.status.value == "expired"


def test_cross_user_list_isolation_with_same_key():
    service = MemoryService()
    service.store(req())
    service.store(req(user_id="user-2", value="English"))
    result = service.list(MemoryListRequest(user_id="user-2", current_time=LATER))
    assert len(result.memories) == 1
    assert result.memories[0].value == "English"


def test_unknown_memory_type_can_be_explicitly_handled():
    result = MemoryService().store(req(memory_type=MemoryType.unknown, key="unknown", value="x"))
    assert result.success


def test_memory_value_is_not_mutated_by_repository_reads():
    service = MemoryService()
    value = {"topic": "AI", "items": ["a"]}
    stored = service.store(req(key="structured", value=value))
    fetched = retrieve(service, stored.memory_id)
    fetched.memory.value["items"].append("b")
    again = retrieve(service, stored.memory_id)
    assert again.memory.value["items"] == ["a"]


def test_update_preserves_memory_id():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryUpdateRequest
    updated = service.update(
        MemoryUpdateRequest(user_id="user-1", memory_id=stored.memory_id, value="English", current_time=LATER)
    )
    assert updated.memory_id == stored.memory_id


def test_update_preserves_creation_timestamp():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryUpdateRequest
    updated = service.update(
        MemoryUpdateRequest(user_id="user-1", memory_id=stored.memory_id, value="English", current_time=LATER)
    )
    assert updated.memory.created_at == NOW


def test_wrong_user_cannot_update():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryUpdateRequest
    result = service.update(
        MemoryUpdateRequest(user_id="user-2", memory_id=stored.memory_id, value="English", current_time=LATER)
    )
    assert result.status == "not_found"


def test_wrong_user_cannot_forget():
    service = MemoryService()
    stored = service.store(req())
    from app.schemas.memory import MemoryForgetRequest
    result = service.forget(
        MemoryForgetRequest(user_id="user-2", memory_id=stored.memory_id, current_time=LATER)
    )
    assert result.status == "not_found"
