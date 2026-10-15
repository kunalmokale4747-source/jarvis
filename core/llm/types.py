"""Normalized LLM request/response types and provider errors.

No provider SDK types leak past this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class LLMRequest:
    system: str
    messages: list[LLMMessage]
    max_tokens: int = 1024
    temperature: float = 0.4
    want_json: bool = False
    tools: list[dict] | None = None


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict
    raw_arguments: str = ""


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    finish_reason: str = "stop"
    tool_calls: list[LLMToolCall] = field(default_factory=list)


class ProviderError(Exception):
    """Base class for provider failures."""


class ProviderUnavailableError(ProviderError):
    """Provider cannot serve the request (network, 5xx, auth, bad config).

    Eligible for fallback to the next provider in the chain.
    """


class ProviderResponseError(ProviderError):
    """Provider responded but the payload could not be used."""
