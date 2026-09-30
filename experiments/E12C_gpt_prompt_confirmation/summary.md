# E12C — GPT-P0 vs GPT-P3 Confirmation — STAGE A (design, artifacts, forecast only)

**No GPT/Qwen/Gemini call has been made.** Prompt files, `retrieval_v1`, DEV and TEST are untouched.

## 1. Research question and nature
"Does GPT-P3 reproduce its directional advantage over P0 on a fresh, document-disjoint TRAIN confirmation manifest?"
E12B ended as a near-tie (P3 122 vs P0 114 joint of 150 = +8, one below the +9 bar; every CI included zero; Contradiction Recall unchanged).
E12C is **confirmation, not optimisation**: only GPT-P0 and GPT-P3, byte-identical to E12B; no P1/P2/P4; no tuning; **no third confirmation manifest afterwards**.

## 2-7. TRAIN pool and manifest `TRAIN_GPT_PROMPT_CONFIRM_v1`
| | |
|---|---|
| TRAIN documents / cases | 423 / 7,191 |
| Docs: PROMPT_v1 / ARCH_v1 / ORACLE_v1 / GPT_PROMPT_v1 | 73 / 78 / 145 / 74 |
| **Union of all previously used docs** | **301** (GPT_PROMPT_v1 overlaps none of the earlier three) |
| **Untouched TRAIN docs remaining** | **122** |
| Untouched label pool (cases) | Entailment 978 · NotMentioned 860 · Contradiction 236 |
| Balanced 150 (50/50/50) feasible? | **Yes**, no relaxation needed |

Final manifest: **150 cases, 50/50/50, 67 unique documents, seed 1300** (unused: prior 42, 99, 123, 300, 500, 700, 1200; bootstrap 900; discarded draft 1100). Same deterministic,
performance-agnostic algorithm as every prior manifest (sort untouched doc ids, shuffle with `random.Random(1300)`, ≤2 cases/doc/class); no hard-case enrichment; no model output read.
Disjointness from all four prior manifests is asserted in `scripts/build_e12c_manifest.py` (documents and cases) and re-checked by the forecast script (0 case overlap with the E12B manifest).

## 8-9. Frozen prompts (untouched)
| | sha1 |
|---|---|
| GPT-P0 | `3fcc7c95cf1287c292e403f12b307c9d912278ce` |
| GPT-P3 | `d2bca31164c2db9ea9995fb769977e3e2c0a6496` |
Verified: the `prompt_hash` recorded in every E12B P0 and P3 result row equals these, so E12C runs the exact prompts E12B ran.

## 10-12. Frozen context artifact and input tokens
`TRAIN_GPT_PROMPT_CONFIRM_v1_RETRIEVED_retrieval_v1.json` (+ separate `_GOLD.json`), built by the unchanged retrieval_v1 generator (`scripts/generate_e12c_retrieved_context.py`).
Verified: 150/150 cases, same IDs/order as the manifest, top-5 only, non-increasing rerank order, no gold-leakage keys, retrieval config equal to E12B's. One artifact shared by both arms.
Calibrated input tokens (cl100k × real/est ratio measured on E12B: P0 0.9907, P3 0.9916):
| | mean | median | p90 | max |
|---|---|---|---|---|
| P0 | 1,110.7 | 1,135.3 | 1,296.8 | 1,538.5 |
| P3 | 1,240.7 | 1,265.3 | 1,427.0 | 1,668.9 |

## 13-15. Confirmation rule and bands (FROZEN before any call)
E12C asks whether the **direction replicates**; it does **not** require another +9 gain.
**Confirm P3 only if ALL hold:** (1) Contradiction guard passes (P3 not ≥3/50, i.e. ≥6pp, below P0); (2) net joint gain over P0 is **positive**; (3) Macro-F1 not materially worse
(drop >0.03); (4) evidence recall **and** precision not materially worse (drop >3pp); (5) P3 joint > P0 joint (direction consistent with E12B). The 0.03 and 3pp tolerances are the same
operational values used for E12B and are fixed here, before results.
Interpretation bands (never a reason to create prompts): **STRONG** = all hold and net joint ≥ +5 · **WEAK** = all hold and net joint +1 to +4 · **NO CONFIRMATION** = net joint ≤ 0, or the
Contradiction guard fails, or material Macro-F1/evidence degradation.

