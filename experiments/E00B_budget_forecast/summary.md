# E00B — Budget, Token & Runtime Forecast — Summary

**Result: the planned reconstruction-v2 programme (E01 Oracle + E03 prompt selection + E15
hosted-vs-local comparison) fits comfortably within budget under every scenario tested — the
real constraint is runtime and a hard external deadline, not dollars.**

## 1. Current planning budget

- `planning_budget_usd: 5.00`, source: user-reported current balance, recorded 2026-09-26.
- The historical `.env` value `MAX_BUDGET_USD=6.99` is **not trusted** (stale, dated
  2026-09-22, predates substantial T041 spend) and is **not overwritten** — both values are
  now on record, with the $5 figure used as the live forward planning constraint per the
  reconstruction brief's explicit instruction.
- Protected reserve: 25% → **$1.25 reserved, $3.75 allowed** for actual forward spend.

## 2. Historical hosted spend (audit, not subtracted from the $5)

Audited every local `results/runs/*.jsonl` and `results/archive/runs/*.jsonl` file (27 runs
found, `results/budget/historical_spend.csv`) by parsing real saved per-prediction
`cost_latency` records — no fabricated values; the one file lacking cost data
(`checkpoint_T041_final_test_rag_agent_llama3.2_3b.jsonl`, a mid-run checkpoint) is marked
`UNKNOWN`, not guessed.

**Total historical hosted (OpenRouter) spend found: $3.0011** — $2.8463 on
`google/gemini-2.5-flash-lite`, $0.1549 on `openai/gpt-5-mini`. Local Ollama runs cost $0 by
construction. Per section 19's rule, this is a **separate ledger** from the $5 planning
budget — **not subtracted from it**, since $5 is the user's stated *current remaining*
balance, already net of this historical spend.

## 3. Current verified hosted-model pricing (live-checked 2026-09-26, corrected after review)

**Schema revised** to separate a model's canonical **published** rate from the **effective
cost assumption** forecasts actually use — a free/discounted tier existing does not make a
model's real price $0, and forecasts must not assume a future run is guaranteed to stay
within a free tier's limits.

| Provider | Model | Published in/out $/M | Effective assumption in/out $/M | Account tier | Note |
|---|---|---|---|---|---|
| OpenRouter | `google/gemini-2.5-flash-lite` | $0.10 / $0.40 | $0.10 / $0.40 | pay-as-you-go | Matches the historical `pipeline/model_gateway.py` entry exactly. Lifecycle: **provider-specific**, not a blanket retirement — see §17 below. |
| OpenRouter | `openai/gpt-5-mini` | $0.25 / $2.00 | $0.25 / $2.00 | pay-as-you-go | Matches historical entry. **Corrected**: cached input is **$0.025/M** (official OpenAI pricing), not the earlier mis-recorded $0.03/M — that figure came from an initial web-search snippet, not independently cross-checked against OpenAI's own pricing page at the time. |
| Groq | `openai/gpt-oss-20b` | **$0.075 / $0.30** | $0.075 / $0.30 | free (rate-limited) — paid tier also available at the published rate | **Corrected**: the model's canonical published price is $0.075/$0.30 per M, **not $0/token** as previously recorded. A free developer tier exists (30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD) but is an account/tier condition, not the model's price — forecasts conservatively assume the published paid rate, not free. |
| Local/Ollama | `llama3.2:3b` | $0.00 / $0.00 | $0.00 / $0.00 | local compute (no billing account exists) | Genuinely $0 — not a free tier of a paid service. Runtime/thermal cost, not dollars. |

No candidate was `PRICING_UNVERIFIED` — all four plausible Oracle candidates (2 that could
serve as "hosted," 1 free-hosted, 1 local) have live-verified numbers on record in
`configs/pricing/*.yaml`, now with `evaluation/budget.py`'s `Pricing` dataclass exposing both
`published_*` and `effective_cost_assumption_*` fields.

