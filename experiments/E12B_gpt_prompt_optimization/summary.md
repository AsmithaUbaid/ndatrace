# E12B — GPT-Specific Prompt Optimisation — STAGE A (design, artifacts, forecast only)

**No GPT/Qwen/Gemini call has been made.** `retrieval_v1`, `classification_prompt_v1`, DEV and TEST are untouched.

## 1. Research question
"Can a compact GPT-specific classification prompt materially improve evidence-grounded NDA classification over the
current Qwen-selected P0 without changing model, retrieval, context size, output schema, or evaluator?"

## 2. Why
E03 picked P0 on Qwen2.5-7B (richer prompts pushed Contradictions toward NotMentioned). GPT-5-mini is much stronger
(E08B). P0 is a valid GPT baseline but was never optimised for GPT.

## 3-6. TRAIN pool inspection and fresh manifest (`TRAIN_GPT_PROMPT_v1`) — corrected protocol (v2 of Stage A)
Protocol correction 1: the first Stage A draft (seed 1100) was disjoint from PROMPT and ARCH only, and 26/76 of its documents
overlapped TRAIN_ORACLE_v1. It was superseded before any model call; the manifest is rebuilt disjoint from **all three** prior manifests.
| | |
|---|---|
| TRAIN documents / cases | 423 / 7,191 |
| Docs: TRAIN_PROMPT_v1 / TRAIN_ARCH_v1 / TRAIN_ORACLE_v1 | 73 / 78 / 145 |
| Pairwise doc overlap: PROMPT∩ARCH / PROMPT∩ORACLE / ARCH∩ORACLE | 19 / 29 / 29 |
| **Union of the three prior manifests** | **227 docs** |
| **Untouched TRAIN docs remaining** | **196** |
| Untouched label pool (cases) | Entailment 1,611 · NotMentioned 1,339 · Contradiction 382 |
| Balanced 150 (50/50/50) feasible? | **Yes** — 382 Contradiction cases exist; no relaxation needed |

Final manifest: **150 cases, 50/50/50, 74 unique documents, seed 1200** (unused; prior 42, 99, 123, 300, 500, 700, 900 bootstrap, and the
discarded 1100 draft). Algorithm = TRAIN_PROMPT_v1/TRAIN_ARCH_v1's (sort doc ids, shuffle with `random.Random(1200)`, ≤2 cases/doc/class) with the
pool restricted to untouched documents by construction. **Independently re-verified**: 0 document overlap and 0 case overlap with PROMPT, ARCH and
ORACLE. Selection reads no model output, difficulty, evidence property or exception language; no hard-case enrichment.

## 7-8. Prompts (full text in `prompts/final/`; each file is the complete effective system prompt)
| Prompt | Chars | Tokens (cl100k) | Added instructions vs P0 | Change |
|---|---|---|---|---|
| GPT-P0 | 464 | 118 | 0 | control — **byte-identical** to E08B's effective system prompt (sha1 config hash `dec7527f24c9` reproduced) |
| GPT-P1 | 698 | 154 | 3 | bare label list → three one-line definitions (Contradiction includes explicit exception/carve-out) |
| GPT-P2 | 1,121 | 242 | 9 | P1 definitions + 6-step decision order (relevance → exception check → E → C → NM → evidence only from excerpts) |
| GPT-P3 | 1,158 | 248 | 7 | P1 definitions + 4 guidance rules: Contradiction only on affirmative conflict (silence/related-topic = NotMentioned); apply limiting exceptions/qualifications rather than trusting an isolated clause; evidence must directly support the label; do not assume absent provisions |

**Prompt file contents are unchanged by the correction** (sha1 of all four files identical before/after; `results/prompt_hashes_stageA_v1.txt`). Every prompt keeps the same opening sentence, the same "Respond with ONLY a JSON object…" block, and the same trailing
evidence instruction as P0. No few-shot, no chain-of-thought, no case IDs/gold/examples. P3 was written from established
failure themes (E08/E09: carve-out reconciliation, definitional over-generalisation, evidence directness) **before** any E12B
output. Known design risk (predeclared): P3's "only on affirmative conflict" wording could push Contradictions to
NotMentioned, as richer prompts did for Qwen in E03 — the Contradiction guard below exists for exactly this.
Prompt length is a tracked variable (+36 to +130 prompt tokens; +3% to +11% mean input).

