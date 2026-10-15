"""Anthropic Messages API provider (buffered streaming)."""

from __future__ import annotations

from typing import Iterator

from core.llm.base import BaseProvider
from core.llm.types import LLMRequest, LLMResponse, LLMUsage, ProviderResponseError


class AnthropicProvider(BaseProvider):
    supports_embedding = False

    def __init__(self, *, model: str, api_key: str, timeout: float = 60.0) -> None:
        self.name = "anthropic"
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def _payload(self, request: LLMRequest) -> dict:
        return {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": request.system,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }

    def complete(self, request: LLMRequest) -> LLMResponse:
        data = self._post_json(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload=self._payload(request),
        )
        try:
            text = "".join(
                block.get("text", "")
                for block in data["content"]
                if block.get("type") == "text"
            )
            usage = data.get("usage") or {}
        except (KeyError, TypeError) as exc:
            raise ProviderResponseError(f"unexpected messages payload: {exc}") from exc
        return LLMResponse(
            text=text,
            provider=self.name,
            model=data.get("model", self.model),
            usage=LLMUsage(
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
            ),
        )

    def stream(self, request: LLMRequest) -> Iterator[str]:
        # Anthropic SSE parsing not yet implemented; buffered fallback.
        yield self.complete(request).text