## 16. Final decision after E12C (predeclared)
- **A — P3 CONFIRMED:** strong confirmation, **or** weak confirmation whose **pooled E12B+E12C** stratified paired-bootstrap 95% CI for the joint delta excludes zero (and pooled Contradiction is not ≥6pp below P0)
  → freeze `classification_prompt_gpt_v1` = P3 (separate from `classification_prompt_v1`; not a final architecture).
- **B — NOT CONFIRMED:** no benefit, reversed direction, or a guard fails → keep P0.
- **C — WEAKLY CONFIRMED, PREFER P0:** weak confirmation and pooled CI includes zero → prefer the simpler P0.
"Combined evidence is clear" is thus operationalised as the pooled CI excluding zero — my definition, fixed now, since the brief did not give a number. **No third confirmation manifest.**

## Combined analysis plan
E12C is reported standalone first, then E12B / E12C / combined side-by-side with manifest identity always visible (P0 joint, P3 joint, delta; pooled totals plus accuracy, Macro-F1, Contradiction Recall, evidence recall/precision).
Pooled inference = stratified paired bootstrap (cases resampled within each manifest, 10,000 draws, seed 900). A between-manifest reversal is reported explicitly and never averaged away.
E12C statistics: exact McNemar (classification, joint) and 10,000 paired bootstrap (Accuracy, Macro-F1, Contradiction Recall, joint), effect sizes and transitions first.
Noise: hosted GPT shows non-zero run-to-run variability (E12A/E12B); E12C tests replication on new documents; surprising cases are not re-run.

## Execution plan (Stage B, after approval)
Arms sequential **P0 then P3**, MAX_CONCURRENCY = 5 within each arm (per-call latency comparable; total arm wall-clock not), 60s timeout both arms, 5-consecutive-failure circuit breaker, ledger run_ids `e12c_gpt_p0`, `e12c_gpt_p3`,
no quality analysis between arms, no rerun of individual cases, create-only output files.

## 17-20. Ledger, cost, budget gate, runtime (ledger read from file)
Ledger now **$1.7637**. Forecast from real E12B distributions (output mean/p90: P0 702/1,188, P3 677/1,135; E12B real 150-case cost: P0 $0.2534, P3 $0.2509).
| | Expected | Conservative (p90 in & out, every case) |
|---|---|---|
| P0 (150 calls) | $0.2523 | $0.3981 |
| P3 (150 calls) | $0.2498 | $0.3870 |
| **Total (300 calls)** | **$0.5020** | **$0.7851** |
| Projected ledger | $2.2657 | $2.5488 |
**Budget gate: PASS** — $1.7637 + $0.7851 + $1.25 reserve = $3.80 ≤ $5.00 (projected $2.55 ≤ allowed $3.75).
Runtime: ~7.3s mean per call; 300 calls ≈ 8 min at concurrency 5 (E12B arms took 3.6-4.0 min each), ≈ 37 min if sequential.

## 21. Files
New: `experiments/E12C_gpt_prompt_confirmation/{README.md, config.yaml, summary.md, E12C_gpt_prompt_confirmation.ipynb (skeleton), TRAIN_GPT_PROMPT_CONFIRM_v1.json, …_RETRIEVED_retrieval_v1.json, …_GOLD.json, results/{manifest_inspection.json, pre_run_forecast.json}}`,
`scripts/{build_e12c_manifest.py, generate_e12c_retrieved_context.py, forecast_e12c_prompts.py}`. Modified: `docs/experiment_registry.md` (E12C row). No prompt file, frozen config, or E12A/E12B artifact touched.

## 23. Unresolved issues
1. After E12C, 122 − 67 = 55 untouched TRAIN documents remain, so TRAIN-only prompt work is nearly exhausted (moot: no third confirmation is planned).
2. n=150 with a "positive net joint" bar is a low bar by design; weak confirmations (+1..+4) are within plausible noise and are handled by the pooled-CI rule, not treated as proof.
3. The "materially worse" tolerances (0.03 Macro-F1, 3pp evidence) and the pooled-CI definition of "clear" were operationalised by me and frozen before results.
4. Single run per arm; no repeat control; inherited schema quirk preserved in both arms.
5. Pooled analysis pools two different manifests (different documents); stratification preserves identity but does not remove manifest heterogeneity.
6. Stage B must reuse the create-only, circuit-breaker runner pattern (E12B resume script) — a new run script will be written from it after approval; not yet created.

