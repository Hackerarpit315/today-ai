from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.schemas.audit import *
from app.services.audit_service import AuditService

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def make_request(**overrides):
    data = dict(
        request_id=UUID("11111111-1111-1111-1111-111111111111"), timestamp=NOW,
        module="action", event_type="action_executed", status="success", severity="info", actor="module",
        message="Action completed", metadata={"adapter": "dry_run"},
        correlation_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    data.update(overrides)
    return AuditEventCreateRequest(**data)


def create(service, **kwargs):
    response = service.create_event(make_request(**kwargs))
    assert response.success
    return response.event


def test_valid_audit_event_creation():
    e = create(AuditService())
    assert e and e.message == "Action completed"


def test_uuid_validation():
    with pytest.raises(ValidationError): make_request(request_id="bad")


def test_timestamp_validation():
    with pytest.raises(ValidationError): make_request(timestamp=datetime(2026, 1, 1))


def test_module_validation():
    with pytest.raises(ValidationError): make_request(module="unknown_module")


def test_event_type_validation():
    with pytest.raises(ValidationError): make_request(event_type="anything")


def test_status_validation():
    with pytest.raises(ValidationError): make_request(status="done")


def test_severity_validation():
    with pytest.raises(ValidationError): make_request(severity="urgent")


def test_actor_validation():
    with pytest.raises(ValidationError): make_request(actor="bot")


def test_request_id_correlation():
    e = create(AuditService())
    assert e.request_id == make_request().request_id


def test_correlation_id():
    c = uuid4(); e = create(AuditService(), correlation_id=c); assert e.correlation_id == c


def test_parent_event_id():
    p = uuid4(); e = create(AuditService(), parent_event_id=p); assert e.parent_event_id == p


def test_action_id():
    a = uuid4(); e = create(AuditService(), action_id=a); assert e.action_id == a


def test_resource_type():
    e = create(AuditService(), resource_type="memory"); assert e.resource_type == "memory"


def test_resource_id():
    r = uuid4(); e = create(AuditService(), resource_id=r); assert e.resource_id == r


def test_message_validation():
    with pytest.raises(ValidationError): make_request(message="")


def test_metadata_validation():
    e = create(AuditService(), metadata={"verification_level": "direct", "attempt": 1}); assert e.metadata["attempt"] == 1


@pytest.mark.parametrize("secret", [
    {"password": "mypassword123"}, {"otp": "123456"}, {"api_key": "abcdef1234567890"},
    {"access_token": "abc123456789"}, {"refresh_token": "abc123456789"},
    {"secret": "hidden-value"}, {"private_key": "-----BEGIN PRIVATE KEY-----"},
    {"authorization": "Bearer abcdefghijklmnop"},
])
def test_secret_rejection(secret):
    with pytest.raises(ValueError, match="Sensitive credential data"):
        AuditService().create_event(make_request(metadata=secret))


def test_immutable_event_behavior():
    s = AuditService(); e = create(s); original_hash = e.integrity_hash
    with pytest.raises(ValueError): e.message = "changed"
    assert e.integrity_hash == original_hash


def test_no_update_operation():
    assert not hasattr(AuditService, "update_event")


def test_no_delete_operation():
    assert not hasattr(AuditService, "delete_event")


def test_retrieve_existing_event():
    s = AuditService(); e = create(s); result = s.retrieve_event(AuditEventRetrieveRequest(event_id=e.event_id)); assert result.success and result.event.event_id == e.event_id


def test_retrieve_missing_event():
    result = AuditService().retrieve_event(AuditEventRetrieveRequest(event_id=uuid4())); assert not result.success and result.status == "not_found"


def test_list_events():
    s = AuditService(); create(s); create(s); assert s.list_events(AuditEventListRequest()).total == 2


def test_filter_request_id():
    s = AuditService(); r1=uuid4(); r2=uuid4(); create(s, request_id=r1); create(s, request_id=r2); result=s.list_events(AuditEventListRequest(request_id=r1)); assert result.total == 1


def test_filter_module():
    s=AuditService(); create(s,module="action"); create(s,module="memory"); assert s.list_events(AuditEventListRequest(module="memory")).total == 1


def test_filter_event_type():
    s=AuditService(); create(s,event_type="warning"); create(s,event_type="action_executed"); assert s.list_events(AuditEventListRequest(event_type="warning")).total == 1


def test_filter_status():
    s=AuditService(); create(s,status="success"); create(s,status="blocked"); assert s.list_events(AuditEventListRequest(status="blocked")).total == 1


def test_filter_severity():
    s=AuditService(); create(s,severity="high"); create(s,severity="info"); assert s.list_events(AuditEventListRequest(severity="high")).total == 1


def test_filter_actor():
    s=AuditService(); create(s,actor="module"); create(s,actor="user"); assert s.list_events(AuditEventListRequest(actor="user")).total == 1


def test_filter_action_id():
    s=AuditService(); a=uuid4(); create(s,action_id=a); create(s); assert s.list_events(AuditEventListRequest(action_id=a)).total == 1


def test_filter_resource():
    s=AuditService(); r=uuid4(); create(s,resource_type="memory",resource_id=r); create(s,resource_type="task"); assert s.list_events(AuditEventListRequest(resource_type="memory",resource_id=r)).total == 1


def test_search_by_message():
    s=AuditService(); create(s,message="Permission required before sending email"); create(s,message="Task completed"); assert s.search_events(AuditEventSearchRequest(query="sending email")).total == 1


def test_search_by_event_type():
    s=AuditService(); create(s,event_type="warning"); create(s,event_type="action_executed"); assert s.search_events(AuditEventSearchRequest(query="warning")).total == 1


def test_pagination():
    s=AuditService();
    for i in range(5): create(s,timestamp=NOW+timedelta(seconds=i))
    result=s.list_events(AuditEventListRequest(limit=2,offset=1)); assert len(result.events)==2 and result.total==5


def test_deterministic_ordering():
    s=AuditService(); e1=create(s,timestamp=NOW+timedelta(seconds=2)); e2=create(s,timestamp=NOW+timedelta(seconds=1));
    result=s.list_events(AuditEventListRequest()); assert [e.event_id for e in result.events]==[e2.event_id,e1.event_id]


def test_event_count():
    s=AuditService(); create(s); create(s); assert s.count_events()==2


def test_integrity_hash_creation():
    e=create(AuditService()); assert len(e.integrity_hash)==64


def test_integrity_verification_success():
    s=AuditService(); e=create(s); assert s.verify_integrity(e) is True


def test_integrity_verification_failure():
    s=AuditService(); e=create(s); tampered=e.model_copy(update={"integrity_hash": "0"*64}); assert s.verify_integrity(tampered) is False


def test_modified_message_detection():
    s=AuditService(); e=create(s); object.__setattr__(e,"message","tampered"); assert s.verify_integrity(e) is False


def test_modified_status_detection():
    s=AuditService(); e=create(s); object.__setattr__(e,"status",AuditStatus.failure); assert s.verify_integrity(e) is False


def test_modified_metadata_detection():
    s=AuditService(); e=create(s); object.__setattr__(e,"metadata",{"changed":True}); assert s.verify_integrity(e) is False


def test_modified_resource_detection():
    s=AuditService(); e=create(s); object.__setattr__(e,"resource_id",uuid4()); assert s.verify_integrity(e) is False


def test_deterministic_repeated_results():
    s=AuditService(); e=create(s); assert s.calculate_integrity_hash(e)==s.calculate_integrity_hash(e)


def test_schema_extra_field_rejection():
    with pytest.raises(ValidationError): make_request(extra_field=True)


def test_invalid_uuid_rejection():
    with pytest.raises(ValidationError): AuditEventRetrieveRequest(event_id="not-a-uuid")


def test_user_isolation():
    s=AuditService(); u1=uuid4(); u2=uuid4(); create(s,user_id=u1); create(s,user_id=u2); result=s.list_events(AuditEventListRequest(user_id=u1)); assert result.total==1 and result.events[0].user_id==u1


def test_correlation_chain():
    s=AuditService(); r=uuid4(); c=uuid4(); a=uuid4(); e1=create(s,request_id=r,correlation_id=c); e2=create(s,request_id=r,correlation_id=c,parent_event_id=e1.event_id,action_id=a); result=s.list_events(AuditEventListRequest(request_id=r,correlation_id=c)); assert len(result.events)==2 and any(e.parent_event_id==e1.event_id for e in result.events)


def test_descending_order():
    s=AuditService(); e1=create(s,timestamp=NOW); e2=create(s,timestamp=NOW+timedelta(seconds=1)); result=s.list_events(AuditEventListRequest(ascending=False)); assert result.events[0].event_id==e2.event_id


def test_count_filtered():
    s=AuditService(); create(s,status="success"); create(s,status="blocked"); assert s.count_events(AuditEventListRequest(status="blocked"))==1


def test_metadata_is_json_compatible():
    with pytest.raises(ValueError, match="JSON-compatible"):
        AuditService().create_event(make_request(metadata={"bad": {1,2}}))


def test_metadata_size_limit():
    with pytest.raises(ValueError):
        AuditService().create_event(make_request(metadata={"x": "a"*17000}))


def test_integrity_endpoint_result():
    s=AuditService(); e=create(s); result=s.verify_event_integrity(e.event_id); assert result.valid is True


def test_integrity_missing_event():
    result=AuditService().verify_event_integrity(uuid4()); assert result.success is False and result.valid is False


def test_event_id_is_unique():
    s=AuditService(); e1=create(s); e2=create(s); assert e1.event_id != e2.event_id


def test_timestamp_preserved():
    e=create(AuditService(), timestamp=NOW); assert e.timestamp == NOW


def test_optional_fields_preserved():
    e=create(AuditService(), error_code="E1", reason="blocked", duration_ms=42, ip_hash="hash", policy_version="v1"); assert (e.error_code,e.reason,e.duration_ms,e.ip_hash,e.policy_version)==("E1","blocked",42,"hash","v1")


def test_search_case_insensitive():
    s=AuditService(); create(s,message="Permission CHECKED"); assert s.search_events(AuditEventSearchRequest(query="permission checked")).total==1


def test_search_module_case_insensitive():
    s=AuditService(); create(s,module="action"); assert s.search_events(AuditEventSearchRequest(query="ACTION")).total==1


def test_search_pagination_is_deterministic():
    s=AuditService();
    for i in range(4): create(s,timestamp=NOW+timedelta(seconds=i),message="same")
    a=s.search_events(AuditEventSearchRequest(query="same",limit=2,offset=1)); b=s.search_events(AuditEventSearchRequest(query="same",limit=2,offset=1)); assert [x.event_id for x in a.events]==[x.event_id for x in b.events]


def test_create_does_not_change_input_request():
    s=AuditService(); req=make_request(); before=req.model_dump(); s.create_event(req); assert req.model_dump()==before


def test_event_model_rejects_missing_integrity_hash():
    with pytest.raises(ValidationError):
        AuditEvent(**make_request().model_dump())


def test_secret_in_message_is_rejected_without_echoing_secret():
    secret = "password=super-secret-value"
    with pytest.raises(ValueError, match="Sensitive credential data") as exc_info:
        AuditService().create_event(make_request(message=secret))
    assert secret not in str(exc_info.value)


def test_audit_repository_failure_is_safe_and_does_not_leak_storage_error():
    class FailingRepository:
        def create(self, _event):
            raise RuntimeError("sqlite password=super-secret-value leaked")

        def get_by_id(self, _event_id):
            return None

        def all(self):
            return []

        def list(self, events, *, ascending, offset, limit):
            return []

        def search(self, events, query, *, ascending, offset, limit):
            return []

        def count(self, events):
            return 0

    with pytest.raises(ValueError, match="Audit event could not be recorded") as exc_info:
        AuditService(FailingRepository()).create_event(make_request())
    assert "super-secret-value" not in str(exc_info.value)


def test_audit_module_has_no_external_network_or_dynamic_execution():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    forbidden_imports = {"requests", "httpx", "aiohttp", "urllib3", "urllib.request"}
    forbidden_calls = {"urlopen", "urlretrieve", "system", "popen", "eval", "exec"}
    violations = []
    for source in [root / "services" / "audit_service.py", root / "services" / "audit", root / "api" / "routes" / "audit.py"]:
        paths = [source] if source.is_file() else list(source.rglob("*.py"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in forbidden_imports:
                            violations.append(f"{path}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".")[0] in forbidden_imports:
                        violations.append(f"{path}: from {node.module}")
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in forbidden_calls:
                        violations.append(f"{path}: {node.func.id}()")
    assert not violations, "\\n".join(violations)
