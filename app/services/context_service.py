"""Deterministic, local Context Engine implementation."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.context import ContextItem, ContextRequest, ContextResponse

# Keep tokenization intentionally simple and deterministic. Unicode word
# characters are retained so the engine can work with non-English text too.
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


def _normalize_tokens(value: str) -> set[str]:
    """Return normalized meaningful tokens from one text value."""
    normalized = value.casefold()
    return {
        token
        for token in _TOKEN_PATTERN.findall(normalized)
        if len(token) > 1 and token not in _STOP_WORDS
    }


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


def _request_tokens(payload: ContextRequest) -> set[str]:
    """Build the normalized token set representing the current request."""
    parts = [payload.intent, payload.goal]
    if payload.time_reference:
        parts.append(payload.time_reference)
    parts.extend(_entity_values(payload.entities))

    tokens: set[str] = set()
    for part in parts:
        tokens.update(_normalize_tokens(part))
    return tokens


def _context_tokens(item: ContextItem) -> set[str]:
    """Build the normalized token set representing one context item."""
    parts = [item.content, item.context_type, *item.tags]
    tokens: set[str] = set()
    for part in parts:
        tokens.update(_normalize_tokens(part))
    return tokens


def _select_relevant_context(
    request_tokens: set[str], available_context: list[ContextItem]
) -> tuple[list[ContextItem], int]:
    """Select context with positive overlap, highest score first."""
    scored: list[tuple[int, int, ContextItem]] = []
    for index, item in enumerate(available_context):
        score = len(request_tokens.intersection(_context_tokens(item)))
        if score > 0:
            scored.append((score, index, item))

    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [entry[2] for entry in scored], (scored[0][0] if scored else 0)


def _confidence(max_overlap: int, request_token_count: int) -> float:
    """Convert the strongest overlap into a bounded deterministic confidence."""
    if max_overlap <= 0 or request_token_count <= 0:
        return 0.0
    return min(1.0, max_overlap / request_token_count)


def process_context(payload: ContextRequest) -> ContextResponse:
    """Select explicitly supplied context relevant to the current request."""
    request_tokens = _request_tokens(payload)
    relevant, max_overlap = _select_relevant_context(
        request_tokens, payload.available_context
    )

    return ContextResponse(
        request_id=payload.request_id,
        relevant_context=relevant,
        context_used=bool(relevant),
        confidence=_confidence(max_overlap, len(request_tokens)),
    )