Stage A ends here. Awaiting explicit approval for Stage B.

---

# STAGE B RESULTS (2026-09-27)

**FINAL OUTCOME: B — P3 NOT CONFIRMED — KEEP P0.** Band: **NO CONFIRMATION**. **The direction reversed:** P3 gained +8 joint cases on the E12B manifest but scored **−3** on this fresh
manifest. GPT prompt optimisation is closed; `classification_prompt_gpt_v1` was **not** created; `classification_prompt_v1` (P0) stays. No third round.

## Execution
Manifest, prompts (full sha1 verified pre-run), retrieval artifact and settings exactly as frozen; P0 then P3, concurrency 5 within each arm, 60s timeout, no interim quality analysis.
150/150 successful calls per arm, no errors/retries/429s/connection failures, circuit breaker never tripped; per-arm operational integrity verified (150 rows, no duplicates, hash, run_id).
Concurrency note: total arm wall-clock (P0 3.4 min, P3 3.1 min) is not a latency comparison; per-call latency is.
Ledger: $1.7637 (verified; 600 E12B rows present, no prior E12C rows) → **$2.2317**. E12C spend **$0.4681** (P0 $0.2358, P3 $0.2322) vs forecast $0.5020 expected / $0.7851 conservative.
Note: the ledger file was already modified vs git only because E12B's 600 rows are still uncommitted; E12C adds 300 more, all append-only.

## Standalone metrics (fresh manifest, 150 cases each)
| Metric | P0 | P3 | Δ |
|---|---|---|---|
| Accuracy | 89.3% | 86.7% | −2.7pp |
| Macro-F1 | 0.893 | 0.867 | −0.026 |
| Entailment / Contradiction / NotMentioned recall | 92 / 82 / 94% | 86 / 84 / 90% | −6 / +2 / −4pp |
| **Joint success** | **128 (85.3%)** | **125 (83.3%)** | **−3 cases** |
| Joint E / C / NM | 86 / 76 / 94% | 80 / 80 / 90% | |
| Evidence recall / precision | 92.0 / 92.9% | 90.0 / 89.1% | −2.0 / **−3.8pp** |
| Source-valid evidence | 95.0% | 95.1% | |
| Strict parse | 150/150 | 150/150 | |
| Mean input / output tokens | 1,111 / 647 | 1,241 / 619 | +130 / −28 |
| Mean / median / p90 latency (per call) | 6.54 / 6.28 / 10.56s | 6.19 / 5.85 / 9.43s | −5.3% mean |
| Total cost | $0.2358 | $0.2322 | −1.5% |
Confusion matrices (rows gold E,C,NM): P0 [[46,2,2],[7,41,2],[3,0,47]]; P3 [[43,4,3],[7,42,1],[3,2,45]].

## Frozen guards (all must hold for confirmation)
| Guard | Result | Pass |
|---|---|---|
| 1. Contradiction not ≥3/50 below P0 | +1 case (41→42) | ✅ |
| 2. Net joint positive | **−3** | ❌ |
| 3. Macro-F1 drop ≤ 0.03 | −0.026 | ✅ |
| 4. Evidence recall drop ≤ 3pp | −2.0pp | ✅ |
| 5. Evidence precision drop ≤ 3pp | **−3.8pp** | ❌ |
Two guards fail → **NO CONFIRMATION** (net joint ≤ 0 alone would suffice).

## Paired transitions (P0 → P3)
Classification: 1 wrong→right, **5 right→wrong**, 129 both right, 15 both wrong. Joint: 2 fail→success, **5 success→fail**, 123 both, 20 neither.
Classification recovered: train::269::nda-20. Classification regressed: 215::nda-3, 481::nda-10, 620::nda-10, 112::nda-1, 583::nda-1.
Joint recovered: 148::nda-1, 269::nda-20. Joint regressed: 215::nda-3, 347::nda-12, 620::nda-10, 112::nda-1, 583::nda-1.
Statistics (supporting only): exact McNemar classification b=5, c=1, p=0.219; joint b=5, c=2, p=0.453. Paired bootstrap: joint −2.0pp [−5.3, +1.3]; accuracy −2.7pp [−6.0, 0.0]; Macro-F1 −0.026 [−0.060, +0.003]; Contradiction Recall +2.0pp [0.0, +6.7].

