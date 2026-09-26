# E13 — GPT Full-Context vs RAG — STAGE A (design, artifacts, forecast only)

**No GPT/Qwen/Gemini call has been made; TEST untouched; prompt files, `retrieval_v1`, TRAIN artifacts unchanged.** (One public OpenRouter `GET /api/v1/models` metadata request was made to read the model's context limit — not a model call, no cost.)

## 1. Question and context
"Under the same GPT-5-mini model, prompt, output contract, and evaluator, does retrieval_v1 RAG outperform or adequately match full-NDA context while reducing token use, latency, and cost?"
GPT prompt optimisation is closed (GPT-P0 = `classification_prompt_v1` active); agent track rejected (A3); static top-11 rejected. This is the **first GPT full-context measurement** (E05 was Qwen; E08B/E12 GPT runs were RAG-only).

## 2-3. DEV audit and historical exposure (DEV is NOT unseen)
| | |
|---|---|
| DEV documents / cases | 61 / 1,037 (Entailment 519 · Contradiction 95 · NotMentioned 423) |
| Reconstruction-v2 (E00–E12C) DEV usage | **none** (E04/E06/E07–E12C all ran on TRAIN; DEV mentions in E04/E07 text describe historical prior art) |
| Historical 150-case seed-42 sample (Oracle/prompt/RAG/confidence/agent tuning) | 150 cases, **58/61 docs** (E 75 · C 14 · NM 61) |
| Historical golden-battery cases (`data/golden/*`) | 55 unique DEV cases, 24 docs (E 21 · C 16 · NM 18) |
| Other historical DEV use | full 1,037-case rule baseline and 614 E/C-case retrieval experiments touched every DEV doc (deterministic/free, but they shaped the OLD retrieval config) |
| Docs untouched by sample/golden | **3** → **document-level disjointness is infeasible** (that pool has 17 E / 5 C / 29 NM) |
| Case-level disjoint pool | E 427 · C 68 · NM 351 → **balanced 150 feasible** |
Per `docs/data_contamination_register.md` §4-5, DEV keeps its Role-B role; no historical DEV outcome may justify an E13 decision. `retrieval_v1` and GPT-P0 were both chosen on TRAIN. This must be reported as "DEV with disclosed historical exposure," not clean held-out data.

## 4-6. `DEV_ARCH_v1` and DEV preservation
**150 cases, 50/50/50, 51 documents, seed 1400** (fresh; prior 42, 99, 123, 300, 500, 700, 900, 1100, 1200, 1300). Deterministic, performance-agnostic (same algorithm as prior manifests: sort doc ids, shuffle with `random.Random(1400)`, ≤2 cases/doc/class);
**case-level disjoint** from the historical 150-case sample and every golden case (asserted); 48 of its 51 documents were touched by *other* hypotheses historically. No hard-case enrichment; no model output read.
**Remaining never-used DEV: 696 cases (E 377 · NM 301 · C 18)**, 10 documents never appear in DEV_ARCH_v1. Only **18 fresh Contradiction cases** remain for later DEV work (routing/abstention calibration, robustness); later work may have to reuse
DEV_ARCH_v1 cases (with disclosure). Alternative if you want more headroom: a smaller balanced manifest (e.g., 40/40/40, leaving 28 fresh Contradictions) — not done; 150 per your preference.

## 7-8. Artifacts (built offline) and verification
`DEV_ARCH_v1_FULL_CONTEXT.json` (complete NDA text) and `DEV_ARCH_v1_RETRIEVED_retrieval_v1.json` (frozen retrieval_v1 top-5) + separate `DEV_ARCH_v1_GOLD.json` (scorer-only).
Verified (all true): 150/150 in both; same case IDs, document IDs, hypothesis text and order as the manifest; **no evaluator truth in model-facing files** (no gold label/span/relevance/expected/failure-family keys);
FULL context equals the complete DEV document text verbatim (no truncation/omission); RAG ≤5 chunks, non-increasing rerank order, retrieval config identical to E12B's; gold/manifest labels agree.

## 9. Common message template (system prompt byte-identical; only the context field differs)
System prompt (both arms; sha1 `3fcc7c95…` = frozen GPT-P0 incl. evidence line):
```
You are given an NDA requirement and relevant excerpts retrieved from the NDA.

Classify the requirement against the excerpts as exactly one of:
- "Entailment"
- "Contradiction"
- "NotMentioned"

Respond with ONLY a JSON object with this exact field:
{
  "label": "Entailment" | "Contradiction" | "NotMentioned"
}
 Also return the exact sentence(s) from the text that support your label, verbatim, as a list under "evidence". Return an empty list for NotMentioned.
```
User message (both arms): `Requirement: {hypothesis_text}\n\nNDA context: {context_text}`
**Only difference between arms:** `{context_text}` = the complete NDA text (A) vs. the retrieval_v1 top-5 chunks joined by `\n\n---\n\n` (B). Verified programmatically: with the context field masked, the two messages are identical for all 150 cases.
**Disclosures:** (i) the shared neutral header "NDA context:" differs from history — E05 full-context used "Full NDA text:", E07/E08B/E12 RAG used "Retrieved NDA excerpts:" — so the E13 RAG arm is not byte-identical to earlier GPT-RAG messages (system prompt/evidence line are identical);
(ii) the frozen system prompt says "excerpts retrieved from the NDA", literally inaccurate for the FULL arm; it was kept byte-identical by requirement and may slightly disadvantage FULL.

## 10-13. Token distributions (exact E13 messages incl. system prompt; cl100k × 0.9907 calibration measured on E12B real API tokens)
| Request tokens | mean | median | p90 | p95 | max |
|---|---|---|---|---|---|
| FULL | 2,456.7 | 2,258.8 | 4,415.5 | 5,826.3 | 6,322.6 |
| RAG top-5 | 1,136.3 | 1,138.3 | 1,278.0 | 1,311.7 | 1,520.7 |
NDA-text-only tokens: FULL mean 2,342 / median 2,142 / p90 4,319 / p95 5,742 / max 6,243; RAG mean 1,009 / median 1,006 / p90 1,149 / p95 1,184 / max 1,396.
**Reduction full → RAG:** −1,320 request tokens/case (**−53.7%** mean; −49.6% median); NDA-text-only −56.9%. The reduction is strongly length-dependent (see groups). Calibration is measured on RAG-type contexts; long-text tokenization ratio is unverified (conservative cost uses uncalibrated counts).

## 14. Context-window safety
OpenRouter's public model listing (metadata only) gives GPT-5-mini `context_length` **400,000**, `max_completion_tokens` 128,000; the repo config records no window (E12A's figure was an unverified assumption — now sourced). Largest FULL request ≈ **6.4K tokens** (97.7% headroom even
with 3K output). **No case risks truncation or provider rejection; no truncation is applied anywhere.**

