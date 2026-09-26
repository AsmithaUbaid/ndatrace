# E07 — Standard RAG (A2) — STAGE A (design/audit only)

**No Qwen call has been made in E07.** This document audits existing RAG code, defines A2's
exact architecture, decides the model tag, generates and characterizes the retrieval-context
artifact on `TRAIN_ARCH_v1` (local-only, zero LLM calls — same precedent as every prior
experiment's Stage A manifest-building step), and proposes the matched E05-vs-E07 statistical
comparison. Nothing in this document is a reconstruction-v2 classification result yet.

## 1. Research question

"Does retrieval_v1 improve qwen2.5:7b-instruct classification and evidence-grounding relative
to full-context input when evaluated on the same frozen cases?" A matched architecture
comparison — E05 (full document) vs. E07 (retrieval_v1 top-5), same 150 cases, everything else
held constant.

## 2. Existing RAG runner(s) found in repo — audit

**Found**: `scripts/run_rag_experiment.py` (T-series T024, historical). **Not reusable
unmodified**:
- Uses a **different retrieval configuration entirely** — `Retriever(doc.text,
  chunk_method="sentence")` + `query_rerank_and_boost` (sentence chunking, rule-boosted RRF
  fusion) — the OLD T-series retrieval decision, not reconstruction-v2's frozen `retrieval_v1`
  (BM25/clause_256/top-20/rerank/top-5, no rule-boost).
- Uses a **different classification mechanism** — `pipeline.classifier.classify()` +
  `prompts/classify_v2.txt`, a heavier schema (`label`, `confidence`, `evidence: list[str]`,
  `explanation`) — not `classification_prompt_v1`/E03's mechanism
  (`evaluation.prompt_selection` + `ModelGateway.complete()`).
- Runs on **DEV split, hosted model** (`ModelGateway()`, OpenRouter) — not TRAIN, not local.

**Reusable as a pattern, not as code**: build-retriever-once-per-document, query-once-per-
hypothesis (avoids redundant re-indexing across the 150 cases' shared documents).

**Confirmed reusable pieces** (unmodified, already exist):
- `scripts/run_e06_retrieval.py::build_or_load_index` — the exact frozen `retrieval_v1` index
  builder, cached by config (top_k excluded from the cache key).
- `pipeline/reranker.py::rerank` — unmodified cross-encoder reranker.
- `evaluation/retrieval_eval.py::score_retrieval`, `compute_retrieval_metrics`,
  `context_size_stats` — E06's already-audited evidence-hit scoring and context-size
  measurement, reused verbatim.
- `scripts/generate_e03_retrieved_context.py`'s exact pattern — replicated (not modified) as
  `scripts/generate_e07_retrieved_context.py`, retargeted at `TRAIN_ARCH_v1` (this pass).
- `evaluation/structured_output.py::parse_structured_output` and
  `pipeline/evidence_validator.py::validate_evidence` — both from E05, unchanged.

## 3. Exact A2 architecture

```
requirement/hypothesis
  → retrieval_v1 (BM25 → clause_256 → top-20 → rerank(ms-marco-MiniLM-L-12-v2) → top-5)
  → final top-5 reranked NDA chunks + hypothesis
  → classification_prompt_v1 (system prompt byte-for-byte unchanged) + evidence instruction
  → "Retrieved NDA excerpts:" architecture wrapper (NOT "Full NDA text:")
  → qwen2.5:7b-instruct-ctx16k, temperature 0.0
  → {"label": ..., "evidence": [...]}
  → evaluation.structured_output.parse_structured_output (strict/recovery, unchanged)
  → pipeline.evidence_validator.validate_evidence (unchanged)
```

No agent, no iterative retrieval, no tool loop, no query rewriting, no adaptive second pass.

## 4. Model-tag decision and rationale

**Decision: `qwen2.5:7b-instruct-ctx16k`, the same tag E05 used.**

E07's retrieved contexts are far shorter than E05's full documents (max 1,649 vs. 5,806 tokens,
measured this pass, section 7) — a plain `qwen2.5:7b-instruct` tag would fit safely too. But the
brief's own stated principle is decisive here: *"the matched-comparison principle is more
important than saving small amounts of context memory."* `num_ctx` does not alter model weights
or sampling behavior — only the maximum context size accepted. An unused larger window has no
expected effect on generation for prompts well below the limit, so using the identical tag
introduces zero expected behavioral difference for E07's shorter inputs while eliminating a
second model-runtime variable from the comparison entirely. **Model family/version is
unchanged** (still `qwen2.5:7b-instruct` underneath both tags).

## 5. Retrieval-context artifact design — generated this pass

`scripts/generate_e07_retrieved_context.py` (new, mirrors
`scripts/generate_e03_retrieved_context.py`'s pattern exactly, retargeted at `TRAIN_ARCH_v1`).
Runs the frozen `retrieval_v1` config, unmodified, over all 150 `TRAIN_ARCH_v1` cases (including
NotMentioned — retrieval never sees the gold label, so it gets whatever `retrieval_v1` naturally
returns, exactly as E03's equivalent artifact does).

**Model-facing file** (`TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json`) — per case: `case_id`,
`document_id`, `hypothesis_id`, `hypothesis_text`, `retrieval_config_version`,
`ranked_chunk_ids`, `ranked_chunk_text`, `ranked_chunk_offsets`,
`ranked_chunk_bm25_candidate_scores`, `ranked_chunk_rerank_scores`. **No gold label, gold
relevance flag, or gold span ID anywhere in this file.**

**Gold-side file** (`TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json`, scorer-only, never passed
to a model) — `case_id`, `gold_label`, `gold_span_indices`.

**New relative to E03's artifact**: both the BM25 candidate-pool score AND the final
cross-encoder rerank score are preserved per chunk (E03's equivalent artifact discarded these —
`pipeline.reranker.rerank` overwrites `RetrievalResult.score` with the rerank score, so the
candidate score is captured before reranking).

## 6. `retrieval_v1` coverage on `TRAIN_ARCH_v1` — characterization, not re-tuning

Computed this pass using the exact frozen `retrieval_v1` config and the existing, unmodified
E06 scoring functions (`evaluation.retrieval_eval`). **`retrieval_v1` itself was not altered,
retuned, or re-evaluated at a different configuration — this is characterization on a new
manifest using the pipeline exactly as frozen.**

| Metric | Value |
|---|---|
| Evidence-bearing cases (Entailment+Contradiction) | 100 |
| Evidence Recall@5, overall | 90.9% |
| Evidence Recall@5, Entailment | 85.4% |
| Evidence Recall@5, Contradiction | 96.3% |
| Evidence Precision, overall | 5.1% |
| MRR, overall | 0.357 |
| Miss count | 6 / 100 |

Consistent with `retrieval_v1`'s E06 characterization on the full 4,371-case evidence-bearing
TRAIN universe (92.2% overall recall, 93.9% Contradiction recall) — this 100-case subset is a
touch lower on Entailment specifically (85.4% vs. E06's aggregate) but well within the range
expected from a 100-case sample of the same underlying retriever, not a sign of degraded
retrieval on this particular manifest.

## 7. Input-token distribution for E07 (retrieved context, all 150 cases, `cl100k_base` approx.)

| Statistic | Tokens |
|---|---|
| Mean | 1,017.4 |
| Median | 1,036.0 |
| P90 | 1,177 |
| Max | 1,649 |
| Mean chunks/case | 4.82 |

## 8. Token reduction vs. E05 (both real, measured distributions)

| Statistic | E05 (full context) | E07 (retrieval_v1) | Reduction |
|---|---|---|---|
| Mean | 2,252.7 | 1,017.4 | **54.8%** |
| Median | 2,045.5 | 1,036.0 | **49.4%** |
| P90 | 3,945 | 1,177 | **70.2%** |

This is one of the main operational comparisons the brief asks for — a real, substantial
compaction, independent of whether classification/evidence quality also improves.

## 9. Exact output/parser/evidence setup

Identical to E05, not reopened: compact schema `{"label": ...,"evidence": [...]}`, evidence
must be verbatim from the provided (retrieved, not full-document) context, no explanation/
rationale, NotMentioned must return `[]`. Parser: `evaluation.structured_output
.parse_structured_output` (unchanged). Evidence validator: `pipeline.evidence_validator
.validate_evidence` (unchanged) — critically, evidence verbatim-checking for E07 must check
against the **retrieved context actually shown**, not the full document, exactly as
`validate_evidence`'s own docstring already requires ("checking against anything else ... would
silently pass quotes the model couldn't have legitimately seen from that context").

## 10. Proposed paired E05-vs-E07 analysis (Stage B, after E07 runs)

**Matched metric table** (both architectures, same 150 cases): Accuracy, Macro-F1, Entailment/
Contradiction/NotMentioned Recall, joint label+evidence success (overall), strict parse rate,
usable parse rate, evidence-valid rate, mean input tokens, mean latency.

**Case-level transitions**: E05-wrong→E07-correct, E05-correct→E07-wrong, both-correct,
both-wrong — overall and specifically restricted to the 50 Contradiction cases.

## 11. Proposed statistical test(s)

- **McNemar's exact test** (two-sided exact binomial, `scipy.stats.binomtest` — same
  methodology as the existing `evaluation.metrics.mcnemar_test`, reimplemented directly on the
  two aligned per-case correctness lists rather than constructing T-series `Prediction`/
  `GoldCase` objects unnecessarily) on the discordant pairs (E05-only-correct vs.
  E07-only-correct), computed both overall (n=150) and restricted to Contradiction (n=50).
- **Paired bootstrap CI**: 10,000-resample paired bootstrap over the 150 case-pairs, reporting a
  95% CI for each headline metric's E07-minus-E05 difference.
- **Explicit caveat, not resolved unilaterally**: with n=150 overall (and only n=50 for the
  Contradiction subgroup), a McNemar test may well be underpowered to reach significance even
  if a real effect exists — this will be reported honestly (a non-significant p-value is not
  the same as "no effect"), and the raw effect size + CI will always be reported alongside any
  test, never a p-value alone. No significance will be manufactured by, e.g., searching for a
  more favorable test after the fact.

## 12. Expected runtime — reasoned estimate, not a fresh guess or new calibration

Applying E05's own fitted latency-vs-input-tokens relationship (`latency_s = 2.145 + 0.004582 ×
input_tokens`, fit on E05's real 8-case calibration and subsequently validated against E05's
real 150-case run) to E07's real, measured, much shorter total-input-token distribution:
**projected mean ≈7.5s/case, total ≈19 minutes for 150 cases.**

**Why no separate calibration run is proposed this time**: E07 uses the identical model tag,
timeout, and parser already validated end-to-end for E05, at a **strictly shorter** context
length (max 1,649 vs. E05's already-validated max 5,806). The two risks a calibration run exists
to catch (context truncation, timeout) are inherently less likely to trigger at a shorter length
than one already confirmed safe. Retrieval itself (BM25 + local cross-encoder rerank) was
already measured as near-instant per case with cached indexes during this pass's context-
generation run (150 cases processed in well under a minute, dominated by index build/cache-load
time on first touch per document, not per-query cost).

## 13. Failure-analysis plan

**Retrieval-aware taxonomy** (new relative to E05, which has no retrieval step): for every
error, evaluator-side only (never passed to the model), record whether gold evidence was
present in the final top-5 context, then classify:
- **A. Retrieval-limited**: gold evidence absent from the final context (not the model's fault
  — it was never shown the answer).
- **B. Reasoning-limited**: gold evidence present but prediction wrong.
- **C. Evidence-selection failure**: label correct but returned evidence invalid/wrong/
  paraphrased.
- **D. Structured-output failure**: response not deterministically parseable.
- **E. Mixed/ambiguous**: multiple factors plausibly contribute.

**Finer families** (from the brief's list, tagged only when actually observed, same
non-forced-categorization discipline as E03/E04/E05): retrieval miss, evidence present but
wrong label, evidence present but model chooses the wrong excerpt among the 5 retrieved,
NotMentioned overprediction, exception/carve-out co-occurrence, multi-clause reasoning,
definition/cross-reference dependency, distractor retrieved chunks, paraphrased/non-verbatim
evidence, structured-output issue. **No family is assumed to dominate in advance** — E04 and
E05 each surfaced a *different* dominant pattern (lexical coverage gaps vs. exception/carve-out
co-occurrence respectively) on the same underlying dataset, so E07's own error data will be let
to speak for itself.

## 14. Files to create / change

**Stage A (this commit)**: `experiments/E07_standard_rag/{README.md, config.yaml, summary.md,
results/}`, `TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json` + `_GOLD.json` (built, local-only, zero
model calls), `scripts/generate_e07_retrieved_context.py` (new). `docs/experiment_registry.md`
E07 row updated.

**Stage B (after approval)**:
- `scripts/run_e07_standard_rag.py` (new — loads the retrieval-context artifact, runs A2's
  classification step per case, mirrors `scripts/run_e05_full_context.py`'s structure with the
  RAG wrapper instead of the full-context wrapper).
- `scripts/analyze_e07_standard_rag.py` (new — classification/structured-output/evidence/
  joint/retrieval-aware-failure analysis, mirroring `scripts/analyze_e05_full_context.py`'s
  structure, plus the new retrieval-limited/reasoning-limited taxonomy).
- `scripts/compare_e05_e07.py` (new — the matched paired comparison: metric table, case
  transitions, McNemar test, paired bootstrap CI).
- `experiments/E07_standard_rag/results/run_E07_A2_train.json`, `run_E07_A2_train_cases.jsonl`,
  `rag_failure_analysis.csv`, `e05_vs_e07_paired_comparison.json`.
- `experiments/E07_standard_rag/E07_standard_rag.ipynb`.

## 15. Unresolved issues (for explicit review)

1. **No separate calibration run proposed** (section 12) — reasoned as low-risk given E07's
   strictly-shorter context than E05's already-validated range, but this is a judgment call, not
   a certainty; the first several real cases in the Stage B run will be watched for any
   unexpected latency/parse anomaly regardless.
2. **Statistical power** (section 11) — n=150 (and n=50 for Contradiction) may not yield
   significance even for a real effect; this is flagged now so it isn't treated as a surprise or
   a reason to retroactively change the design later.
3. Whether the retrieval-aware failure taxonomy's five categories will need a "primary +
   secondary" allowance the way E05's did — cannot be confirmed before real E07 error data
   exists.

Stage A ends here and was approved. Results below.

---

## Full Benchmark Results (2026-09-26) — all 150 TRAIN_ARCH_v1 cases

**Frozen configuration, unchanged from the approved Stage A design**: `retrieval_v1`
unmodified, `classification_prompt_v1` unchanged, model `qwen2.5:7b-instruct-ctx16k` (same tag
as E05), temperature 0.0, 60s timeout, "Retrieved NDA excerpts:" wrapper,
`evaluation.structured_output.parse_structured_output`, unmodified
`pipeline.evidence_validator.validate_evidence`. No DEV, no TEST, no hosted call. Total wall
time: **1,152.5s (19.2 minutes)** — matching the ~19-minute Stage A projection closely.

### Manifest/artifact verification

Re-verified before running: `TRAIN_ARCH_v1` — 150 cases, 50/50/50, seed=700, 78 unique
documents, zero overlap with `TRAIN_PROMPT_v1`. `TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json` —
150/150 present, ordering matches, `retrieval_config` confirmed
(`bm25`/`clause`/256/top_k=5), zero gold leakage, top-5 chunks confirmed. **Additionally**: for
every one of the 150 cases, retrieval was re-run live (from the cached index) and its output
was asserted identical to the frozen artifact before use — zero divergence.

### Classification metrics

| Metric | Value |
|---|---|
| Accuracy | 43.3% |
| Macro-F1 | 0.431 |
| Entailment Recall | 34.0% |
| **Contradiction Recall** | **42.0% [95% CI 29.4%, 55.8%]** |
| NotMentioned Recall | 54.0% |

### Confusion matrix (rows = gold, cols = predicted; order Entailment/Contradiction/NotMentioned)

- **Entailment**: `[17, 17, 16]`
- **Contradiction**: `[3, 21, 26]`
- **NotMentioned**: `[12, 11, 27]`

### Structured-output metrics — reported separately, never collapsed

**Strict parse validity: 150/150 (100.0%). Recovered: 0. Invalid: 0. Usable structured-output
validity: 100%.** Retries: 0. Model errors: 0. Timeouts: 0. Unlike E05 (94.0% strict, 9 recovered
cases, all correlated with longer full-document contexts), E07's uniformly short retrieved
contexts (max 1,797 tokens vs. E05's max 5,806) produced zero instruction-following/formatting
degradation anywhere in the 150-case run — consistent with the length-correlation E05 itself
observed.

### Evidence metrics — explicit returned evidence only, never full-document access

| Metric | Value |
|---|---|
| Evidence-bearing cases (Entailment+Contradiction) | 100 |
| Evidence Recall | 29.0% |
| Evidence Precision | 35.8% |
| Correct label but invalid evidence | 14 |
| **Wrong label but valid (verbatim, correctly-located) evidence** | **54** |
| Paraphrased (non-verbatim) evidence | 32 |

Evidence is checked against the retrieved context actually shown to the model (per
`validate_evidence`'s own requirement), not the full document. As with E05, a large fraction of
errors (54) have correctly-located, verbatim evidence but the wrong label — the reasoning
bottleneck persists even with retrieval's more compact, curated context.

### Joint label+evidence success

| | Rate |
|---|---|
| Overall | 33.3% |
| Entailment | 16.0% |
| Contradiction | 30.0% |
| NotMentioned | 54.0% |

### Retrieval-limited vs. reasoning-limited decomposition (new for E07)

| Count | Category |
|---|---|
| 79 | B — reasoning-limited (gold evidence present in the retrieved context, label still wrong) |
| 14 | C — evidence-selection failure (correct label, invalid/paraphrased evidence) |
| 6 | A — retrieval-limited (gold evidence absent from the top-5 context) |
| 51 | n/a (correct) |

**Contradiction-specific**: 28 reasoning-limited, 7 evidence-selection, 1 retrieval-limited, 14
correct. **The overwhelming majority of E07's errors (79/99, 80%) are reasoning-limited, not
retrieval-limited (6/99, 6%)** — consistent with `retrieval_v1`'s measured 90.9%
Evidence-Recall@5 coverage on this manifest (Stage A) and with E01 Oracle's earlier,
independent finding that Qwen's classification bottleneck is reasoning, not evidence access.
Retrieval is doing its job; the model frequently still gets the label wrong even when shown the
right text.

### Latency — retrieval overhead disclosed, not hidden

| | Mean | Median | P90 | Max |
|---|---|---|---|---|
| **Retrieval** (candidate gen + rerank, ms) | 416.3 | 405.5 | 645.3 | 2,999.4 |
| **Generation** (ms) | 7,266.1 | 6,106.2 | 11,730.8 | 19,851.6 |
| **End-to-end** (ms) | 7,682.4 | 6,516.4 | 12,370.2 | 20,327.2 |

Retrieval overhead is small relative to generation (~5.4% of end-to-end latency on average) but
real and reported, not hidden. **Generation latency is substantially lower than E05's**
(mean 7,266ms vs. E05's 12,764ms; max 19,852ms vs. E05's 84,039ms) — a direct, expected
consequence of E07's much shorter contexts.

### Token reduction vs. E05 (both real, measured)

| Statistic | E05 | E07 | Reduction |
|---|---|---|---|
| Mean | 2,252.7 | 1,176.8 | **47.7%** |
| Median | 2,045.5 | 1,191.5 | **41.8%** |
| P90 | 3,945 | 1,341 | **66.0%** |

(Slightly smaller than Stage A's raw-retrieved-context-only estimate of 54.8%/49.4%/70.2%,
since these totals include the fixed system-prompt/wrapper overhead, which is a larger fraction
of E07's already-short prompts — the underlying retrieved-context compaction is unchanged.)

### E05 vs. E07 matched metric table

| Metric | E05 (Full Context) | E07 (RAG) | Delta (E07−E05) |
|---|---|---|---|
| Accuracy | 40.0% | 43.3% | **+3.3pp** |
| Macro-F1 | 0.397 | 0.431 | **+0.034** |
| Entailment Recall | 48.0% | 34.0% | −14.0pp |
| Contradiction Recall | 28.0% | 42.0% | **+14.0pp** |
| NotMentioned Recall | 44.0% | 54.0% | **+10.0pp** |
| Joint success (overall) | 28.0% | 33.3% | **+5.3pp** |
| Strict parse rate | 94.0% | **100.0%** | **+6.0pp** |
| Usable parse rate | 100.0% | 100.0% | 0 |
| Evidence Recall | 25.0% | 29.0% | +4.0pp |
| Mean input tokens | 2,252.7 | 1,176.8 | **−47.7%** |
| Median input tokens | 2,045.5 | 1,191.5 | −41.8% |
| P90 input tokens | 3,945 | 1,341 | −66.0% |
| Mean generation latency | 12,764ms | 7,266ms | **−43.1%** |
| Median generation latency | 10,174ms | 6,106ms | −40.0% |
| P90 generation latency | 22,214ms | 11,731ms | −47.2% |

**E07 improves on E05 on nearly every classification and efficiency metric simultaneously**,
with one clear exception (Entailment Recall, −14pp) — see the case-transition and statistical
analysis below before drawing a conclusion.

### Case-level transitions

**Overall**: E05-wrong→E07-correct **24**, E05-correct→E07-wrong **19**, both-correct 41,
both-wrong 66. Recovery outnumbers regression (24 vs. 19), a real but modest margin.

**Contradiction only**: E05-wrong→E07-correct **11**, E05-correct→E07-wrong **4**, both-correct
10, both-wrong 25. **Recovery outnumbers regression nearly 3-to-1** on Contradiction
specifically — the strongest directional signal in this comparison.

### Paired statistical analysis

**McNemar's exact test (overall)**: b=19 (E05-only-correct), c=24 (E07-only-correct),
n_discordant=43, **p=0.542 — not significant at α=0.05.**

**McNemar's exact test (Contradiction subset)**: b=4, c=11, n_discordant=15, **p=0.118 — not
significant at α=0.05**, though the 11-vs-4 raw split (2.75-to-1) is the most suggestive
directional signal in this comparison.

**Paired bootstrap (10,000 resamples), accuracy delta (E07−E05)**: point estimate **+3.3pp**,
**95% CI [−5.3pp, +12.0pp]** — the interval includes zero, consistent with the non-significant
McNemar result.

**Paired bootstrap, Contradiction Recall delta (E07−E05)**: point estimate **+14.0pp**, **95% CI
[0.0pp, +28.0pp]** — the interval's lower bound touches exactly zero. This is a borderline,
suggestive-but-not-conclusive result: at n=50 Contradiction cases, the data cannot rule out "no
real difference," but every measure (raw transitions, McNemar's discordant-pair ratio, and the
bootstrap point estimate) points the same direction.

**Per the brief's explicit instruction: no significance is manufactured from this.** At n=150
overall (and n=50 for Contradiction), this comparison is honestly underpowered to reach
conventional significance even for an effect of this apparent size — exactly as flagged as a
risk in Stage A section 11. The correct reading is: **a real, consistent, multi-metric
directional advantage for E07 that does not (yet) clear a formal significance bar**, not "no
effect" and not "proven effect."

### Failure analysis (families, not forced)

| Count | Family |
|---|---|
| 37 | NotMentioned overprediction, evidence was present (model saw the right text, still defaulted to NotMentioned) |
| 22 | Reasoning failure, evidence present (wrong label despite correct, located evidence) |
| 18 | Evidence paraphrasing |
| 5 | Retrieval miss → NotMentioned overprediction (evidence genuinely absent) |
| 3 | Exception/carve-out candidate (keyword co-occurrence, not a causal claim) |

The dominant pattern (37+22=59 of 99 non-evidence-selection errors, 60%) is the model
under-committing to a label it had correct evidence for — a genuine reasoning/calibration
issue, not a retrieval or evidence-formatting problem. This is consistent with, and adds detail
to, the same E01-Oracle-predicted "reasoning is the bottleneck" story E05 also showed.

### Representative cases

- **E05-wrong→E07-correct** (retrieval helped): `train::88::nda-2`, `train::106::nda-2`,
  `train::178::nda-20` — all gold Contradiction, all predicted NotMentioned under full context,
  correctly predicted Contradiction once retrieval isolated the relevant clause.
- **E05-correct→E07-wrong** (retrieval hurt): `train::92::nda-17`, `train::92::nda-20`,
  `train::141::nda-7` — all gold Contradiction, correctly predicted under full context but
  predicted NotMentioned once only the top-5 retrieved excerpts were shown (plausibly missing
  surrounding context that made the contradiction clear in the full document, even though
  `retrieval_v1`'s own coverage check confirms the gold span WAS present in the retrieved
  context for these cases — a reasoning-limited regression, not retrieval-limited).
- **Retrieval-limited failure**: `train::438::nda-2` (Contradiction→NotMentioned, gold evidence
  absent from the top-5 context).
- **Reasoning-limited failure**: `train::88::nda-1` (Contradiction→NotMentioned, evidence
  present).
- **Evidence-selection failure**: `train::161::nda-7` (correct Contradiction label, invalid/
  paraphrased evidence).

Full detail: `results/rag_failure_analysis.csv` (150 rows).

### Interpretation (per the predeclared rule — all outcomes were valid)

E07 shows the **"B, with directional lean toward A"** outcome from the predeclared interpretation
framework: quality is not statistically distinguishable from E05 at this sample size, but it is
consistently better in the same direction across nearly every metric (accuracy, Macro-F1,
Contradiction Recall, NotMentioned Recall, joint success, strict-parse reliability), AND
efficiency is substantially and unambiguously better (47.7% mean token reduction, 43.1% mean
generation-latency reduction). **Retrieval earns itself at minimum as a clear efficiency win,
with a real but not-yet-statistically-confirmed quality improvement**, most concentrated in
Contradiction Recall (+14pp, CI touching zero) — not proof that "RAG beats full-context," but a
substantially stronger case for `retrieval_v1` than a coin flip. **`retrieval_v1` was not
altered in response to these results.**

### Final `A2_standard_rag_v1` freeze

Recorded in full in `config.yaml`'s `frozen_a2` block: `retrieval_v1` (unmodified),
`classification_prompt_v1` (unchanged), model + tag, output schema, parser, evidence validator,
manifest, full metrics, latency/token profile. **"Frozen" means a reproducible architecture
configuration for later comparison (E12) — not a claim that A2 is production-ready.** No change
was made to `retrieval_v1`, the prompt, the parser, the model, or the timeout in response to
these results.

### Files created this pass

- `scripts/run_e07_standard_rag.py` (full 150-case runner — verifies the frozen manifest and
  retrieved-context artifact, re-runs retrieval live per case and asserts it matches the frozen
  artifact exactly, measures real retrieval/generation/end-to-end latency separately).
- `scripts/analyze_e07_standard_rag.py` (classification/structured-output/evidence/joint/
  retrieval-aware-failure analysis).
- `scripts/compare_e05_e07.py` (matched paired comparison: metric table, case transitions,
  McNemar's exact test, paired bootstrap CI).
- `experiments/E07_standard_rag/results/run_E07_A2_train_cases.jsonl` (150 fully-traceable
  records), `run_E07_A2_train.json`, `run_E07_A2_train_wall_seconds.json`,
  `rag_failure_analysis.csv`, `e05_vs_e07_paired_comparison.json`.
- `experiments/E07_standard_rag/E07_standard_rag.ipynb` (21-section notebook, executed, zero
  errors).

**Not done, and not authorized**: E08, DEV/TEST access, any hosted model call, agent work, or a
commit.
