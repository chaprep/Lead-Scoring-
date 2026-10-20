from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    # Existing non-container installs retain live behaviour unless explicitly changed.
    app_mode: Literal["demo", "live"] = "live"
    database_url: PostgresDsn = Field(
        default="postgresql+psycopg://leadscoring:leadscoring@localhost:5433/leadscoring"
    )
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    profile_provider: str = "apify"
    qualification_provider: str = "jev"
    openrouter_api_key: str | None = None
    jev_model: str = "typesafe/jev-1.13"
    jev_decisions_url: str = "https://openrouter.ai/api/alpha/decisions"
    jev_request_timeout_seconds: float = Field(default=30, gt=0)
    apify_api_key: str | None = None
    apify_profile_actor_id: str = "AgfKk0sQQxkpQJ1Dt"
    apify_request_timeout_seconds: int = Field(default=20, ge=1)
    apify_run_timeout_seconds: int = Field(default=180, ge=1)
    apify_poll_interval_seconds: float = Field(default=2, gt=0)
    company_enrich_api_key: str | None = None
    company_enrich_url: str = "https://api.companyenrich.com/companies/enrich"
    company_enrich_request_timeout_seconds: float = Field(default=45, gt=0)
    prioritization_model: str = "openai/gpt-6-luna"
    prioritization_reasoning_effort: str = "medium"
    prioritization_url: str = "https://openrouter.ai/api/v1/chat/completions"
    prioritization_request_timeout_seconds: float = Field(default=45, gt=0)
    signalhire_api_key: str | None = None
    signalhire_url: str = "https://www.signalhire.com/api/v1/candidate/search"
    signalhire_callback_base_url: str | None = None
    signalhire_request_timeout_seconds: float = Field(default=30, gt=0)
    internal_api_key: str | None = None
    celery_worker_concurrency: int = Field(default=4, ge=1)
    phase1_max_concurrency: int = Field(default=4, ge=1)
    phase2_max_concurrency: int = Field(default=4, ge=1)
    company_provider_max_concurrency: int = Field(default=2, ge=1)
    contact_provider_max_concurrency: int = Field(default=2, ge=1)
    llm_max_concurrency: int = Field(default=2, ge=1)
    contact_callback_timeout_seconds: int = Field(default=900, ge=1)
    max_retry_attempts: int = Field(default=3, ge=0)
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Accept a comma-separated environment variable as well as a settings list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
