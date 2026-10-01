#!/usr/bin/env python3
"""Business-economics scenario: measured inference cost + an externally sourced
review-time baseline + a transparently modeled effort-reduction scenario.

Three categories, never blended:
  MEASURED BY NDATRACE   -- this project's own saved inference-cost numbers
  EXTERNALLY SOURCED      -- a published, dated, sample-sized third-party survey
  MODELED / ILLUSTRATIVE  -- explicit scenario assumptions, formulas shown, not fit to any target

No reviewer-time number has been measured by this project (no pilot has been run). Every
"hours saved" / "dollars saved" figure below is a scenario output of the formulas at the
bottom of this file, not a result. Zero model calls.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "results" / "business_economics_scenario.json"

# ---------------------------------------------------------------- MEASURED BY NDATRACE
# Reused, not recomputed, from experiments/E20_final_rag_test/results/E20_final_report.json
# ("ops"."cost_per_case" for RAG and FULL) -- the same numbers the README's Metrics table cites.
MEASURED = {
    "rag_cost_per_case_usd": 0.00168,
    "full_cost_per_case_usd": 0.00202,
    "source": "experiments/E20_final_rag_test/results/E20_final_report.json",
}

# ---------------------------------------------------------------- EXTERNALLY SOURCED BASELINE
# LegalOn Technologies, "2025 State of Contracting Survey" (n=286, published 15 Jan 2025),
# https://www.legalontech.com/press-releases/2025-survey -- vendor research (LegalOn sells AI
# contract review software), not independent academic evidence. Exact published claim: "52% of
# organizations handle 101-1,000 contracts annually" at "2-4 hours per contract" review time.
# See docs/citation_fixes.md item 1 for the instructor-feedback-driven citation review of this
# exact source.
EXTERNAL_BASELINE = {
    "source_name": "LegalOn Technologies, \"2025 State of Contracting Survey\"",
    "source_type": "vendor research (LegalOn sells AI contract review software) -- not independently verified academic evidence",
    "publication_date": "2025-01-15",
    "sample_size": 286,
    "population": "legal professionals surveyed by LegalOn Technologies",
    "exact_published_claim": "52% of organizations handle 101-1,000 contracts annually, at 2-4 hours of review time per contract",
    "url": "https://www.legalontech.com/press-releases/2025-survey",
    "baseline_hours_per_contract_used_below": 3.0,
    "baseline_derivation": "midpoint of the published 2-4 hour range -- not itself a published point estimate",
}

# ---------------------------------------------------------------- MODELED / ILLUSTRATIVE
# Every value in this block is a stated assumption, not a measurement or a fitted parameter.
SCENARIO_VOLUME_CONTRACTS_PER_YEAR = 500  # illustrative mid-size legal-ops team, not sourced
ASSUMED_REDUCTION_RATES = [0.10, 0.20, 0.30]  # illustrative, NOT derived from any measurement
ASSUMED_HOURLY_RATE_USD = 40.0  # same illustrative rate used in E18's cost-to-serve scenarios


def scenario_table(baseline_hours_per_contract: float, contracts_per_year: int,
                    hourly_rate_usd: float, reduction_rates: list[float]) -> list[dict]:
    """Transparent formulas, no hidden assumptions:
        annual_hours  = contracts_per_year * baseline_hours_per_contract
        hours_saved   = annual_hours * assumed_reduction_rate
        labor_savings = hours_saved * assumed_hourly_rate
    """
    annual_hours = contracts_per_year * baseline_hours_per_contract
    rows = []
    for rate in reduction_rates:
        hours_saved = annual_hours * rate
        labor_savings = hours_saved * hourly_rate_usd
        rows.append({
            "assumed_reduction_rate": rate,
            "annual_hours_baseline": annual_hours,
            "hours_saved": round(hours_saved, 1),
            "modeled_labor_savings_usd": round(labor_savings, 2),
        })
    return rows


def main() -> None:
    table = scenario_table(
        EXTERNAL_BASELINE["baseline_hours_per_contract_used_below"],
        SCENARIO_VOLUME_CONTRACTS_PER_YEAR,
        ASSUMED_HOURLY_RATE_USD,
        ASSUMED_REDUCTION_RATES,
    )
    out = {
        "measured_by_ndatrace": MEASURED,
        "externally_sourced_baseline": EXTERNAL_BASELINE,
        "modeled_scenario": {
            "contracts_per_year_assumption": SCENARIO_VOLUME_CONTRACTS_PER_YEAR,
            "hourly_rate_assumption_usd": ASSUMED_HOURLY_RATE_USD,
            "formula": "annual_hours = contracts_per_year * baseline_hours_per_contract; "
                       "hours_saved = annual_hours * assumed_reduction_rate; "
                       "labor_savings = hours_saved * assumed_hourly_rate",
            "rows": table,
        },
        "disclosure": "No productivity study was conducted by this project. The hours/cost "
                       "figures above are scenario outputs of explicit assumptions applied to a "
                       "published external baseline, not realized or measured results. Purpose: "
                       "show potential economic scale, not prove ROI.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
