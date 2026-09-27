# E18 — Business, Cost, Safety & Course Synthesis

Offline analysis phase, refreshed on top of E17B commit `270b006` (E17B: full TEST completion — GPT-5-mini now has one prediction for every one of the 2,091 official TEST cases: the immutable E17 150 + the E17B 1,941, merged and verified). No model calls, no retuning, no TEST-output changes. **Source-of-truth policy: the full merged GPT n=2,091 result is the primary final GPT TEST measurement everywhere below; the E17 n=150 balanced sample is kept only for methodology/sample-representativeness discussion (§8b), never as a headline number.** Every number below is read from an existing artifact (cited inline) or is an explicitly labelled scenario assumption / config-derived approximation. See `results/e18_analysis.json` and `course_coverage_matrix.md` for detail; figures in `figures/00..13`.

## 1. Majority-class TEST baseline (extra descriptive baseline; does not replace B01)
Always predict Entailment, empty evidence, on all 2,091 official TEST cases (968 E / 220 C / 903 NM).
**Accuracy 46.3%** (968/2091), **macro-F1 0.211** (F1 collapses to ~0 for Contradiction/NotMentioned since they're never predicted), Entailment recall 100%, Contradiction/NotMentioned recall 0%, **joint success 0.0%** (empty evidence never satisfies E's evidence-overlap requirement, and label is always wrong for C/NM). Confirms even the rule baseline (59.0% acc, E04) and the always-NM rule fallback both beat naive majority-guessing; joint success shows why label accuracy alone is a weak metric for an evidence-grounded system.

## 2. Agent token economics — B and D
- **B (repeated per turn) = 1,986 tokens** — measured: the frozen `agent_step_v1_3tools.txt` control prompt (510 tokens, tiktoken cl100k) + a representative resent top-5 RAG context (1,476 tokens, a real E11 agent-trace case).
- **D (new tokens per turn) ≈ 1,000 tokens — APPROXIMATION, not measured.** No real NDATrace agent trace ever made a tool call: all 15 real E11 agent traces (`agent_traces.jsonl`) show `agent_steps=1, stop_reason="final"` — the agent concluded immediately in every case this project actually ran. D is derived from E10's own hard limit (`max_cumulative_retrieved_tokens=2000` across `max_tool_calls=2`) as a config-implied per-turn ceiling, clearly labelled as such — not substituted from classroom values.
- **Quadratic growth (Input(T) ≈ B·T + D·T(T-1)/2), T=1..3 (configured cap):**

| T | B·T | D·T(T-1)/2 | Total |
|---|---|---|---|
| 1 | 1,986 | 0 | 1,986 |
| 2 | 3,972 | 1,000 | 4,972 |
| 3 | 5,958 | 3,000 | 8,958 |
Figure 3. **Message:** agent loops accumulate context; cost grows faster than turn count — but NDATrace's own agent never exercised turns 2–3 in the cases actually run, so this is a real formula demonstrated on a config ceiling, not an observed cost blow-up.

## 3. Reliability compounding — P(success) ≈ sᵀ
No real multi-step NDATrace trace exists, so s is a **scenario**, using measured single-call joint-success rates as the per-step proxy: E13 FULL DEV (0.773), E17 hosted TEST (0.767), and the (trivial, T=1-only) E11 agent first-step-final rate (1.0). At T=3 (the configured cap): 0.773³=46.2%, 0.767³=45.1%. Figure 4. **Message:** more turns increase both token burden (§2) and failure opportunity, even though this project's real agent never reached T=2.

## 4. FULL vs RAG token economics by document length (E13, DEV n=150; measured)
Overall: FULL mean 2,455 input tokens vs RAG mean 1,139 (joint 0.773 vs 0.753 — **FULL was materially better**, the frozen E13 outcome). By tercile: short docs (2.3–7.1k chars) save 192 tok (15.3%); medium (7.1–13.6k) save 1,015 tok (46.9%); long (13.6–32.4k) save 2,742 tok (69.5%). Figure 5. **RAG's token savings scale with document length, but did not improve measured quality on this DEV comparison** — the core reason full-context, not RAG, is the frozen candidate.

