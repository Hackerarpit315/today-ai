"""Deterministic local provider used until a real LLM is introduced."""

from __future__ import annotations

import re

from .provider import LLMProvider
from .schemas import LLMRequest, LLMResponse


class MockLLMProvider(LLMProvider):
    """Small deterministic rule provider with no external side effects."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        text = request.user_input.strip()
        lower = text.casefold()

        if "college" in lower and re.search(r"\b(kal|tomorrow)\b", lower):
            return LLMResponse(
                request_id=request.request_id,
                intent="task",
                goal="Go to college",
                entities={},
                time_reference="tomorrow",
                confidence=0.95,
                reasoning_summary="The user expressed a future task.",
            )

        time_reference = None
        if re.search(r"\b(kal|tomorrow)\b", lower):
            time_reference = "tomorrow"
        elif re.search(r"\b(aaj|today)\b", lower):
            time_reference = "today"

        return LLMResponse(
            request_id=request.request_id,
            intent="unknown",
            goal=text,
            entities={},
            time_reference=time_reference,
            confidence=0.50,
            reasoning_summary="The mock provider returned a safe generic interpretation.",
        )
