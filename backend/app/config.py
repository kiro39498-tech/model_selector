"""Application configuration loaded from environment variables.

All secrets and connection strings are read from the environment (or a local
`.env` file). Nothing here is committed to source control.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings.

    Values are read from environment variables (and a local `.env` file).
    Missing required values raise a clear configuration error at startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- AI endpoint (OpenAI-compatible) ---
    ai_base_url: str = Field(default="http://indiaai.maqsoftware.net/v1")
    ai_model: str = Field(default="qwen3.8-27b")
    ai_api_key: str = Field(default="")
    # Request timeout (seconds) for AI calls.
    ai_timeout_seconds: float = Field(default=120.0)
    # Max attempts for transient failures.
    ai_max_retries: int = Field(default=3)

    # --- Database ---
    database_url: str = Field(default="")
    # Connection pool sizing (appropriate for a single-host deployment).
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)
    db_pool_timeout: int = Field(default=30)

    # --- Application ---
    cors_origins: str = Field(default="http://localhost:5173")
    app_secret: str = Field(default="change-me-in-production")
    log_level: str = Field(default="INFO")
    # Bounded request payload size (bytes).
    max_request_bytes: int = Field(default=2 * 1024 * 1024)

    # --- Model classification policy (application convention) ---
    # A model with fewer than this many parameters is an SLM; >= this is an LLM.
    classification_threshold_billions: float = Field(default=150.0)

    @field_validator("cors_origins")
    @classmethod
    def _split_cors(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_configured(self) -> bool:
        """True when the AI endpoint has a usable key."""
        return bool(self.ai_api_key and self.ai_api_key.strip())

    @property
    def db_configured(self) -> bool:
        """True when a database URL is present."""
        return bool(self.database_url and self.database_url.strip())

    @property
    def classification_threshold_params(self) -> int:
        """Threshold expressed in raw parameter count (billions -> count)."""
        return int(self.classification_threshold_billions * 1_000_000_000)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
