# E09 — Agent Justification After Stronger Model — STAGE A (audit + design proposal only)

**No model call has been made. No agent has been built. `retrieval_v1`, `classification_prompt_v1`,
and E08B's GPT-5-mini results are all read-only inputs.** This document verifies E08B's exact
residual counts from raw artifacts, audits all historical (T-series) agent-related code as
hypothesis-generating prior art, and proposes the full E09 diagnostic design: failure taxonomy,
manual-review population, oracle-action fields, candidate runtime-observable signals, a
signal-evaluation methodology across all 150 cases, an Oracle Agent Opportunity Ceiling
calculation, and a cost/complexity decision framework.

## 1. Research question

"After upgrading Standard RAG to GPT-5 mini, do the remaining failures contain a meaningful,
runtime-observable subset that requires case-dependent information acquisition and therefore
justifies a selective agent?" E09 is a justification gate, not agent implementation, tool-policy
optimisation, prompt engineering, model selection, or retrieval tuning.

## 2-5. Exact residual counts (verified from raw E08B artifacts, not aggregate percentages)

Computed directly from `experiments/E08B_stronger_model_diagnostic/results/gpt5mini_failure_analysis.csv`:

| Count | Value |
|---|---|
| Classification-wrong | **32** |
| Joint-fail (total residual population) | **39** |
| Correct-label but joint-fail | **7** (39 − 32) |
| Contradiction classification-wrong | **12** |
| Contradiction joint-fail | **15** |

All match the numbers stated in the kickoff message exactly. 39 = 32 + 7 confirmed by direct
count, not inferred.

## 6-7. Historical agent audit (T-series prior art — hypothesis-generation only)

Audited `pipeline/agent.py`, `pipeline/agent_tools.py`, `pipeline/confidence.py`,
`prompts/agent_step_v1.txt`/`agent_step_v2.txt`, `data/agent_experiment.json`, and
`docs/decisions.md`'s ADR-005 through ADR-009. Full inventory in `config.yaml`'s
`historical_agent_audit` block; summary:

| Component | Read-only? | Reusable? | Key risk |
|---|---|---|---|
| Agent loop (`pipeline/agent.py`) | Yes | Pattern only (step/time/token limits + duplicate-call detection + fallback-to-classify) | ~21% duplicate-loop rate, never root-caused |
| 5 tools (`pipeline/agent_tools.py`) | Yes, confirmed no write/mutation anywhere | Pattern only (5-tool "why retrieval missed it" taxonomy) | `search_exceptions` exists specifically for carve-out patterns but has a documented **100% (4/4) failure rate** on exactly those golden-battery cases — a tool existing is not evidence it works |
| Confidence routing (`pipeline/confidence.py`) | Yes | Pattern only ("validate the signal isn't circular") | (1) originally circular (C-1: rule match fed into RAG context AND the routing check); (2) no signal ever cleared 0.7 AUROC — confidence gating is unsolved prior art, not something to reuse as a working signal |
| Agent experiment schema (`data/agent_experiment.json`) | n/a | Schema directly reusable for E09's own logging | — |

**Most important finding**: ADR-007's dev-sample (67 cases) and 500-case T041-subsample results
showed agent recovery beating regression ~2:1 (McNemar p=0.51, then p=0.058 — neither
significant), the stated basis for including that agent. But recomputed against the **full
2,091-case test set**, the result **reverses**: regression (87) now exceeds recovery (65), and
RAG+agent's overall accuracy (77.7%) falls **below** plain RAG's (78.7%). McNemar p=0.088, still
not significant either direction, but the point estimate flipped, not just weakened. Disclosed
honestly in that project's own ADR-007, not retroactively reversed.

**Direct implication for E09**: prior art is read-only-confirmed safe as a *reference pattern*
(control-loop design, tool taxonomy), but its own outcome evidence is a cautionary tale, not a
success story to imitate — a dev-sample agent-inclusion decision did not survive full-scale
re-measurement in this same codebase before. E09 must not silently inherit the old architecture,
confidence signal, or tool set, and any eventual A3 (E10) must budget for a larger-scale
validation than TRAIN_ARCH_v1's 150 cases before treating an inclusion decision as final.

## 8. Proposed final failure taxonomy (for the 39 GPT joint failures)

