from __future__ import annotations

import base64
import json
import re
import urllib.parse
from typing import Any
from uuid import UUID, uuid4

from app.schemas.security import (
    ActionCategory, ActionSecurityRequest, POLICY_VERSION, RiskLevel,
    SecurityCheckRequest, SecurityCheckResult, SecurityCheckType,
    SecurityDecision, SecurityDecisionType, SecurityPolicyRequest,
    ThreatType, URLSecurityRequest,
)

MAX_TEXT_LENGTH = 10_000
MAX_METADATA_SIZE = 32_768
MAX_LIST_ITEMS = 100
MAX_NESTING_DEPTH = 6
MAX_URL_LENGTH = 2_048

SECRET_KEYS = {"password", "passwd", "pwd", "otp", "api_key", "apikey", "access_token", "refresh_token", "secret", "private_key", "client_secret", "authorization", "token"}
THREAT_ORDER = {t: i for i, t in enumerate([ThreatType.secret_exposure, ThreatType.credential_exposure, ThreatType.malicious_url, ThreatType.command_injection, ThreatType.script_injection, ThreatType.path_traversal, ThreatType.oversized_payload, ThreatType.suspicious_payload, ThreatType.data_exposure, ThreatType.unsafe_action, ThreatType.invalid_request, ThreatType.unknown_threat, ThreatType.none])}

