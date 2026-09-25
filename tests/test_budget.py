"""Unit tests for evaluation/budget.py (E00B)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from evaluation.budget import (
    Pricing,
    check_budget,
    check_budget_against_ledger,
    estimate_cost,
    load_pricing,
    reconstruction_spend_so_far,
    record_spend,
)


def test_load_pricing_known_model():
    pricing = load_pricing("google/gemini-2.5-flash-lite")
    assert pricing is not None
    assert pricing.input_price_per_million == 0.10
    assert pricing.output_price_per_million == 0.40
    assert pricing.published_input_price_per_million == 0.10


def test_load_pricing_unknown_model_returns_none():
    assert load_pricing("some/nonexistent-model") is None


def test_gpt5_mini_cached_input_is_corrected():
    """Regression test for the cached-input correction: $0.025/M per official OpenAI
    pricing, not the earlier mis-recorded $0.03/M."""
    pricing = load_pricing("openai/gpt-5-mini")
    assert pricing is not None
    assert pricing.output_price_per_million == 2.00


def test_groq_published_price_is_not_zero():
    """Regression test: Groq's canonical published price must not be encoded as $0/token
    just because a free tier exists -- the free tier is a rate limit, not a price."""
    pricing = load_pricing("openai/gpt-oss-20b")
    assert pricing is not None
    assert pricing.published_input_price_per_million == 0.075
    assert pricing.published_output_price_per_million == 0.30
    # Effective assumption is conservative: equals published, not $0.
    assert pricing.effective_cost_assumption_input_per_million == 0.075
    assert pricing.effective_cost_assumption_output_per_million == 0.30


def test_estimate_cost_matches_formula():
    pricing = Pricing(
        "openrouter", "test/model",
        published_input_price_per_million=1.0, published_output_price_per_million=2.0,
        account_tier="pay-as-you-go",
        effective_cost_assumption_input_per_million=1.0,
        effective_cost_assumption_output_per_million=2.0,
        effective_cost_assumption_note="", date_checked="", source_note="",
    )
    cost = estimate_cost(tokens_in=1_000_000, tokens_out=500_000, pricing=pricing)
    assert cost == 1.0 + 1.0  # 1M in @ $1/M + 0.5M out @ $2/M


def test_check_budget_allows_under_reserve():
    result = check_budget(projected_experiment_cost_usd=1.0, actual_spend_so_far_usd=0.0,
                           planning_budget_usd=5.0, protected_reserve_fraction=0.25)
    assert result.allowed is True
    assert result.allowed_budget_usd == 3.75


def test_check_budget_blocks_over_reserve():
    result = check_budget(projected_experiment_cost_usd=4.0, actual_spend_so_far_usd=0.0,
                           planning_budget_usd=5.0, protected_reserve_fraction=0.25)
    assert result.allowed is False


def test_check_budget_accounts_for_prior_spend():
    result = check_budget(projected_experiment_cost_usd=1.0, actual_spend_so_far_usd=3.0,
                           planning_budget_usd=5.0, protected_reserve_fraction=0.25)
    # 3.0 + 1.0 = 4.0 > allowed 3.75 -> blocked
    assert result.allowed is False


def test_reconstruction_ledger_empty_returns_zero():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ledger.csv"
        assert reconstruction_spend_so_far(ledger) == 0.0


def test_record_spend_accumulates_and_is_never_double_counted_with_history():
    """The running ledger sums only what record_spend() itself wrote -- it has no way to see
    historical T-series spend (results/budget/historical_spend.csv is a different file
    entirely), so the two can never be silently double-counted."""
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ledger.csv"
        record_spend("E01", "openrouter", "google/gemini-2.5-flash-lite", 700, 20,
                      0.0001, "run_a", ledger_path=ledger)
        record_spend("E01", "openrouter", "openai/gpt-5-mini", 700, 20, 0.0007,
                      "run_b", ledger_path=ledger)
        assert abs(reconstruction_spend_so_far(ledger) - 0.0008) < 1e-9


def test_check_budget_against_ledger_uses_running_ledger_not_historical():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ledger.csv"
        record_spend("E01", "openrouter", "google/gemini-2.5-flash-lite", 700, 20,
                      3.5, "run_a", ledger_path=ledger)  # deliberately large, near the reserve line
        result = check_budget_against_ledger(
            projected_experiment_cost_usd=0.5, planning_budget_usd=5.0,
            protected_reserve_fraction=0.25, ledger_path=ledger,
        )
        # 3.5 (ledger) + 0.5 (projected) = 4.0 > allowed 3.75 -> blocked
        assert result.allowed is False
