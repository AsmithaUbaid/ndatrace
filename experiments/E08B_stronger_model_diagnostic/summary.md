# E08B — Stronger-Model Diagnostic — STAGE A (design/audit + budget gate only)

**No GPT-5 mini call has been made. No Qwen call has been made. `retrieval_v1` and
`classification_prompt_v1` are read-only inputs.** This document audits the current GPT-5 mini
provider/pricing configuration, verifies the frozen A2 input artifact's integrity, reads the
real reconstruction-v2 spend ledger, applies the existing pre-run budget gate, projects the
150-case cost using real historical output-token data, and proposes the full matched-comparison,
E08-bucket-recovery, and statistical analysis plan for Stage B.

## 1. Research question

"How much of A2 Standard RAG's remaining failure is attributable to the base model rather than
the retrieval architecture?" The only change from E07: `qwen2.5:7b-instruct-ctx16k` →
`openai/gpt-5-mini`. Everything else — manifest, retrieved context, prompt, schema, parser,
evidence validator — held fixed. This is model-capability isolation, not prompt tuning: no
GPT-specific prompt, no P3, no new instructions.

## 2. GPT-5 mini config/provider audit

| Setting | Value | Source |
|---|---|---|
| Provider | OpenRouter | `pipeline/config.py`'s default (`ModelGateway(model=...)`, no `.local()`/`.groq()` wrapper) |
| Base URL | `https://openrouter.ai/api/v1` | `pipeline/config.py` |
| Model string | `openai/gpt-5-mini` | unchanged from E01/E00B — no silent substitution |
| Published pricing | $0.25/M input, $2.00/M output | `configs/pricing/openrouter_openai_gpt-5-mini.yaml`, verified 2026-09-26, no free tier |
| Timeout | 30s | `pipeline/config.py`'s unchanged default — **not verified against real GPT-5-mini latency for this task shape, flagged as unresolved (section 17)** |
| Max retries | 3 | unchanged default |
| Reasoning-effort parameter | Not set, does not exist in `pipeline/model_gateway.py` | confirmed by reading the module — nothing to accidentally introduce |
| Structured JSON mode (`response_format`) | **Available but will NOT be used** | see section 7 |

**Critical, historically-confirmed cost behavior**: GPT-5 mini bills hidden reasoning tokens as
output tokens (found independently during T009, `docs/decisions.md`, and restated in this
model's own pricing file). Real E01 Oracle data (300 real calls, this reconstruction-v2
lineage) shows output tokens ranging **43-1,118**, mean **149.9**, median **124.0** — a long
right tail. A2's task (full 3-way classification from ~5 retrieved chunks) is structurally
harder than Oracle's single-evidence-sentence decision, so reasoning-token usage could plausibly
be similar or higher. This affects the *precision* of the cost forecast, not its pass/fail
outcome (section 5).

## 3. Frozen A2 input artifact — verified this pass

`experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json`, re-checked directly
(not assumed from memory): **150/150 cases present, ordering matches `TRAIN_ARCH_v1` exactly,
zero gold leakage, retrieval config confirmed** (`bm25`/`clause`/256/top_k=5/
`ms-marco-MiniLM-L-12-v2`). **Retrieval was NOT re-run** — this is an integrity check on the
existing frozen artifact only, per explicit instruction.

## 4. Input-token distribution (real, computed from the frozen artifact + exact A2 prompt construction)

Using the identical system prompt (`classification_prompt_v1` + the same additive evidence
instruction used in E05/E07) and the identical `"Retrieved NDA excerpts:"` wrapper, `cl100k_base`
approximation (consistent with every other reconstruction-v2 token estimate — GPT-5 mini's own
tokenizer will differ slightly, a disclosed approximation, not exact):

| Statistic | Tokens |
|---|---|
| Mean | 1,159.9 |
| Median | 1,176.0 |
| P90 | 1,313 |
| Max | 1,784 |

Matches E07's own real measured Qwen-tokenizer distribution closely (mean 1,176.8, median
1,191.5) — confirming this is the correct, unchanged input.