SECRET_PATTERNS = [
    ("password", re.compile(r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*[^\s,;]+")),
    ("otp", re.compile(r"(?i)\b(?:otp|one[- ]time[- ]password)\s*[:=]?\s*\d{4,8}\b")),
    ("api_key", re.compile(r"(?i)\b(?:api[_-]?key|apikey)\s*[:=]\s*[A-Za-z0-9_\-]{8,}")),
    ("access_token", re.compile(r"(?i)\baccess[_-]?token\s*[:=]\s*\S+")),
    ("refresh_token", re.compile(r"(?i)\brefresh[_-]?token\s*[:=]\s*\S+")),
    ("client_secret", re.compile(r"(?i)\bclient[_-]?secret\s*[:=]\s*\S+")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("authorization", re.compile(r"(?i)\bauthorization\s*:\s*(?:bearer\s+)?\S+")),
    ("token", re.compile(r"(?i)\btoken\s*[:=]\s*\S+")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
]

COMMAND_PATTERNS = [re.compile(p, re.I) for p in [r";", r"&&", r"\|\|", r"(?<!\|)\|(?!\|)", r"`[^`]+`", r"\$\([^)]*\)", r"\$\{[^}]+\}", r"\b(?:cmd\.exe|powershell(?:\.exe)?|cmd\s+/c|sh\s+-c|bash\s+-c|wget|curl|nc|netcat)\b"]]
SCRIPT_PATTERNS = [re.compile(p, re.I) for p in [r"<script\b", r"javascript:", r"\bonerror\s*=", r"\bonload\s*=", r"\bonclick\s*=", r"document\.cookie", r"\beval\s*\(", r"\bFunction\s*\(", r"innerHTML"]]
TRAVERSAL_PATTERNS = [re.compile(p, re.I) for p in [r"\.\./", r"\.\.\\", r"%2e%2e", r"%2f", r"%5c"]]
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{8,}\d)(?!\d)")
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _json_safe(value: Any, depth: int = 0) -> None:
    if depth > MAX_NESTING_DEPTH:
        raise ValueError("metadata nesting depth exceeded")
    if isinstance(value, dict):
        if len(value) > MAX_LIST_ITEMS:
            raise ValueError("metadata item limit exceeded")
        for k, v in value.items():
            if not isinstance(k, str): raise ValueError("metadata keys must be strings")
            _json_safe(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_LIST_ITEMS: raise ValueError("metadata item limit exceeded")
        for v in value: _json_safe(v, depth + 1)
    elif not isinstance(value, (str, int, float, bool)) and value is not None:
        raise ValueError("metadata must be JSON compatible")


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for k, v in value.items():
            key = f"{prefix}.{k}" if prefix else k
            out.extend(_flatten(v, key))
    elif isinstance(value, list):
        for i, v in enumerate(value): out.extend(_flatten(v, f"{prefix}[{i}]"))
    else:
        out.append((prefix, "" if value is None else str(value)))
    return out


def _secret_types(content: str, metadata: dict[str, Any]) -> list[str]:
    found = {name for name, pattern in SECRET_PATTERNS if pattern.search(content)}
    for key, value in _flatten(metadata):
        leaf = key.rsplit(".", 1)[-1].split("[")[0].lower()
        if leaf in SECRET_KEYS and value:
            found.add(leaf)
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(value): found.add(name)
    return sorted(found)


def _threat_result(check_type: SecurityCheckType, threat: ThreatType, risk: RiskLevel, reason: str) -> SecurityCheckResult:
    return SecurityCheckResult(check_type=check_type, passed=False, risk_level=risk, threat_type=threat, reason=reason)


def _ok(check_type: SecurityCheckType, reason="Security check passed") -> SecurityCheckResult:
    return SecurityCheckResult(check_type=check_type, passed=True, risk_level=RiskLevel.none, threat_type=ThreatType.none, reason=reason)


def _risk_max(levels: list[RiskLevel]) -> RiskLevel:
    order = {RiskLevel.none:0, RiskLevel.low:1, RiskLevel.medium:2, RiskLevel.high:3, RiskLevel.critical:4}
    return max(levels, key=lambda x: order[x], default=RiskLevel.none)


def _decision(request_id: UUID, results: list[SecurityCheckResult], checks: list[SecurityCheckType], reason: str | None = None, sanitize=False) -> SecurityDecision:
    threats = sorted({r.threat_type for r in results if r.threat_type != ThreatType.none}, key=lambda x: THREAT_ORDER[x])
    risk = _risk_max([r.risk_level for r in results])
    failed = [r for r in results if not r.passed]
    if not failed:
        decision = SecurityDecisionType.allow
        blocked = False
        why = reason or "Security checks passed"
    elif sanitize and all(r.threat_type in {ThreatType.data_exposure, ThreatType.suspicious_payload} for r in failed):
        decision = SecurityDecisionType.sanitize; blocked = False; why = reason or "Input requires safe sanitization"
    else:
        decision = SecurityDecisionType.block; blocked = True; why = reason or failed[0].reason
    return SecurityDecision(security_check_id=uuid4(), request_id=request_id, decision=decision, risk_level=risk, threat_detected=bool(threats), threat_types=threats, blocked=blocked, reason=why, policy_version=POLICY_VERSION, checks_performed=checks, results=results)


def detect_secret(content: str, metadata: dict[str, Any]) -> SecurityCheckResult:
    kinds = _secret_types(content, metadata)
    if kinds: return _threat_result(SecurityCheckType.secret_detection, ThreatType.secret_exposure, RiskLevel.critical, "Sensitive credential-like data detected")
    return _ok(SecurityCheckType.secret_detection)


def validate_url(url: str) -> SecurityCheckResult:
    if len(url) > MAX_URL_LENGTH: return _threat_result(SecurityCheckType.url_validation, ThreatType.oversized_payload, RiskLevel.high, "URL length exceeds policy limit")
    if CONTROL_RE.search(url): return _threat_result(SecurityCheckType.url_validation, ThreatType.malicious_url, RiskLevel.high, "URL contains control characters")
    try: p = urllib.parse.urlsplit(url)
    except ValueError: return _threat_result(SecurityCheckType.url_validation, ThreatType.malicious_url, RiskLevel.high, "Malformed URL")
    if p.scheme.lower() not in {"http", "https"} or not p.netloc:
        return _threat_result(SecurityCheckType.url_validation, ThreatType.malicious_url, RiskLevel.high, "URL scheme or structure is not allowed")
    if p.username is not None or p.password is not None:
        return _threat_result(SecurityCheckType.url_validation, ThreatType.malicious_url, RiskLevel.critical, "Embedded URL credentials are not allowed")
    return _ok(SecurityCheckType.url_validation)


def _pattern_result(check: SecurityCheckType, patterns: list[re.Pattern], content: str, threat: ThreatType, reason: str, risk=RiskLevel.high) -> SecurityCheckResult:
    return _threat_result(check, threat, risk, reason) if any(p.search(content) for p in patterns) else _ok(check)


def _data_exposure(content: str, metadata: dict[str, Any]) -> SecurityCheckResult:
    text = content + " " + " ".join(v for _, v in _flatten(metadata))
    if _secret_types(content, metadata): return _threat_result(SecurityCheckType.data_exposure_detection, ThreatType.credential_exposure, RiskLevel.critical, "Credential exposure detected")
    if EMAIL_RE.search(text) or PHONE_RE.search(text) or any(_looks_like_card(x) for x in CARD_RE.findall(text)):
        return _threat_result(SecurityCheckType.data_exposure_detection, ThreatType.data_exposure, RiskLevel.medium, "Potentially sensitive personal or payment data detected")
    return _ok(SecurityCheckType.data_exposure_detection)


def _looks_like_card(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if not 13 <= len(digits) <= 19: return False
    total = 0; parity = len(digits) % 2
    for i, ch in enumerate(digits):
        n = int(ch)
        if i % 2 == parity:
            n *= 2
            if n > 9: n -= 9
        total += n
    return total % 10 == 0


def _input_limits(content: str, metadata: dict[str, Any]) -> SecurityCheckResult:
    if len(content) > MAX_TEXT_LENGTH: return _threat_result(SecurityCheckType.input_validation, ThreatType.oversized_payload, RiskLevel.high, "Text length exceeds policy limit")
    try:
        _json_safe(metadata)
        raw = json.dumps(metadata, separators=(",", ":"), ensure_ascii=True)
        if len(raw.encode()) > MAX_METADATA_SIZE: return _threat_result(SecurityCheckType.input_validation, ThreatType.oversized_payload, RiskLevel.high, "Metadata size exceeds policy limit")
    except ValueError as e:
        return _threat_result(SecurityCheckType.input_validation, ThreatType.invalid_request, RiskLevel.high, str(e))
    return _ok(SecurityCheckType.input_validation)


def check_request(req: SecurityCheckRequest) -> SecurityDecision:
    results=[]; checks=req.check_types
    for c in checks:
        if c == SecurityCheckType.secret_detection: results.append(detect_secret(req.content, req.metadata))
        elif c == SecurityCheckType.credential_detection: results.append(detect_secret(req.content, req.metadata).model_copy(update={"check_type": c, "threat_type": ThreatType.credential_exposure} if _secret_types(req.content, req.metadata) else {"check_type": c}))
        elif c == SecurityCheckType.url_validation:
            results.append(validate_url(req.content))
        elif c == SecurityCheckType.input_validation: results.append(_input_limits(req.content, req.metadata))
        elif c == SecurityCheckType.command_injection_detection: results.append(_pattern_result(c, COMMAND_PATTERNS, req.content, ThreatType.command_injection, "Suspicious command execution pattern detected"))
        elif c == SecurityCheckType.script_injection_detection: results.append(_pattern_result(c, SCRIPT_PATTERNS, req.content, ThreatType.script_injection, "Suspicious script injection pattern detected"))
        elif c == SecurityCheckType.path_traversal_detection: results.append(_pattern_result(c, TRAVERSAL_PATTERNS, req.content, ThreatType.path_traversal, "Path traversal pattern detected"))
        elif c == SecurityCheckType.suspicious_payload_detection:
            results.append(_pattern_result(c, COMMAND_PATTERNS + SCRIPT_PATTERNS + TRAVERSAL_PATTERNS, req.content, ThreatType.suspicious_payload, "Suspicious payload pattern detected"))
        elif c == SecurityCheckType.data_exposure_detection: results.append(_data_exposure(req.content, req.metadata))
        elif c == SecurityCheckType.request_integrity_check:
            results.append(_ok(c) if req.request_id else _threat_result(c, ThreatType.invalid_request, RiskLevel.high, "Invalid request structure"))
        else: results.append(_ok(c))
    return _decision(req.request_id, results, checks, sanitize=req.sanitize)


def check_url(req: URLSecurityRequest) -> SecurityDecision:
    r=validate_url(req.url); return _decision(req.request_id, [r], [SecurityCheckType.url_validation])


def action_check(req: ActionSecurityRequest) -> SecurityDecision:
    cat=req.action_category
    if cat == ActionCategory.unknown: r=_threat_result(SecurityCheckType.action_safety_check, ThreatType.unsafe_action, RiskLevel.high, "Unknown action category requires review")
    elif req.credential_handling or cat == ActionCategory.authentication: r=_threat_result(SecurityCheckType.action_safety_check, ThreatType.credential_exposure, RiskLevel.critical, "Credential or authentication operation is security-sensitive")
    elif cat in {ActionCategory.financial, ActionCategory.purchase}: r=_threat_result(SecurityCheckType.action_safety_check, ThreatType.unsafe_action, RiskLevel.critical, "Financial operation is security-sensitive")
    elif cat in {ActionCategory.deletion, ActionCategory.account_change, ActionCategory.form_submission}: r=_threat_result(SecurityCheckType.action_safety_check, ThreatType.unsafe_action, RiskLevel.high, "High-impact action requires security review")
    elif cat == ActionCategory.external_side_effect: r=_threat_result(SecurityCheckType.action_safety_check, ThreatType.unsafe_action, RiskLevel.medium, "External side effect requires security review")
    elif cat == ActionCategory.communication: r=SecurityCheckResult(check_type=SecurityCheckType.action_safety_check, passed=True, risk_level=RiskLevel.medium, threat_type=ThreatType.none, reason="Communication classified as medium risk")
    elif cat == ActionCategory.draft: r=SecurityCheckResult(check_type=SecurityCheckType.action_safety_check, passed=True, risk_level=RiskLevel.low, threat_type=ThreatType.none, reason="Draft action classified as low risk")
    else: r=SecurityCheckResult(check_type=SecurityCheckType.action_safety_check, passed=True, risk_level=RiskLevel.low, threat_type=ThreatType.none, reason="Read-only/information action classified as low risk")
    if r.passed and req.content:
        s=detect_secret(req.content, req.metadata)
        if not s.passed: r=s.model_copy(update={"check_type": SecurityCheckType.action_safety_check})
    return _decision(req.request_id,[r],[SecurityCheckType.action_safety_check])


def permission_policy_check(req: SecurityPolicyRequest) -> SecurityDecision:
    if req.credential_handling or req.action_category == ActionCategory.authentication:
        r=_threat_result(SecurityCheckType.permission_policy_check, ThreatType.unsafe_action, RiskLevel.critical, "Permission cannot override credential security policy")
    elif req.action_category in {ActionCategory.financial, ActionCategory.purchase}:
        r=_threat_result(SecurityCheckType.permission_policy_check, ThreatType.unsafe_action, RiskLevel.critical, "Permission cannot override financial security policy")
    elif req.action_category == ActionCategory.unknown:
        r=_threat_result(SecurityCheckType.permission_policy_check, ThreatType.unsafe_action, RiskLevel.high, "Unknown operation requires security review")
    else:
        r=_ok(SecurityCheckType.permission_policy_check, "Permission state does not violate security policy")
    return _decision(req.request_id,[r],[SecurityCheckType.permission_policy_check])


def sanitize_text(text: str) -> tuple[str, bool]:
    if _secret_types(text, {}) or any(p.search(text) for p in COMMAND_PATTERNS + SCRIPT_PATTERNS + TRAVERSAL_PATTERNS):
        raise ValueError("unsafe content cannot be safely sanitized")
    cleaned=CONTROL_RE.sub("", text.replace("\x00", ""))
    cleaned=re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, cleaned != text
