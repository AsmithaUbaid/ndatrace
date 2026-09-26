# E12A — Static Context Expansion — STAGE A (offline design + forecast only)

**No GPT/Qwen/Gemini call has been made. `retrieval_v1` and `classification_prompt_v1` are
unmodified.** This document verifies which fixed final-K covers E09's six
RETRIEVAL_FILTERING_LIMITED cases, builds the candidate context artifact offline from the frozen
top-20 pool, forecasts context size / cost / runtime, and freezes the metrics and analysis plan.

## 1. Research question

"Can deterministic expansion of the final retrieved context recover the retrieval/filtering
failures identified after GPT-5-mini without introducing enough distractor regressions, context
growth, latency, or cost to negate the benefit?" A static pipeline experiment — not agent work,
retrieval re-optimisation, prompt engineering, or model selection. E10/E11 completed as a
controlled agent comparison and A3 was rejected; this tests the cheaper deterministic alternative
E09 identified (static ceiling +4.0pp joint success vs. agent ceiling +0.67pp).

## 2-3. The six retrieval/filtering cases and their reranked gold ranks

Re-verified directly (local BM25 top-20 + the same cross-encoder, zero model calls), matching
E08's own stored `post_rerank_rank_of_20` values exactly:

| Case | Reranked gold rank | In top-5? | Covered by top-10? | Covered by top-11? |
|---|---|---|---|---|
| `train::160::nda-10` | **11** | no | **no** | yes |
| `train::247::nda-10` | 9 | no | yes | yes |
| `train::353::nda-10` | 9 | no | yes | yes |
| `train::379::nda-10` | 8 | no | yes | yes |
| `train::438::nda-2` | 8 | no | yes | yes |
| `train::518::nda-10` | 9 | no | yes | yes |

**Top-10 covers only 5 of the 6.** No required rank exceeds 11.

## 4. Chosen fixed final K: **11**

The kickoff proposed top-10, conditional on this verification. The verification found it
insufficient, so per the kickoff's own fallback instruction the smallest fixed K covering all six
— **K=11** — is frozen as the only candidate. **No K sweep was performed.** This deviates from the
kickoff's suggested top-10 and is disclosed here rather than glossed over. One fixed policy,
applied identically to all 150 cases — never case-selective, never using gold labels or failure
buckets as runtime selectors.

## 5. Control config (unchanged)

BM25 → clause_256 → top-20 candidate pool → `ms-marco-MiniLM-L-12-v2` rerank → final **top-5** →
`classification_prompt_v1` → `openai/gpt-5-mini` → same parser → same evidence validator. Frozen
result: E08B's `run_E08B_A2_gpt5mini_train_cases.jsonl`.

## 6. Candidate config

Identical in every respect except final context = top-**11** (`static_context_candidate_v1`). Same
BM25 pool, same reranker, same order, same model, same prompt, same schema/parser/validator.

## 7. Candidate artifact

`experiments/E12A_static_context_expansion/TRAIN_ARCH_v1_RETRIEVED_static_context_candidate_v1.json`,
built by `scripts/build_e12a_static_context_candidate.py` from the frozen index and reranker
(nothing re-run or re-trained). **Integrity verified**: for all 150 cases, candidate ranks 1-5 are
identical to the frozen control's top-5 (0 mismatches), and no gold-leakage key is present. The
model-facing artifact contains only case/document/hypothesis identifiers, chunk IDs/text/offsets,
and BM25/reranker scores; evaluator truth stays in the separate `_GOLD.json` file. Chunk counts
range 2-11 per case — **94/150 documents have fewer than 11 clause-chunks**, so for those K=11
already exposes most or all of the document (disclosed as a property of a fixed-K policy on this
dataset, not a bug).

## 8-10. Input-token distributions (actual message-construction path)

Estimated with cl100k_base and **calibrated against E08B's real OpenRouter-reported input
tokens** (measured control-side ratio 0.9904 — near-exact):

| | Mean | Median | p90 | Max |
|---|---|---|---|---|
| CONTROL top-5 (real API tokens, E08B) | 1,148.8 | 1,163.5 | 1,307 | 1,784 |
| CANDIDATE top-11 (calibrated) | 1,884.6 | 2,010.6 | 2,519.7 | 3,273.4 |

**Mean increase: +735.8 tokens (+64.0%).** Retrieved-text-only mean tokens (kept distinct from
total input): control 1,019.2 → candidate 1,762.1; the 118-token system prompt is identical in
both arms.

## 11. Context-window safety