## 15-18. Ledger, cost, budget gate (pricing from `configs/pricing/openrouter_openai_gpt-5-mini.yaml`: $0.25/M in, $2.00/M out; matches the provider listing)
Ledger now **$2.2317**. Output tokens from real E12B/E12C P0 behaviour (mean 674.6, p90 1,150; assumed the same for FULL — an assumption, since longer context could change hidden reasoning).
| | Expected (in / out / total) | Conservative (p90 in & out, every case) |
|---|---|---|
| FULL (150 calls) | $0.092 / $0.202 / **$0.2945** | $0.5121 |
| RAG (150 calls) | $0.043 / $0.202 / **$0.2450** | $0.3929 |
| **Total (300 calls)** | **$0.5395** | **$0.9051** |
| Projected ledger | $2.7713 | $3.1368 |
Info-only stress case (output tokens ×1.5): $0.7428. **Budget gate: PASS** — $2.2317 + $0.9051 + $1.25 reserve = **$4.39 ≤ $5.00** (projected $3.14 ≤ allowed $3.75; margin $0.61). Note the budget is now tight: after E13 only ~$1.86 of the $5.00 plan remains including the $1.25 reserve.

## 19. Runtime
RAG ≈ 7.1 s/call (E12B/E12C P0); FULL ≈ 8.4 s/call **extrapolated** from E12A's input–latency relation (large extrapolation, uncertain). 300 calls ≈ 39 min sequential, **≈ 8 min at concurrency 5**. Arms run sequentially (FULL then RAG), concurrency 5 and 60s timeout for **both**, 5-consecutive-failure circuit breaker, create-only outputs, no interim quality analysis, ledger run_ids `e13_gpt_full` / `e13_gpt_rag`.