## 5. Final full-TEST comparison — Rule vs Qwen vs GPT, identical n=2,091 (measured; Figure 0, the headline figure)
| | Accuracy | Macro-F1 | Joint | Contradiction recall | Evidence recall/precision | Source-valid | Cost |
|---|---|---|---|---|---|---|---|
| Rule | 59.0% | 0.479 | 50.1% | 16.8% | 29.3%/60.8% | n/a | $0 |
| Qwen ctx16k | 49.9% | 0.431 | 39.7% | 25.5% | 35.3%/35.9% | 70.3% | $0 API (local compute/time NOT monetized; 7.13h) |
| **GPT-5-mini FULL** | **77.6%** | **0.727** | **74.6%** | **75.5%** | 93.3%/74.7% | 98.0% | $4.23 total ($0.00202/case) |
GPT materially outperforms both baselines on the identical TEST population.

**Paired GPT-vs-Qwen (same 2,091 cases; McNemar exact):** classification both-correct 780, GPT-only 843, Qwen-only 263, both-wrong 205, **p≈2.8×10⁻⁷¹**; joint both-correct 579, GPT-only 981, Qwen-only 251, both-wrong 280, **p≈3.1×10⁻¹⁰²** — very strong paired evidence in GPT's favor overall. By class: **Contradiction** — GPT-only-correct 129 vs Qwen-only-correct 19 (p≈2.8×10⁻²¹ classification), a clear direction, not a coin-flip effect. **Entailment** — similarly strongly in GPT's favor. **NotMentioned** — both-correct 325, GPT-only 241, Qwen-only 214, both-wrong 123, **p≈0.22–0.24, not statistically significant**: GPT is materially stronger overall and on Entailment/Contradiction, while both systems remain comparably weak on NotMentioned. Full detail: E17B `results/final_full_test_metrics.json`.

