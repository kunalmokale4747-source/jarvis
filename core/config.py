from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "sqlite:///./data/jarvis.db"
    auth_mode: str = "dev"  # dev | supabase
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    session_ttl_hours: int = 720
    app_version: str = "0.1.0"
    current_phase: int = 9

    # ── LLM providers (Phase 2) ────────────────────────────────────
    # Comma-separated fallback chain, e.g. "anthropic,openai,local".
    # Empty = AI offline (chat degrades honestly, everything else works).
    llm_provider: str = ""
    llm_model: str = ""
    llm_base_url: str = ""  # for provider "local" (OpenAI-compatible, e.g. Ollama)
    llm_timeout_seconds: int = 60
    llm_max_history: int = 40
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    # Optional OpenAI Realtime voice. Empty/disabled by default.
    openai_realtime_enabled: bool = False
    openai_realtime_api_key: str = ""
    openai_realtime_model: str = "gpt-realtime"
    openai_realtime_voice: str = "alloy"
    openai_realtime_expires_in_seconds: int = 60
    openai_realtime_base_url: str = "https://api.openai.com/v1"

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_dev_auth(self) -> bool:
        return self.auth_mode == "dev"

    @property
    def llm_providers(self) -> list[str]:
        return [p.strip().lower() for p in self.llm_provider.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
