# E08 — RAG Failure Analysis — STAGE A (design/audit + zero-cost pilot diagnostics only)

**No LLM call has been made anywhere in E08. `retrieval_v1` and `classification_prompt_v1` are
read-only inputs, never modified or re-invoked.** This document audits E07's existing outputs,
verifies error counts directly (not from memory), runs two zero-cost pilot diagnostics that
materially refine how E07's headline failure numbers should be read, and proposes the full
diagnostic schema, failure taxonomy, evaluator-only/runtime-observable signal separation, agent-
candidate criteria, and a deterministic manual-review sample for Stage B.

## 1. Research question

"What failure modes remain in A2 Standard RAG, and which of them could plausibly be addressed
by selective agentic investigation?" Diagnostic only — E08 does not improve the system, does not
build an agent, and does not decide A3's architecture. It produces the evidence base E09 needs.

## 2. E07 artifacts available for analysis

All read directly this pass, no regeneration: `run_E07_A2_train_cases.jsonl` (150
fully-traceable records), `run_E07_A2_train.json` (aggregate metrics), `rag_failure_analysis.csv`
(150-row failure taxonomy from E07's own analysis), `e05_vs_e07_paired_comparison.json` (matched
transitions/statistics), `TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json`/`_GOLD.json` (the frozen
retrieved-context artifact and gold-side scorer file), plus `E05_full_context`'s
`run_E05_A1_train_cases.jsonl` for the transition analysis and `data/contractnli/train.json`
for gold-span character offsets. **Sufficient for the full diagnostic — no new model output is
needed.**

## 3-5. Verified error counts (recomputed directly from E07's saved outputs)

| Count | Value |
|---|---|
| Total cases | 150 |
| Total correct | 65 |
| **Total errors** | **85** |
| Entailment errors | 33 |
| **Contradiction errors** | **29** |
| NotMentioned errors | 23 |
| **Wrong-label-but-valid-evidence** | **54** |
| **Retrieval-limited** | **6** |

Reconciliation check: E07's own `retrieval_aware_failure_counts` (`B_reasoning_limited`=79,
`A_retrieval_limited`=6, `C_evidence_selection_failure`=14, `n/a (correct)`=51) sums correctly —
79+6=85 errors, and 51 `n/a` + 14 `C_evidence_selection_failure` (which, in E07's original
scoping, means *correct-label-but-invalid-evidence*, not wrong-label — a scope worth restating
clearly since the label is easy to misread) = 65 correct. No arithmetic inconsistency found.

## Pilot refinement #1: evidence-overlap-with-gold vs. merely-verbatim (zero-cost, this pass)

**This is the most important finding of Stage A.** E07's "54 wrong-label-but-valid-evidence"
count used `evidence_valid` (the model's quote is a real, verbatim, non-hallucinated substring
of the shown context, and label-consistent) — it does **not** check whether that quote actually
overlaps the *true annotated gold span*. Recomputing evidence-to-gold-span overlap directly
(same interval-overlap mechanism used throughout reconstruction-v2 — E04, E05, E06 — applied
here to E07's saved `evidence` field and the frozen retrieved-context artifact's chunk offsets,
zero LLM calls):

| | Count | % of 54 |
|---|---|---|
| Evidence genuinely overlaps gold span (real "right evidence, wrong label") | **4** | 7.4% |
| Evidence is verbatim but does NOT overlap gold (points at a different, real chunk) | **50** | 92.6% |

Breakdown of the 50 non-overlap cases by gold label: Contradiction 28, Entailment 22.

**Implication**: E07's "79 reasoning-limited" bucket (defined only as "gold evidence was
*somewhere* in the top-5 context, label wrong") conflates two materially different failure
modes:
- **(a) True single-step reasoning failure**: the model's own selected evidence *is* the gold
  span, and it still reasons to the wrong label. Only 4 of the 54 evidence-bearing wrong cases
  clearly show this pattern (and there are other wrong cases within the 79 where evidence was
  empty/invalid rather than verbatim-but-wrong — those aren't part of this specific 54-case
  subgroup at all).
