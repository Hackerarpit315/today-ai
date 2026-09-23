from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas.security import *
from app.services.security_service import *
import app.services.security_service as ss

_pattern_result=ss._pattern_result
_data_exposure=ss._data_exposure


RID=uuid4()
def req(**kw): return SecurityCheckRequest(request_id=RID, **kw)

def test_valid_security_request(): assert check_request(req(content="hello")).decision == SecurityDecisionType.allow
def test_uuid_validation():
    with pytest.raises(ValidationError): SecurityCheckRequest(request_id="bad")
def test_policy_version(): assert req().policy_version == "1.0"
def test_low_risk_allowed_input(): assert check_request(req(content="Read my notes")).blocked is False
def test_secret_detection(): assert not detect_secret("password=myPassword123", {}).passed
def test_password_detection(): assert not detect_secret("password=myPassword123", {}).passed
def test_otp_detection(): assert not detect_secret("otp=123456", {}).passed
def test_api_key_detection(): assert not detect_secret("api_key=abcdefgh123", {}).passed
def test_access_token_detection(): assert not detect_secret("access_token=abcdefgh123", {}).passed
def test_bearer_detection(): assert not detect_secret("Authorization: Bearer abcdefgh123", {}).passed
def test_private_key_detection(): assert not detect_secret("-----BEGIN PRIVATE KEY-----", {}).passed
def test_secret_not_leaked_in_response():
    d=check_request(req(content="password=SuperSecret123")); s=d.model_dump_json(); assert "SuperSecret123" not in s

def test_secret_not_leaked_in_exception():
    with pytest.raises(ValidationError) as e: SecurityCheckRequest.model_validate({"request_id":str(RID),"metadata":{"password":"SuperSecret123"},"bad":1})
    assert "SuperSecret123" not in str(e.value)

def test_http_url_allowed(): assert check_url(URLSecurityRequest(request_id=RID,url="http://example.com")).decision == SecurityDecisionType.allow
def test_https_url_allowed(): assert check_url(URLSecurityRequest(request_id=RID,url="https://example.com/path")).decision == SecurityDecisionType.allow
def test_file_url_blocked(): assert check_url(URLSecurityRequest(request_id=RID,url="file:///etc/passwd")).blocked
def test_javascript_url_blocked(): assert check_url(URLSecurityRequest(request_id=RID,url="javascript:alert(1)")).blocked
def test_data_url_blocked(): assert check_url(URLSecurityRequest(request_id=RID,url="data:text/plain,hello")).blocked
def test_vbscript_url_blocked(): assert check_url(URLSecurityRequest(request_id=RID,url="vbscript:msgbox(1)")).blocked
def test_malformed_url(): assert check_url(URLSecurityRequest(request_id=RID,url="https://")).blocked
def test_embedded_credential_url(): assert check_url(URLSecurityRequest(request_id=RID,url="https://user:pass@example.com")).blocked
def test_command_semicolon(): assert not _pattern_result(SecurityCheckType.command_injection_detection,ss.COMMAND_PATTERNS,"hello; whoami",ThreatType.command_injection,"x").passed
def test_command_andand(): assert not _pattern_result(SecurityCheckType.command_injection_detection,ss.COMMAND_PATTERNS,"echo hi && whoami",ThreatType.command_injection,"x").passed
def test_command_oror(): assert not _pattern_result(SecurityCheckType.command_injection_detection,ss.COMMAND_PATTERNS,"a || whoami",ThreatType.command_injection,"x").passed
def test_pipe_injection(): assert not _pattern_result(SecurityCheckType.command_injection_detection,ss.COMMAND_PATTERNS,"a | whoami",ThreatType.command_injection,"x").passed
def test_command_substitution(): assert not _pattern_result(SecurityCheckType.command_injection_detection,ss.COMMAND_PATTERNS,"$(whoami)",ThreatType.command_injection,"x").passed
def test_powershell_pattern(): assert not _pattern_result(SecurityCheckType.command_injection_detection,ss.COMMAND_PATTERNS,"powershell.exe -Command x",ThreatType.command_injection,"x").passed
def test_cmd_pattern(): assert not _pattern_result(SecurityCheckType.command_injection_detection,ss.COMMAND_PATTERNS,"cmd.exe /c dir",ThreatType.command_injection,"x").passed
def test_shell_pattern(): assert not _pattern_result(SecurityCheckType.command_injection_detection,ss.COMMAND_PATTERNS,"bash -c id",ThreatType.command_injection,"x").passed
def test_script_tag(): assert not _pattern_result(SecurityCheckType.script_injection_detection,ss.SCRIPT_PATTERNS,"<script>alert(1)</script>",ThreatType.script_injection,"x").passed
def test_javascript_pattern(): assert not _pattern_result(SecurityCheckType.script_injection_detection,ss.SCRIPT_PATTERNS,"javascript:alert(1)",ThreatType.script_injection,"x").passed
def test_event_handler_pattern(): assert not _pattern_result(SecurityCheckType.script_injection_detection,ss.SCRIPT_PATTERNS,'<img onerror="x">',ThreatType.script_injection,"x").passed
def test_eval_pattern(): assert not _pattern_result(SecurityCheckType.script_injection_detection,ss.SCRIPT_PATTERNS,"eval(x)",ThreatType.script_injection,"x").passed
def test_traversal_forward(): assert not _pattern_result(SecurityCheckType.path_traversal_detection,ss.TRAVERSAL_PATTERNS,"../../etc/passwd",ThreatType.path_traversal,"x").passed
def test_traversal_backslash(): assert not _pattern_result(SecurityCheckType.path_traversal_detection,ss.TRAVERSAL_PATTERNS,"..\\windows\\system32",ThreatType.path_traversal,"x").passed
def test_encoded_traversal(): assert not _pattern_result(SecurityCheckType.path_traversal_detection,ss.TRAVERSAL_PATTERNS,"%2e%2e%2fsecret",ThreatType.path_traversal,"x").passed
def test_oversized_payload(): assert check_request(req(content="x"*(ss.MAX_TEXT_LENGTH+1),check_types=[SecurityCheckType.input_validation])).blocked
def test_oversized_url(): assert check_url(URLSecurityRequest(request_id=RID,url="https://example.com/"+"x"*ss.MAX_URL_LENGTH)).blocked
def test_oversized_metadata(): assert check_request(req(metadata={"x":"y"*ss.MAX_METADATA_SIZE},check_types=[SecurityCheckType.input_validation])).blocked
def test_control_character_handling(): assert check_request(req(content="hello\x00world",check_types=[SecurityCheckType.input_validation])).decision == SecurityDecisionType.allow
def test_email_detection(): assert not _data_exposure("a@example.com",{}).passed
def test_phone_detection(): assert not _data_exposure("+91 98765 43210",{}).passed
def test_payment_card_detection(): assert not _data_exposure("4111 1111 1111 1111",{}).passed
def test_credential_exposure_classification(): assert _data_exposure("token=abc123456789",{}).threat_type == ThreatType.credential_exposure
def test_safe_information_action(): assert action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.information)).risk_level == RiskLevel.low
def test_unknown_action(): assert action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.unknown)).risk_level == RiskLevel.high
def test_financial_action(): assert action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.financial)).risk_level == RiskLevel.critical
def test_deletion_action(): assert action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.deletion)).risk_level == RiskLevel.high
def test_authentication_action(): assert action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.authentication)).risk_level == RiskLevel.critical
def test_external_side_effect_risk(): assert action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.external_side_effect)).risk_level == RiskLevel.medium
def test_permission_security_conflict():
    d=permission_policy_check(SecurityPolicyRequest(request_id=RID,permission_granted=True,action_category=ActionCategory.authentication,credential_handling=True)); assert d.blocked

