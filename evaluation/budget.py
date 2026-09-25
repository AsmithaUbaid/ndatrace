"""
Budget forecasting and pre-run gate utilities (E00B, reconstruction-v2).

Pure functions: reads verified pricing from `configs/pricing/*.yaml` and does arithmetic.
No network calls, no model/API calls. This is the module any future hosted-run script should
import to check itself against the planning budget before spending real money — logic lives
here, not buried in the E00B notebook, so it's actually reusable by later experiments.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

PRICING_DIR = Path(__file__).resolve().parent.parent / "configs" / "pricing"
RECONSTRUCTION_LEDGER_PATH = (
    Path(__file__).resolve().parent.parent / "results" / "budget" / "reconstruction_spend_ledger.csv"
)
LEDGER_FIELDNAMES = [
    "timestamp", "experiment_id", "provider", "model",
    "input_tokens", "output_tokens", "cost_usd", "run_id",
]


@dataclass
class Pricing:
    provider: str
    model: str
    # The model's canonical published rate card — what the provider actually bills at,
    # regardless of any free tier. Never $0 just because a free tier exists (see
    # effective_cost_assumption below for the rate forecasts should conservatively use).
    published_input_price_per_million: float
    published_output_price_per_million: float
    account_tier: str
    # What cost forecasts should actually assume per token — conservative by default
    # (usually equal to the published rate). Only drops below published when reconstruction-v2
    # has explicitly committed to relying on a free/discounted tier for a specific run, which
    # is a model-selection decision, not assumed here.
    effective_cost_assumption_input_per_million: float
    effective_cost_assumption_output_per_million: float
    effective_cost_assumption_note: str
    date_checked: str
    source_note: str

    @property
    def input_price_per_million(self) -> float:
        """Backward-compatible alias: the rate estimate_cost() actually uses."""
        return self.effective_cost_assumption_input_per_million

    @property
    def output_price_per_million(self) -> float:
        return self.effective_cost_assumption_output_per_million


def load_pricing(model: str) -> Pricing | None:
    """
    Load a verified pricing entry for `model` from configs/pricing/*.yaml.

    Returns None if no verified entry exists for this exact model string — callers must
    treat that as PRICING_UNVERIFIED and exclude the model from precise cost projections,
    never guess a price.
    """
    if not PRICING_DIR.exists():
        return None
    for path in sorted(PRICING_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        with open(path) as f:
            d = yaml.safe_load(f)
        if d and d.get("model") == model:
            return Pricing(
                provider=d["provider"],
                model=d["model"],
                published_input_price_per_million=d["published_input_price_per_million"],
                published_output_price_per_million=d["published_output_price_per_million"],
                account_tier=d.get("account_tier", "unknown"),
                effective_cost_assumption_input_per_million=d["effective_cost_assumption_input_per_million"],
                effective_cost_assumption_output_per_million=d["effective_cost_assumption_output_per_million"],
                effective_cost_assumption_note=d.get("effective_cost_assumption_note", ""),
                date_checked=d["date_checked"],
                source_note=d["source_note"],
            )
    return None


def estimate_cost(tokens_in: int, tokens_out: int, pricing: Pricing) -> float:
    """cost = (tokens_in / 1e6 * input_price) + (tokens_out / 1e6 * output_price)."""
    return (
        (tokens_in / 1_000_000) * pricing.input_price_per_million
        + (tokens_out / 1_000_000) * pricing.output_price_per_million
    )


@dataclass
class BudgetCheckResult:
    allowed: bool
    projected_total_usd: float
    allowed_budget_usd: float
    reason: str


def check_budget(
    projected_experiment_cost_usd: float,
    actual_spend_so_far_usd: float,
    planning_budget_usd: float,
    protected_reserve_fraction: float = 0.25,
) -> BudgetCheckResult:
    """
    Hard pre-run gate (reconstruction brief section 12). Call this BEFORE any hosted
    experiment executes: block the run if projected_total > allowed_budget.

    No hosted API is contacted here — pure arithmetic against a caller-supplied
    actual_spend_so_far (the caller is responsible for tracking real spend as it accrues,
    e.g. by summing metrics.total_cost_usd across this reconstruction-v2 lineage's own
    result files — historical T-series spend is a separate ledger and is NOT included here,
    per the "don't double-count" rule).
    """
    reserve = planning_budget_usd * protected_reserve_fraction
    allowed_budget = planning_budget_usd - reserve
    projected_total = actual_spend_so_far_usd + projected_experiment_cost_usd
    allowed = projected_total <= allowed_budget
    reason = (
        f"OK: projected total ${projected_total:.4f} <= allowed ${allowed_budget:.4f} "
        f"(planning budget ${planning_budget_usd:.2f} - reserve ${reserve:.2f})"
        if allowed else
        f"BLOCKED: projected total ${projected_total:.4f} > allowed ${allowed_budget:.4f} "
        f"(planning budget ${planning_budget_usd:.2f} - reserve ${reserve:.2f})"
    )
    return BudgetCheckResult(allowed, projected_total, allowed_budget, reason)


def record_spend(
    experiment_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    run_id: str,
    ledger_path: Path = RECONSTRUCTION_LEDGER_PATH,
) -> None:
    """
    Append one successful hosted call to the reconstruction-v2 spend ledger (append-only,
    never overwritten — same convention as results/runs/). Call this after every real hosted
    call reconstruction-v2 makes, starting with E01. Historical T-series spend is a SEPARATE
    ledger (results/budget/historical_spend.csv, built once by scripts/build_e00b_forecast.py
    from old result files) and is never written here or summed into
    reconstruction_spend_so_far() — the two must not be double-counted.
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not ledger_path.exists() or ledger_path.stat().st_size == 0
    with open(ledger_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDNAMES)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment_id": experiment_id, "provider": provider, "model": model,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": cost_usd, "run_id": run_id,
        })


def reconstruction_spend_so_far(ledger_path: Path = RECONSTRUCTION_LEDGER_PATH) -> float:
    """Sum of cost_usd across every row ever recorded by record_spend(). Returns 0.0 if the
    ledger doesn't exist yet (reconstruction-v2 hasn't spent anything) — never raises."""
    if not ledger_path.exists():
        return 0.0
    total = 0.0
    with open(ledger_path) as f:
        for row in csv.DictReader(f):
            total += float(row["cost_usd"])
    return total


def check_budget_against_ledger(
    projected_experiment_cost_usd: float,
    planning_budget_usd: float,
    protected_reserve_fraction: float = 0.25,
    ledger_path: Path = RECONSTRUCTION_LEDGER_PATH,
) -> BudgetCheckResult:
    """
    Convenience wrapper: reads reconstruction-v2's own actual spend from the running ledger
    (never historical T-series spend) and calls check_budget(). This is the function a real
    hosted-run script should call — check_budget() itself stays a pure function for testing.
    """
    return check_budget(
        projected_experiment_cost_usd=projected_experiment_cost_usd,
        actual_spend_so_far_usd=reconstruction_spend_so_far(ledger_path),
        planning_budget_usd=planning_budget_usd,
        protected_reserve_fraction=protected_reserve_fraction,
    )


def demo() -> None:
    """Smallest runnable self-check — no network, no model calls."""
    pricing = load_pricing("google/gemini-2.5-flash-lite")
    assert pricing is not None, "expected configs/pricing/openrouter_google_gemini-2.5-flash-lite.yaml"
    cost = estimate_cost(1000, 100, pricing)
    assert cost > 0

    result = check_budget(
        projected_experiment_cost_usd=1.0, actual_spend_so_far_usd=0.0,
        planning_budget_usd=5.0, protected_reserve_fraction=0.25,
    )
    assert result.allowed_budget_usd == 3.75
    assert result.allowed is True

    blocked = check_budget(
        projected_experiment_cost_usd=4.0, actual_spend_so_far_usd=0.0,
        planning_budget_usd=5.0, protected_reserve_fraction=0.25,
    )
    assert blocked.allowed is False

    unverified = load_pricing("some/nonexistent-model")
    assert unverified is None

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "test_ledger.csv"
        assert reconstruction_spend_so_far(ledger) == 0.0
        record_spend("E01_test", "openrouter", "google/gemini-2.5-flash-lite",
                      100, 20, 0.0001, "run_001", ledger_path=ledger)
        record_spend("E01_test", "openrouter", "google/gemini-2.5-flash-lite",
                      100, 20, 0.0001, "run_002", ledger_path=ledger)
        assert abs(reconstruction_spend_so_far(ledger) - 0.0002) < 1e-9
        gated = check_budget_against_ledger(1.0, 5.0, 0.25, ledger_path=ledger)
        assert gated.allowed is True

    print("evaluation/budget.py self-check OK")


if __name__ == "__main__":
    demo()