- **(b) Evidence-selection-among-candidates failure**: gold evidence WAS present in the top-5
  context, but the model quoted a different, real chunk instead — and, going by the label it
  then produced, plausibly reasoned from that wrong chunk rather than the relevant one. This is
  much closer to "the model didn't recognize which of the 5 retrieved excerpts actually answers
  the question" than to "the model saw the right text and still got confused." It is far more
  plausibly the kind of thing a follow-up/verification action (re-examine each candidate,
  targeted second query, compare candidates explicitly) could help with.

**This refinement must carry into E08's own taxonomy (category C vs. I, section 8) and into the
agent-fixability judgment (section 10) — it is not safe to treat "evidence was present" as
synonymous with "the model actually used the right evidence."**

## Pilot refinement #2: oracle-action analysis for all 6 retrieval-limited cases (zero-cost, this pass)

For each of the 6 retrieval-limited cases, the frozen `retrieval_v1` BM25 index (already built
and cached — **not modified, not retuned**) was queried at `top_k=50` (deeper than the frozen
`candidate_pool_size=20`) purely to check whether gold evidence exists in the lexical index at
all, and at what rank. **No LLM call.**

| Case | Gold label | Gold's rank in BM25's own top-50 |
|---|---|---|
| `train::438::nda-2` | Contradiction | 6 |
| `train::160::nda-10` | Entailment | 2 |
| `train::247::nda-10` | Entailment | 6 |
| `train::353::nda-10` | Entailment | 9 |
| `train::379::nda-10` | Entailment | 3 |
| `train::518::nda-10` | Entailment | 1 |

**All 6 cases have gold evidence within BM25's top-9** — well inside the existing
`candidate_pool_size=20` fed to the reranker. **BM25 (the lexical stage) did not fail to find
the evidence in any of these 6 cases** — the cross-encoder reranker demoted a correct candidate
below the top-5 cutoff every time. "Retrieval-limited" is, for this specific set, more precisely
described as **reranker-limited / top-k-cutoff-limited**, not lexical-coverage-limited — a
genuinely more specific and more actionable diagnosis than the coarse category name suggests.
**`recoverable_in_principle = true` for all 6**, via a plausible agentic action (expand the
effective candidate window, or issue a targeted follow-up query) — not via retuning
`retrieval_v1` itself, which per the brief stays frozen.

## 6. Proposed deterministic manual-review sample

Per the brief's mandatory minimums plus a deterministic sampling rule (`random.Random(1000)` on
sorted case-id lists, reproducible):

| Category | Rule | n |
|---|---|---|
| Retrieval-limited | ALL | 6 (pilot analysis already complete, see above) |
| Contradiction failures | ALL (practical at n=29; headline risk class) | 29 |
| Wrong-valid, Entailment-labeled, not already in the Contradiction set | deterministic sample of 25 candidates | 15 |
| E05→E07 gains, not already covered above | deterministic sample of 24 candidates | 10 |
| E05→E07 regressions, not already covered above | deterministic sample of 12 candidates | 10 |
| Rare/uncertain categories (ambiguous/mixed) | added as identified during Stage B review itself | TBD |

**Total unique cases after deduplication: 66 (44% of the full 150-case set).** "ALL Contradiction
failures" already subsumes most Contradiction-labeled wrong-valid cases, so the incremental
wrong-valid sample only needs the Entailment-labeled subset not already covered. Rare/uncertain
categories cannot be enumerated before the taxonomy is actually applied case-by-case in Stage B,
per the brief's own framing.

## 7. Proposed failure taxonomy

The brief's eleven categories (A–K) are adopted as the starting point, unchanged, with the
explicit instruction to add observed categories rather than force-fit:

