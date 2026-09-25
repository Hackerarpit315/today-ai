"""Provider interface for future LLM implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Minimal provider contract used by the intelligence layer."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Return structured intelligence for a request."""
        raise NotImplementedError