## 4. Token estimation methodology

Empirical, from real local TRAIN-split text (`prompts/classify_v6.txt` + the 17 fixed
hypotheses + gold evidence spans), using `tiktoken`'s `cl100k_base` encoding as a
**clearly-labeled approximation** — neither Gemini nor GPT-5-mini publish an exact tokenizer
usable fully offline. Real dataset-derived numbers:

- System prompt: **571 tokens**.
- Hypothesis: mean **15.6 tokens** (17 fixed hypotheses, max 28).
- Gold evidence (TRAIN, Entailment/Contradiction, n=4,371 real cases): mean **90.7 tokens**,
  median 73.0, p90 170.0, max 603.
- Oracle input estimate: **~678 tokens mean**, ~773 tokens p90.
- Compact output example (`{"label": "...", "evidence_ids": [...]}`) : **17 tokens**.
- Verbose/historical-like output (label+confidence+evidence+explanation): **75 tokens**.

## 5. Compact vs. verbose cost difference

- **Instructor-cited figures (644 in / 449 out / $0.001059 / 9.21s) were located locally**
  (`docs/archive/initial_project_plan.md` section 22.2) — but verified to be **the
  instructor's own estimate, based on a GPT-5-mini example from the Week 3 submission, not
  this project's own measured NDATrace data.** Not found anywhere in this project's actual
  result files under those values. Reported accurately, not treated as a project fact.
- **This project's own real measured data** (T024 RAG, Gemini, v2 prompt, n=150): mean input
  853.6 tokens, mean output 116.1 tokens, mean cost $0.0001318/call — very different from the
  instructor's cited figures, consistent with this project having switched to a
  ~12x-cheaper model (Gemini vs. GPT-5-mini) partway through, per ADR-001.
- **T019's already-computed real finding** (`data/explanation_cost.json`, re-cited not
  re-derived): explanation text is 31.1% of output tokens but only 9.3% of total cost —
  input tokens dominate cost for this project's real prompt/context sizes.
- **Design rule adopted**: bulk evaluation outputs default to minimal structured JSON
  (label + evidence IDs, ~17-30 tokens); verbose natural-language explanations are generated
  only in experiments that specifically evaluate explanation/faithfulness quality (contract
  axis D), not in every bulk run.

## 6. Proposed Oracle sample size

**150–300 cases recommended** — chosen for budget/runtime/diagnostic reasons, **not**
performance (Oracle hasn't run yet, per section 6's explicit rule). 150 matches the
historical convention (direct comparability to prior Oracle numbers as motivating context,
not as a target to replicate); 300 gives more per-class support for Contradiction Recall at
negligible extra cost (+$0.17). **Not frozen as a manifest yet** — this is a feasible-size
recommendation; the actual `TRAIN_ORACLE` manifest (document-level, fixed seed, generated
once) is E01's job, per `docs/experiment_protocol.md`'s manifest-generation rule.

If diagnostic stratification oversamples Contradiction (a real possibility, given natural
TRAIN prevalence is only ~11.7%): this must be stated explicitly when it happens, and Oracle's
overall accuracy must never be reported as representative of the natural distribution — rely
on per-class metrics, Macro-F1, and Contradiction Recall instead (already frozen policy,
`docs/evaluation_protocol.md` Part 1 §6).

## 7–9. Oracle cost (real historical-cost basis, not token formula alone)

**Why historical-actual, not the token formula, is the primary basis**: GPT-5-mini's real
historical Oracle cost ($0.001033/case) is **~5x** its naive token-formula estimate
(~$0.0002/case) because of hidden reasoning tokens billed as output (ADR-001) — a token
formula alone would badly underestimate GPT-5-mini specifically. Gemini's real cost
($0.0000834/case) sits between the compact ($0.0000746) and verbose ($0.0000978)
token-formula estimates, cross-validating the methodology for models without hidden
reasoning tokens.