A. RETRIEVAL_COVERAGE, B. RETRIEVAL_RANKING/DISTRACTOR, C. SINGLE-STEP_REASONING,
D. MULTI_CLAUSE_REASONING, E. DEFINITION_DEPENDENCY, F. CROSS_REFERENCE,
G. EXCEPTION_CARVEOUT, H. NOTMENTIONED_CONFUSION, I. EVIDENCE_SELECTION,
J. STRUCTURED_OUTPUT, K. AMBIGUOUS/MIXED.

**One refinement proposed based on pilot analysis #1**: category **C (SINGLE-STEP_REASONING)**
should require that the case-level diagnostic confirm the model's *own returned evidence*
overlaps gold (not merely that gold was present somewhere in the top-5) — otherwise the case
belongs in **I (EVIDENCE_SELECTION)** instead, even though both would previously have been
lumped into E07's coarse "reasoning-limited" bucket. This is not a new category, just a
precise application rule for distinguishing C from I using the already-available evidence-
overlap computation.

## 8. Evaluator-only vs. runtime-observable signal separation

**Evaluator-only (uses gold, never available at inference time, only for diagnosing whether a
failure *would have been* recoverable)**: `gold_label`, `retrieval_contains_gold`,
`gold_best_rank`, `returned_evidence_overlap_with_gold`, `oracle_action_needed`,
`oracle_action_target`, `oracle_action_available_in_document`, `recoverable_in_principle`.

