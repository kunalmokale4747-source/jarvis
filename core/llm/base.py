"""AIProvider protocol and shared HTTP helpers."""

from __future__ import annotations

import json
import time
from typing import Iterator, Protocol, runtime_checkable

import httpx

from core.llm.types import (
    LLMRequest,
    LLMResponse,
    ProviderResponseError,
    ProviderUnavailableError,
)

TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}


@runtime_checkable
class AIProvider(Protocol):
    name: str
    model: str
    supports_embedding: bool

    def complete(self, request: LLMRequest) -> LLMResponse: ...

    def stream(self, request: LLMRequest) -> Iterator[str]: ...

    def embedding(self, text: str) -> list[float]: ...


class BaseProvider:
    """Default implementations: single-attempt HTTP with one retry on
    transient failures; non-streaming providers buffer `stream()`."""

    name: str = "base"
    model: str = ""
    supports_embedding: bool = False
    timeout: float = 60.0

    # -- HTTP -------------------------------------------------------
    def _post_json(self, url: str, *, headers: dict, payload: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = httpx.post(
                    url, headers=headers, json=payload, timeout=self.timeout
                )
            except httpx.TimeoutException as exc:
                last_error = ProviderUnavailableError(f"timeout calling {url}: {exc}")
                continue
            except httpx.HTTPError as exc:
                last_error = ProviderUnavailableError(f"network error calling {url}: {exc}")
                continue
            if response.status_code in TRANSIENT_STATUSES and attempt == 0:
                last_error = ProviderUnavailableError(
                    f"HTTP {response.status_code} from {url}"
                )
                time.sleep(0.5)
                continue
            if response.status_code in TRANSIENT_STATUSES:
                raise ProviderUnavailableError(
                    f"HTTP {response.status_code} from {url}: {response.text[:200]}"
                )
            if response.status_code in (401, 403):
                raise ProviderUnavailableError(
                    f"authentication/authorization failed for {url} (HTTP {response.status_code})"
                )
            if response.status_code >= 400:
                raise ProviderResponseError(
                    f"HTTP {response.status_code} from {url}: {response.text[:300]}"
                )
            try:
                return response.json()
            except json.JSONDecodeError as exc:
                raise ProviderResponseError(f"invalid JSON from {url}: {exc}") from exc
        raise last_error if last_error else ProviderUnavailableError("unknown provider failure")

    # -- defaults ---------------------------------------------------
    def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    def stream(self, request: LLMRequest) -> Iterator[str]:
        yield self.complete(request).text

    def embedding(self, text: str) -> list[float]:
        raise NotImplementedError(f"provider {self.name!r} does not support embeddings")
