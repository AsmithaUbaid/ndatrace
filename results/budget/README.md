# Budget tracking

**E00B is complete.** This directory holds its reconciled output:

- `current_pricing.csv`, `experiment_forecast.csv`, `runtime_forecast.csv`, `token_estimates.csv`,
  `historical_spend.csv`, `budget_plan.json` — the reconciled forecast/pricing/spend artifacts
  (also mirrored in `experiments/E00B_budget_forecast/results/` as that experiment's own frozen
  snapshot; both copies are required — `evaluation/budget.py` and `tests/test_budget.py` read from
  this directory specifically)
- `final_spend_ledger.csv` — the running, append-only spend ledger for every final
  experiment that made real API calls, updated as the project progressed (not a frozen E00B
  snapshot; this is the live source)

See `experiments/E00B_budget_forecast/summary.md` for the full reconciliation methodology.
