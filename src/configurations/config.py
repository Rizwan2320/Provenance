"""
Environment configuration — single source of truth.

Rules:
  - Every module imports get_settings(), never os.environ directly.
  - Adding a new env var means adding it here AND to .env.example.
  - Field(...) = required. Field(default=...) = optional with fallback.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # ------------------------------------------------------------------
    # LLM provider — AgentRouter gateway (Claude via custom base URL)
    # Get key from: agentrouter.org/console/token
    # ------------------------------------------------------------------
    agentrouter_api_key: str = Field(..., description="Required — get from agentrouter.org")
    llm_model_name: str = Field(default="claude-opus-4-6")
    llm_base_url: str = Field(default="https://agentrouter.org/")

    # ------------------------------------------------------------------
    # Embedding provider  
    # ------------------------------------------------------------------
    embedding_model_name: str = Field(default="all-MiniLM-L6-v2")
    embedding_dimension: int = Field(default=384)

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    environment:          str = Field(default="development")
    log_level:            str = Field(default="INFO")
    max_upload_size_mb:   int = Field(default=50, ge=1)

    # ------------------------------------------------------------------
    # Data paths — all relative to project root
    # ------------------------------------------------------------------
    data_dir: Path = Field(default=Path("data"))

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def extracted_dir(self) -> Path:
        return self.data_dir / "extracted"

    @property
    def page_images_dir(self) -> Path:
        return self.data_dir / "page_images"

    @property
    def evaluation_dir(self) -> Path:
        return self.data_dir / "evaluation"

    # ------------------------------------------------------------------
    # Environment helpers
    # ------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the singleton Settings instance.
    In tests: call get_settings.cache_clear() before monkeypatching.
    """
    return Settings()