## Contradiction (unchanged headline metric)
P0 41/50 (82%): →Entailment 7, →NotMentioned 2. P3 42/50 (84%): →Entailment 7, →NotMentioned 1. One recovery (269::nda-20), **no regressions**. P3's Contradiction behaviour is neutral-to-slightly-positive here;
its losses are on Entailment and NotMentioned (Entailment recall −6pp, NotMentioned −4pp) — the opposite of E12B's Entailment-driven gain.

## Evidence: E12B's evidence-quality direction did NOT reproduce
E12B: P3 evidence recall +7pp, precision +5.9pp. E12C: recall −2.0pp, precision −3.8pp. Case categories (150 cases): correct label + gold-valid evidence P0 128 / P3 125; correct label + bad evidence 6 / 5; wrong label + gold-overlapping evidence 7 / 7;
wrong label + source-valid evidence (any) 10 / 14. P3 produced more confidently-cited wrong labels here.

## E12B recap and pooled (manifest identity kept explicit)
| | P0 joint | P3 joint | Δ | per-manifest bootstrap Δ joint |
|---|---|---|---|---|
| E12B (n=150) | 114 | 122 | **+8** | +5.3pp [−0.7, +11.3] |
| E12C (n=150) | 128 | 125 | **−3** | −2.0pp [−5.3, +1.3] |
| **Pooled (n=300)** | **242** | **247** | +5 | **+1.7pp [−1.7, +5.0]** (stratified, 10,000 draws) |
Pooled others (P0 → P3): accuracy 85.3% → 85.3% (Δ 0.0, CI [−3.3, +3.3]); Macro-F1 0.854 → 0.854 (Δ +0.0002, [−0.033, +0.033]); Contradiction Recall 82/100 → 83/100 (Δ +1.0pp, [−3.2, +5.6]); evidence recall 88.5% → 91.0%; evidence precision 87.6% → 88.8%.
**The pooled +5 hides a manifest-level reversal and must not be read as replication.** The pooled CI includes zero. E12B's +8 is best explained as a mix of noise and manifest-specific effects (P0 itself scored 76.0% joint on E12B's manifest vs 85.3% on E12C's — manifest difficulty differs far more than the prompts do).

## Decision (rule applied mechanically)
Strong confirmation? No (net −3). Weak confirmation? No (net ≤ 0, guards 2 and 5 fail). → **B — P3 NOT CONFIRMED — KEEP P0.** Not chosen because P0 is simpler, and P3 was not favored for sophistication or sunk cost.
`classification_prompt_gpt_v1` was not created. GPT-prompt optimisation is permanently closed; P1/P2/P3 are not to be tuned further.

## Caveat
E12A showed non-zero hosted-model repeatability noise; E12C tests new documents, which reduces but does not remove that concern — it is still one run per arm. Claim: **P3's E12B advantage did not replicate**, not that P0 is deterministically superior
(E12C's P0 lead of 3 cases is itself within plausible noise). Any residual difference between the two prompts on this task is small.

New Stage B files: `scripts/{run_e12c_confirmation.py, analyze_e12c_confirmation.py}`; `results/{run_E12C_gpt_p0_cases.jsonl, run_E12C_gpt_p3_cases.jsonl, run_E12C_gpt_p0.json, run_E12C_gpt_p3.json, e12c_analysis.json, pre_run_verification.json, run_E12C_wall_seconds.json, run.log}`; executed notebook.

---

# FINAL REVIEW ADDENDUM (approved): KEEP GPT-P0; GPT prompt optimisation CLOSED

P3 showed a directional advantage on the development manifest, but the effect reversed on a fresh document-disjoint confirmation manifest. The pooled effect remained uncertain, so P3 did not earn adoption.
The pooled +5 (242 vs 247 of 300) must not be presented as successful replication: E12C reversed direction, the pooled joint CI includes zero, E12B's evidence-quality gains did not replicate,
and P0's own joint success differed substantially by manifest (76.0% E12B vs 85.3% E12C). `classification_prompt_v1` / GPT-P0 remains the active prompt; `classification_prompt_gpt_v1` was not created;
P0/P3 untouched; no P4/P5, no third confirmation, schema wording not cleaned up (a separate later controlled change if ever wanted).