`STATIC_PIPELINE_FIXABLE` / `DYNAMIC_INFORMATION_ACQUISITION` (the main A3 candidate) /
`MODEL_REASONING_LIMITED` / `EVIDENCE_SELECTION_LIMITED` (resolved into static/dynamic/reasoning
per case, same discipline E08 used) / `RETRIEVAL_FILTERING_LIMITED` / `OUTPUT_PROTOCOL` (expect
0 — E08B had 150/150 strict parse) / `AMBIGUOUS_IRREDUCIBLE` (no forced agentic label).

**Strict 6-part agentic-justification test** (all must hold for `DYNAMIC_INFORMATION_ACQUISITION`):
current context insufficient/ambiguous; additional info exists that could change the decision; the
correct next action is case-dependent; the action cannot be replaced by one fixed deterministic
rule; an inference-time observable signal exists; the action changes what the model sees. "Think
again" / "reason more carefully" explicitly does **not** qualify.

## 9. Proposed manual-review population

**All 39 GPT joint failures — no sampling** (32 classification-wrong + 7 correct-label/joint-fail),
matching E08's own precedent of exhaustively reviewing all 54 wrong-evidence cases and all 29
Contradiction failures rather than sampling. Contradiction subset: all 15 Contradiction joint
failures, reviewed within the same pass.

## 10. Proposed oracle-action fields (evaluator-side only)

`oracle_action_needed` ∈ {none, expand_final_k, retrieve_definition, follow_cross_reference,
retrieve_adjacent_clause, search_exception, search_specific_term, compare_conflicting_clauses,
retrieve_additional_candidate, other}, plus `oracle_action_target`, `oracle_action_available`,
`static_fix_possible`, `dynamic_action_required`, `recoverable_in_principle` — mirrors E08's
schema. **Explicit exclusion, preserved**: gold label, gold span, "GPT was wrong," and
evaluator-known missing evidence must never be used as a *runtime* trigger — these fields are
evaluator-only diagnosis.

## 11. Candidate runtime-observable signals

Explicit section cross-reference cue; defined-term-referenced-but-definition-absent; exception/
carve-out cue; conflicting retrieved clauses; incomplete conditional clause; evidence-validator
failure; weak/flat reranker score margin; evidence not directly addressing the requirement;
multiple contradictory candidate clauses. **Excluded as triggers** (never inference-time-legal):
gold label, gold span, "GPT was wrong," evaluator-known missing evidence.