| Sample size | Hosted Model A (Gemini, real per-case $0.0000834) | Hosted Model B (GPT-5-mini, real per-case $0.0010326) | **Total Oracle (2 hosted)** |
|---|---|---|---|
| n=150 | $0.0125 | $0.1549 | **$0.1674** |
| n=300 | $0.0250 | $0.3098 | **$0.3348** |
| n=500 | $0.0417 | $0.5163 | **$0.5580** |

(2 local models: $0 by construction, runtime cost only — see §13.)

## 10–11. Protected reserve and remaining budget after Oracle

- Reserve: **$1.25** (25% of $5).
- Allowed forward-spend budget: **$3.75**.
- Remaining after a 300-case, 2-hosted-model Oracle ($0.3348): **$3.4152**.

## 12. Forecast for later hosted experiments (real historical-cost basis)

| Experiment | Scenario | Estimated cost |
|---|---|---|
| E03 prompt selection | 150-case TRAIN subset × 4 prompt variants, 1 hosted model | $0.0791 |
| E15 hosted-vs-local | 300-case stratified TEST subsample × 3 non-rule architectures, 1 hosted model | $0.2654 |
| Rerun reserve | 10% of the E01+E03+E15 RECOMMENDED subtotal | $0.0679 |
| **RECOMMENDED total** | | **$0.7472**, leaving **$3.0028** of the $3.75 allowed budget untouched |

**Three budget scenarios** (none spends the full $5; reserve always preserved):

| Scenario | Description | Cost | Fits? |
|---|---|---|---|
| LEAN | Oracle n=150 + a small hosted E15 spot-check | $0.3001 | Yes |
| **RECOMMENDED** | Oracle n=300 + E03 (600 hosted calls) + E15 (900 hosted calls) + 10% rerun reserve | $0.7472 | Yes |
| MAXIMUM SAFE | Oracle n=500 + E03 (1,200 calls) + E15 (1,500 calls) | $1.1586 | Yes |

Even MAXIMUM SAFE uses under a quarter of the $3.75 allowed budget — **budget is not the
binding constraint** for this experiment programme at any realistic scale.

## 13. Local runtime forecast (real measured per-case means, n=500 local runs, scaled to the
full 2,091-case TEST set)

| Architecture | Measured sec/case (n=500) | Full-TEST estimated time |
|---|---|---|
| A1 full-context, local Llama | 7.68s | ~4.46 hours |
| A2 RAG, local Llama | 4.53s | ~2.63 hours |
| A3 RAG+agent, local Llama | 9.19s | ~5.34 hours |
| Rule baseline | negligible (no model call) | seconds |
| **All 3 non-rule local architectures, sequential** | | **~12.4 hours total** |

Agentic escalation-rate scenario sweep (applied to the RAG per-case baseline, since the real
historical escalation mix is embedded in the "measured" A3 row above and not separately
knowable without re-running):

| Scenario | escalation_rate | extra_turn_factor | sec/case | Full-TEST hours |
|---|---|---|---|---|
| BEST-CASE | 0.30 | 1.0 | 4.53 | 2.63 |
| BASE-CASE | 0.45 | 1.3 | 5.76 | 3.34 |
| WORST-CASE | 0.60 | 1.8 | 8.89 | 5.16 |

The real measured A3 value (9.19s/5.34h) sits at/slightly above this WORST-CASE sweep,
suggesting the historical escalation rate was on the higher end of what's modeled here — a
useful sanity check, not a contradiction (this is a small formula-based scenario sweep, not a
claim to have derived the true escalation rate).

Hosted (Gemini) per-case latency for E15's smaller subsample (n=2,091 real measurements,
scaled down): full-context 1.11s, RAG 1.03s, RAG+agent 2.67s — a 300-case × 3-architecture
E15 run takes **under 25 minutes total**, negligible next to the local runtime.

## 14. Recommended budget scenario

