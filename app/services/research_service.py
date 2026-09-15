"""Deterministic, local Research Engine implementation."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.research import (
    ResearchRequest,
    ResearchResponse,
    ResearchResult,
    ResearchSource,
)

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "have", "in", "is", "it", "me", "my", "of", "on", "or",
        "that", "the", "this", "to", "was", "were", "with", "you", "your",
        "i", "we", "he", "she", "they", "them", "our", "their", "will",
        "can", "could", "should", "would", "do", "does", "did",
    }
)


def _normalize_tokens(value: str) -> list[str]:
    """Return normalized meaningful tokens in deterministic first-seen order."""
    tokens: list[str] = []
    seen: set[str] = set()

    for token in _TOKEN_PATTERN.findall(value.casefold()):
        if len(token) <= 2 or token in _STOP_WORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)

    return tokens


def _entity_values(entities: dict[str, Any]) -> list[str]:
    """Flatten entity values into text without interpreting their meaning."""
    values: list[str] = []
    for value in entities.values():
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (list, tuple, set)):
            values.extend(str(item) for item in value)
        elif isinstance(value, dict):
            values.extend(str(item) for item in value.values())
        elif value is not None:
            values.append(str(value))
    return values


def _request_tokens(payload: ResearchRequest) -> list[str]:
    """Build the normalized meaningful token list for the request."""
    parts = [payload.query, payload.intent, payload.goal]
    parts.extend(_entity_values(payload.entities))

    tokens: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for token in _normalize_tokens(part):
            if token not in seen:
                seen.add(token)
                tokens.append(token)
    return tokens


def _source_tokens(source: ResearchSource) -> set[str]:
    """Build normalized meaningful tokens for one supplied source."""
    tokens: set[str] = set()
    for part in (source.title, source.content, source.source_type):
        tokens.update(_normalize_tokens(part))
    return tokens


def _confidence(relevant_count: int) -> float:
    """Return bounded confidence that relevant supplied sources were found."""
    if relevant_count <= 0:
        return 0.0
    return min(1.0, relevant_count / 3.0)


def process_research(payload: ResearchRequest) -> ResearchResponse:
    """Rank explicitly supplied sources using deterministic token overlap."""
    request_tokens = _request_tokens(payload)
    request_token_set = set(request_tokens)
    scored: list[tuple[float, int, ResearchSource, list[str]]] = []

    for index, source in enumerate(payload.sources):
        source_tokens = _source_tokens(source)
        matched_terms = [
            token for token in request_tokens if token in source_tokens
        ]

        if not matched_terms:
            continue

        score = min(
            1.0,
            max(0.0, len(matched_terms) / len(request_token_set)),
        )
        scored.append((score, index, source, matched_terms))

    # Python's stable sort preserves source order for equal scores.
    scored.sort(key=lambda entry: -entry[0])

    results = [
        ResearchResult(
            source_id=source.source_id,
            title=source.title,
            url=source.url,
            relevance_score=score,
            matched_terms=matched_terms,
        )
        for score, _index, source, matched_terms in scored
    ]

    return ResearchResponse(
        request_id=payload.request_id,
        query=payload.query,
        results=results,
        sources_found=len(results),
        research_completed=True,
        confidence=_confidence(len(results)),
    )