**Two candidates were zero-cost pre-checked this pass** (local text search / cached rerank scores
only, no model calls — same precedent as E08's own Stage A pilot diagnostics):

- **Exception/carve-out cue, re-evaluated against GPT (not assumed to carry over from Qwen)**:
  present in **110/111 (99.1%) of GPT successes** and **39/39 (100.0%) of GPT failures** — overall
  prevalence 99.3% of all 150 cases. **Confirmed still useless as a standalone trigger**,
  consistent with E08's finding on Qwen (62/63 errors), now independently verified against GPT
  rather than assumed to carry over.
- **Weak/flat reranker top1–top2 score margin**: success-case mean margin 1.584 (median 1.002) vs
  failure-case mean margin 1.705 (median 1.288) — **not clearly discriminating on its own**.
  Consistent with E08's own earlier finding that retrieval-score-based signals underperform.
  Not ruled out as one component of a combined signal, but not viable alone.

## 12. Signal-evaluation methodology (all 150 cases, not just failures)

Per candidate signal: true positives (signal present AND case is genuinely
`DYNAMIC_INFORMATION_ACQUISITION` per the independent manual-review taxonomy — not circular),
false positives, false negatives, true negatives, precision, recall, escalation rate. No grid
search across dozens of combinations — descriptive diagnostics on hand-picked candidates and at
most a small combined signal, per the explicit instruction.

## 13. Proposed Oracle Agent Opportunity Ceiling calculation

If every case manually assigned `DYNAMIC_INFORMATION_ACQUISITION` were counterfactually fixed
(assume the correct action would have produced the correct label+evidence), recompute accuracy /
Contradiction recall / joint success as an explicit **ORACLE AGENT OPPORTUNITY CEILING** — labeled
as a ceiling, never as an expected result. Caveat, informed by the historical-agent-audit finding
above: real agent recovery in the T-series prior art fell well below its own dev-sample ceiling
and reversed entirely at full scale — this ceiling answers "could A3 matter enough to justify
implementation," not "will A3 achieve this."

## 14. Proposed cost/complexity decision framework

Factors (no fixed numeric threshold invented, per instruction): fraction of **all 150** cases
requiring escalation (not just fraction-of-failures — a 150-case denominator is what determines
real operational cost, e.g. "8% of all cases" vs. "31% of failures"), potential joint-success
uplift, Contradiction-risk uplift, extra model/retrieval-tool calls per escalated case, latency
impact, hosted cost impact, implementation complexity, new-failure-surface risk. E09 proposes the
framework's factors; a final numeric threshold is not proposed here.

## 15. Files to create / change

**Stage A (this commit)**: `experiments/E09_agent_justification/{README.md, config.yaml,
summary.md, results/}` (empty, for Stage B). No code touched, no model call made.

**Stage B (after approval)**:
- `scripts/manual_review_e09_gpt_residuals.py` (loads the 39 cases + full 150-case context;
  **zero model calls** — local BM25/reranker re-query only where needed, mirroring E08's
  reranker-limited pilot).
- `experiments/E09_agent_justification/results/gpt_residual_failure_analysis.csv` (39 rows, full
  taxonomy + oracle-action fields, same schema shape as E08's `rag_failure_analysis.csv`).
- `experiments/E09_agent_justification/results/signal_prevalence_150case.json`.
- `experiments/E09_agent_justification/results/oracle_agent_opportunity_ceiling.json`.
- `experiments/E09_agent_justification/results/e09_decision.json` (final A/B/C decision).
- `experiments/E09_agent_justification/E09_agent_justification.ipynb`.

## 16. Expected effort

Manual review of 39 cases (same per-case depth as E08's 73-case review: requirement, top-5
context, GPT prediction/evidence, gold label, gold evidence evaluator-side, BM25 top-20 pool,
rerank ranks) is the dominant time cost. All computation is local/free — **zero new hosted or
local model calls** are needed anywhere in E09, including Stage B.

## 17. Unresolved issues

1. **TRAIN_ARCH_v1 is only 150 cases** — any E09 conclusion (Oracle Agent Opportunity Ceiling,
   signal precision/recall) is a dev-sample estimate. The T-series prior art's own full-2,091-case
   reversal (section 6-7) is a direct, concrete warning that dev-sample agent conclusions have
   **not** held up at scale in this exact codebase before — E10 (if A3 proceeds) must budget for a
   larger-scale validation, not treat E09's numbers as final.
2. Exception-carveout-cue and score-margin were both pre-checked and found weak as standalone
   signals — Stage B should not re-derive this, but should still test them as components of a
   combined signal before fully discarding either.
3. The T-series confidence-routing signal (rule-agreement) is task/dataset-specific to that
   project's own rule baseline and does not carry over to reconstruction-v2's architecture — E09
   must derive its own candidate signals from GPT-5-mini's actual residual failures.
4. GPT-5-mini still uses Qwen-selected `classification_prompt_v1` (P0) — whether this is itself
   suboptimal for GPT is an explicitly separate, unresolved downstream question, deliberately not
   mixed into E09's agent-justification analysis.

Stage A ends here. No model call has been made, no agent has been built. Awaiting explicit
approval to proceed to Stage B.

## Stage B result (executed — manual review of all 39 residuals, no sampling)

`scripts/build_e09_residual_review_bundle.py` assembled the full diagnostic bundle per case
(requirement, GPT prediction/evidence, final top-5 context, local BM25 top-20 re-query, gold
label/evidence — zero model calls). Every one of the 39 cases was read directly and assigned a
primary bucket in `scripts/analyze_e09_agent_justification.py`'s `MANUAL_TAXONOMY`, with a
written evidence-based note per case (full detail: `results/gpt_residual_failure_analysis.csv`).

**Failure-bucket decomposition** (of 39 failures / of all 150 cases):

| Bucket | Count (of 39) | % of 39 | % of 150 |
|---|---|---|---|
| MODEL_REASONING_LIMITED | 26 | 66.7% | 17.3% |
| RETRIEVAL_FILTERING_LIMITED | 6 | 15.4% | 4.0% |
| EVIDENCE_SELECTION_LIMITED | 6 | 15.4% | 4.0% |
| DYNAMIC_INFORMATION_ACQUISITION | **1** | 2.6% | **0.67%** |
| OUTPUT_PROTOCOL / AMBIGUOUS_IRREDUCIBLE | 0 | 0% | 0% |

**Key qualitative findings**: 26 MODEL_REASONING_LIMITED cases split into two sub-patterns — (a)
11 NotMentioned false-positives where GPT quotes a real, verbatim, topically-relevant
definitional clause and over-generalizes to a specific hypothesis it doesn't actually address (7
of these share hypothesis nda-1, a systematic "expressly identified" marking-requirement
confusion); (b) 12 Contradiction cases where GPT's own returned evidence *already overlaps gold*
(the correct clause was found and quoted) but the final label is still wrong — 7 of these share
hypothesis nda-17, a systematic conflation of a general "disclosure" exception with a specific
"copying" prohibition. **All 6 RETRIEVAL_FILTERING_LIMITED cases have gold evidence within the
BM25 top-20 pool** (ranks 1–9) but cut by the reranker before the final top-5 — identical in kind
to E08's own reranker-limited diagnostic, confirming the gap is architectural, not model-specific.
**Only 1 case (`train::273::nda-1`) passes all 6 strict agentic criteria**: its gold evidence is
itself a cross-reference to undefined "paragraphs (a) to (c) of the definition of Confidential
Information," a concrete, inference-time-observable signal.

**Correct-label/joint-fail (7 cases)**: 6 EVIDENCE_SELECTION_LIMITED (correct label, evidence
incomplete/invalid/partial-coverage) + 1 RETRIEVAL_FILTERING_LIMITED (`train::438::nda-2`, label
correct but gold evidence was cut before top-5). None require dynamic action — the label was
already right in every case.

**Contradiction residuals (15 cases)**: 12 MODEL_REASONING_LIMITED, 2 EVIDENCE_SELECTION_LIMITED,
1 RETRIEVAL_FILTERING_LIMITED. Of the 12 Contradiction classification-wrong cases, **all 12 had
gold evidence already present in the final top-5** — Contradiction's residual risk is entirely a
reasoning problem on this sample, not an information-acquisition one.

**Signal evaluation across all 150 cases** (not just failures — pre-declared, no post-hoc
grid-search): exception/carve-out cue re-confirmed useless (99.1% success / 100% failure
prevalence). Reranker score margin re-confirmed non-discriminating (means 1.584 vs 1.705). The
one signal derived directly from the genuinely dynamic case — cross-reference-to-named-provision
— has **precision 6.7%, recall 100%, escalation rate 10%** (TP=1, FP=14, FN=0, TN=135): gating an
agent on this signal would investigate 14 unnecessary cases for every 1 it correctly helps.

**Static Pipeline Opportunity Ceiling** (fix all 6 RETRIEVAL_FILTERING_LIMITED cases via a
deterministic top-k increase): joint success 74.0% → 78.0% (**+4.0pp**), accuracy → 82.0%.

**Oracle Agent Opportunity Ceiling** (upper bound, NOT expected performance — fix the single
DYNAMIC_INFORMATION_ACQUISITION case only): joint success 74.0% → 74.67% (**+0.67pp**), accuracy →
79.33%. The static ceiling is **6x larger** than the agentic ceiling on this residual.

**Final E09 decision: A — A3 NOT JUSTIFIED.** The dominant residual (66.7% of failures) is
reasoning-limited with no information-acquisition fix available; the second-largest bucket
(retrieval-filtering) has a larger, cheaper, deterministic fix than any agent could offer; and the
one genuinely dynamic case's own best signal has 6.7% precision. Combined with the historical
T-series agent's full-scale reversal (recovery/regression flipped between the dev sample and the
full 2,091-case test set), the cost/complexity case for A3 is not supported by this evidence. This
is not a claim that an agent could never help — only that this residual, on this 150-case sample,
does not justify building one now. Full results: `results/gpt_residual_failure_analysis.csv`,
`results/signal_prevalence_150case.json`, `results/oracle_agent_opportunity_ceiling.json`,
`results/e09_decision.json`, `E09_agent_justification.ipynb`. Not committed — awaiting review.