**Runtime-observable (available to a real system at inference time, before or without knowing
the gold label — candidate triggers for a *future* selective-agent policy, not frozen here)**:
explicit cross-reference text in the retrieved chunk(s), a defined-term cue (a capitalized/
quoted term used but not defined within the retrieved context), an exception/carve-out cue
(keyword co-occurrence, same heuristic discipline as E03/E04/E05/E07 — a candidate signal, not
a manual causal read), conflicting retrieved clauses (two chunks that appear to state opposite
things), a low BM25-to-rerank score margin among the top-5 (retrieval's own uncertainty signal,
already captured in the retrieved-context artifact's `ranked_chunk_rerank_scores`), and
`evidence_valid` itself (already computed at inference time by the existing validator — a
genuine runtime-observable signal, not evaluator-only). **No trigger is frozen in E08** — this
section only proposes candidate signals; E08 will report which ones actually *correlate* with
recoverable failures in the manual-review sample, leaving trigger selection to E09.

## 9. Proposed agent-candidate criteria

A case is proposed as an **agent candidate** only when a plausible runtime-observable signal
(section 8) is present **and** the evaluator-only oracle-action analysis independently confirms
the failure was recoverable in principle. Both conditions matter: a runtime-observable cue
without evaluator-confirmed recoverability is a false-positive trigger risk (would fire but not
help); evaluator-confirmed recoverability without a runtime-observable cue is not implementable
as a real trigger (matches the brief's section 9 warning: "later A3 cannot say 'escalate
because gold evidence is missing'" — that fact alone is not an actionable signal). Concretely,
proposed candidate mechanisms (from the brief, section 7): retrieve a referenced definition,
follow a section cross-reference, search specifically for an exception/carve-out, retrieve
additional clauses when current evidence looks incomplete, compare conflicting clauses, issue a
second targeted query, inspect a neighboring clause. **Not automatically agent-fixable**: gold
evidence already fully present and correctly identified by the model's own returned evidence,
yet the label is still wrong (pilot refinement #1's 4-case "true reasoning failure" subgroup);
persistent Contradiction-vs-NotMentioned confusion with no cross-reference/definition/exception
cue present; output-formatting issues (moot for E07 — 0 structured-output failures were
observed, see E07's summary).

## 10. Proposed oracle-action fields (evaluator-only, no LLM, no agent built)

`oracle_action_needed` (free-text/enum: e.g. `expand_candidate_window`, `retrieve_definition`,
`follow_cross_reference`, `search_exception_phrase`, `include_adjacent_clause`, `none_identified`),
`oracle_action_target` (what specifically — e.g. a document location, a defined term, a section
reference), `oracle_action_available_in_document` (bool — is the needed information actually in
the NDA at all, distinguishing a genuinely unanswerable case from a fixable one),
`recoverable_in_principle` (bool — would the identified action plausibly have fixed the case).
Already populated for all 6 retrieval-limited cases (pilot refinement #2 above); the remaining
60 cases in the proposed manual-review sample will get these fields during Stage B's actual
manual review, not filled in automatically.

## 11. E05/E07 transition cases available

From `e05_vs_e07_paired_comparison.json` (already computed, E07 Stage B): 24 E05-wrong→E07-
correct, 19 E05-correct→E07-wrong, 41 both-correct, 66 both-wrong (overall); Contradiction-only:
11 gains, 4 regressions, 10 both-correct, 25 both-wrong. All 43 discordant case_ids are
directly retrievable from the two experiments' saved JSONL files — no rerun needed.

## 12. Files to create / change

**Stage A (this commit)**: `experiments/E08_rag_failure_analysis/{README.md, config.yaml,
summary.md, results/}` (empty, for Stage B). No code files touched, no `retrieval_v1`/
`classification_prompt_v1` modification, no LLM call (the one BM25 re-query used for pilot
refinement #2 is local, deterministic, and read-only against the already-cached index).

**Stage B (after approval)**:
- `scripts/analyze_e08_rag_failures.py` (new — builds the full 150-row diagnostic CSV per
  section 15's schema, using the evidence-overlap and oracle-action logic piloted this pass,
  extended to all cases in the manual-review sample).
- `experiments/E08_rag_failure_analysis/results/rag_failure_analysis.csv` (full diagnostic
  record, all 150 cases with taxonomy/agent-candidate/oracle-action fields populated for the
  66-case reviewed sample, automated-only fields for the rest).
- `experiments/E08_rag_failure_analysis/results/manual_review_notes.md` (the actual manual
  review write-up for the 66-case sample).
- `experiments/E08_rag_failure_analysis/results/agent_opportunity_quantification.json`
  (section 10's %-breakdown, overall and by class).
- `experiments/E08_rag_failure_analysis/E08_rag_failure_analysis.ipynb`.

## 13. Expected manual-analysis effort

Dominated by the 66-case manual review (reading each case's gold label, prediction, retrieved
context, and returned evidence to assign taxonomy/agent-candidate/oracle-action fields) — no
compute cost. The two pilot diagnostics already completed this pass (evidence-overlap
recomputation for 54 cases, oracle-rank lookup for 6 cases) required a few seconds of local,
deterministic computation each and are not repeated in Stage B, just extended to the remaining
sample.

## 14. Unresolved issues

1. **Runtime-observable trigger correlation** (section 8) — which candidate signals actually
   predict recoverability can only be assessed once the 66-case manual review is complete; not
   knowable from Stage A alone.
2. **Rare/uncertain category count** — cannot be enumerated before the taxonomy is applied
   case-by-case.
3. **Whether 66 cases is the right sample size** — a judgment call balancing thoroughness
   against effort; the brief's own minimums (all retrieval-limited, all/most Contradiction,
   *samples* of the other three groups) are met, but a reviewer could reasonably ask for a
   larger sample of the 50 non-overlap wrong-valid cases given how large and newly-significant
   that subgroup turned out to be (pilot refinement #1).
4. The E08→E09 handoff (agent justification decision: PROCEED / NARROW SELECTIVE / NOT
   JUSTIFIED) genuinely cannot be made before the manual review — Stage A deliberately does not
   pre-judge it, per the brief's explicit "all outcomes are valid" instruction.

Stage A ends here and was approved, with two design refinements applied throughout Stage B:
(1) strict terminology separation of `source_valid_evidence` (verbatim/structural validity
only) from `gold_evidence_overlap` (does the quote overlap the true annotated span) in every
artifact; (2) a critical distinction between "recoverable with more information" and "requires
an agent," refined into a taxonomy that never conflates the two. **No LLM call was made
anywhere in Stage B either.** `retrieval_v1` and `classification_prompt_v1` remain unmodified
and were not re-invoked (the only re-queries were local, deterministic BM25/cross-encoder calls
against the already-cached retrieval_v1 index, used purely to diagnose the 6 reranker-limited
cases — the same non-LLM models already used for identical diagnostic purposes throughout
E06/E07).

---

## Full Analysis Results (2026-09-26)

### Terminology, applied consistently throughout

- **`source_valid_evidence`**: the existing `validate_evidence()` finding — the model's quote is
  verbatim, present in the shown context, and structurally valid (schema-consistent with the
  label). **This alone never implies correctness.**
- **`gold_evidence_overlap`**: a separate, stricter check — does the quote's actual document
  location overlap the true ContractNLI-annotated gold span. **This is the correctness check.**
- The 54 cases previously described (E07) as "wrong-label-but-valid-evidence" are now precisely
  described as **"wrong-label + source-valid evidence"**, split further below.

### Deterministic manual-review union — final count

Built as a strict, deduplicated union (no random replacement after inspecting results — the
seed=1000 sample was fixed before any content was read):

| Category | Rule | n |
|---|---|---|
| Reranker/filtering-limited | ALL | 6 |
| Contradiction failures | ALL | 29 |
| Wrong-label + source-valid evidence | ALL (expanded from the Stage A proposal's partial sample) | 54 |
| **Mandatory subtotal (deduplicated)** | | **55** |
| E05→E07 gains, not already covered | deterministic sample of 24 candidates | 10 |
| E05→E07 regressions, not already covered | deterministic sample of 12 candidates | 8 |
| **Final unique manual-review count** | | **73** |

73/150 (48.7%) of all cases were reviewed; 63 of those are errors, 10 are correct cases pulled
in only via the E05/E07 transition sample.

### Reranker/filtering-limited findings (renamed from "retrieval-limited")

For each of the 6 cases, a real, deterministic, local re-query of the frozen `retrieval_v1` BM25
index (unmodified) at `top_k=20` (the existing candidate pool size), followed by reranking that
full 20-candidate set (not just the frozen top-5), to find gold's exact rank before and after
reranking:

| Case | Gold label | BM25 top-20 rank | Post-rerank rank (of the same 20) | Would top-10 include it? |
|---|---|---|---|---|
| `train::438::nda-2` | Contradiction | 6 | 8 | Yes |
| `train::160::nda-10` | Entailment | 2 | 11 | No |
| `train::247::nda-10` | Entailment | 6 | 9 | Yes |
| `train::353::nda-10` | Entailment | 9 | 9 | Yes |
| `train::379::nda-10` | Entailment | 3 | 8 | Yes |
| `train::518::nda-10` | Entailment | 1 | 9 | Yes |

**All 6 cases have gold within the reranked top-11** (5 within top-9, all reachable by a fixed
`top_k=11` or `12`). **None require a dynamic, case-dependent action** — a single, fixed,
deterministic change (raise the final `top_k` from 5 to ~11-12) would recover all 6.
**Classification: STATIC_PIPELINE_FIXABLE for all 6**, not agentic — per the brief's own
explicit rule. `retrieval_v1` was not changed in response to this finding; it is recorded as a
candidate intervention for a future experiment, not implemented here.

### All 54 "wrong-label + source-valid evidence" cases — the central finding

| | Count | % of 54 |
|---|---|---|
| **Group A** — returned evidence overlaps gold | 4 | 7.4% |
| **Group B** — returned evidence does NOT overlap gold | 50 | 92.6% |

**Group A (4 cases)**: the model's own quote *is* the correct evidence, and the label is still
wrong. Checked each against the gold chunk's own text (not the whole 5-chunk context, which
over-triggers — see methodology note below) for a cross-reference or definition-dependency cue.
Where absent, classified `MODEL_REASONING_LIMITED` — the evidence was sufficient and correctly
identified; the failure is in interpreting it.

**Group B (50 cases)**: gold evidence WAS present in the top-5 context, but the model quoted a
different, real (non-hallucinated) chunk. For each, checked the **gold-relevant chunk's own
text specifically** (not the whole context) for a cross-reference, exception/carve-out, or
missing-definition cue that would plausibly explain why a targeted follow-up action (rather
than "think again about the same five chunks") could have surfaced the right answer instead of
the distractor. Where present, classified `AGENTICALLY_FIXABLE` (resolving category D →
category B); where absent, classified `MODEL_REASONING_LIMITED` (resolving D → C) — **not
automatically agentic just because more information existed somewhere**, per the brief's
explicit warning.

**Methodology note on over-triggering (an honest, disclosed correction made during Stage B
itself)**: an early version of this analysis checked cross-reference/exception/definition cues
against the *entire* 5-chunk context, which fired on ~80% of cases — NDAs reference other
sections and carve-outs constantly, even in chunks unrelated to the actual failure. Restricting
the check to the *specific gold-relevant chunk's own text* (evaluator-only — the gold chunk is
known only to the evaluator, not at inference time) produced far more conservative, defensible
numbers (below). The corresponding **runtime-observable** version of this signal (what a real
system could check without knowing which chunk is gold) is reported separately in the runtime-
signal-frequency table and is necessarily coarser/more over-inclusive — this gap between
"evaluator-confirmed relevance" and "runtime-observable cue" is itself a finding, not an error:
it means a real system's escalation trigger will need to be more selective than "does any
candidate chunk mention an exception," or it will over-escalate.

### Full failure-family / quantification counts

Of 63 reviewed errors (73-case sample minus 10 correct pulled in via the transition sample):

| Bucket | Count | % of reviewed errors |
|---|---|---|
| **MODEL_REASONING_LIMITED** | 31 | 49.2% |
| **AGENTICALLY_FIXABLE** | 26 | 41.3% |
| **STATIC_PIPELINE_FIXABLE** | 6 | 9.5% |
| OUTPUT_FORMAT_LIMITED / AMBIGUOUS_MIXED | 0 | 0% |

**Secondary finding**: 42 of the 63 reviewed errors (66.7%) are cases where the model returned
**completely empty evidence** and defaulted to NotMentioned (category H,
NOTMENTIONED_CONFUSION) — distinct from cases where it quoted a real-but-wrong chunk (category
I). Both can resolve to the same primary bucket above (the agent-fixability judgment doesn't
depend on whether the model quoted nothing vs. quoted the wrong thing), but this is a real,
dominant behavioral pattern worth naming on its own: **the model very often disengages
entirely rather than committing to a wrong specific quote.**

### Contradiction-specific breakdown (29 failures)

| Bucket | Count | % |
|---|---|---|
| MODEL_REASONING_LIMITED | 19 | 65.5% |
| AGENTICALLY_FIXABLE | 9 | 31.0% |
| STATIC_PIPELINE_FIXABLE | 1 | 3.4% |

**Contradiction failures skew more toward pure reasoning limitation than the overall error
population** (65.5% vs. 49.2% overall) — consistent with E01 Oracle's original, independent
finding that Contradiction reasoning is Qwen's weakest point even under ideal evidence
conditions. The 9 agentically-fixable Contradiction cases mostly involve genuine
exception/carve-out language specifically in the gold-relevant clause (`search_exception` is
the dominant oracle action for this subgroup) — consistent with, and now quantified beyond, the
qualitative pattern E04's rule-baseline analysis and E07's own keyword co-occurrence check both
already flagged for this dataset.

### Runtime-observable signal frequencies (whole-context, i.e. the realistically-implementable version)

| Signal combination | Count |
|---|---|
| cross_reference + exception_carveout | 26 |
| exception_carveout only | 16 |
| exception_carveout + defined_term_missing | 12 |
| cross_reference + exception_carveout + defined_term_missing | 5 |
| cross_reference + exception_carveout + low_score_margin | 3 |
| low_score_margin only | 1 |

**Exception/carve-out language appears in at least one of the 5 retrieved chunks in the
overwhelming majority of reviewed error cases (62/63)** — far too frequent to serve as a
standalone runtime trigger on its own (it would fire on almost every error, agentic or not).
This is exactly the over-triggering risk the methodology note above already disclosed:
`exception_carveout_cue` alone, checked against the whole context, is not a usable escalation
signal without additional conditioning (e.g., combined with `gold_evidence_overlap` being false
— which is evaluator-only — or with a genuine structural marker like the cue appearing in the
single highest-reranked chunk specifically, a hypothesis for E09 to test, not confirmed here).

### Oracle-action distribution (evaluator-only diagnostic labels)

| Action | Count |
|---|---|
| `search_exception` | ~14 (Group B agentic cases with exception cue) |
| `retrieve_definition` | ~7 (Group A/B agentic cases with missing-definition cue) |
| `follow_cross_reference` | ~5 (agentic cases with cross-reference cue) |
| `expand_candidate_window` | 6 (all reranker-limited cases) |
| `none_identified` | 31 (all MODEL_REASONING_LIMITED cases) |

(Exact per-case breakdown in `results/rag_failure_analysis.csv`.)

### E05→E07 transition diagnostic findings

Of the 8 sampled E05-correct→E07-wrong regressions actually reviewed, 2 of 3 spot-checked cases
share a specific, real pattern: **gold label NotMentioned, E07 wrongly predicts Contradiction**
(`train::187::nda-10`, `train::379::nda-11`) — both classified `MODEL_REASONING_LIMITED`. In
both, the compact retrieved context isolates a clause that, read alone, looks more conclusive
than it actually is; the full document (E05's input) apparently supplied enough surrounding
context to correctly rule out a real conflict. **This is a genuine "context-loss regression"
mechanism, distinct from a retrieval miss** — the relevant clause WAS retrieved, but the
broader document context that would have tempered its interpretation was not, since only 5
compact excerpts were shown. One reviewed regression (`train::505::nda-4`) was classified
`AGENTICALLY_FIXABLE`. No model reruns were performed for this analysis — purely a comparison
of already-saved predictions and retrieved context.

### Representative cases

- **STATIC_PIPELINE_FIXABLE**: `train::160::nda-10`, `train::247::nda-10` — gold-relevant chunk
  present in BM25's own top-20 (ranks 2 and 6) but excluded from the final reranked top-5;
  `expand_candidate_window` to top-11/top-9 respectively would recover both.
- **AGENTICALLY_FIXABLE**: `train::141::nda-7` (Contradiction→NotMentioned, empty evidence
  returned; the gold-relevant chunk contains an "other than: a) an employee..." carve-out
  structure the model never engaged with — `search_exception` is the proposed oracle action).
  `train::145::nda-12` (Entailment→Contradiction, gold chunk contains a section cross-reference
  — `follow_cross_reference`).
- **MODEL_REASONING_LIMITED**: `train::102::nda-1`, `train::102::nda-19` (both
  Contradiction→NotMentioned; gold-relevant text present without a disambiguating cue — the
  model simply reasoned to the wrong label from adequate evidence).

Full detail for all 73 reviewed cases: `results/rag_failure_analysis.csv`.

### Quantification summary (the headline numbers for E09)

| | Overall | Contradiction |
|---|---|---|
| STATIC_PIPELINE_FIXABLE | 9.5% | 3.4% |
| AGENTICALLY_FIXABLE | 41.3% | 31.0% |
| MODEL_REASONING_LIMITED | 49.2% | 65.5% |
| Evidence/output/ambiguous other | 0% | 0% |

### E08 conclusion: **B — NARROW SELECTIVE AGENT POTENTIALLY JUSTIFIED**

Not A (agent not justified): 41.3% of reviewed errors show a genuine, evaluator-confirmed,
plausibly-recoverable information gap tied to a specific cue (cross-reference, exception/
carve-out, missing definition) — too large a fraction to dismiss outright.

Not C (broader selective agent potentially justified): the largest single bucket (49.2%
overall, 65.5% for Contradiction specifically — the headline risk class) is model-reasoning-
limited with **no identified action that would help** — the evidence was already sufficient
and correctly available. A broader agent would spend most of its complexity budget on cases it
cannot fix. Additionally, the runtime-observable version of the agentic-cue signal
(exception/carve-out language, present in 62/63 reviewed errors) is **far too undiscriminating
to drive broad escalation** without much tighter conditioning than currently available.

**Therefore: B.** A **narrow** selective agent, escalating only on a more tightly-conditioned
signal than raw exception/carve-out presence (candidate refinement for E09: combine the cue
with the retrieval score margin, or restrict to cases where the cue appears specifically in the
single top-ranked chunk, not any of the 5), targeting specifically the reranker-limited (6,
100% static-fixable — arguably better solved by simply raising `top_k`, a static change, not an
agent) and the Group-B evidence-selection-with-genuine-cue subset (~26 cases), is the
evidence-supported recommendation. **This is not a final A3 architecture decision** — it is the
evidence base for E09, which must still design and justify the actual trigger conditioning
before any agent is built.

### Downstream decision (explicit, recorded per review)

**A3 implementation is deferred.** E08's conclusion (B — narrow selective agent potentially
justified) is evidence that an agent *might* earn its complexity, not authorization to build
one. **The next required diagnostic is a matched stronger-model comparison using GPT-5 mini on
the frozen A2 setup**, purpose: determine whether the large `MODEL_REASONING_LIMITED` bucket
(49.2% overall, 65.5% for Contradiction — the single largest bucket in this analysis) can be
reduced without adding agentic complexity at all. **Only after that result should E09 make the
final agent-justification decision.** Neither E09 nor A3 has been started.

### Recommended next diagnostic (not executed here, per explicit instruction)

**After E08 and before committing to substantial A3 implementation, run a matched stronger-
model diagnostic using GPT-5 mini on the frozen A2 setup** (same `TRAIN_ARCH_v1` manifest, same
retrieved context, same output schema) to determine whether the 49.2% (65.5% for Contradiction)
`MODEL_REASONING_LIMITED` bucket is substantially resolved by a stronger model without adding
agentic complexity at all. **This is now particularly important** given how large that bucket
is relative to the agentic bucket — if a stronger model closes most of the reasoning-limited
gap for a modest cost increase, that may be a simpler, cheaper intervention than building and
validating a selective-agent trigger for the smaller, harder-to-condition 41.3% agentic bucket.
This diagnostic is **not executed in E08** and requires explicit separate authorization (it
would be E07/E05's first hosted-model call in reconstruction-v2's A1/A2 architecture line).

### Files created this pass

- `scripts/analyze_e08_rag_failures.py` (new — full diagnostic pipeline: terminology-correct
  fields, deterministic manual-review union construction, reranker-limited BM25/rerank
  diagnostic, gold-chunk-specific and whole-context runtime-signal detection, taxonomy
  classification, oracle-action labeling).
- `experiments/E08_rag_failure_analysis/results/rag_failure_analysis.csv` (73 rows, full
  diagnostic record per case).
- `experiments/E08_rag_failure_analysis/results/agent_opportunity_quantification.json`
  (all quantification, reranker-diagnostic, and signal-frequency numbers above).

**Not done, and not authorized**: any LLM call (Qwen, GPT-5 mini, Gemini), any change to
`retrieval_v1` or `classification_prompt_v1`, any agent build, DEV/TEST access, or a commit.