## 5. Budget gate (real ledger, existing gate function, applied directly)

Read via `evaluation.budget.reconstruction_spend_so_far()` (not assumed): **current
reconstruction-v2 spend = $0.1178** — entirely E01 Oracle's 300 real `openai/gpt-5-mini` calls
(historical T-series spend is a separate ledger, never summed here, per the module's own
"don't double-count" rule).

| | USD |
|---|---|
| Planning budget | $5.00 |
| Protected reserve (25%) | $1.25 |
| **Allowed budget** | **$3.75** |
| Reconstruction spend so far | $0.1178 |
| **Available headroom** | **$3.6322** |

**Projected 150-case cost** (real frozen A2 token distribution, not Oracle's shape, for input;
Oracle's real historical output-token stats as the starting calibration point for output, given
no A2-specific GPT data exists yet):

| | Central estimate | Worst-plausible estimate (illustrative) |
|---|---|---|
| Input cost | $0.0435 (150 × 1,159.9 tok × $0.25/M) | same, $0.0435 |
| Output cost | $0.045 (150 × 150 tok × $2/M, using Oracle's real historical mean) | $0.335 (150 × 1,118 tok × $2/M, using Oracle's real historical **max**, applied to all 150 cases — an extreme, not-expected-to-materialize upper bound) |
| **Total** | **~$0.089** | **~$0.379** |

**Budget gate: PASS.** Both the central estimate and the deliberately-extreme worst-plausible
upper bound are comfortably within the $3.6322 available headroom — **the gate outcome is not
sensitive to the output-token uncertainty at this budget scale.** No run is blocked.

## 6. Calibration run — proposed, not executed

**Not needed to clear the budget gate** (section 5 shows it passes either way). **Proposed
anyway, optional**, purely to sharpen the cost-effectiveness precision the brief's section 14
requires (cost per additional correct/joint-success case) with real A2-task-specific
output-token data, since Oracle's task (single-sentence evidence, no retrieved-chunk context,
no evidence-quoting requirement) differs structurally enough from A2 that extrapolating blindly
would weaken that specific downstream analysis. **Not run in Stage A** per the explicit
instruction to run it only if needed and justified — deferred to Stage B pending approval, and
would not be scored/used to tune anything if run (matching E05's calibration precedent).

## 7. Output schema, parser, evidence setup — identical to E07, not reopened

Compact `{"label": ..., "evidence": [...]}`, evidence verbatim from the provided (retrieved)
context, no explanation/rationale, NotMentioned → `[]`. **Parser**:
`evaluation.structured_output.parse_structured_output` (unchanged). **Evidence validator**:
`pipeline.evidence_validator.validate_evidence` (unchanged), checked against the same retrieved
context.

**Structured-output decision (explicit)**: provider-side JSON schema enforcement
(`response_format`) is available via `ModelGateway.complete()` but **will not be used**. E07's
Qwen run did not use it (confirmed by reading `scripts/run_e07_standard_rag.py` — no
`response_format` argument passed), relying entirely on the prompt instruction plus the
deterministic strict/recovery parser. Using provider-side enforcement for GPT but not Qwen
would advantage GPT on parse validity for a reason unrelated to underlying model capability —
exactly the confound the brief's section 7 warns against. Both models are evaluated under the
identical "ask nicely in the prompt, recover deterministically if needed" regime.

## 8-13. Exact matched metrics / statistical plan / bucket-recovery / wrong-evidence-subgroup / reranker-limited plan

**Matched metrics** (both architectures, same 150 cases): accuracy, Macro-F1, per-class recall
(Contradiction Recall + 95% CI), confusion matrix, joint success (overall + by class), strict/
usable parse validity, evidence-valid rate, Evidence Recall/Precision, mean/median/p90 input
tokens, mean/median/p90/max latency, total cost.

**E08 bucket-recovery plan**: for each of E08's 73 manually-reviewed cases (31
`MODEL_REASONING_LIMITED`, 26 `AGENTICALLY_FIXABLE`, 6 `STATIC_PIPELINE_FIXABLE`, 10 correct/
transition-only), look up GPT's prediction on the identical case_id and report the recovery
count/rate per bucket — directly tests whether E08's labels reflect a Qwen-specific limitation
(GPT fixes most `MODEL_REASONING_LIMITED` cases) or a genuinely information/architecture-bound
problem (GPT fails on them too). Reported overall and Contradiction-specific.