## 5b. Oracle/ceiling result (E01 Oracle vs real-context systems; measured, full TEST primary)
Qwen Oracle (gold evidence) macro-F1 **0.638**, Contradiction recall 30% — weak even with the correct clause handed to it. GPT Oracle macro-F1 **0.906**, Contradiction recall 82%. GPT real-context, full TEST (n=2,091, primary): macro-F1 **0.727**, joint 74.6%. Figure 2. **GPT substantially outperformed Qwen and moved much closer to the Oracle reasoning ceiling, but a meaningful gap remained** (0.727 vs 0.906). For final GPT Contradiction failures specifically, interpretation was the dominant observed failure mode: **38 of 50 evidence-bearing Contradiction misses (full TEST, n=220) quoted text overlapping the annotated gold evidence but still predicted the wrong label** — missed-provision and evidence-selection failures still exist elsewhere (§11's taxonomy), so this narrower claim should not be generalized to every failure mode. Oracle accuracy is a diagnostic ceiling, not an achievable production number.

## 6. Quality vs. raw model cost (measured, full TEST)
Rule: $0 API, joint 50.1% (full TEST). Qwen local: $0 API, joint 39.7% (full TEST) — **API cost = $0; local compute/time is NOT monetized** (7.13h wall time for 2,091 cases on the dev laptop is a real cost, just not a dollar one). GPT hosted: $0.00202/case, joint **74.6%** (full TEST, n=2,091). Figure 6.

## 7. Cost-to-serve (three-layer model; C_AI measured, C_H/V/F scenario)
`C_month = V·[C_AI + (1−p_safe)·C_H] + F`, where p_safe = joint success (the automatically-handled-correctly rate), NOT classification accuracy. **NDATrace has no verified enterprise human-review cost** — C_H, V, F are explicit scenario variables, never a single "real company" ROI:
- **C_AI (measured):** GPT $0.00202/case (full TEST); Qwen/rule $0 API.
- **p_safe (measured, = joint success, full TEST n=2,091, primary):** GPT **74.6%**, Qwen 39.7%, rule 50.1%. (E17's 150-case sample value, 76.7%, is recorded only in §8b for representativeness — not used here.)
- **C_H scenarios (illustrative only):** 1/3/5/10-minute reviews × $20/$40/$75 per hour → $0.0033 to $12.50 per case (5 min @ $40/hr = **$3.33/case**, used as the headline scenario).
- Full grid: 3 systems × 12 review-cost scenarios × 3 volumes × 2 fixed-cost scenarios (36 combinations per system) in `results/e18_analysis.json`.

## 8. Break-even success rates (illustrative human-review cost scenario, $3.33/case; recomputed with full-TEST p_safe)
GPT's all-in cost (C_AI + (1−p)·C_H) at its own measured full-TEST p is **$0.8485/case** (up from a stale $0.780 computed on the 150-case sample's optimistic p — recalculated, not retained). For Qwen to match that all-in cost at $0 API cost, it would need **p ≥ 74.5%** (formula: p_BE = 1 − (E_target − C_alt)/C_H; recomputed from the old, now-superseded 76.6% figure) — its real measured p is **39.7%**, still far short. GPT beats manual-only ($3.33/case) at essentially any positive success rate (p_BE ≈ 0.06%). Figure 8. **Sensitivity (Figure 7, regenerated with full-TEST p_safe):** human fallback still dominates the ranking far more than the sub-cent AI cost does.

## 8b. E17 sample vs. full population — how representative was the 150-case balanced sample?
| | Accuracy | Joint | E recall | C recall | NM recall |
|---|---|---|---|---|---|
| A. E17 balanced n=150 | 78.0% | 76.7% | 92.0% | 78.0% | 64.0% |
| B. E17 standardized estimate | 78.4% | 78.0% | — | — | — |
| C. Merged full population n=2,091 (primary) | **77.6%** | **74.6%** | **92.0%** | **75.5%** | **62.7%** |
The accuracy estimate was close (within 0.4–0.8pp); the **joint-success estimate was optimistic by about 3.4 percentage points** (76.7%/78.0% sampled vs 74.6% true). This is a useful evaluation-methodology finding, not a defect in the original protocol — the sample was reasonably representative, and completing full TEST coverage materially improved the precision of the final comparison (Contradiction n grew from 50 to 220, narrowing its Wilson interval from ±11pp to ±5.5pp).

## 9. Safe automation / silent failure / review trade-off (E15 fresh DEV_ROUTING_v1 validation, n=138; principal routing view)
| Policy | Review rate | Safe automated | Human review | Unsafe automated (silent failure) | Failure capture | Residual joint error |
|---|---|---|---|---|---|---|
| R0 (none) | 0% | 71.0% | 0% | **29.0%** | 0% | 29.0% |
| R1 (integrity floor) | 4.3% | 70.3% | 4.3% | 25.4% | 12.5% | 26.5% |
| R2 (+all predicted C) | 21.0% | 60.9% | 21.0% | 18.1% | 37.5% | 22.9% |
| R3 (+rule disagreement) | 51.4% | 43.5% | 51.4% | 5.1% | 82.5% | 10.4% |
Each row sums to 100%. Provisional target region: review ≤40% AND residual <10% (inherited/provisional, not a measured SLA) — **no policy enters it** (Figures 9, 10, 11). **E15's demonstrated conclusion stands: deterministic observable runtime signals were not sufficient to reliably detect confident reasoning errors** within an acceptable workload.

## 10. E16 robustness summary
Clean joint 85.0% → attack joint 75.0% (20 matched pairs); **4/11 injection-type pairs succeeded** (2 label hijacks, 2 output-format compliances); 2 clean-correct→attack-wrong regressions; source-valid quote rate 96.7% clean / 100% attack. Outcome **B**. Figure 12. **Source-valid evidence ≠ trusted instruction source** — do not overstate an n=20-pair finding.

## 11. Final failure taxonomy and Contradiction story (full TEST, n=2,091, primary; Figure 13)
**531 total joint failures** (of 2,091): NotMentioned over-inference **323** (the dominant bucket by far), Contradiction reasoning-failure-or-missed-provision 48, other Entailment reasoning failure 42, missed provision (no evidence) 39, correct-label/evidence-mismatch 43, source-validation issue 36. **NotMentioned is now GPT's main residual limitation** — 62.7% recall, and the 323-case over-inference bucket dwarfs every other category; paired against Qwen it shows no statistically significant advantage there either (§5). GPT delivered large gains overall and on Contradiction, but NotMentioned remained substantially weaker and did not show a statistically significant paired advantage over Qwen — this is a real, disclosed residual limitation, not equivalence with Qwen elsewhere.
**Contradiction, all 220 (primary):** 166/220 correct (75.5% recall), 158/220 joint-correct. 54 classification misses: 50→Entailment, 4→NotMentioned. Among the 50 evidence-bearing C→E misses, **38 quoted text overlapping the annotated gold evidence but still predicted the wrong label** — at full TEST scale, many remaining Contradiction errors were interpretation failures rather than evidence-access failures. This is the primary Contradiction finding; do not generalize it to every failure mode (missed-provision and evidence-selection failures still occur, per the taxonomy above).
*(Consistency check only, superseded above: the original E17 150-case sample showed 35 joint failures — NotMentioned over-inference 18, reasoning failure with gold evidence available 10, missed provision 4, correct-label/evidence-mismatch 2, exception/carve-out 1 — and 39/50 Contradiction correct, 37/50 joint. Same shape, smaller n.)*

## 12. Seven-layer final AI stack
| Layer | Actual NDATrace choice | Build/Rent/Use | Why | Production implication |
|---|---|---|---|---|
| Compute | OpenRouter (hosted GPT-5-mini); local Ollama (Qwen/Llama) | Rent + Own | Rent for quality/scale; own for $0-cost comparator, no thermal margin at scale | Hosted needs a provider SLA/spend cap; local needs hardware provisioning |
| Data / embeddings | `all-mpnet-base-v2` (sentence-transformers, local) | Use existing | Swapping embedding models made no measured difference once reranking was applied (Decisions Log, round 4) | No embedding fine-tuning needed for this domain at this scale |
| Vector/retrieval | In-process dense + BM25-fusion candidates over ~10-doc-sized NDAs, `cross-encoder/ms-marco-MiniLM-L-12-v2` reranker | Build (thin) + Use (models) | Corpus is per-document (not corpus-wide), so no managed vector DB was ever needed | A larger multi-document deployment would need a real vector store |
| Model | `openai/gpt-5-mini` via OpenRouter (FULL context, frozen) | Rent | Best measured quality (E13 outcome B: FULL beat RAG) at ~$0.002/case | Single-vendor dependency; no fallback model wired in |
| Orchestration | Plain synchronous Python scripts/pipeline, no agent in the frozen system | Build (thin) | The agent (built, evaluated, E09-E11) was **rejected**; orchestration is a single classify() call, not a graph/loop | Simpler to operate and audit than an agent-based system |
| Serving | Not built in reconstruction-v2 (backend/frontend exist in the earlier "ndatrace" pipeline, not this reconstruction) | — | Reconstruction-v2 stayed at the offline-evaluation stage | Serving layer is future work, not part of the frozen TEST result |
| Observability / evaluation | `evaluation/` harness + `evidence_evaluator_v2` (offline) and `pipeline/evidence_text.py` runtime validator v2 (E14), append-only ledger, structured logs | Build | Two-tier by design: offline scoring knows gold; runtime validation never does (E14 §7) | Real production observability plan below |
**RAG is a measured experimental architecture, not the selected serving path** — the frozen candidate is FULL context.

## 13. Observability / monitoring plan (production; not built, specified)
**Per-request:** request ID, model/version, prompt/version hash, NDA length/input tokens, output tokens, latency, monetary cost, predicted label, parse status, quote count, source-valid quote count, evidence-validator version, route/review status, error/retry status.
**Aggregates:** p50/p95/p99 latency, cost/case, token distributions, parse-failure rate, source-validation failure rate, prediction-class distribution, review/escalation rate, sampled human-audit error rate, silent-failure estimate, prompt-injection/security incidents, document-length drift, model/provider/version changes.
**Never logged by default:** confidential NDA content (matches the reconstruction's own logging rule, carried from the original NDATrace plan).

## 14. Class-6 production feedback loop
```
OFFLINE EVALUATION (knows ground truth: TRAIN/DEV/TEST gold labels)
        ↓
FROZEN SYSTEM (E13/E17 frozen model+prompt+architecture+evaluator+validator)
        ↓
RUNTIME GUARDRAILS + OBSERVABILITY (§13 — only runtime proxies, no gold; E14's validator, R1's structural checks)
        ↓
HUMAN REVIEW / ESCALATION (only ~R1-flagged cases in the frozen system; E15 found no adequate broader policy)
        ↓
HUMAN RESOLUTION = NEW LABEL (delayed, not available at inference time)
        ↓
PERIODIC REGRESSION SET (folds resolved labels back into evaluation, NOT into online routing)
        ↺ back to OFFLINE EVALUATION
```
**Offline evaluation knows ground truth before deployment; runtime guardrails only ever have proxies (parse validity, source-validity, rule agreement) — E15 showed those proxies do not reliably catch confident reasoning errors. Human resolution is the only source of a real production label, and it always arrives late.**

## 15. Prompt-complexity economics (E03/E12, no new experiment)
Qwen: P0 (simplest) beat every more-elaborate variant. GPT: P3 showed a development-set gain that **reversed on confirmation** (E12C); P0 was retained as the frozen default. **Additional prompt tokens/instruction complexity must earn a measurable, repeatable quality improvement — twice in this project it did not.**

## 16. Evaluator-hardening story (E13B/E14, QA box, not a main result)
v1: exact-substring match only. Problem: harmless formatting differences (line breaks, zero-width characters, NFC) produced false evidence misses. v2: NFC + selected zero-width removal + whitespace collapse. Historical re-scoring: 41 changed mappings, **all formatting rescues, 0 false positives, 0 valid→invalid regressions**. E14 aligned the runtime validator to the same v2 semantics.

## 17. Experimental governance / leakage timeline
| Split | Role | Reconstruction-v2 discipline |
|---|---|---|
| TRAIN | Development | All prompt/retrieval/agent tuning happened here |
| DEV | Architecture/prompt/routing validation | **Disclosed historical exposure** from prior project iterations (documented in `docs/data_contamination_register.md`); used only after that disclosure, never to justify a config choice retroactively |
| TEST | Final, one-shot | **First accessed only after** model, prompt, architecture, evaluator, validator, and routing were all frozen (E17, 2026-09-26T19:23:43Z, commit 5717bdf). No TEST-informed changes were made afterward. |
The register does not claim historical TEST access was ever perfectly blind pre-reconstruction; reconstruction-v2's own access is the clean, disclosed one this report stands on.

## 18. Files created/changed (this refresh)
Changed: `scripts/e18_business_analysis.py` (oracle_ceiling, cost_to_serve, failure_taxonomy now source from E17B full n=2,091), `scripts/e18_generate_figures.py` (new Figure 0; 01/02/06/07/13 regenerated with full-population values; Figure 4's caption corrected). New: `figures/00_final_test_comparison.png`. Unchanged (§27, no bug found): majority baseline, agent B/D setup, quadratic-growth analysis, FULL-vs-RAG DEV result, E15 routing calculations, E16 robustness result, seven-layer stack, observability plan, feedback loop, prompt-complexity/evaluator-hardening conclusions, leakage/governance history, coverage-matrix structure.

## 19. Core vs appendix figures (revised)
**Core (8):** 00 final full-TEST comparison (Rule/Qwen/GPT, n=2091 — new headline), 02 Oracle ceiling, 03 agent token growth, 05 FULL vs RAG tokens, 07 cost sensitivity, 09 safe automation composition, 10 review vs residual error, 13 failure taxonomy (full TEST, n=2091).
**Appendix (6):** 01 architecture ladder (mixed DEV/TRAIN/TEST manifests, explicitly labelled), 04 reliability vs turns (illustrative, not measured), 06 quality vs cost, 08 break-even, 11 review vs capture, 12 robustness.

## 20. Claim discipline
**Measured:** model quality (E01/E13/E17/E17B), tokens (E13/E17/E17B), latency (E17/E17B), API cost (E17/E17B, $4.23 total GPT TEST spend), routing results (E15), security test results (E16), paired GPT-vs-Qwen significance (E17B).
**Scenario (explicitly labelled, never merged with measured numbers):** human-review cost/time, enterprise volume, fixed monthly cost, reviewer-time savings, ROI, agent D (config-derived), reliability s (measured single-call rate used as an illustrative anchor, not per-step agent correctness).

## 21. Final project conclusion (revised for full TEST)
On all 2,091 TEST cases, GPT-5-mini with full NDA context achieved **77.6% classification accuracy, 74.6% joint label-plus-evidence success, and 75.5% Contradiction recall**. It materially outperformed the full-population rule (59.0% acc / 50.1% joint / 16.8% C recall) and local-Qwen (49.9% acc / 39.7% joint / 25.5% C recall) baselines, with the GPT-vs-Qwen advantage statistically significant overall and on Entailment/Contradiction (paired McNemar p<10⁻²⁰), though not on NotMentioned. RAG reduced token usage substantially for longer NDAs (up to 69.5% on the longest DEV tercile) but did not earn selection on quality in the matched architecture study — full context remains the frozen candidate. The tested selective agent added orchestration without demonstrated tool-use benefit and was rejected (E09–E11); the tested selective-review policies (E15) added workload without meeting the provisional safety/workload targets and were also not adopted. Residual errors were dominated by NotMentioned over-inference (323 of 531 full-TEST failures) and by cases — especially Contradiction — where relevant evidence was available but interpreted incorrectly (38 of 50 evidence-bearing Contradiction misses quoted the correct clause). The system remains evidence-grounded but not prompt-injection-hardened (E16).