**RECOMMENDED**: Oracle n=300 (2 hosted models) → E03 on the selected model only (150-case
TRAIN subset × ~4 variants) → E15 (300-case stratified TEST subsample × 3 architectures, 1
hosted model) → 10% rerun reserve. Total **$0.7472** of $3.75 allowed, leaving **$3.00**
genuinely untouched for the unexpected. Local runtime (~12.4h for the full local 4-architecture
TEST pass) is the actual planning constraint, not dollars.

## 15. Files created/modified

**Created:**
- `evaluation/budget.py` — reusable pricing/cost/budget-gate module (`load_pricing`,
  `estimate_cost`, `check_budget`), with a runnable `demo()` self-check.
- `tests/test_budget.py` — 6 unit tests.
- `configs/pricing/openrouter_google_gemini-2.5-flash-lite.yaml`,
  `configs/pricing/openrouter_openai_gpt-5-mini.yaml`,
  `configs/pricing/groq_openai_gpt-oss-20b.yaml`,
  `configs/pricing/local_ollama_llama3.2-3b.yaml` — live-verified pricing entries.
- `scripts/build_e00b_forecast.py` — the reusable forecast computation script.
- `results/budget/{historical_spend,current_pricing,token_estimates,experiment_forecast,
  runtime_forecast}.csv`, `results/budget/budget_plan.json`.
