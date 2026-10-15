"""Stub provider for tests and local development without network access.

Deterministic: records the last request it received so tests can assert on
the exact system prompt/context that reached the model.
"""

from __future__ import annotations

import hashlib
import math
from typing import Iterator

from core.llm.types import LLMRequest, LLMResponse, LLMUsage, ProviderUnavailableError


class StubProvider:
    name = "stub"
    supports_embedding = True

    def __init__(
        self,
        *,
        model: str = "stub-1",
        replies: list[str] | None = None,
        fail: bool = False,
        fail_stream: bool = False,
        chunk_size: int = 8,
    ) -> None:
        self.model = model
        self.replies = list(replies or [])
        self.fail = fail
        self.fail_stream = fail_stream
        self.chunk_size = chunk_size
        self.requests: list[LLMRequest] = []

    def _check(self) -> None:
        if self.fail or self.fail_stream:
            raise ProviderUnavailableError(f"stub provider {self.name!r} is failing on purpose")

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        self._check()
        if self.replies:
            text = self.replies.pop(0)
        else:
            last_user = next(
                (m.content for m in reversed(request.messages) if m.role == "user"), ""
            )
            text = f"STUB:{last_user}"
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage=LLMUsage(
                input_tokens=len(request.system) // 4,
                output_tokens=len(text) // 4,
            ),
        )

    def stream(self, request: LLMRequest) -> Iterator[str]:
        text = self.complete(request).text
        for i in range(0, len(text), self.chunk_size):
            yield text[i : i + self.chunk_size]

    def embedding(self, text: str) -> list[float]:
        """Deterministic bag-of-tokens embedding (dim 64) for tests."""
        vec = [0.0] * 64
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            vec[digest[0] % 64] += 1.0
            vec[digest[1] % 64] += 0.5
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
