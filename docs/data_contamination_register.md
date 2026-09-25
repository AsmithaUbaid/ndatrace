# Data Contamination Register

Produced during E00 (dataset/split validation), local-only — no LLM/API calls, no model results
inspected beyond what already existed on disk. Covers every historical (T-series) dataset/sample
construction found in this repo, and specifically which touched the official DEV or TEST splits.
Nothing here is deleted or rewritten; this is disclosure, not remediation of the past.

## 1. Full historical dataset/sample inventory

| Sample | Historical purpose | Source split | Selection method | Doc count | Case count | Seed | Labels available? | Gold evidence available? | Used by | Keep for reconstruction-v2? |
|---|---|---|---|---|---|---|---|---|---|---|
| `dev.json` (full, 614-case subset used for retrieval sweeps) | Retrieval-only tuning (chunking, reranking, top-K) — no LLM calls | official DEV | all Entailment/Contradiction cases in dev | 61 (all) | 614 | — | yes | yes | ADR-002 (9 rounds of retrieval experiments) | **Historical evidence only.** E06 re-derives independently. |
| 150-case dev sample (`stratified_sample`, seed=42) | Oracle, model selection, prompt v1–v6, RAG e2e, full-context baseline, confidence/abstention, agent experiment | official DEV | case-level (not document-first) stratified-by-label random sample via `random.Random(42)` | ≤150 distinct docs (case-level, not doc-first sampling — see §2 below) | 150 | 42 | yes | yes | ADR-001, ADR-002 (partially), ADR-003, ADR-004, ADR-005, ADR-007, ADR-008 | **Historical evidence only.** Reused adaptively across nearly every T-series decision — the single biggest reason reconstruction-v2 exists. Not reused as-is; E01–E11 build fresh manifests. |
| Golden regression battery (`data/golden/golden_cases.json` 30, `negative_cases.json` 15) | Catch known behavioural regressions after a pipeline/prompt change | official DEV | hand-picked | ≤45 | 45 | — | yes | yes | ADR-011, ongoing regression checks | Historical regression suite — keep running as-is for regression detection; not a reconstruction-v2 benchmark. |
| System/robustness cases (`injection_cases.json` 11, `llm_behaviour_cases.json` 7, `agent_cases.json` 7, `confidence_cases.json` 2, `evidence_quality_cases.json` 4, `logging_security_cases.json` 5) | Behavioural/security checks, not benchmark accuracy | official DEV (+ some synthetic) | hand-picked / synthetic | small | 36 | — | yes (where applicable) | partial | ADR-004 (v6 injection fix), T040 | Historical — keep for regression/security checks (E17 may extend, not replace). |
| AV01 — architecture validation set | Independent check of the architecture freeze (ADR-009), on data untouched by any prior tuning decision | official TRAIN | **document-level** random sample (whole NDAs first, then their cases), verified zero overlap with dev sample, golden cases, and `test.json` | 20 docs | 340 | 99 (deliberately distinct from 42) | yes | yes | ADR-009 update, `data/architecture_validation_manifest.json` | Historical evidence — genuinely clean methodology (doc-level, disjoint, verified). Motivates E12's approach but is not reused as reconstruction-v2's manifest. |
| PVAL01 — prompt validation set | Same rationale as AV01, for prompt-version comparison on untouched data | official TRAIN | document-level, seed=123 (distinct from 42 and 99), verified disjoint from AV01 and all other pools | 26 docs | — (not fully audited this phase) | 123 | yes | yes | `data/prompt_validation_manifest.json` | Historical evidence — same clean methodology as AV01. |
| T041-A — interim final-test run | Early pass at the final locked evaluation | **official TEST** | stratified case-level subsample, seed=42 | — | 500 | 42 | yes | yes | `results/archive/runs/` (superseded) | **TEST split — see contamination table below.** |
| T041-B — full final-test run | The final locked evaluation, cited everywhere as "the T041 result" | **official TEST** | full split, no subsampling | 123 (all) | 2,091 (all) | 0 (deterministic, no sampling) | yes | yes | `results/final/run_T041_*.jsonl`, ADR-010 | **TEST split — see contamination table below.** |
| Rule baseline full test run | Zero-cost deterministic baseline on the full test split | official TEST | full split | 123 | 2,091 | 0 | yes | yes | `results/final/run_T041_final_test_rule_full.jsonl` | **TEST split — see contamination table below.** Lowest risk (rules were frozen before this ran and cannot be "tuned" by a deterministic keyword match). |
| Hosted-vs-local comparison run | Compare Gemini (hosted) vs. Llama/local on the same cases as T041 | **official TEST** | identical seed=42 subsample as T041-A/full split | — | matches T041 | 42 | yes | yes | `results/final/`, ADR-010 | **TEST split — see contamination table below.** |

## 2. Document-level vs. case-level sampling — audit finding

Section 5 of the reconstruction brief requires whole-document sampling first, then hypothesis
cases, to avoid a document's cases being scattered across differently-purposed subsets.

- **AV01 and PVAL01 already do this correctly** — both explicitly sample whole train documents
  first (`random.Random(seed).sample(...)` over document ID lists), then include all cases for
  each selected document. Verified in their scripts' own code, not just their docstrings.
- **The 150-case dev sample (`stratified_sample`, seed=42) does not** — it samples individual
  `(doc, annotation)` pairs directly, stratified by label, with no document-first step. This is
  not a leakage bug in the way it was actually used (it was reused whole, as one manifest, across
  many *experiment types* — never split further into disjoint train/tune subsets drawn from the
  same pool), but it does mean the same NDA's cases can appear scattered arbitrarily within that
  one sample. **Reconstruction-v2's TRAIN_WORKING / TRAIN_ORACLE manifests must sample documents
  first**, per the brief's rule — this is a concrete methodology change from the historical
  pattern, not a continuation of it.