Max candidate input ≈ 3,273 tokens. GPT-5 mini's exact context-window figure is an **unverified
assumption** (no repo source; no provider-metadata call made in Stage A) — commonly cited as 400K
(99.2% headroom), but the conclusion does not depend on it: even against a pessimistic 16,384
window, headroom is 80%.

## 12-15. Cost forecast and budget gate

Real ledger read from file: **$0.4090**. Forecast (OpenRouter GPT-5-mini, $0.25/M in, $2.00/M out;
E08B's real output-token distribution as the starting empirical assumption):

| | Expected | Conservative (E08B p90 output every case) |
|---|---|---|
| 150-case spend | $0.2833 (mean $0.00189/case) | $0.4650 |
| Ledger after run | $0.6923 | $0.8740 |

**Budget gate: PASS** (conservative $0.8740 ≤ allowed $3.75 = $5.00 planning − $1.25 reserve).

## 16. Expected runtime

~21.5 minutes for 150 calls (E08B's own run took 18.5 min; scaled modestly for +64% input growth
— an assumed 25% input-share of latency, not a measurement).

## 17. Frozen metrics

Classification (accuracy, Macro-F1, per-class recall); evidence (Evidence Recall/Precision,
source-valid rate, gold-overlap rate, joint success overall and by class); operational (input/
output tokens, latency, hosted cost). Source-valid and gold-overlapping evidence stay distinct.

## 18. Paired analysis plan

Classification transitions (top-5 wrong→top-11 correct, correct→wrong, both correct, both wrong)
and joint transitions (fail→success, success→fail, both success, both fail) over all 150 —
transitions weigh more than aggregate uplift. Exact McNemar (classification and joint) and a
10,000-resample paired bootstrap (accuracy, Macro-F1, Contradiction Recall, joint success deltas);
effect size over p-value.

## 19. Subgroup analysis plan

(A) the six retrieval-filtering cases — newly exposed? transitions? evidence change; (B) the six
evidence-selection cases — more context can help or hurt; (C) the 26 reasoning-limited cases —
not expected to change, any change reported; (D) Contradiction residuals — fixes, regressions,
unchanged. **Every regression is inspected individually** (previous result, candidate result, the
added rank 6-11 content, and whether it introduced a conflicting/irrelevant clause, exception
language, misleading definition, or evidence-selection drift). More context is not assumed better.

## Adoption decision (predeclared, frozen before any result)

**A.** STATIC EXPANSION EARNS ADOPTION · **B.** LIMITED/NEUTRAL VALUE — KEEP TOP-5 · **C.** STATIC
EXPANSION HURTS — KEEP TOP-5. Weighs net joint recoveries/regressions, Contradiction impact,
evidence quality, input growth, latency, cost, and implementation simplicity.

## 20. Files created / changed

New: `experiments/E12A_static_context_expansion/{README.md, config.yaml, summary.md,
E12A_static_context_expansion.ipynb, results/pre_run_forecast.json,
TRAIN_ARCH_v1_RETRIEVED_static_context_candidate_v1.json}`, `scripts/build_e12a_static_context_
candidate.py`, `scripts/forecast_e12a_context_cost.py`. Modified: `docs/experiment_registry.md`
(E12A row). No frozen file touched; no model call made.

## 21. Unresolved issues

1. K=11 deviates from the kickoff's suggested top-10 (top-10 covers only 5/6) — disclosed,
   evidence-driven, but "top-10" as originally imagined is not what is tested.
2. 94/150 cases have <11 chunks, so for short NDAs K=11 approaches full-context — the effect is
   not uniformly "more distractors" across cases.
3. GPT-5 mini's exact context window is unverified (safety holds against a pessimistic 16K).
4. Output-token behavior under longer context is unknown — assumed equal to E08B's distribution.
5. Runtime scales E08B latency by an assumed input-share factor, not a measurement.

Stage A ends here. No GPT call has been made. Awaiting explicit approval to proceed to Stage B.

---

# STAGE B RESULTS (run once, 150/150, 2026-09-27)

Candidate = *a deterministic fixed context expansion from top-5 to up to top-11, which for many
shorter NDAs exposes most or all available chunks* (94/150 docs have <11 chunks). Control = frozen
E08B A2 (not re-run). Pre-run checks all passed (`results/pre_run_verification.json`); 338/338 tests
before and after. **Disclosed deviation:** request timeout 60s (E08B: 30s) because input is +64%; no
call timed out. Ledger: $0.4090 → **$0.7078** (E12A spend **$0.2987**; forecast $0.2833). Runtime 20.5 min.

| Metric | Top-5 | Top-11 | Delta |
|---|---|---|---|
| Accuracy | 78.67% | 80.67% | +2.00pp |
| Macro-F1 | 0.787 | 0.808 | +0.021 |
| Entailment / Contradiction / NotMentioned recall | 82 / 76 / 78% | 88 / 76 / 78% | +6 / 0 / 0pp |
| Evidence recall / precision | 86.0% / 83.5% | 91.0% / 84.3% | +5.0 / +0.8pp |
| Joint (overall) | 74.0% | 78.0% | +4.0pp |
| Joint E / C / N | 74 / 70 / 78% | 84 / 72 / 78% | +10 / +2 / 0 |
| Strict parse | 150/150 | 150/150 | 0 |
| Mean input / output tokens | 1,148.8 / 708.7 | 1,881.8 / 760.5 | +733 (+63.8%) / +51.8 (+7.3%) |
| Mean latency | 7.41s | 8.20s | +0.79s (+10.7%) |
| Total cost (150) | $0.2557 | $0.2987 | +16.8% |

Input tokens (real API): mean 1,881.8, median 1,985.5, p90 2,522, max 3,299 (forecast mean 1,884.6).
Cost/case mean $0.00199, median $0.00195, p90 $0.00294, max $0.00474. Observed projection:
**$1.99 / 1,000 cases, $15.93 / 8,000** (top-5: $1.70 / $13.64). Latency median 6.68→7.47s, p90 12.5→14.1s, max 16.8→25.3s.

**Classification transitions:** 8 wrong→right, 5 right→wrong, 113 both right, 24 both wrong (net +3).
Recoveries: 178::nda-20, 160::nda-10, 248::nda-10, 353::nda-10, 379::nda-10, 518::nda-10, 279::nda-1, 320::nda-1.
Regressions: 553::nda-20, 273::nda-10, 375::nda-15, 86::nda-1, 297::nda-1.

**Joint transitions:** 13 fail→success, 7 success→fail, 104 both, 26 neither (**net +6**).
Recoveries: 178::nda-20, 318::nda-2, 438::nda-2, 515::nda-2, 160::nda-10, 248::nda-10, 317::nda-13,
352::nda-12, 353::nda-10, 379::nda-10, 518::nda-10, 279::nda-1, 320::nda-1.
Regressions: 88::nda-1, 161::nda-7, 553::nda-20, 226::nda-12, 375::nda-15, 86::nda-1, 297::nda-1.

**Six retrieval/filtering cases:** 4/6 recovered classification (160, 353, 379, 518), 1 already correct
(438, joint recovered), 1 still wrong (247). 5/6 joint recovered. Exposure did not guarantee recovery (247 stayed wrong).
**Six evidence-selection cases:** 5 unchanged-correct, 1 regressed (226, pure noise, see below); joint recovered 4/6
(evidence selection improved in 3, worsened in 1). No visible increase in evidence competition.
**26 reasoning-limited:** 22 remain wrong, **4 unexpectedly recover**, 0 regress. Recovery does not by itself
falsify E09's diagnosis (broader context can supply redundant/clarifying text). The 1 DYNAMIC case stays wrong.

**Contradiction:** recall 76%→76% (0 delta); 1 recovery (178::nda-20), 1 regression (553::nda-20). Joint 70→72%
(4 joint recoveries, 3 joint regressions). No improvement on the headline risk metric.

**Manual inspection of all 8 regression cases (5 classification, 7 joint; 88/161/226 joint-only):**
| Case | What ranks 6–11 added | Cause (trace-supported only) |
|---|---|---|
| 88::nda-1 | 2 boilerplate chunks (entire agreement, signature block) | evidence-selection drift: dropped one quote; label still correct |
| 161::nda-7 | 6 chunks (warranty, term, export, governing law…) | irrelevant text + evidence-selection drift (dropped affiliates quote); label correct |
| 553::nda-20 | 6 chunks (waiver, non-compete recitals…) | label flipped on the *same evidence* as top-5; added text irrelevant → not clearly distractor-caused |
| 226::nda-12 | **0** (identical context) | pure noise: quote differs only by newline/space |
| 273::nda-10 | 6 chunks incl. a "publicly known" exclusion, third-party-rights clauses | broad exception language/redundant clauses; NotMentioned with empty evidence |
| 375::nda-15 | 1 chunk (agreement title header) | added a second quote and flipped to Contradiction; header irrelevant → evidence-selection drift |
| 86::nda-1 | 6 chunks (notice, table of contents, program blurb) | definition distraction: broad definition + "in case of doubt deemed confidential" |
| 297::nda-1 | 6 chunks incl. duplicate definition (rank 9 repeats rank 1) and disclosure clause | definition distraction + redundant evidence |
Only 273, 86, 297 (arguably 375) plausibly involve ranks 6-11 content; 226 (and largely 88, 553) had none or irrelevant
added content. No causal claims beyond this.

**Short-document saturation** (n; chunks shown; acc top5→top11; joint top5→top11):
- A ≤5 chunks (17; 3.4 shown, *identical context in both arms*): 70.6→76.5%; joint 70.6→70.6 (1 recovery, 1 regression). **A direct noise floor: with unchanged input the model still flips ~2/17 cases.**
- B 6–10 chunks (77; 7.8 shown vs 5): 79.2→83.1%; joint 77.9→81.8% (net +3).
- C ≥11 chunks (56; 11 shown): 80.4→78.6% (−1 case); joint 69.6→75.0% (net +3).
Gains are not confined to short documents that are simply fully exposed, but group sizes are too small to separate depth effects from noise.

**Statistics:** exact McNemar classification b=5, c=8, n=13, **p=0.581**; joint b=7, c=13, n=20, **p=0.263**.
Paired bootstrap (10,000): accuracy +2.0pp [−2.7, +6.7]; Macro-F1 +0.021 [−0.026, +0.070]; Contradiction recall
0.0pp [−5.9, +5.8]; joint +4.0pp [−2.0, +10.0]. All CIs include zero.

## Adoption decision: **B — STATIC EXPANSION SHOWS LIMITED/NEUTRAL VALUE — KEEP TOP-5**
For: net +3 classification, net +6 joint, evidence recall +5pp, targeted six mostly recovered (5/6 joint).
Against: nothing distinguishable from zero (p=0.58/0.26, CIs span 0); Contradiction unchanged; one regression had zero
context change and the group-A noise floor (2/17 flips on identical input) is the same order as the net effect; 3-4
regressions plausibly definition/exception distraction; +64% input, +16.8% cost, +10.7% latency. Not C: aggregate is not worse.
Directionally consistent with E09's static ceiling (+4.0pp joint); carried forward as **static_context_candidate_v1**,
pending GPT-specific prompt optimisation and GPT full-context vs RAG comparison. **Not retrieval_v2**; `retrieval_v1` unmodified.
Caveat: single run per arm, n=150; a repeat top-5 run would size the noise floor directly (not authorized here).

New Stage B files: `scripts/run_e12a_static_context.py`, `scripts/analyze_e12a_static_context.py`,
`results/{run_E12A_top11_gpt5mini_train_cases.jsonl, run_E12A_top11_gpt5mini_train.json, e12a_analysis.json,
pre_run_verification.json, run_E12A_wall_seconds.json, run.log}`, executed notebook.

---

# FINAL REVIEW ADDENDUM (approved decision: B — KEEP TOP-5)

**Headline risk metric:** Contradiction Recall 76% → 76%. Static expansion did NOT improve it; this is a major
reason top-5 is not replaced.

**Model variability / noise floor.** Observed outcome variability on cases with effectively identical context
indicates a non-zero hosted-model repeatability/noise floor. Consequently, the apparent top-11 uplift should not
be interpreted as purely causal. Evidence: `train::226::nda-12` regressed on joint despite zero additional chunks,
and the ≤5-chunk group (identical context in both arms) had 2/17 cases change outcome. These cases were not
removed from any analysis. No repeat control was run in E12A; repeatability is recorded as a design consideration
for later experiments.

**Short documents.** K=11 is a fixed expansion from top-5 to up to top-11, often approaching full available
context for shorter NDAs (94/150 documents have <11 chunks) — not a minor top-K increase. This matters for the
later GPT full-context comparison.

**Interpretation limits.** Exposing missing evidence does not guarantee recovery (case 247 stayed wrong with gold
exposed); additional context does not universally improve evidence selection (improved 3, worsened 1 of 6); the 4
reasoning-limited recoveries may reflect redundant/clarifying context and do not by themselves invalidate the E09 diagnosis.

**Timeout deviation (operational, not an experimental variable).** E12A used a 60-second request timeout rather
than E08B's 30-second timeout because of the substantially larger inputs. No request approached the original 30s
timeout and no timeout/error occurred. Not hidden; E12A was not rerun because of it.

**Status:** `retrieval_v1` unchanged; `static_context_candidate_v1` is an experimental candidate only, not retrieval_v2.