## 20-21. Metrics (frozen)
**Primary:** joint label+evidence success · Contradiction Recall · Macro-F1. **Secondary:** accuracy, Entailment/NotMentioned recall, evidence recall/precision, source-valid rate, strict parse rate. **Operational:** input/output tokens, per-call latency, cost.
Joint success is primary because NDATrace promises a correct decision plus traceable evidence; a small accuracy gain cannot override a large evidence-quality loss. Contradiction analysis per arm: correct/50, recall, C→E, C→NM, Contradiction joint, and every discordant Contradiction case inspected.

## 22. DECISION RULE — FROZEN (user-approved correction; replaces the Stage A proposal; frozen before any hosted call)
Wording: **"DEV architecture validation with disclosed historical exposure"** (DEV is not unseen/pristine/contamination-free; DEV_ARCH_v1 is case-level disjoint from the seed-42 sample and golden battery; E00–E12C never used DEV; TEST untouched).
**net_joint = RAG joint successes − FULL joint successes** (of 150). **RAG quality guards** (RAG fails if ANY is true): Contradiction correct ≥3/50 below FULL (≥6pp); Macro-F1 >0.03 below FULL; Evidence Recall >3pp below FULL; Evidence Precision >3pp below FULL.
- **A — RAG materially better:** net_joint ≥ +5 and all guards pass.
- **B — FULL materially better:** net_joint ≤ −5, or RAG fails a guard while net_joint ≤ 0 (not overridden because RAG is cheaper; FULL's operational penalty reported separately).
- **C — Effectively tied → select RAG for operational efficiency:** −4 ≤ net_joint ≤ +4 and RAG passes all guards (≈54% fewer input tokens, lower expected cost, more scalable, explicit evidence selection).
- **D — Mixed, no architecture freeze:** RAG positive net_joint but fails a guard, or metrics disagree in a way not covered.
(Exhaustive: net≥5&pass→A; net≤−5→B; −4..0&fail→B; −4..4&pass→C; 1..4&fail→D; ≥5&fail→D.) **±5 = 5/150 = 3.3pp**, a predeclared *practical* difference threshold chosen cautiously given known hosted-model variability — **not** a significance threshold; the E12B +9 threshold is not reused.
**Operational principle:** no automatic overrides from latency/cost ratios or p95; actual input-token, latency and cost ratios and timeout/error behaviour are reported; only technical infeasibility (truncation, repeated timeouts, provider rejection) invalidates an arm.
**Limitation to preserve:** DEV NDAs are short (max request ≈6.3K tokens); E13 does not show full-context scales to much larger enterprise NDAs; scalability remains a later production consideration. E13 is the DEV architecture-selection result, not the final production architecture.

## 23. Paired statistics plan
Same-case pairs: classification and joint transitions (Full wrong→RAG correct, Full correct→RAG wrong, both, neither; joint likewise) with all discordant case IDs; exact McNemar (classification, joint); 10,000 paired bootstrap (seed 900) of Accuracy, Macro-F1, Contradiction Recall and joint deltas. Effect sizes and transitions first. One-case flips are not architecture effects (E12A repeatability noise); no case is re-run.
**Context-loss vs distractor analysis:** FULL✓/RAG✗ cases classified as retrieval/filtering loss, context-isolation problem, evidence-selection issue, or variability/other; RAG✓/FULL✗ cases inspected for distractor clauses, conflicting provisions, exception distraction, evidence-selection drift, other.

## 24. Length-group plan (cutoffs fixed now from FULL-NDA token tertiles, not performance)
| Group | NDA tokens | n | FULL request tokens (mean) | RAG request tokens (mean) | Labels E/C/NM |
|---|---|---|---|---|---|
| short | ≤1,352 | 53 | 1,265 | 1,063 | 18 / 17 / 18 |
| medium | 1,353–2,683 | 49 | 2,231 | 1,159 | 12 / 21 / 16 |
| long | >2,683 | 48 | 4,003 | 1,194 | 20 / 12 / 16 |
Per group in Stage B: n, FULL tokens, RAG tokens, FULL joint, RAG joint, delta — to see whether RAG's value grows with length. Caveat: even the "long" group tops out near 6.2K NDA tokens; DEV cannot speak to genuinely long contracts.

## 25. Files
New: `experiments/E13_gpt_context_architecture/{README.md, config.yaml, summary.md, E13_gpt_context_architecture.ipynb (skeleton), DEV_ARCH_v1.json, DEV_ARCH_v1_FULL_CONTEXT.json, DEV_ARCH_v1_RETRIEVED_retrieval_v1.json, DEV_ARCH_v1_GOLD.json, results/{dev_audit.json, pre_run_forecast.json, message_template_examples.json}}`,
`scripts/{build_e13_manifest.py, build_e13_artifacts.py, forecast_e13.py}`. Modified: `docs/experiment_registry.md` (E13 row). No frozen artifact, prompt file, or historical experiment touched.

## 27. Unresolved issues
1. **DEV is not clean**: 48/51 selected documents and the entire DEV split were touched historically; only case-level disjointness from the seed-42 sample and golden battery is achievable. Results must be reported as DEV-with-disclosed-exposure.
2. **Only 18 never-used Contradiction cases remain** after selection; later DEV work (routing/abstention calibration) will be Contradiction-starved unless DEV_ARCH_v1 cases are reused or the manifest is shrunk.
3. **Budget is tight**: conservative E13 leaves ~$1.86 of the $5.00 plan (incl. the $1.25 reserve); a later TEST run or further hosted experiments may not fit without a budget decision.
4. **Wrapper and system-prompt wording** (both disclosed above) are limitations; the FULL arm is told it has "excerpts".
5. **FULL output-token/latency behaviour is assumed** equal to RAG's (unmeasured); latency for FULL is extrapolated.
6. **Scope of any FULL win**: DEV NDAs are short (max ~6.2K tokens); the earlier project decision (CLAUDE.md, T031) excluded full-context from production on scalability grounds. Outcome B would need a separate product/scalability review.
7. Fixed arm order (FULL then RAG), not randomised; the effect on a stateless temperature-0 call is expected to be negligible but is not measured.
8. Stage B run/analyze scripts are not yet written (they will be adapted from the E12C runner/analyzer after approval).

Stage A ends here. Awaiting explicit approval for Stage B.

---

# STAGE B RESULTS (2026-09-27) — DEV architecture validation with disclosed historical exposure

**OUTCOME (frozen rule, applied mechanically): B — FULL MATERIALLY BETTER.** This is the DEV architecture-selection result, **not** a final production architecture.
**Read it precisely:** `net_joint = RAG − FULL = −3` sits *inside* the ±4 tie band; outcome B is triggered by the rule's second clause — **RAG fails two quality guards (Evidence Recall −6.0pp, Evidence Precision −4.2pp; threshold 3pp) while net_joint ≤ 0** —
not by net_joint ≤ −5. Label-level metrics are close and every CI includes zero (below). The rule says FULL is not overridden because RAG is cheaper; FULL's operational penalty is reported separately.

## Execution and integrity
Pre-run verification passed (manifest, both artifacts, complete-document FULL context, no evaluator truth, P0 hash `3fcc7c95…`, ledger $2.2317 with 600 E12B + 300 E12C rows and no E13 rows, gate 4.387 ≤ 5.00). FULL then RAG, concurrency 5, 60 s timeout for both.
**150/150 successful calls per arm; 0 errors, 0 timeouts, 0 retries, 0 rate-limit events; circuit breaker never tripped; no truncation.** (Wall-clock FULL 3.9 min, RAG 4.0 min is concurrency-dependent, not a latency measure.)
Spend: FULL **$0.3120**, RAG **$0.2607**, total **$0.5727** (forecast $0.54 expected / $0.91 conservative). Ledger $2.2317 → **$2.8044** (append-only; run_ids `e13_gpt_full`, `e13_gpt_rag`). New-key check: this key has ≈$9.0 of its $10 limit left; the local $5.00 planning budget is unchanged.

## Matched metrics (150 cases each)
| Metric | FULL | RAG | RAG − FULL |
|---|---|---|---|
| Accuracy | 83.3% | 81.3% | −2.0pp |
| Macro-F1 | 0.834 | 0.814 | −0.020 |
| Entailment / Contradiction / NM recall | 86 / 84 / 80% | 84 / 80 / 80% | −2 / −4 / 0pp |
| **Joint success** | **116 (77.3%)** | **113 (75.3%)** | **−3 cases** |
| Joint E / C / NM | 78 / 74 / 80% | 74 / 72 / 80% | |
| Evidence recall / precision | 90.0 / 85.7% | 84.0 / 81.6% | **−6.0 / −4.2pp** |
| Source-valid evidence | 91.4% | 94.2% | +2.7pp |
| Strict parse | 150/150 | 150/150 | |
Confusion (rows gold E,C,NM): FULL [[43,3,4],[7,42,1],[6,4,40]]; RAG [[42,4,4],[7,40,3],[8,2,40]].

## Frozen guards
| Guard (RAG fails if…) | Result | Fails? |
|---|---|---|
| Contradiction correct ≥3/50 below FULL | −2 (42→40) | no |
| Macro-F1 >0.03 below FULL | −0.020 | no |
| Evidence Recall >3pp below FULL | −6.0pp | **YES** |
| Evidence Precision >3pp below FULL | −4.2pp | **YES** |
net_joint −3, two guards failed → **B**.

## Paired transitions (FULL → RAG)
Classification: 9 FULL-wrong→RAG-right, **12** FULL-right→RAG-wrong, 113 both right, 16 both wrong. Joint: 13 fail→success, **16** success→fail, 100 both, 21 neither.
Classification FULL-wrong→RAG-right: 44::nda-7, 75::nda-20, 610::nda-4, 152::nda-1, 456::nda-15, 64::nda-10, 507::nda-1, 563::nda-16, 595::nda-1. FULL-right→RAG-wrong: 56::nda-20, 440::nda-1, 478::nda-1, 547::nda-16, 563::nda-1, 7::nda-1, 73::nda-13, 547::nda-10, 13::nda-11, 547::nda-15, 563::nda-11, 598::nda-16 (all `dev::`).
Joint fail→success: 44::nda-7, 69::nda-2, 75::nda-20, 563::nda-2, 610::nda-4, 13::nda-12, 15::nda-12, 456::nda-15, 610::nda-12, 64::nda-10, 507::nda-1, 563::nda-16, 595::nda-1. Joint success→fail: 37::nda-2, 56::nda-20, 435::nda-2, 478::nda-1, 563::nda-1, 590::nda-2, 7::nda-1, 37::nda-12, 37::nda-19, 56::nda-13, 73::nda-13, 547::nda-10, 13::nda-11, 547::nda-15, 563::nda-11, 598::nda-16.
**Statistics (supporting only):** exact McNemar classification b=12, c=9, p=0.664; joint b=16, c=13, p=0.711. Paired bootstrap (RAG − FULL): accuracy −2.0pp [−8.0, +4.0]; Macro-F1 −0.020 [−0.080, +0.040]; Contradiction Recall −4.0pp [−15.7, +7.0]; joint −2.0pp [−8.7, +4.7]. **All CIs include zero.**

## Contradiction (headline metric; all 13 discordant cases inspected)
| | Correct/50 | Recall | C→E | C→NM | Contradiction joint |
|---|---|---|---|---|---|
| FULL | 42 | 84% | 7 | 1 | 37 (74%) |
| RAG | 40 | 80% | 7 | 3 | 36 (72%) |
RAG lost 5 Contradictions (56::nda-20, 440::nda-1, 478::nda-1, 547::nda-16, 563::nda-1) and gained 3 (44::nda-7, 75::nda-20, 610::nda-4). The guard (≥3 fewer) was not tripped. 478::nda-1 is a clear carve-out omission ("Notwithstanding…" clause missing from RAG's top-5); 610::nda-4 is the mirror image
(FULL missed the "Residuals" exception that RAG's retrieval surfaced) — exception handling cuts both ways.

## Context-loss (FULL success → RAG failure; all 18 inspected; trace-supported, not causal proof)
- **Retrieval/filtering omission — gold spans not in RAG top-5 (7):** 37::nda-2, 440::nda-1, 478::nda-1, 563::nda-1, 590::nda-2, 37::nda-19, 73::nda-13 (labels lost in 4, evidence-only in 3).
- **Evidence-selection issue — gold in context, partial/alternative quotes (3):** 435::nda-2, 37::nda-12, 56::nda-13.
- **Context isolation / over-inference on absent topics — gold NotMentioned, RAG saw related chunks and inferred a label (4):** 13::nda-11, 547::nda-15, 563::nda-11, 598::nda-16 (the known RAG false-positive family; FULL can verify absence).
- **Model variability / unclear — gold in context, label lost anyway (4):** 56::nda-20, 547::nda-16, 7::nda-1, 547::nda-10.
Retrieval omission is the single largest cause but only 7 of 18 — not automatic blame on retrieval.

## Distractor analysis (FULL failure → RAG success; all 14 inspected)
- **Evaluation mapping artifact (5):** 69::nda-2, 563::nda-2, 13::nda-12, 15::nda-12, 610::nda-12 — FULL's label was right but its quote merged lines/ellipsis/zero-width characters, so the exact-substring span mapping found no gold span.
- **Plausible full-context over-inference (4, all gold NotMentioned):** 64::nda-10 (5.7K tokens), 507::nda-1, 563::nda-16, 595::nda-1 — FULL cited related definition/conditional clauses and inferred a label; RAG correctly abstained.
- **Carve-out surfaced by retrieval (1):** 610::nda-4.
- **Model variability / unclear (4):** 44::nda-7 (identical evidence spans, different label), 456::nda-15 (442-token NDA; RAG context ≈ whole document), 152::nda-1, 75::nda-20.
So the full-context "distractor" effect is real but small (≈4–5 cases); FULL's extra "failures" are as much a scoring artifact as a distraction effect.

## POST-HOC EVALUATOR SENSITIVITY ANALYSIS: evidence-span mapping (NOT the frozen result; frozen E13 headline metrics are not replaced)
The frozen scorer's exact-substring mapping penalises quotes whose whitespace differs from the source. A whitespace-tolerant, ellipsis-segmented mapping applied identically to both arms rescues 5 FULL cases and 1 RAG case: joint FULL 121 vs RAG 114 (net −7), evidence recall 94% vs 84% (−10pp), precision 89.5% vs 81.6% (−8pp);
guards 3 and 4 still fail; outcome would still be **B**. The artifact therefore *understated* FULL's advantage; the frozen result is conservative toward RAG on this point. (`scripts/e13_evidence_mapping_sensitivity.py`, `results/e13_evidence_mapping_sensitivity.json`.) The same scorer artifact was seen in E12A (case 226).

## Length groups (predeclared cutoffs)
| Group | n | NDA tokens (mean) | FULL / RAG request tokens | FULL / RAG accuracy | FULL / RAG joint | Joint Δ (RAG−FULL) |
|---|---|---|---|---|---|---|
| short (≤1,352) | 53 | 1,139 | 1,270 / 1,070 | 81.1 / 83.0% | 40 / 41 (75.5 / 77.4%) | +1 |
| medium (≤2,683) | 49 | 2,114 | 2,224 / 1,155 | 81.6 / 73.5% | 38 / 35 (77.6 / 71.4%) | −3 |
| long (>2,683) | 48 | 3,904 | 4,000 / 1,199 | 87.5 / 87.5% | 38 / 37 (79.2 / 77.1%) | −1 |
RAG's *token savings* grow sharply with length (−16% short, −48% medium, −70% long), but its *quality relative to FULL* does not improve with length in this sample (no monotone trend; deltas are 1–3 cases per group, well inside noise).

## Actual operational comparison (FULL vs RAG)
| | FULL | RAG | FULL / RAG |
|---|---|---|---|
| Input tokens mean / median / p90 / p95 / max | 2,455 / 2,256 / 4,439 / 5,738 / 6,253 | 1,139 / 1,139 / 1,280 / 1,296 / 1,537 | **2.16×** (RAG −53.6%) |
| Output tokens mean / median / p90 / p95 / max | 733 / 674 / 1,229 / 1,536 / 2,152 | 727 / 654 / 1,236 / 1,391 / 2,152 | 1.01× |
| Latency mean / median / p90 / p95 / max (s) | 7.67 / 6.86 / 12.05 / 15.33 / 19.45 | 7.70 / 6.74 / 12.87 / 14.91 / 21.17 | **1.00×** mean (1.02× median, 1.03× p95) |
| Cost total / mean per case | $0.3120 / $0.00208 | $0.2607 / $0.00174 | **1.20×** |
| Projected per 1,000 / per 8,000 | $2.08 / $16.64 | $1.74 / $13.90 | +$0.34 / +$2.73 |
Timeouts/errors/retries: none in either arm. **FULL's measured operational penalty at this scale is small: +20% cost, no latency penalty; output tokens (hidden reasoning) did not grow with the longer input.** No arm is technically infeasible.

## Interpretation and required limitations
1. **B is real but modest and mostly an evidence-quality finding.** Label quality (accuracy −2.0pp, Macro-F1 −0.020, Contradiction −2 cases) and joint (−3) are within noise; RAG's clearest deficit is evidence recall/precision, driven by 7 cases where the gold clause was not in the top-5. This is consistent with the project's earlier findings (retrieval recall ceiling; carve-out/exception omissions).
2. **The result is single-run and inside the known noise floor** (E12A). No case was re-run. Do not read −3 as an architecture effect.
3. **Full-context scalability is NOT established:** DEV NDAs are short (max request ≈6.3K tokens). E13 does not show full-context scales to much larger enterprise NDAs; scalability remains a later production consideration and historical assumptions do not override this measured result.
4. **DEV is not clean:** DEV architecture validation with disclosed historical exposure; E00–E12C did not use DEV; TEST is untouched.
5. **Shared wrapper/system prompt caveat** (Stage A) still applies: the frozen system prompt says "excerpts", unnatural for FULL — if anything this disadvantages FULL, which makes FULL's edge slightly more notable.
6. **Nothing is frozen as the production architecture.** Outcome B is the DEV architecture-selection result; the next decision (e.g., whether B changes the RAG-centered plan, whether a hybrid/larger-K retrieval is worth studying, or whether the tokens-vs-evidence trade-off is acceptable) belongs to the architecture review.

New Stage B files: `scripts/{run_e13_architecture.py, analyze_e13_architecture.py, e13_evidence_mapping_sensitivity.py}`; `results/{run_E13_gpt_full_cases.jsonl, run_E13_gpt_rag_cases.jsonl, run_E13_gpt_full.json, run_E13_gpt_rag.json, e13_analysis.json, e13_manual_inspection.json, e13_evidence_mapping_sensitivity.json, pre_run_verification.json, run_E13_wall_seconds.json, run.log}`; executed notebook.


---

# FINAL REVIEW ADDENDUM (approved): E13 outcome B — DEV architecture-selection result

**Interpretation (approved wording):** FULL context showed a modest but consistent evidence-quality advantage over top-5 RAG on DEV. The joint-success difference was small and statistically uncertain, but RAG exceeded the predeclared evidence-quality degradation guards.
For the NDA lengths represented here, FULL therefore becomes the preferred architecture candidate for subsequent validation. This does **not** show that FULL conclusively dominates RAG, that RAG is useless, that RAG cannot scale better, or that FULL is production-ready.
Contradiction direction is preserved: FULL 42/50 (84%) vs RAG 40/50 (80%), −4pp for RAG; the guard did not trip (2 cases < 3-case threshold) but Contradiction remains a headline risk metric. Discordant-case labels (18 FULL✓→RAG✗: 7 retrieval/filtering omission, 3 partial/alternative evidence, 4 over-inference on absent topics, 4 unclear/variability; 14 RAG✓→FULL✗: 5 evidence-scoring artefact,
4 plausible FULL over-inference, 1 exception surfaced by RAG, 4 unclear/variability) are diagnostic, not causal certainty; preserved examples 478::nda-1 (carve-out omitted from RAG's top-5) and 610::nda-4 (RAG surfaced an exception FULL missed).
**Evaluator hardening:** the post-hoc sensitivity result (whitespace-tolerant mapping rescues 5 FULL / 1 RAG cases; strengthens, not reverses, the FULL result) must be addressed in a separate evaluator-hardening step **before the final TEST benchmark**; it does not alter the frozen numbers above.
**Length:** RAG's token saving rises sharply with length (≈16% short, ≈48% medium, ≈70% long) but did not translate into a quality advantage within the tested range (joint Δ +1 / −3 / −1); not extrapolable to very long enterprise contracts. **Operations:** FULL ≈2.16× input tokens, latency ≈ equal, cost ≈1.20× ($2.08 vs $1.74 per 1,000; $16.64 vs $13.90 per 8,000) — a modest penalty at these lengths.
**Limitations (prominent):** disclosed DEV exposure; one run per arm; all paired CIs include zero; non-zero hosted-model variability; short DEV NDAs (max request ≈6.3K tokens); FULL scalability at much larger lengths untested; the frozen GPT-P0 system prompt mentions "retrieved excerpts" and is unnatural for FULL.
**Architecture status after E13:** current preferred candidate = GPT-5-mini + GPT-P0 (`classification_prompt_v1`) + **FULL NDA context** + same structured output/parser. `retrieval_v1` is NOT deleted or overwritten; RAG remains a measured baseline, operationally cheaper and potentially relevant for longer documents. No hybrid FULL/RAG router is proposed yet. TEST has not been touched.