def test_request_integrity_validation(): assert not check_request(req(check_types=[SecurityCheckType.request_integrity_check])).blocked
def test_deterministic_repeated_result():
    a=check_request(req(content="hello; world")); b=check_request(req(content="hello; world")); assert a.decision==b.decision and a.threat_types==b.threat_types and a.risk_level==b.risk_level

def test_threat_ordering_deterministic():
    d=check_request(req(content="password=x; javascript:alert(1) ../x",check_types=[SecurityCheckType.secret_detection,SecurityCheckType.command_injection_detection,SecurityCheckType.script_injection_detection,SecurityCheckType.path_traversal_detection])); assert d.threat_types == sorted(d.threat_types,key=lambda x: ss.THREAT_ORDER[x])
def test_extra_field_rejection():
    with pytest.raises(ValidationError): SecurityCheckRequest(request_id=RID,unknown_field=1)
def test_invalid_enum_rejection():
    with pytest.raises(ValidationError): ActionSecurityRequest(request_id=RID,action_category="not_real")
def test_invalid_uuid_rejection():
    with pytest.raises(ValidationError): URLSecurityRequest(request_id="bad",url="https://example.com")
def test_sanitization_behavior(): assert sanitize_text("  hello   world  ")[0] == "hello world"
def test_unsafe_sanitization_blocked():
    with pytest.raises(ValueError): sanitize_text("password=secret")
def test_policy_version_consistency():
    assert check_request(req()).policy_version == POLICY_VERSION
    assert check_url(URLSecurityRequest(request_id=RID,url="https://example.com")).policy_version == POLICY_VERSION

def test_metadata_secret_key_detected(): assert not detect_secret("",{"password":"hidden"}).passed
def test_metadata_nested_secret_detected(): assert not detect_secret("",{"user":{"api_key":"hidden"}}).passed
def test_jwt_like_detection(): assert not detect_secret("eyJabc.def.ghi",{}).passed
def test_control_url_blocked(): assert check_url(URLSecurityRequest(request_id=RID,url="https://example.com/\x00x")).blocked
def test_communication_medium_risk(): assert action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.communication)).risk_level == RiskLevel.medium
def test_draft_low_risk(): assert action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.draft)).risk_level == RiskLevel.low
def test_credential_handling_blocks_even_with_permission():
    d=action_check(ActionSecurityRequest(request_id=RID,action_category=ActionCategory.communication,permission_granted=True,credential_handling=True)); assert d.blocked and d.risk_level==RiskLevel.critical