## 3. Contamination: which historical work touched official TEST or DEV

| Experiment/script | Split touched | Labels inspected? | Evidence inspected? | Influenced later decisions? | Reconstruction-v2 consequence |
|---|---|---|---|---|---|
| `scripts/run_final_test_evaluation.py` (T041-A, T041-B) | **TEST** | Yes — real predictions scored against real gold labels | Yes | **No architecture-level decision changed because of these results** (freeze was ADR-009, 2026-09-23, before T041 ran on 2026-09-24) — but the run happened, so TEST is no longer a pristine blind set for the historical lineage. | TEST split is **not disqualified** for reconstruction-v2 (a document being previously scored doesn't teach a future model anything — no weights were updated, no human retuned a threshold from it), but reconstruction-v2's own E14 run must not reuse or reference T041's per-case results when picking reconstruction-v2 configs. |
| `scripts/run_full_rule_baseline_test.py` | **TEST** | Yes | Yes (rule matching only) | No — rule logic was already frozen (deterministic keyword baseline) before this ran; nothing to "tune." | Lowest-risk historical TEST touch. |
| `scripts/run_hosted_comparison.py` | **TEST** | Yes | Yes | No — ran after freeze, for a hosted-vs-local comparison, not a config decision. | Same as T041 above. |
| `scripts/analyze_test_set_results.py` | **TEST** (reads T041's already-saved predictions) | Yes, post-hoc | Yes, post-hoc | **Explicitly documented in its own docstring as read-only, no re-scoring, no pipeline feedback** — audited directly, confirmed accurate. | No consequence — this is exactly the discipline reconstruction-v2 wants going forward. |
| `scripts/extract_failure_examples.py` | Reads T041 predictions + `data/golden/negative_cases.json` (DEV) | Yes, post-hoc | Yes, post-hoc | Read-only, used only to pull quotable examples for the report (confirmed in its own docstring, which also correctly notes negative_cases.json is DEV-sourced with zero doc overlap with TEST). | No consequence. |
| `scripts/run_reliability_tests.py` | **TEST** (K02/K03: real shortest/longest NDA) | No — used document length/structure only, not labels | No | No | Negligible — structural property, not a label/evidence read. |
| `scripts/build_architecture_validation_set.py`, `scripts/build_prompt_validation_set.py` | **TEST** (read `test.json` only to compute `test_ids` for overlap exclusion) | No — IDs only, never labels or text | No | No | Clean. This is exactly the right way to use TEST during development: to verify you *haven't* touched it, never to read its content. |
| Golden battery / injection / behavioural case builders | **DEV** | Yes | Yes | Yes, by design — these exist specifically to encode findings (e.g. ADR-004's v6 prompt fix) back into the pipeline. | Historically used DEV as tuning (Role A-style) material, which is a role-conflation against reconstruction-v2's own TRAIN/DEV/TEST role assignment (DEV = Role B, validation only). Disclosed here; does not disqualify DEV from Role B going forward — see §4. |
| Oracle / prompt / RAG / confidence / agent experiments (150-case sample) | **DEV** | Yes | Yes | Yes — directly drove ADR-001, ADR-002 (partially), ADR-004, ADR-005, ADR-007 | Same role-conflation as above: DEV was used as development/tuning material historically, not reserved for validation. Reconstruction-v2 sources its own tuning experiments from TRAIN going forward, independent of this historical use — see §4. |

## 4. Role structure — final

Reconstruction-v2 uses the **official ContractNLI three-way split as-is** — TRAIN (Role A,
development/tuning: Oracle, model screening, prompt selection, retrieval tuning, agent
development; fixed TRAIN subsets may be created only for cost/runtime-controlled diagnostics) /
DEV (Role B, validation and architecture/configuration selection, used only after candidate
configs are sufficiently frozen from TRAIN development; after DEV-based selection, freeze the
configuration before TEST) / TEST (Role C, final held-out benchmark under the reconstruction-v2
protocol, no tuning after viewing reconstruction-v2 TEST results) — and does **not** invent a
fourth operational split. The role-conflation finding above (DEV used historically for both
tuning-style and validation-style purposes) is disclosed as a **methodological limitation of the
historical T-series work**, not a reason to reassign DEV's role for reconstruction-v2. The same
disqualification logic, applied consistently, would also disqualify TEST (which has its own real
historical exposure — T041-A/B, the rule/hosted-comparison runs); reconstruction-v2 instead
disqualifies **historical outcomes** from influencing new decisions (§5's standing rule), not the
**splits themselves** from their standard roles.

## 5. Standing rule for reconstruction-v2

> Prior knowledge from historical DEV- or TEST-split runs (the 150-case dev sample, T041-A/B, the
> rule/hosted-comparison test runs) may motivate broad reconstruction-v2 hypotheses (e.g. "the
> agent's dev-sample gain didn't replicate on a larger sample — check this again independently"),
> but no reconstruction-v2 decision (model, prompt, retrieval, routing, agent policy) may be tuned
> against, or justified by reference to, any individual historical DEV- or TEST-split outcome.
> E12–E14 must arrive at their own conclusions from reconstruction-v2's own TRAIN/DEV evidence
> before official TEST — reconstruction-v2's final held-out benchmark under this protocol — is
> ever touched again.

This does not invalidate the historical T041 numbers as evidence of what that specific pipeline
did — they remain valid, disclosed history (`docs/decisions.md` ADR-010). It only prevents them
from silently shaping reconstruction-v2's choices.
