"""
Model gateway (WBS T009) - unified interface to the LLM provider.

Wraps OpenRouter's OpenAI-compatible chat completions API with retries,
exponential backoff, timeout handling, token counting, and cost tracking.
This is the ONLY module that should ever call the LLM directly - the
classifier, agent, etc. all go through ModelGateway.complete() so cost/
latency accounting stays centralized and consistent (Section 6, "Model
Gateway").

Failure handling (Section 4, Flow 7 "External Model Failure"):
- Timeout -> retry with backoff
- 429 (rate limit) -> retry with backoff, respecting Retry-After if present
- 5xx (server error) -> retry with backoff
- 4xx other than 429 (bad request, auth) -> raise immediately, retrying won't help
- All retries exhausted -> raise ModelError
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import openai
from openai import OpenAI

from pipeline.config import settings
from pipeline.logging_config import get_logger

logger = get_logger("model_gateway")

# Pricing in USD per million tokens. Verified live against OpenRouter's
# GET /api/v1/models on 2026-09-22 (see data/cost_estimates.json) - exact
# match to the planning doc's Section 13 assumption.
PRICING_PER_MILLION: dict[str, dict[str, float]] = {
    "openai/gpt-5-mini": {"input": 0.25, "output": 2.00},
    # Added for the C01 model comparison / bake-off (different vendor,
    # different architecture, not just a cheaper OpenAI tier).
    "google/gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    # Local, via Ollama - no per-call API fee (problem statement's
    # hosted-vs-local comparison, C02). Uses local compute instead.
    "llama3.2:3b": {"input": 0.0, "output": 0.0},
    # Groq's free tier, run on Groq's hardware instead of locally (avoids
    # taxing the dev machine). Groq's catalog no longer includes a
    # general-purpose Llama chat model (checked live, 2026-09-23 - only
    # llama-prompt-guard, a content classifier, not usable here) - this
    # is a real deviation from the problem statement's literal "Llama
    # 3.2 3B" commitment, kept honest rather than silently substituted.
    # gpt-oss-20b is what's actually available and working.
    "openai/gpt-oss-20b": {"input": 0.0, "output": 0.0},
    "llama-3.2-3b-preview": {"input": 0.0, "output": 0.0},  # kept registered in case Groq relists it
}


class ModelError(Exception):
    """Raised when a model call fails after exhausting all retries."""


@dataclass
class ModelResponse:
    """Result of a single ModelGateway.complete() call."""
    content: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    num_retries: int = 0
    stage_latencies: dict[str, float] = field(default_factory=dict)


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estimate cost in USD for a call. Unknown models log a warning and cost $0."""
    pricing = PRICING_PER_MILLION.get(model)
    if pricing is None:
        logger.warning(f"No pricing entry for model '{model}', estimating cost as $0")
        return 0.0
    return (tokens_in / 1_000_000) * pricing["input"] + (tokens_out / 1_000_000) * pricing["output"]


class ModelGateway:
    """Unified, retrying interface to the OpenRouter chat completions API."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int | None = None,
        timeout_seconds: int | None = None,
    ):
        self.model = model or settings.default_model
        self.max_retries = max_retries if max_retries is not None else settings.max_retries
        self.timeout_seconds = timeout_seconds or settings.request_timeout_seconds

        api_key = api_key or settings.openrouter_api_key
        base_url = base_url or settings.openrouter_base_url
        if not api_key:
            raise ModelError(
                "No OPENROUTER_API_KEY configured. Add a real key to .env "
                "(see .env.example) before calling the model gateway."
            )

        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=self.timeout_seconds)

    @classmethod
    def local(
        cls,
        model: str | None = None,
        base_url: str | None = None,
        max_retries: int | None = None,
        timeout_seconds: int | None = None,
    ) -> "ModelGateway":
        """
        Gateway pointed at a local Ollama instance instead of OpenRouter -
        the problem statement's hosted-vs-local comparison (C02). Ollama
        exposes an OpenAI-compatible /v1 endpoint, so this reuses the same
        complete()/retry/cost-tracking logic unchanged; only the base_url,
        api_key (Ollama ignores it, but the openai client requires a
        non-empty string), and pricing (registered at $0 above) differ.
        """
        return cls(
            model=model or settings.local_model_name,
            api_key="ollama",
            base_url=base_url or settings.local_base_url,
            max_retries=max_retries, timeout_seconds=timeout_seconds,
        )

    @classmethod
    def groq(
        cls,
        model: str | None = None,
        base_url: str | None = None,
        max_retries: int | None = None,
        timeout_seconds: int | None = None,
    ) -> "ModelGateway":
        """
        Gateway pointed at Groq's free-tier hosted Llama - same model
        family as .local(), but runs on Groq's hardware instead of this
        machine. Added specifically because local inference during the
        T041 final test-set run was overheating the dev laptop; this is
        functionally the same $0-cost comparison arm without that cost.
        Requires GROQ_API_KEY in .env (free signup at console.groq.com).
        """
        if not settings.groq_api_key:
            raise ModelError(
                "No GROQ_API_KEY configured. Sign up free at console.groq.com, "
                "generate a key, and add it to .env (see .env.example)."
            )
        return cls(
            model=model or settings.groq_model_name,
            api_key=settings.groq_api_key,
            base_url=base_url or settings.groq_base_url,
            max_retries=max_retries, timeout_seconds=timeout_seconds,
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> ModelResponse:
        """
        Run one chat completion with retries and exponential backoff.

        Never logs prompt or response content (may contain NDA text) -
        only metadata (latency, token counts, retry count, error class).
        """
        temperature = settings.temperature if temperature is None else temperature
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                kwargs = {}
                if response_format is not None:
                    kwargs["response_format"] = response_format

                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    **kwargs,
                )
                latency_ms = (time.perf_counter() - start) * 1000

                content = response.choices[0].message.content or ""
                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                cost = estimate_cost(self.model, tokens_in, tokens_out)

                logger.info("Model call succeeded", extra={
                    "stage": "model_call", "model": self.model, "latency_ms": round(latency_ms, 1),
                    "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost,
                })

                return ModelResponse(
                    content=content,
                    model=self.model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    num_retries=attempt,
                )

            except openai.AuthenticationError as e:
                # Bad/expired key - retrying will never help.
                logger.error(f"Model authentication failed: {type(e).__name__}")
                raise ModelError(f"Authentication failed - check OPENROUTER_API_KEY: {e}") from e

            except openai.BadRequestError as e:
                # Malformed request - retrying will never help.
                logger.error(f"Model request malformed: {type(e).__name__}")
                raise ModelError(f"Bad request (not retried): {e}") from e

            except (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError,
                    openai.APIConnectionError) as e:
                last_error = e
                if attempt < self.max_retries:
                    backoff = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"Model call failed ({type(e).__name__}), retrying in {backoff}s "
                        f"(attempt {attempt + 1}/{self.max_retries + 1})"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Model call failed after {self.max_retries + 1} attempts: {type(e).__name__}")

        raise ModelError(
            f"All {self.max_retries + 1} attempts failed for model '{self.model}': {last_error}"
        ) from last_error
