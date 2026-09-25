"""Application-level LLM provider selection for Today AI."""

from __future__ import annotations

import os

from .mock_provider import MockLLMProvider
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider
from .provider import LLMProvider


class LLMProviderConfigurationError(RuntimeError):
    """Safe application-level error for invalid provider configuration."""


_DEFAULT_PROVIDER = "mock"
_SUPPORTED_PROVIDERS = frozenset({"mock", "openrouter", "openai"})


def create_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Create the configured provider without performing any network call."""
    configured = (
        provider_name
        if provider_name is not None
        else os.getenv("TODAY_AI_LLM_PROVIDER", _DEFAULT_PROVIDER)
    )
    name = configured.strip().casefold()

    if name == "mock":
        return MockLLMProvider()
    if name == "openrouter":
        return OpenRouterProvider()
    if name == "openai":
        return OpenAIProvider()

    raise LLMProviderConfigurationError(
        "Unsupported LLM provider configuration"
    )


def configured_llm_provider_name(provider_name: str | None = None) -> str:
    """Return the normalized configured provider name without exposing secrets."""
    configured = (
        provider_name
        if provider_name is not None
        else os.getenv("TODAY_AI_LLM_PROVIDER", _DEFAULT_PROVIDER)
    )
    name = configured.strip().casefold()
    if name not in _SUPPORTED_PROVIDERS:
        raise LLMProviderConfigurationError(
            "Unsupported LLM provider configuration"
        )
    return name
