"""OpenAI-compatible chat/embeddings provider.

Serves both the OpenAI API and any OpenAI-compatible local server
(Ollama, vLLM, llama.cpp server, …) via base_url.
"""

from __future__ import annotations

import json
from typing import Iterator

from core.llm.base import BaseProvider
from core.llm.types import LLMRequest, LLMResponse, LLMToolCall, LLMUsage, ProviderResponseError


class OpenAICompatProvider(BaseProvider):
    supports_embedding = True

    def __init__(self, *, model: str, api_key: str = "", base_url: str = "https://api.openai.com/v1", timeout: float = 60.0, name: str | None = None) -> None:
        self.name = name if name else ("openai" if base_url.startswith("https://api.openai.com") else "local")
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(self, request: LLMRequest) -> dict:
        messages = [{"role": "system", "content": request.system}]
        messages += [{"role": m.role, "content": m.content} for m in request.messages]
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.want_json:
            payload["response_format"] = {"type": "json_object"}
        if request.tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = "auto"
        return payload

    def complete(self, request: LLMRequest) -> LLMResponse:
        data = self._post_json(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            payload=self._payload(request),
        )
        try:
            choice = data["choices"][0]
            message = choice.get("message") or {}
            text = message.get("content") or ""
            tool_calls = []
            for raw_call in message.get("tool_calls") or []:
                function = raw_call.get("function") or {}
                raw_args = function.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
                except json.JSONDecodeError:
                    args = {"_raw_arguments": str(raw_args)}
                tool_calls.append(
                    LLMToolCall(
                        id=str(raw_call.get("id") or ""),
                        name=str(function.get("name") or ""),
                        arguments=args,
                        raw_arguments=str(raw_args),
                    )
                )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(f"unexpected chat.completions payload: {exc}") from exc
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            provider=self.name,
            model=data.get("model", self.model),
            usage=LLMUsage(
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
            finish_reason=str(choice.get("finish_reason") or "stop"),
            tool_calls=tool_calls,
        )

    def stream(self, request: LLMRequest) -> Iterator[str]:
        payload = self._payload(request)
        payload["stream"] = True
        try:
            with httpx_stream(f"{self.base_url}/chat/completions", headers=self._headers(), payload=payload, timeout=self.timeout) as response:
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content
        except Exception as exc:  # noqa: BLE001 - normalized to provider errors
            from core.llm.types import ProviderUnavailableError

            if isinstance(exc, (ProviderUnavailableError, ProviderResponseError)):
                raise
            raise ProviderUnavailableError(f"stream failed: {exc}") from exc

    def embedding(self, text: str) -> list[float]:
        data = self._post_json(
            f"{self.base_url}/embeddings",
            headers=self._headers(),
            payload={"model": "text-embedding-3-small", "input": text},
        )
        try:
            return [float(x) for x in data["data"][0]["embedding"]]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(f"unexpected embeddings payload: {exc}") from exc


def httpx_stream(url: str, *, headers: dict, payload: dict, timeout: float):
    import httpx

    return httpx.stream("POST", url, headers=headers, json=payload, timeout=timeout)
