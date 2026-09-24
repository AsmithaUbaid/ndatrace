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
    # Bare OpenRouter model ID (verified via GET /models 2026-09-22) - no
    # "openrouter/" prefix, that's a litellm routing convention, not what
    # OpenRouter's own REST API expects in the request body.
    #
    # Chosen via a model bake-off (C01, 2026-09-22): same 150-case Oracle
    # sample, same harness, scored against gpt-5-mini. Gemini won on a
    # weighted scorecard - 12x cheaper, 6x faster, tied on risk-sensitive
    # recall (1.000 both), ~1.4pt lower accuracy (96.7% vs 95.3%). See
    # docs/decisions.md and docs/experiments.md's C01 row.
    default_model: str = Field(
        default="google/gemini-2.5-flash-lite",
        description="Default LLM model identifier",
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_retries: int = Field(default=3, ge=0)

    # --- Local model (hosted-vs-local comparison, C02, problem statement's
    # "Compute: Rent + local" commitment) ---
    # Ollama's default local port, OpenAI-compatible /v1 endpoint.
    local_base_url: str = Field(default="http://localhost:11434/v1")
    local_model_name: str = Field(default="llama3.2:3b")

    # --- Groq (free-tier hosted Llama - same model family as "local", but
    # runs on Groq's hardware instead of the laptop. Added when local
    # inference was overheating the dev machine during the T041 final
    # test-set run - functionally the same $0-cost comparison arm, just
    # without the thermal cost.) ---
    groq_api_key: str = Field(default="")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")
    # gpt-oss-20b, not Llama - Groq's catalog no longer includes a
    # general-purpose Llama chat model (verified live, 2026-09-23).
    groq_model_name: str = Field(default="openai/gpt-oss-20b")
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

    # --- Safety gates ---
    # Must be explicitly set True to feed gold evidence into a classifier
    # call (Oracle-style). Never flip this in production code - only
    # scripts/run_oracle_experiment.py sets it, and only for the duration
    # of that script (WBS T026, eval case 090 - "Oracle experiment gated
    # by explicit config flag").
    oracle_mode: bool = Field(default=False)

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
    # Verified via OpenRouter /auth/key on 2026-09-22: real remaining balance
    # is $6.99 (key limit $10.00, already used $3.01). See data/budget_plan.json.
    max_budget_usd: float = Field(default=6.99, ge=0.0)
    warn_budget_pct: int = Field(default=80, ge=0, le=100)

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def results_path(self) -> Path:
        return Path(self.results_dir)


# Singleton — import this everywhere
settings = Settings()