**Wrong-evidence subgroup plan**: for the same 54 Qwen wrong-label+source-valid-evidence
case_ids (4 gold-overlap, 50 non-overlap), report GPT's correct-label count, gold-overlapping-
evidence count, source-valid-but-non-gold-evidence count, and joint-success count — tests
whether stronger reasoning also improves evidence *selection*, not just final-label accuracy.

**Reranker-limited plan**: for the 6 `STATIC_PIPELINE_FIXABLE` cases, report whether GPT
nevertheless solves any of them from the same gold-absent top-5 context. **Explicit
instruction, preserved**: a GPT failure on these 6 must NOT be interpreted as a reasoning
failure — the information genuinely was not in the context for either model.

**Statistical plan**: exact two-sided McNemar (`scipy.stats.binomtest`, same methodology as
`scripts/compare_e05_e07.py`), overall and Contradiction-restricted; 10,000-resample paired
bootstrap for accuracy/Macro-F1/Contradiction-Recall/joint-success deltas (GPT minus Qwen), 95%
CI reported alongside every test — no significance manufactured if underpowered.

## 14. Expected runtime

Not yet measured for this specific task shape — E01 Oracle's historical GPT-5-mini calls were
sub-2s typical (much shorter context). A2's ~1,160-token average input is still modest by
hosted-API standards; a full 150-case run is expected to complete in a few minutes, dominated by
per-call network/API latency rather than local compute. No calibration-based projection is
offered here (unlike E05's local-Ollama calibration, which existed because local context-window
truncation was a real, confirmed risk) — hosted APIs do not have the same context-truncation
failure mode, and 30s timeout at ~1,160 input tokens is not expected to be tight, though this is
flagged as unverified (section 17) rather than assumed safe.

## 15. Files to create / change

**Stage A (this commit)**: `experiments/E08B_stronger_model_diagnostic/{README.md, config.yaml,
summary.md, results/}` (empty, for Stage B). No code touched, no model call made.

