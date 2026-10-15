"""Google Gemini generateContent provider (buffered streaming)."""

from __future__ import annotations

from typing import Iterator

from core.llm.base import BaseProvider
from core.llm.types import LLMRequest, LLMResponse, LLMUsage, ProviderResponseError


class GeminiProvider(BaseProvider):
    supports_embedding = False

    def __init__(self, *, model: str, api_key: str, timeout: float = 60.0) -> None:
        self.name = "gemini"
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def _payload(self, request: LLMRequest) -> dict:
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in request.messages
        ]
        return {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": request.system}]},
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }

    def complete(self, request: LLMRequest) -> LLMResponse:
        data = self._post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            payload=self._payload(request),
        )
        try:
            candidate = data["candidates"][0]
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(f"unexpected generateContent payload: {exc}") from exc
        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage=LLMUsage(
                input_tokens=int(usage.get("promptTokenCount") or 0),
                output_tokens=int(usage.get("candidatesTokenCount") or 0),
            ),
        )

    def stream(self, request: LLMRequest) -> Iterator[str]:
        # Gemini SSE parsing not yet implemented; buffered fallback.
        yield self.complete(request).text