## 13-14. Frozen context artifact
`TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1.json` (+ separate `_GOLD.json`, scorer-only), built by
`scripts/generate_e12b_retrieved_context.py` — the unchanged E07 generator retargeted at the new manifest; retrieval config
asserted equal to E07's. One artifact shared by every arm; no per-prompt retrieval. Verified: 150/150 cases, same IDs/order
as the manifest, ≤5 chunks (top-5), non-increasing rerank order, zero gold-leakage keys.
**Regenerated** for the rebuilt manifest (same unchanged E07 generator; retrieval config asserted equal to E07's). Retrieved-text tokens (cl100k): mean 1,011 / median 1,039 / p90 1,164 / max 1,374.
Calibrated total input tokens (real/est ratio 0.9904 from E08B): P0 mean 1,141 (p90 1,292, max 1,499) · P1 1,176 · P2 1,264 · P3 1,270 (p90 1,420, max 1,627).

## 15. Metrics (frozen)
**Primary:** joint label+evidence success · Contradiction Recall · Macro-F1. **Secondary:** accuracy, Entailment/NotMentioned
recall, evidence recall/precision, source-valid rate, strict parse rate, tokens, latency, cost. Per-prompt confusion matrices
and the exact Contradiction confusion pattern are reported. Winner is never chosen on accuracy alone; joint is primary
because the product promise is a correct decision **plus** traceable evidence.

## 16-17. Selection rule and near-tie policy (FROZEN; simplified by protocol correction 2, no weighted score)
E12A found hosted-model outcomes flip on identical context, so a 1-case edge is not evidence.
- **Primary objective:** joint label+evidence success. **Headline safety guard:** Contradiction Recall. **Secondary:** Macro-F1, evidence quality, simplicity.
- **Contradiction guard:** a candidate is disqualified if its Contradiction Recall is ≥3 cases of 50 (≥6pp) below P0's.
- **Adoption** (all three required): (1) passes the Contradiction guard; (2) **net joint gain ≥ +9 cases over P0** on the 150-case manifest — the predeclared
  substantive-effect threshold; (3) Macro-F1 not materially worse than P0. McNemar is **not** an adoption gate (removed); it and the bootstrap are supporting evidence.
- **Near-tie:** best non-P0 candidate passes the guard with **+1 to +8** net joint cases → inconclusive. No further tuning on this manifest. Then either keep the simpler P0, or —
  if the gain is practically interesting enough to justify more spend — ONE fresh TRAIN-only confirmation manifest. Which of the two is decided only after Stage B results.
- **No benefit/harm:** 0 or negative net joint gain → no adoption from E12B; if all alternatives do this, keep P0.
- **Simplicity tie-break:** effectively tied candidates → prefer the shorter/simpler prompt.
Outcomes: **A** earns adoption · **B** effectively tied, keep P0 · **C** hurts, keep P0. Even under A the winner is only `classification_prompt_gpt_v1`, not a final architecture.
**P0 is re-run on the new manifest** (E08B numbers are on a different manifest).

## 18. Paired statistical plan
Each candidate vs P0 on identical cases/contexts: classification and joint transition counts; exact McNemar (classification,
joint); 10,000-resample paired bootstrap (seed 900) of Accuracy, Macro-F1, Contradiction Recall and joint deltas. Effect sizes and
transitions come first, statistics second; p-values are not a selection requirement. Stage B also reports prompt sensitivity (all-correct, all-wrong, prompt-sensitive cases;
Contradiction↔NotMentioned transitions) and, for sensitive cases, correct-label good/bad evidence and wrong-label
source-valid/gold-overlapping evidence — evidence quality is never collapsed into label accuracy.

## 19-22. Ledger, cost, budget gate, runtime — RECOMPUTED for the rebuilt manifest (real ledger read from file)
Ledger now **$0.7078** (unchanged; append-only). Output-token assumption: mean 734.6 / p90 1,245 (E08B + E12A real distributions).
| | Expected | Conservative (p90 in & out, every case) |
|---|---|---|
| GPT-P0 (150 calls) | $0.2632 | $0.4163 |
| GPT-P1 | $0.2645 | $0.4176 |
| GPT-P2 | $0.2678 | $0.4209 |
| GPT-P3 | $0.2680 | $0.4211 |
| **Total (600 calls)** | **$1.0634** | **$1.6759** |
| Projected ledger | $1.7712 | $2.3837 |

**Budget gate: PASS** — $0.7078 + $1.6759 + $1.25 reserve = $3.63 ≤ $5.00 (projected $2.38 ≤ allowed $3.75).
Runtime (sequential, assumed mean 7.8s/call from E08B/E12A): ≈19.5 min per prompt (150 calls), ≈78 min for 600 calls.
Risk: longer prompts may change GPT-5-mini's hidden reasoning-token output (assumed unchanged).

## 23-24. Timeout, schema quirk, architecture note
- **Timeout:** ONE uniform **60 s** for all four arms; an operational setting, not a variable (E12A used 60; its slowest call was 25.3s).
- **Schema quirk (preserved):** P0's schema block asks for a label-only JSON object while a trailing sentence also asks for an `evidence` list. Kept verbatim in
  all four arms because P0 is the frozen E08B control; cleaning it now would confound prompt-semantic changes with output-contract cleanup. **Documented limitation**;
  a schema cleanup may be a separate later controlled experiment.
- No prompt winner is a final architecture.

## 25. Files created/changed
New: `experiments/E12B_gpt_prompt_optimization/{README.md, config.yaml, summary.md, E12B_gpt_prompt_optimization.ipynb (skeleton),
TRAIN_GPT_PROMPT_v1.json, TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1.json, …_GOLD.json, results/{manifest_inspection.json, pre_run_forecast.json}}`,
`prompts/final/gpt_p{0,1,2,3}.txt`, `scripts/{build_e12b_manifest.py, generate_e12b_retrieved_context.py, forecast_e12b_prompts.py}`.
Modified: `docs/experiment_registry.md` (E12B row). No frozen file touched.

## 26. Unresolved issues
1. The inherited P0 schema quirk (above) is preserved and is a known limitation of all four arms.
2. n=150 has low power: the +9-case threshold means only large effects earn adoption; small real gains land in the near-tie band by design.
3. P0 is re-run, so its result differs from E08B's 78.7% (different manifest); the cross-manifest gap is not a finding.
4. Output-token/latency effects of longer prompts on a reasoning model are unmeasured until Stage B.
5. Three prompts vs one control on one manifest carries a mild multiple-comparison risk; mitigated by the predeclared thresholds and near-tie rule.
6. The near-tie choice between "keep P0" and "one confirmation manifest" is deliberately deferred until after Stage B results.

Stage A ends here. Awaiting explicit approval for Stage B.

---

# STAGE B RESULTS (2026-09-26/27)

**Outcome: B — PROMPTS ARE EFFECTIVELY TIED (NEAR-TIE) — KEEP P0.** Best candidate GPT-P3 has **+8 net joint cases** — one short of the frozen +9 adoption threshold —
and passes the Contradiction guard. Applied mechanically; no threshold was adjusted. No confirmation manifest has been run.

## Execution, outage and concurrency disclosure
- **P0** ran sequentially, 150/150, $0.2534, 19.0 min. **Outage:** during P1 (first attempt) OpenRouter connections failed: 5 attempts, all `APIConnectionError` after 4
  retries, $0, first failure 2026-09-26T17:13:26Z; the sequential circuit breaker stopped the run. Preserved unmodified as
  `results/P1_INTERRUPTED_PROVIDER_OUTAGE_20260926T171526Z.jsonl` (+ `.meta.json`), **excluded from all quality metrics**.
- **Connectivity re-check** (17:22Z, no experiment file touched): OpenRouter `/models` HTTP 200 (0.15s); authenticated `/key` HTTP 200 (0.69s).
- **P1 (resume), P2, P3** ran afterwards with **bounded concurrency = 5 within each arm, arms sequential** — an operational change only (model, prompts, manifest, retrieval,
  context, schema, parser, evaluator, temperature, 60s timeout and selection rule unchanged). Total wall-clock (P1 3.8, P2 4.0, P3 3.6 min vs P0 19.0 min sequential) is **not** a
  fair latency comparison; per-call latency is. 0 rate-limit (429) events, 0 new connection failures, 0 failed calls, 5-consecutive-failure breaker never tripped.
- **Successful benchmark calls:** P0 150 · P1 150 · P2 150 · P3 150 = 600. Per-arm integrity verified before continuing (150 records, no duplicates, all case IDs, hash, run_id).
- **Spend:** P0 $0.2534 · P1 $0.2636 · P2 $0.2880 · P3 $0.2509 = **$1.0559 total E12B** (remaining after resume $0.8025). Ledger $0.7078 → **$1.7637**
  (append-only; run_ids e12b_gpt_p0, e12b_gpt_p1_resume, e12b_gpt_p2, e12b_gpt_p3). Forecast was $1.06 expected.

## Four-prompt matched table (150 cases each, P0 re-run on this manifest)
| Metric | P0 | P1 | P2 | P3 |
|---|---|---|---|---|
| Prompt tokens | 118 | 154 | 242 | 248 |
| Accuracy | 81.3% | 78.7% | 76.0% | **84.0%** |
| Macro-F1 | 0.814 | 0.787 | 0.761 | **0.840** |
| Entailment / Contradiction / NM recall | 82 / 82 / 80% | 78 / 84 / 74% | 76 / 80 / 72% | 90 / 82 / 80% |
| **Joint success** | 114 (76.0%) | 112 (74.7%) | 106 (70.7%) | **122 (81.3%)** |
| Joint E / C / NM | 68 / 80 / 80% | 68 / 82 / 74% | 62 / 78 / 72% | 82 / 82 / 80% |
| Evidence recall / precision | 85.0 / 82.5% | 85.0 / 80.2% | 85.0 / 78.7% | **92.0 / 88.5%** |
| Source-valid evidence | 97.1% | 97.2% | 96.3% | 99.0% |
| Strict parse | 150/150 | 150/150 | 150/150 | 150/150 |
| Mean input / output tokens | 1,141 / 702 | 1,177 / 731 | 1,264 / 802 | 1,271 / 677 |
| Mean latency (per call) | 7.58s | 7.47s | 7.81s | 7.09s |
| Total cost | $0.2534 | $0.2636 (+4.0%) | $0.2880 (+13.7%) | $0.2509 (−1.0%) |

## Contradiction (headline guard) — E03's concern did not reproduce
| | Correct/50 | Recall | →Entailment | →NotMentioned |
|---|---|---|---|---|
| P0 | 41 | 82% | 8 | 1 |
| P1 | 42 | 84% | 6 | 2 |
| P2 | 40 | 80% | 8 | 2 |
| P3 | 41 | 82% | 7 | 2 |
No prompt pushed Contradiction toward NotMentioned (≤2 cases everywhere); GPT's Contradiction errors are overwhelmingly →Entailment, unchanged by wording. All candidates pass
the guard (deltas +1, −1, 0 cases vs a −3 disqualification line). **Contradiction Recall did not improve under any prompt.** 8 Contradiction cases were prompt-sensitive.

## Paired vs P0 (transitions first; statistics are supporting evidence only)
| | Cls wrong→right / right→wrong | Joint fail→success / success→fail | Net joint | McNemar cls / joint p | Bootstrap Δ joint [95% CI] | Δ Accuracy | Δ Macro-F1 | Δ Contra recall |
|---|---|---|---|---|---|---|---|---|
| P1 | 10 / 14 | 12 / 14 | **−2** | 0.54 / 0.85 | −1.3pp [−8.0, +5.3] | −2.7pp [−9.3, +4.0] | −0.027 [−0.092, +0.038] | +2.0pp [−8.3, +12.5] |
| P2 | 5 / 13 | 7 / 15 | **−8** | 0.096 / 0.134 | −5.3pp [−11.3, +0.7] | −5.3pp [−10.7, 0.0] | −0.053 [−0.109, +0.001] | −2.0pp [−9.3, +4.4] |
| P3 | 11 / 7 | 15 / 7 | **+8** | 0.48 / 0.134 | +5.3pp [−0.7, +11.3] | +2.7pp [−2.7, +8.0] | +0.027 [−0.028, +0.084] | 0.0pp [−8.0, +8.0] |
All bootstrap CIs include zero. Discordant case IDs are in `results/e12b_analysis.json` and the notebook (sections 14-15).

## Selection-rule application (frozen; 'materially worse' Macro-F1 fixed as a drop >0.03 before results)
| | Contradiction guard | Net joint vs +9 | Macro-F1 | Status |
|---|---|---|---|---|
| P1 | pass (+1) | −2 | −0.027 (ok) | NO BENEFIT |
| P2 | pass (−1) | −8 | −0.053 (worse) | HARMFUL (worse on joint, F1 and evidence precision) |
| P3 | pass (0) | **+8 (one short)** | +0.027 (ok) | **NEAR-TIE** |
Not A (needs ≥+9). Under the frozen rule the result is inconclusive; no further tuning on this manifest; the simpler P0 stays the default.

## Prompt sensitivity and evidence
All-correct 102/150 · all-wrong 14 · **prompt-sensitive 34** (C↔E 18, C↔NM 13, E↔NM 9 pairwise transitions; note C↔E dominates). Evidence drift (different cited spans across prompts) in 33 of the 34.
Among prompt-sensitive cases: correct label + gold-valid evidence P0 19 / P1 16 / P2 11 / **P3 23**; wrong label + gold-overlapping evidence 5 / 6 / 10 / 4; wrong label + source-valid evidence 7 / 10 / 10 / 4;
correct label but bad evidence 1 / 0 / 1 / 1; evidence omitted 0 everywhere. P3's edge came with **better** evidence (recall +7pp, precision +5.9pp, source-valid 99.0%), not at its expense; P2's longer decision-order prompt degraded precision (−3.8pp).

## Cost, tokens, latency
Prompt length did not scale cost or latency simply: P2 (+124 prompt tokens) raised mean output tokens +14% (hidden reasoning) and cost +13.7%; P3 (+130 prompt tokens) *lowered* output tokens 3.5% and cost 1.0%, with the lowest latency (−6.4%). Latency means differ by <7% and p90s overlap; per-call latency differences are within plausible noise. 

## Interpretation and recommendation
P3 is the only candidate with a consistent multi-metric edge (joint +8 cases, accuracy +2.7pp, Macro-F1 +0.027, evidence recall/precision up, cost/latency neutral-to-better), but the effect is one case below the predeclared bar, every CI includes zero, and E12A measured a non-zero repeatability noise floor; Contradiction Recall — the headline risk metric — did not move. P1 and P2 do not merit further consideration (P2 is clearly worse). **Whether to run ONE fresh TRAIN-only confirmation (P0 vs P3 only, ≈$0.5) or simply keep P0 is left for your decision, as agreed;** my read is that P3 is worth one confirmation because its gain is broad across metrics and cost-free, but it should not be adopted on this evidence. A fresh disjoint pool remains feasible (122 untouched docs after this manifest). Even if confirmed it would be `classification_prompt_gpt_v1`, not a final architecture.

## Limitations
n=150, single run per arm (no repeat control); P0 re-run here scores 81.3% vs E08B's 78.7% on a different manifest (not a finding); schema quirk preserved in all arms; concurrency differs between P0 (sequential) and P1-P3, which affects wall-clock but not per-call latency or quality; 'materially worse Macro-F1' threshold (0.03) was operationalised by me before any result and was not previously specified numerically.

New Stage B files: `scripts/{run_e12b_gpt_prompts.py, run_e12b_resume.py, analyze_e12b_gpt_prompts.py}`; `results/{run_E12B_gpt_p0_cases.jsonl, run_E12B_gpt_p1_resume_cases.jsonl, run_E12B_gpt_p2_cases.jsonl, run_E12B_gpt_p3_cases.jsonl,
P1_INTERRUPTED_PROVIDER_OUTAGE_*.jsonl/.meta.json, run_E12B_gpt_p{0..3}.json, e12b_analysis.json, pre_run_verification*.json, run_resume.log, run_first_attempt_sequential.log}`; executed notebook.

---

# FINAL REVIEW ADDENDUM (approved)
E12B's near-tie (P3 +8 joint, 122 vs 114 of 150; below the +9 bar) was resolved by the fresh confirmation experiment E12C, where P3 scored −3 (125 vs 128) and failed the positive-gain and evidence-precision guards. **Final decision: keep GPT-P0
(`classification_prompt_v1`); GPT prompt optimisation is closed.** Operational history (kept, not hidden): P0 completed before a provider outage; the first P1 attempt had 5 `APIConnectionError` records ($0), preserved in
`results/P1_INTERRUPTED_PROVIDER_OUTAGE_20260926T171526Z.jsonl` and excluded from all quality metrics; connectivity was verified; P1/P2/P3 were resumed at bounded concurrency = 5 with no 429s or further failures;
all 600 benchmark calls completed successfully.