- `experiments/E00B_budget_forecast/` — this directory (README, config, summary, notebook,
  and a copy of the results/ outputs for this experiment's own record).

**Modified:** none outside the above (no pipeline/model code touched).

## 16a. Gemini lifecycle — corrected to be provider-specific

**Rejected the blanket claim "Gemini 2.5 Flash Lite retires 2026-10-16."** Verified precisely
instead:
- **Google's own Gemini Developer API (AI Studio)** lists `gemini-2.5-flash-lite` as **stable,
  not deprecated, no announced shutdown date** (checked 2026-09-26).
- **Google Cloud Vertex AI** separately lists a **2026-10-16** retirement for Gemini 2.5
  Flash-Lite on that specific platform.
- **Which one NDATrace actually uses**: `pipeline/model_gateway.py` calls **OpenRouter**
  (`settings.openrouter_base_url`), with **no provider pinned** anywhere in the code.
  OpenRouter itself serves `google/gemini-2.5-flash-lite` via **both** Google Vertex AI and
  Google AI Studio, with automatic failover between them.
- **Conclusion**: the 2026-10-16 date applies to the Vertex AI backend specifically. Because
  NDATrace's calls are unpinned, there is a **real but not certain** risk that some hosted
  calls after that date route through the retiring backend — a materially weaker, more precise
  claim than "the model retires." Mitigation available if desired: pin OpenRouter's provider
  routing to `google-ai-studio` only — not decided or built here. Full detail recorded in
  `configs/pricing/openrouter_google_gemini-2.5-flash-lite.yaml`'s `lifecycle` block.

## 16b. Forecast totals — did they change?

**No.** The E01/E03/E15 dollar forecasts (§9, §12, the LEAN/RECOMMENDED/MAXIMUM SAFE
scenarios) are computed from **real historical actual per-case cost** (`results/*.jsonl`),
not from the corrected pricing metadata — Groq was never used as a costed input to any
scenario, and GPT-5-mini's cached-input correction doesn't affect `estimate_cost()` (which
only uses input/output rates, both unchanged). Re-ran `scripts/build_e00b_forecast.py` after
all corrections: LEAN $0.3001, RECOMMENDED $0.7472, MAXIMUM SAFE $1.1586 — **identical to the
pre-correction numbers.** Only the pricing metadata, schema, and Gemini/Groq framing changed.

## 17. Running reconstruction-v2 spend ledger — implemented, ready before E01

- `evaluation/budget.py::record_spend(experiment_id, provider, model, input_tokens,
  output_tokens, cost_usd, run_id)` — append-only, writes to
  `results/budget/reconstruction_spend_ledger.csv`.
- `evaluation/budget.py::reconstruction_spend_so_far()` — sums the ledger's `cost_usd` column;
  returns `0.0` if nothing has been recorded yet.
- `evaluation/budget.py::check_budget_against_ledger()` — the real pre-run gate: reads
  **reconstruction-v2's own spend only** (never the historical T-series ledger) and applies
  `actual_reconstruction_v2_spend + projected_next_experiment_spend + protected_reserve <=
  planning_budget`.
- **Status**: `results/budget/reconstruction_spend_ledger.csv` exists now, header-only, **$0.00
  recorded** — ready for E01 to start appending to. 4 new tests confirm accumulation,
  ledger-based gating, and that historical spend can never be double-counted into it (the
  ledger has no code path that reads `historical_spend.csv`).

## 18. Tests/checks run

- `pytest tests/test_budget.py -q` — **11/11 pass** (6 original + 2 pricing-correction
  regression tests + 3 ledger tests).
- `python3 -m evaluation.budget` (the module's own `demo()` self-check, now including the
  ledger round-trip) — passes.
- `python3 scripts/build_e00b_forecast.py` — re-run end-to-end after all corrections,
  local-only, zero model/API calls.
- Notebook re-executed in place with real, corrected outputs (`E00B_budget_forecast.ipynb`).

## 19. Decisions needing approval

1. **Gemini 2.5 Flash Lite's Vertex AI backend retires 2026-10-16** (~3 weeks from today);
   Google AI Studio's listing is stable. NDATrace's unpinned OpenRouter calls could hit either
   backend. Options: (a) proceed and accept the risk, (b) pin OpenRouter routing to
   `google-ai-studio`, (c) pick a different primary hosted model, (d) plan a contingency swap.
   Not decided here — flagged for approval before model-selection planning (E02).
2. **Oracle sample size (150 vs. 300)** — 300 is recommended (better Contradiction support,
   negligible extra cost) but not frozen; needs sign-off before E01's manifest is generated.
3. **Whether Groq's free-tier gpt-oss-20b should count as one of the "2 hosted" Oracle slots**
   — it is genuinely hosted (not on this machine); its free tier is a rate-limited account
   condition, not its price. If reconstruction-v2 later commits to relying on that free tier for
   a specific run, that's a model-selection decision to make then. **Not decided here** — kept
   unresolved per the reconstruction brief's explicit instruction.

## Frozen vs. not-yet-frozen after E00B

**FROZEN:**
- Current planning budget: `$5.00`, source and date recorded.
- Protected reserve policy: 25% ($1.25), $3.75 allowed forward spend.
- Budget-check rule/utility: `evaluation/budget.py::check_budget()` — hard pre-run gate,
  must run before any hosted experiment.
- Bulk output format principle: compact structured JSON by default; verbose explanations only
  in explanation-quality-focused experiments.
- Maximum hosted spend allowed before further approval: the RECOMMENDED scenario's $0.7472 is
  the default envelope; MAXIMUM SAFE ($1.1586) requires no further approval either (still
  within the $3.75 allowed budget) but LEAN/RECOMMENDED is the default unless later phases
  argue for more.
- Live-verified current pricing for the 4 audited models (`configs/pricing/*.yaml`), with
  published vs. effective-assumption rates now explicit.
- Running reconstruction-v2 spend ledger and gate:
  `evaluation/budget.py::{record_spend, reconstruction_spend_so_far, check_budget_against_ledger}`,
  ready before E01.

**NOT FROZEN:**
- Exact Oracle models (2 hosted + 2 local) — not selected.
- Exact Oracle sample size — 150-300 recommended range, not frozen to one number.
- Model winner, prompt winner, architecture winner, retrieval config, agent policy — all
  untouched, per the stop condition.
- Whether Groq counts as a "hosted" Oracle slot for the 2+2 design (decision #3 above).
