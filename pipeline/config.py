"""
NDATrace configuration — loads settings from .env using pydantic-settings.

All configuration is centralised here.  Pipeline modules import `settings`
from this module rather than reading os.environ directly.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM Provider ---
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter base URL",
    )

    # --- Model ---
    default_model: str = Field(
        default="openrouter/openai/gpt-4.1-mini",
        description="Default LLM model identifier",
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_retries: int = Field(default=3, ge=0)
    request_timeout_seconds: int = Field(default=30, ge=1)

    # --- Embedding ---
    embedding_model: str = Field(
        default="all-mpnet-base-v2",
        description="Sentence-transformers model name",
    )

    # --- Retrieval ---
    default_top_k: int = Field(default=5, ge=1)
    chunk_size: int = Field(default=512, ge=64)
    chunk_overlap: int = Field(default=50, ge=0)

    # --- Agent ---
    agent_max_steps: int = Field(default=5, ge=1)
    agent_max_tokens: int = Field(default=3000, ge=100)
    agent_max_seconds: int = Field(default=30, ge=1)

    # --- Confidence / Abstention ---
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # --- Paths ---
    data_dir: str = Field(default="data/contractnli")
    results_dir: str = Field(default="results")
    logs_dir: str = Field(default="logs")
    cache_dir: str = Field(default="cache")

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/ndatrace.jsonl")

    # --- Backend ---
    backend_host: str = Field(default="0.0.0.0")
    backend_port: int = Field(default=8000)

    # --- Database ---
    database_url: str = Field(default="sqlite:///ndatrace.db")

    # --- Budget Safety ---
    max_budget_usd: float = Field(default=15.00, ge=0.0)
    warn_budget_pct: int = Field(default=80, ge=0, le=100)

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def results_path(self) -> Path:
        return Path(self.results_dir)


# Singleton — import this everywhere
settings = Settings()
