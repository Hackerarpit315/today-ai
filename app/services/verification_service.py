"""Deterministic, local Verification Engine implementation."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.schemas.verification import (
    VerificationRequest,
    VerificationResponse,
    VerificationResearchResult,
)

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{2,4}|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2},?\s+\d{2,4})\b",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"(?<![\w])(?:\d+(?:\.\d+)?)(?![\w])")
_URL_PATTERN = re.compile(r"https?://[^\s)]+", re.IGNORECASE)
_PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*%")
_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "being", "but",
        "by", "can", "could", "did", "do", "does", "for", "from", "has", "have",
        "he", "her", "here", "his", "how", "i", "if", "in", "into", "is", "it",
        "its", "me", "more", "my", "of", "on", "or", "our", "she", "that", "the",
        "their", "them", "there", "these", "they", "this", "those", "to", "was", "we",
        "were", "what", "when", "where", "which", "who", "why", "will", "with", "would",
        "you", "your",
    }
)


@dataclass(frozen=True)
class _Claim:
    """A deterministic representation of one factual-looking statement."""

    key: str
    value: str
    display: str
    source_id: str
    relevance_score: float


def _tokens(text: str) -> list[str]:
    """Normalize text into meaningful, first-seen tokens."""
    result: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_PATTERN.findall(text.casefold()):
        if len(token) <= 2 or token in _STOP_WORDS or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def _canonical_value(value: str) -> str:
    """Normalize a factual value, including common date formats."""
    raw = value.casefold().strip(" .,:;()[]{}")
    raw = re.sub(r"\s+", " ", raw)

    date_formats = (
        "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
        "%B %d, %Y", "%b %d, %Y", "%d/%m/%Y", "%d-%m-%Y",
        "%m/%d/%Y", "%m-%d-%Y",
    )
    for fmt in date_formats:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    raw = raw.replace("september", "sep").replace("sept", "sep")
    raw = raw.replace("january", "jan").replace("february", "feb")
    raw = raw.replace("march", "mar").replace("april", "apr")
    raw = raw.replace("june", "jun").replace("july", "jul")
    raw = raw.replace("august", "aug").replace("october", "oct")
    raw = raw.replace("november", "nov").replace("december", "dec")
    return re.sub(r"\s+", " ", raw)


def _fact_values(sentence: str) -> list[str]:
    """Extract dates, percentages, numbers, URLs, and simple named values."""
    values: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        canonical = _canonical_value(value)
        if canonical and canonical not in seen:
            seen.add(canonical)
            values.append(canonical)

    for match in _URL_PATTERN.findall(sentence):
        add(match)

    masked = _URL_PATTERN.sub(" ", sentence)
    for match in _DATE_PATTERN.findall(masked):
        add(match)
    masked = _DATE_PATTERN.sub(" ", masked)

    for match in _PERCENT_PATTERN.findall(masked):
        add(match)
    masked = _PERCENT_PATTERN.sub(" ", masked)

    for match in _NUMBER_PATTERN.findall(masked):
        add(match)

    return values


def _claim_key(sentence: str) -> str:
    """Create a normalized claim subject by removing extracted factual values."""
    without_urls = _URL_PATTERN.sub(" ", sentence)
    without_dates = _DATE_PATTERN.sub(" ", without_urls)
    without_percentages = _PERCENT_PATTERN.sub(" ", without_dates)
    without_numbers = _NUMBER_PATTERN.sub(" ", without_percentages)
    terms = _tokens(without_numbers)

    # Small deterministic synonym normalization handles common claim phrasing.
    synonyms = {
        "applications": "application",
        "closes": "deadline",
        "close": "deadline",
        "closing": "deadline",
    }
    terms = [synonyms.get(term, term) for term in terms]
    return " ".join(dict.fromkeys(terms))


def _sentences(content: str) -> Iterable[str]:
    """Split source content into simple deterministic statements."""
    return (part.strip() for part in re.split(r"(?<=[.!?])\s+|[\n;]+", content) if part.strip())


def _extract_claims(source: VerificationResearchResult) -> list[_Claim]:
    """Extract factual-looking claims from a source."""
    claims: list[_Claim] = []
    for sentence in _sentences(source.content):
        values = _fact_values(sentence)
        if not values:
            continue
        key = _claim_key(sentence)
        if not key:
            continue
        for value in values:
            claims.append(
                _Claim(
                    key=key,
                    value=value,
                    display=sentence,
                    source_id=source.source_id,
                    relevance_score=source.relevance_score,
                )
            )
    return claims


def _relevant_sources(payload: VerificationRequest) -> list[VerificationResearchResult]:
    """Ignore research results that contain no relevance signal."""
    return [item for item in payload.research_results if item.relevance_score > 0.0]


def _confidence(
    agreeing_groups: int,
    conflicting_groups: int,
    insufficient_groups: int,
    relevant_source_count: int,
) -> float:
    """Calculate an explainable deterministic evidence-consistency score."""
    if relevant_source_count == 0:
        return 0.0
    if conflicting_groups:
        base = 0.25
    elif agreeing_groups:
        base = 0.55
    elif insufficient_groups:
        base = 0.25
    else:
        base = 0.15

    if agreeing_groups:
        base += min(0.30, 0.15 * (agreeing_groups - 1))
    if relevant_source_count >= 2 and agreeing_groups:
        base += 0.10
    if insufficient_groups:
        base -= min(0.15, 0.05 * insufficient_groups)
    if conflicting_groups:
        base -= min(0.15, 0.05 * conflicting_groups)
    return min(1.0, max(0.0, round(base, 6)))


def verify_research(payload: VerificationRequest) -> VerificationResponse:
    """Verify consistency among explicitly supplied research results."""
    sources = _relevant_sources(payload)
    claims = [claim for source in sources for claim in _extract_claims(source)]

    grouped: dict[str, list[_Claim]] = defaultdict(list)
    for claim in claims:
        grouped[claim.key].append(claim)

    verified_claims: list[str] = []
    conflicting_claims: list[str] = []
    insufficient_claims: list[str] = []
    supporting_sources: list[str] = []
    conflicting_sources: list[str] = []
    conflict_detected = False
    agreeing_groups = 0
    conflicting_groups = 0
    insufficient_groups = 0

    for key, group in grouped.items():
        values: dict[str, list[_Claim]] = defaultdict(list)
        for claim in group:
            values[claim.value].append(claim)

        source_ids = list(dict.fromkeys(claim.source_id for claim in group))
        if len(values) == 1:
            only_value = next(iter(values))
            if len(source_ids) >= 2:
                agreeing_groups += 1
                verified_claims.append(f"{key}: {only_value}")
                supporting_sources.extend(source_ids)
            else:
                insufficient_groups += 1
                insufficient_claims.append(f"{key}: {only_value}")
                supporting_sources.extend(source_ids)
        else:
            conflict_detected = True
            conflicting_groups += 1
            conflicting_claims.append(key)
            for value_claims in values.values():
                for claim in value_claims:
                    conflicting_sources.append(claim.source_id)

    supporting_sources = list(dict.fromkeys(supporting_sources))
    conflicting_sources = list(dict.fromkeys(conflicting_sources))

    # Sources with no extractable factual claim cannot be deterministically verified.
    claimed_source_ids = {claim.source_id for claim in claims}
    for source in sources:
        if source.source_id not in claimed_source_ids:
            insufficient_groups += 1
            insufficient_claims.append(source.title)

    if conflict_detected:
        status = "conflicting"
        verified = False
    elif verified_claims:
        status = "verified"
        verified = True
    elif insufficient_claims:
        status = "insufficient_evidence"
        verified = False
    else:
        status = "unverified"
        verified = False

    return VerificationResponse(
        request_id=payload.request_id,
        verified=verified,
        conflict_detected=conflict_detected,
        verification_status=status,
        verified_claims=list(dict.fromkeys(verified_claims)),
        conflicting_claims=list(dict.fromkeys(conflicting_claims)),
        insufficient_claims=list(dict.fromkeys(insufficient_claims)),
        supporting_sources=supporting_sources,
        conflicting_sources=conflicting_sources,
        confidence=_confidence(
            agreeing_groups,
            conflicting_groups,
            insufficient_groups,
            len(sources),
        ),
    )
