```
Experiment ID: E00B
Question: Can the planned reconstruction-v2 experiment programme (E01 Oracle, E03 prompt
    selection, E15 hosted-vs-local comparison) fit within the remaining hosted-model budget
    and practical runtime, and how should that constraint shape the experimental design?
Hypothesis: Given this project's own real historical per-case costs (not a token formula
    guess), the full E01+E03+E15 programme costs well under $1 against a $5 planning
    budget -- budget is not the binding constraint; runtime and the Gemini 2.5 Flash Lite
    retirement date (2026-10-16) are the real constraints.
Why this experiment exists: the professor explicitly required token/budget calculation
    BEFORE Oracle and before spending the remaining hosted-model budget (docs/project_contract.md
    section 14; reconstruction brief Part 4).
Input dataset/split: data/contractnli/train.json (token estimation only, TRAIN per Role A),
    results/runs/*.jsonl + results/archive/runs/*.jsonl (historical spend audit, local-only)
Frozen dependencies: none (pre-Oracle forecasting)
Independent variable: none (this is a forecast, not a comparison)
Controlled variables: n/a
Metrics: USD cost (mean/median/p90/total), token counts (mean/p90/max), runtime (sec/case,
    total hours) under BEST/BASE/WORST-CASE scenarios
Expected cost: $0 (no LLM/API calls; live pricing lookup via documentation search only)
Expected runtime: minutes (local computation only)
Stop condition: budget/runtime forecast complete, no model called
Result: see summary.md and results/budget_plan.json
Decision: see summary.md
What becomes frozen after this: see summary.md's Frozen / Not-yet-frozen list
```

## What this experiment does

Local-only budget, token, and runtime forecasting. Makes **zero LLM/API calls** and **zero
local-model inference calls**. The only network activity this phase used was documentation
lookup (web search) to verify current hosted-model pricing — no model was called.

- `scripts/build_e00b_forecast.py` — the reusable computation script (also importable logic
  lives in `evaluation/budget.py`, used by this script and intended for reuse by future
  hosted-run scripts as the pre-run budget gate).
- `results/historical_spend.csv` — every historical hosted/local run found under
  `results/runs/`, `results/archive/runs/` (including the pre-C1-fix superseded run),
  parsed from real saved JSONL records — no fabricated values, unknowns marked explicitly.
- `results/current_pricing.csv` — live-verified pricing for the plausible hosted candidates
  (Gemini 2.5 Flash Lite, GPT-5 mini, Groq gpt-oss-20b), plus the $0 local Ollama entry.
- `results/token_estimates.csv` — empirical token estimates from real local TRAIN-split text
  (system prompt + hypothesis + gold evidence), using `tiktoken`'s `cl100k_base` encoding as
  a clearly-labeled approximation (no model publishes an exact tokenizer usable fully
  offline for both candidate providers).
- `results/experiment_forecast.csv` — E01/E03/E15 cost scenarios at several sample sizes,
  using **real historical actual per-case cost** as the primary basis (more reliable than a
  token formula alone — it already captures GPT-5-mini's hidden reasoning-token inflation).
- `results/runtime_forecast.csv` — local (measured, n=500 real per-architecture runs) and
  hosted (measured, n=2091 real per-architecture runs) runtime, plus a BEST/BASE/WORST-CASE
  escalation-rate scenario sweep for the agentic architecture.
- `results/budget_plan.json` — the consolidated decision output (all scenarios + the 10
  required answers).
- `E00B_budget_forecast.ipynb` — executed analysis notebook walking through all of the above.

Full write-up: `summary.md`.
