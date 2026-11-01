"""Runtime configuration from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://salesforge:salesforge@localhost:5432/salesforge"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    # LLM. "none" serves rule-based explanations only.
    llm_provider: Literal["none", "openai_compatible", "ollama"] = "none"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: float = 20.0

    # Per-client limit on write requests (the demo is public and has no login).
    write_requests_per_minute: int = 30

    @field_validator("database_url")
    @classmethod
    def use_psycopg3(cls, url: str) -> str:
        # Render and Neon hand out postgres:// or postgresql:// URLs; SQLAlchemy would pick psycopg2 for those.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