**Stage B (after approval)**:
- `scripts/run_e08b_stronger_model_diagnostic.py` (new — loads the frozen retrieved-context
  artifact directly, no retrieval rerun; calls `openai/gpt-5-mini` via `ModelGateway`; applies
  the budget gate before running; records real spend via `evaluation.budget.record_spend`;
  mirrors `scripts/run_e07_standard_rag.py`'s structure with the model substituted).
- `scripts/analyze_e08b_stronger_model.py` (new — matched metrics, E08 bucket-recovery mapping,
  wrong-evidence-subgroup analysis, reranker-limited check).
- `scripts/compare_qwen_gpt_e08b.py` (new — paired McNemar + bootstrap, mirrors
  `scripts/compare_e05_e07.py`'s structure).
- `experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train.json`,
  `..._cases.jsonl`, `qwen_vs_gpt_paired_comparison.json`, `e08_bucket_recovery.json`.
- `experiments/E08B_stronger_model_diagnostic/E08B_stronger_model_diagnostic.ipynb`.

## 16. Unresolved issues

1. **30s timeout unverified for this task shape** — E01 Oracle's much-shorter context makes it
   an imperfect precedent; not raised preemptively, flagged for Stage B to watch (mirrors E05's
   own discipline of verifying rather than assuming a timeout is adequate).
2. **Calibration run** (section 6) — proposed but not executed; a judgment call on whether the
   cost-effectiveness precision is worth the small extra step before the full 150-case run.
3. **Output-token uncertainty** does not affect the budget-gate pass/fail outcome but does
   affect the precision of the section-14 cost-effectiveness numbers the full report will need
   — Stage B's real 150-case data will resolve this regardless of whether calibration runs
   first.
4. Whether GPT-5 mini's own tokenizer differs materially from the `cl100k_base` approximation
   used for the input-token projection — a known, disclosed approximation, not expected to be
   large enough to matter at this budget scale.

Stage A ends here. No GPT-5 mini call has been made, no Qwen call has been made. Awaiting
explicit approval to proceed to Stage B.

## Stage B result (executed, all 150 cases)

Calibration (8 cases) approved, followed by the full 150-case run. Real spend: $0.2557 (ledger
total now $0.3872, well within the $3.75 allowed budget). 150/150 strict parse, 0 errors, 0
timeouts (max latency 16.8s of 30s).

**Matched Qwen vs. GPT-5-mini result** (identical 150 TRAIN_ARCH_v1 cases, identical retrieved
context, identical prompt/schema/parser/validator — only the model differs):

| Metric | Qwen | GPT-5-mini | Δ |
|---|---|---|---|
| Accuracy | 43.3% | 78.7% | +35.3pt |
| Macro-F1 | 0.431 | 0.787 | +0.356 |
| Entailment Recall | 34.0% | 82.0% | +48.0pt |
| Contradiction Recall | 42.0% | 76.0% | +34.0pt |
| NotMentioned Recall | 54.0% | 78.0% | +24.0pt |
| Joint success (overall, full 150) | 33.3% (50/150) | 74.0% (111/150) | +40.7pt |
| Evidence Recall | 29.0% | 86.0% | +57.0pt |
| Evidence Precision | 35.8% | 83.5% | +47.7pt |

**Joint-success transitions, full 150 matched cases** (corrected — originally miscomputed over
only E08's 73 manually-reviewed cases; recomputed from E07's own `rag_failure_analysis.csv`,
which independently scores `joint_success` for all 150 cases using the identical scorer used for
GPT): Qwen-fail→GPT-success 75, Qwen-success→GPT-fail 14, both-success 36, both-fail 25.
Marginals verified: Qwen 50/150 (33.3%), GPT 111/150 (74.0%), sum 150. Additional joint-success
cases: 61, at $0.2557/61 = **$0.00419 per additional joint-success case**. Additional correct
classifications: 53 (65→118), at $0.2557/53 = **$0.00482 per additional correct case**.

**E08 failure-bucket recovery** (mapping GPT onto E08's 73 manually-reviewed cases):
MODEL_REASONING_LIMITED 30/31 (96.8%) now correct; AGENTICALLY_FIXABLE 19/26 (73.1%) now correct
without any retrieval/agent change; STATIC_PIPELINE_FIXABLE 1/6 (16.7%) — expected, gold evidence
was absent from context for both models. McNemar overall p=5.24×10⁻⁹; Contradiction-restricted
p=0.0033.

**Evidence-metric semantics verified**: `evidence_to_span_indices`, `retrieval_contains_gold`,
and `joint_success` in `scripts/analyze_e08b_stronger_model.py` are AST-confirmed byte-identical
in logic to `scripts/analyze_e07_standard_rag.py` — Qwen and GPT are scored with the exact same
gold-overlap semantics. `source_valid_evidence` (verbatim/structural validity) and
`gold_evidence_overlap` (true overlap with the annotated gold span) are reported as distinct
fields in both runs' CSVs and were never conflated in any reported metric.

**Diagnostic conclusion: A — STRONGER MODEL LARGELY SOLVES THE REASONING BOTTLENECK.** This does
**not** mean agents are unnecessary: the static-six retrieval-limited cases and GPT's own
residual failures (16/150 classification-wrong, 14/150 joint-wrong) have not been analyzed for
agentic recoverability. E09 must reassess agent justification using GPT's residual failures, not
Qwen's — A3 should not be designed to solve a reasoning weakness that was largely specific to the
weaker model. Full results: `results/qwen_vs_gpt_paired_comparison.json`,
`results/e08_bucket_recovery.json`, `E08B_stronger_model_diagnostic.ipynb`. Not committed —
awaiting review.
