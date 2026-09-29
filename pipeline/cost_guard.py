"""
E22 LLM10 remediation: pre-flight budget enforcement.

E21 (LLM10, FAIL) found `settings.max_budget_usd` was declared in
pipeline/config.py but never read anywhere in the live runtime - it only
informed offline experiment-planning docs. This module makes it a real,
enforced gate on the live product path (backend/routes/review.py), checked
BEFORE any hosted model call, not after.

Cumulative spend is tracked as the sum of `reviews.total_cost_usd` in this
backend's own SQLite database - a deliberate, prototype-scope proxy for
"session/day cost ceiling" covering live product traffic specifically. It is
NOT the same as the offline experiment ledger (results/budget/*.csv), which
mixes in every notebook/script run and would conflate research spend with
what the deployed API itself is responsible for.

Per-request cost is estimated conservatively rather than measured (the real
cost is only known after the model responds): the frozen RAG runtime already
architecturally bounds retrieved context to TOP_K * CHUNK_SIZE tokens
(pipeline/frozen_rag.py), so the estimate adds the free-text requirement
length on top of that fixed ceiling plus a generous assumed-output-token
budget (observed E20/E21 output tokens: ~100-1,500; 2,000 is a deliberate
safety margin, not a measured average).
"""

from __future__ import annotations

from pipeline.config import settings
from pipeline.frozen_rag import CHUNK_SIZE, TOP_K
from pipeline.model_gateway import estimate_cost

CHARS_PER_TOKEN_ESTIMATE = 4  # rough, conservative-high (real text averages ~4 chars/token)
ASSUMED_MAX_OUTPUT_TOKENS = 2000  # safety margin over observed ~100-1,500 (E20/E21 ledgers)
ARCHITECTURAL_MAX_CONTEXT_TOKENS = TOP_K * CHUNK_SIZE  # 5 * 256 = 1,280

# Generous vs. observed real per-call cost (~$0.0007-0.0033, E20/E21 ledgers) -
# this ceiling exists to catch a pathological/misconfigured single request,
# not to constrain ordinary traffic.
MAX_ESTIMATED_REQUEST_COST_USD = 0.05


class CostCeilingExceeded(Exception):
    def __init__(self, message: str, estimated_cost_usd: float, cumulative_spend_usd: float | None = None):
        super().__init__(message)
        self.estimated_cost_usd = estimated_cost_usd
        self.cumulative_spend_usd = cumulative_spend_usd


def estimate_request_cost_usd(requirement_text: str, model: str = "openai/gpt-5-mini") -> float:
    estimated_input_tokens = ARCHITECTURAL_MAX_CONTEXT_TOKENS + len(requirement_text) // CHARS_PER_TOKEN_ESTIMATE
    return estimate_cost(model, estimated_input_tokens, ASSUMED_MAX_OUTPUT_TOKENS)


def cumulative_spend_usd() -> float:
    from backend import database  # local import: avoids a backend<->pipeline import cycle at module load time

    with database.get_connection() as conn:
        row = conn.execute("SELECT COALESCE(SUM(total_cost_usd), 0) AS total FROM reviews").fetchone()
    return float(row["total"])


def check_budget(requirement_text: str, model: str = "openai/gpt-5-mini") -> float:
    """Raises CostCeilingExceeded if this request should not proceed to a model call.
    Returns the estimated cost (for logging) if it's allowed to proceed."""
    estimated = estimate_request_cost_usd(requirement_text, model)
    if estimated > MAX_ESTIMATED_REQUEST_COST_USD:
        raise CostCeilingExceeded(
            f"Estimated request cost (${estimated:.4f}) exceeds the per-request ceiling "
            f"(${MAX_ESTIMATED_REQUEST_COST_USD}).",
            estimated_cost_usd=estimated,
        )
    spent = cumulative_spend_usd()
    if spent + estimated > settings.max_budget_usd:
        raise CostCeilingExceeded(
            f"This request would exceed the configured budget (${settings.max_budget_usd:.2f}): "
            f"${spent:.4f} already spent by this backend + ${estimated:.4f} estimated for this request.",
            estimated_cost_usd=estimated, cumulative_spend_usd=spent,
        )
    return estimated


def check_batch_budget(requirement_texts: list[str], model: str = "openai/gpt-5-mini") -> float:
    """Same budget check as check_budget(), but for a batch of N sequential calls (the
    /review endpoint's up-to-17-requirement path) - the per-request ceiling doesn't apply
    (a legitimate batch is expected to cost more than one call), only the cumulative
    session/day budget does."""
    estimated_total = sum(estimate_request_cost_usd(t, model) for t in requirement_texts)
    spent = cumulative_spend_usd()
    if spent + estimated_total > settings.max_budget_usd:
        raise CostCeilingExceeded(
            f"This batch (~${estimated_total:.4f} for {len(requirement_texts)} requirements) would "
            f"exceed the configured budget (${settings.max_budget_usd:.2f}): ${spent:.4f} already spent.",
            estimated_cost_usd=estimated_total, cumulative_spend_usd=spent,
        )
    return estimated_total


def demo() -> None:
    cost = estimate_request_cost_usd("Receiving Party shall not disclose Confidential Information.")
    assert 0 < cost < MAX_ESTIMATED_REQUEST_COST_USD
    print(f"demo OK: estimated cost for a typical request = ${cost:.5f}")


if __name__ == "__main__":
    demo()
