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
    current_phase: int = 1

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_dev_auth(self) -> bool:
        return self.auth_mode == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
