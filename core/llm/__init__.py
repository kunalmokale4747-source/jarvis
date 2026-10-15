"""Provider factory, fallback chain, and AI status reporting.

LLM_PROVIDER is a comma-separated chain, e.g. "anthropic,openai,local".
Empty chain = AI offline (chat degrades honestly; nothing else needs AI).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.config import Settings, get_settings
from core.llm.base import AIProvider
from core.llm.types import ProviderUnavailableError

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
    "gemini": "gemini-2.0-flash",
    "local": "llama3.1",
    "groq": "openai/gpt-oss-20b",
    "stub": "stub-1",
}


class ProviderConfigError(Exception):
    """A provider was requested but cannot be constructed (missing key/URL)."""


def build_provider(name: str, settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    key = name.lower()
    model = settings.llm_model or DEFAULT_MODELS.get(key, "")

    if key == "stub":
        from core.llm.stub import StubProvider

        return StubProvider(model=model or "stub-1")

    if key == "openai":
        if not settings.openai_api_key:
            raise ProviderConfigError("openai selected but OPENAI_API_KEY is empty")
        from core.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            model=model, api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds
        )

    if key == "local":
        if not settings.llm_base_url:
            raise ProviderConfigError(
                "local selected but LLM_BASE_URL is empty (e.g. http://localhost:11434/v1)"
            )
        from core.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            model=model,
            api_key="",
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    if key == "anthropic":
        if not settings.anthropic_api_key:
            raise ProviderConfigError("anthropic selected but ANTHROPIC_API_KEY is empty")
        from core.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            model=model, api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds
        )

    if key == "gemini":
        if not settings.gemini_api_key:
            raise ProviderConfigError("gemini selected but GEMINI_API_KEY is empty")
        from core.llm.gemini_provider import GeminiProvider

        return GeminiProvider(
            model=model, api_key=settings.gemini_api_key, timeout=settings.llm_timeout_seconds
        )

    if key == "groq":
        if not settings.groq_api_key:
            raise ProviderConfigError("groq selected but GROQ_API_KEY is empty")
        from core.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            model=model or DEFAULT_MODELS["groq"],
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=settings.llm_timeout_seconds,
            name="groq",
        )

    raise ProviderConfigError(f"unknown LLM_PROVIDER {name!r} (known: {', '.join(DEFAULT_MODELS)})")


@dataclass
class AIStatus:
    status: str  # online | not_configured | error
    providers: list[str]
    models: list[str]
    detail: str

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "providers": self.providers,
            "models": self.models,
            "detail": self.detail,
        }


def get_provider_chain(settings: Settings | None = None) -> list[AIProvider]:
    """Build the configured chain. Providers with bad config are skipped;
    an empty result means chat runs in offline mode."""
    settings = settings or get_settings()
    chain: list[AIProvider] = []
    for name in settings.llm_providers:
        try:
            chain.append(build_provider(name, settings))
        except ProviderConfigError:
            continue
    return chain


def ai_status(settings: Settings | None = None) -> AIStatus:
    settings = settings or get_settings()
    requested = settings.llm_providers
    if not requested:
        return AIStatus(
            status="not_configured",
            providers=[],
            models=[],
            detail="LLM_PROVIDER is empty — AI features (chat) are offline. "
            "Everything else works without AI.",
        )
    chain = get_provider_chain(settings)
    if not chain:
        return AIStatus(
            status="error",
            providers=requested,
            models=[],
            detail="LLM_PROVIDER is set but no provider could be constructed "
            "(missing API key, base URL, or unknown name). Chat will report the error.",
        )
    return AIStatus(
        status="online",
        providers=[p.name for p in chain],
        models=[p.model for p in chain],
        detail="Provider chain ready (fallback order: " + " -> ".join(p.name for p in chain) + ").",
    )



def probe_provider(settings: Settings | None = None, timeout_seconds: float = 5.0) -> dict:
    """Run one bounded live call. Explicit endpoint only; never called by /health."""
    settings = settings or get_settings()
    requested = settings.llm_providers
    if not requested:
        return {"live_status": "offline", "detail": "LLM_PROVIDER is empty; provider is configured as offline."}
    chain = get_provider_chain(settings)
    if not chain:
        return {"live_status": "misconfigured", "detail": "No configured provider could be constructed."}
    provider = chain[0]
    previous_timeout = getattr(provider, "timeout", timeout_seconds)
    provider.timeout = min(previous_timeout if previous_timeout else timeout_seconds, timeout_seconds)
    from core.llm.types import LLMRequest, ProviderError, ProviderUnavailableError

    try:
        resp = provider.complete(
            LLMRequest(system="Reply with the single word OK.", messages=[], max_tokens=64, temperature=0)
        )
        success = bool(resp.text.strip())
        return {
            "live_status": "reachable" if success else "invalid_response",
            "provider": provider.name,
            "model": resp.model,
            "detail": resp.text.strip()[:100],
        }
    except (ProviderUnavailableError, ProviderError) as exc:
        detail = str(exc)
        if "rate" in detail.lower() or "429" in detail:
            return {"live_status": "rate_limited", "provider": provider.name, "model": getattr(provider, "model", None), "detail": detail}
        if "timeout" in detail.lower():
            return {"live_status": "timeout", "provider": provider.name, "model": getattr(provider, "model", None), "detail": detail}
        return {"live_status": "unavailable", "provider": provider.name, "model": getattr(provider, "model", None), "detail": detail}
    finally:
        provider.timeout = previous_timeout


__all__ = [
    "AIProvider",
    "AIStatus",
    "ProviderConfigError",
    "ProviderUnavailableError",
    "ai_status",
    "build_provider",
    "get_provider_chain",
]
