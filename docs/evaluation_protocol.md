# Evaluation Protocol

This document has two parts. **Part 1 (below) is the reconstruction-v2 protocol** — the live,
binding rules for E00 onward. **Part 2 ("Historical (T-series) Evaluation Practice")** is the
original evaluation-protocol document, preserved unmodified as historical disclosure — it
describes a different, already-completed evaluation regime and is not rewritten or reconciled
with Part 1. Where they conflict (e.g. Part 2's dev-sample reuse vs. Part 1's train/dev/test role
split), Part 1 governs all new work; Part 2 stands only as a record of what happened before.

---

# Part 1 — Reconstruction-v2 Evaluation Protocol

Produced by E00 (`experiments/E00_dataset_validation/`), local-only, no model calls. Audit
findings behind every claim below are in `experiments/E00_dataset_validation/results/` and
`docs/data_contamination_register.md`.

## 1. Dataset and source

[ContractNLI](https://stanfordnlp.github.io/contract-nli/) (Koreeda & Manning, Findings of EMNLP
2021) — document-level three-class NLI on NDAs (`Entailment` / `Contradiction` / `NotMentioned`)
with evidence-span annotation. Local copy: `data/contractnli/{train,dev,test}.json` +
`LICENSE`/`TERMS`. Raw data is immutable — never edited by this or any later phase.

## 2. Official split policy

Reconstruction-v2 uses ContractNLI's own train/dev/test partition as-is. **No re-splitting.**
Verified directly (E00, zero API calls): zero document-ID overlap and zero filename overlap
between every pair of splits (train↔dev, train↔test, dev↔test).

| Split | Documents | Cases (doc × 17 hypotheses) | Entailment | Contradiction | NotMentioned |
|---|---|---|---|---|---|
| train | 423 | 7,191 | 3,530 | 841 | 2,820 |
| dev | 61 | 1,037 | 519 | 95 | 423 |
| test | 123 | 2,091 | 968 | 220 | 903 |

The **TEST split is reconstruction-v2's final held-out benchmark under this protocol** — not
described as "perfectly unseen" or "blind" in an absolute sense, because it isn't: historical
T-series runs already scored against it (T041-A/B, the rule-baseline-full-test run, the
hosted-comparison run — see `docs/data_contamination_register.md`). That prior exposure is a real,
disclosed methodological limitation, not something reconstruction-v2 can undo. What reconstruction-
v2 *can* guarantee, and does: **TEST is not accessed at all during reconstruction-v2 tuning** — not
for model selection, prompt selection, retrieval tuning, chunk-size/top-K/reranker selection,
routing-threshold selection, agent-tool selection, failure-driven prompt changes, or deciding
whether A3 earns its place. Prior TEST-split knowledge may motivate a hypothesis but must never be
cited to justify a reconstruction-v2 config choice (§18). Any report of reconstruction-v2's final
numbers must use the phrase **"final held-out benchmark under the reconstruction-v2 protocol,"**
not "blind" or "unseen," precisely because of this disclosed prior exposure.

## 3. Data roles

Reconstruction-v2 uses the **official ContractNLI three-way split as-is** — TRAIN / DEV / TEST —
with **no fourth operational split**. An earlier draft of this document considered carving a
separate held-out subset out of TRAIN for validation, reasoning that DEV's historical exposure
disqualified it from that role; that idea was **rejected**. DEV's historical exposure is real and
stays disclosed in the contamination register as a methodological limitation, but it does not
change DEV's *role*: DEV is still where reconstruction-v2 performs its own validation/architecture
selection, done independently of what historical T-series decisions happened to use it for. The
premise that historical exposure disqualifies a split from its role would, taken to its
conclusion, also disqualify TEST (which has real historical exposure too) — reconstruction-v2
instead disqualifies *historical outcomes* from influencing new decisions (§18's standing rule),
not the *splits themselves* from their standard roles.

Role structure:

- **Role A — Development/tuning.** Source: official **TRAIN**. Oracle/model/prompt/retrieval/
  agent development. Fixed TRAIN subsets may be created **only for cost/runtime-controlled
  experiments** (e.g. Oracle screening doesn't need the full 7,191-case TRAIN split) — not as a
  substitute validation split. Gold labels/evidence may reach the evaluation harness; they must
  never reach the model, except the explicit Oracle exception (§9).
- **Role B — Validation / architecture and configuration selection.** Source: official **DEV**.
  Used to compare frozen candidate configurations, calibrate routing, and decide whether added
  complexity earns its place. After DEV-based selection, the architecture and configuration are
  **frozen** — not repeatedly tuned case-by-case against DEV. A DEV failure motivates going back to
  a Role-A TRAIN experiment, not a direct patch against DEV until it passes. **Historical exposure
  disclosed, not treated as disqualifying**: DEV was used adaptively across Oracle/prompt/RAG/
  confidence/agent experiments historically (`docs/data_contamination_register.md`) — reconstruction-
  v2's own DEV-based selection is a new, independent pass, and any report of it states this history
  plainly rather than implying DEV is untouched.
- **Role C — Final evaluation.** Source: official **TEST**. Not accessed during reconstruction-v2
  tuning (§2). Run only after model, prompt, retrieval config, routing policy, agent policy, and
  scoring code are all frozen from Role B. No tuning after seeing results. Historical exposure
  disclosed (§2, `docs/data_contamination_register.md`) — described as "the final held-out
  benchmark under the reconstruction-v2 protocol," never as "blind" or "perfectly unseen." A code
  defect discovered after a TEST run gets documented, fixed, and the prior run marked **INVALID**
  — never silently replaced (§20; already demonstrated once historically, see the T041
  joint-metric bug in `docs/decisions.md` ADR-010).

## 4. Manifests — conceptual structure only, sizes not yet chosen

A small, fixed set of reused manifests, not a new random subset per experiment:

- **TRAIN_WORKING** — fixed reconstruction development universe, document-level sample from
  TRAIN (Role A), sized for cost/runtime control, not as a validation substitute.
- **TRAIN_ORACLE** — fixed stratified subset of `TRAIN_WORKING`, reused by all four Oracle models
  (2 local + 2 hosted) — not a new sample per model.
- **TRAIN_PROMPT** — only if a smaller prompt-evaluation subset is genuinely needed; one fixed
  subset reused across every prompt version, drawn from `TRAIN_WORKING`, not one per version.
- **DEV** — official DEV, unchanged, Role B (validation/architecture selection).
- **TEST** — official TEST, unchanged, Role C (final evaluation).

**Not yet frozen:** exact `TRAIN_WORKING`/`TRAIN_ORACLE`/`TRAIN_PROMPT` sample sizes. E00B may
inform *feasible* sample size and runtime (budget/label-distribution constraints), but **must not
use model performance to determine any partition** — sizes are decided before any model result
exists, not adjusted in response to one. See `docs/experiment_protocol.md`'s manifest-generation
rule for the full procedure (document-level partition, fixed recorded seed, generated once, never
resampled for convenience).

## 5. Document-level sampling rule

Any custom subset drawn from TRAIN samples whole documents first, then includes all of that
document's hypothesis cases — never scatters cases from one NDA across differently-purposed
partitions. Audited: the historical AV01/PVAL01 sets already do this correctly; the historical
150-case dev sample does not (case-level stratified sampling, no document-first step) — see
`docs/data_contamination_register.md` §2. Reconstruction-v2 manifests follow the AV01/PVAL01
pattern, not the 150-case sample's pattern.

## 6. Stratification serves a purpose, not a default

- **Primary/benchmark evaluation** (Role B/C): preserve the real dataset distribution — no
  oversampling.
- **Diagnostic subsets** (e.g. Oracle): may intentionally oversample Contradiction so Contradiction
  Recall has enough support to be informative. Any oversampled subset must be labeled diagnostic
  explicitly, must never have its overall accuracy reported as representative of the natural
  distribution, and must report per-class metrics with counts beside percentages.
- Exact Oracle oversampling ratio: **not decided in this phase** (E01).

## 7. Gold-evidence handling

| | Model input may contain | Scorer may contain |
|---|---|---|
| Normal A0–A3 evaluation | NDA text/retrieved chunks, requirement, allowed system instructions | gold label, gold evidence spans |
| **Model must never receive** | gold label, gold evidence | — |
| **Oracle exception** | requirement + **gold evidence** | gold label (hidden from model, used only to score) |

Verified this is already enforced in code, not just policy: `scripts/run_oracle_experiment.py`'s
`build_oracle_context()` raises `RuntimeError` unless `settings.oracle_mode` is explicitly set
`True` by that script alone — a real guard against gold evidence leaking into a non-Oracle call
(this is eval case 090, Category 8, "data leakage prevention").

## 8. Case identity — FROZEN

**Canonical reconstruction-v2 case ID: `f"{split}::{document_id}::{hypothesis_id}"`.** All future
reconstruction-v2 manifests (`TRAIN_WORKING`, `TRAIN_ORACLE`, `TRAIN_PROMPT`, and direct use of
official `DEV`/`TEST`) must use this scheme. `document_id` is ContractNLI's own integer
`id` field; `hypothesis_id` is the fixed `"nda-N"` key from the 17-entry `labels` dict (confirmed
identical 17 keys across all three splits). No manifests are generated yet, so nothing currently
uses this ID in practice — it's frozen as the format future manifest files must follow.

**Note on existing code (not changed this phase):** `evaluation/metrics.py`'s
`_match_predictions_to_golds()` currently matches on `(doc_id, hypothesis_id)` only, without
`split`. Verified the three splits happen to have disjoint `doc_id` sets in this dataset instance,
so no current collision exists — but this is a property of the data, not an enforced invariant.
Reconciling the matching code with the frozen case-ID scheme above is future work (before E12,
once manifests spanning multiple splits are actually in play), not done in this phase.

## 9. Label mapping

Frozen, identity mapping — verified, not assumed:

```
ContractNLI "choice"  →  NDATrace Label
"Entailment"          →  Label.ENTAILMENT     ("Entailment")
"Contradiction"       →  Label.CONTRADICTION  ("Contradiction")
"NotMentioned"        →  Label.NOT_MENTIONED  ("NotMentioned")
```

`evaluation/schemas.py`'s `Label(str, Enum)` and `pipeline/parser.py`'s `VALID_LABELS` check
enforce this — an unrecognized value is skipped with a warning, never silently coerced. No other
representation exists in the raw data; audited directly against all three split files, not
assumed from documentation.

## 10. NotMentioned evidence policy — REVISED

Audited directly against all 7,191/1,037/2,091 cases in train/dev/test: **NotMentioned cases have
empty `spans` in 100% of cases, in every split; Entailment and Contradiction cases have non-empty
`spans` in 100% of cases, in every split.** This is unambiguous and definitional in ContractNLI's
own annotation, not a convention NDATrace invented.

**Corrected policy** (this revision — the original version below was too permissive):
- For **classification metrics** (accuracy, per-class recall, Macro-F1): a correct NotMentioned
  label is sufficient. No evidence check applies at this layer.
- For the **joint evidence-grounded metric**: a NotMentioned case is jointly correct only if the
  label is correct **AND no evidence is claimed/returned** (`retrieved_span_indices` is empty).
  ContractNLI provides zero gold evidence for NotMentioned by definition — a NotMentioned
  prediction that nonetheless cites evidence is fabricating support for an absence, which the
  joint metric must not reward just because the label happened to be right.

**Implemented this phase** (evaluation code, not a model/pipeline change):
`joint_label_evidence_correctness()` in `evaluation/metrics.py` now requires
`not pred.retrieved_span_indices` for a correct-NotMentioned case to count as jointly correct.
Previously it counted any correct-NotMentioned label unconditionally — that was the bug this
revision fixes. Two new deterministic tests added:
`test_joint_correctness_not_mentioned_empty_evidence_passes` (correct NM + empty evidence → PASS)
and `test_joint_correctness_not_mentioned_fabricated_evidence_fails` (correct NM + non-empty/
fabricated evidence → FAIL).

## 11. Primary metrics — four layers, never averaged together

**A. Classification** — Macro-F1, accuracy (supporting figure only, not headline), recall per
class, **Contradiction Recall** and **NotMentioned Recall** reported prominently and separately,
class counts alongside percentages.

**B. Retrieval** (only for architectures that retrieve in the traditional sense — **A2, A3**) —
Evidence Recall@K, Evidence Precision@K, MRR, retrieval miss count.

**B′. Evidence identification (all four architectures, REVISED — replaces the old "A0/A1 don't
report retrieval metrics" framing).** Every architecture must **explicitly identify** the evidence
it relied on, as span/clause IDs, not merely "the answer is somewhere in what the model saw":
- **A0 (rule):** the matched clause/span ID(s) the keyword rule fired on.
- **A1 (full-context):** the specific evidence clause/span ID(s) the model *selects* from the full
  NDA as its citation — not "the whole document," which would make every full-context case
  trivially evidence-complete by construction and defeat the point of the joint metric.
- **A2 (RAG):** the retrieved/final selected evidence span ID(s) after retrieval+rerank.
- **A3 (agentic RAG):** the final selected evidence span ID(s) after investigation — the agent's
  concluding evidence set, not every span any tool happened to touch along the way.

**Rejected, this revision:** the historical convention (`docs/decisions.md` ADR-010's joint-metric
backfill) that full-context's evidence = "all span indices in the document," on the reasoning that
seeing everything means nothing can be missed. That conflates *access* to evidence with
*identification* of evidence, and makes A1's joint score collapse to plain label accuracy by
construction — not a meaningful joint measurement. Rejected for reconstruction-v2.

**Implementation consequence, documented but not built this phase** (would touch
`pipeline/classifier.py`/`pipeline/rule_baseline.py`/`pipeline/orchestrator.py`, explicitly out of
scope — "do not change model pipelines now"): A1's classification prompt/output schema must be
extended to require the model to cite specific span/clause identifiers from the full document it
was given, the same way A2/A3 already do via retrieval. A0's rule baseline must expose its
matched-span ID explicitly if it doesn't already (`pipeline/rule_baseline.py` — not audited this
phase; flagged for E04/E05 to confirm before those architectures are scored on the joint metric).
Until this is implemented, A0/A1 cannot be fairly scored on the joint metric under this revised
policy — this is a real blocker for E12 that must be resolved in E04/E05, not silently worked
around.

**C. Joint evidence-grounded success** — the headline project metric: correct classification AND
(for Entailment/Contradiction) *identified* evidence (§B′) overlapping gold spans above threshold
τ, or (for NotMentioned) exact label match with no evidence claimed (§10). Reported separately from
label accuracy, never averaged into it.

**D. Operational** (latency, tokens, cost, review-routing rate, agent invocation rate, turns, tool
calls) — schema already supports all of these (`evaluation/schemas.py`'s `MetricResult`,
`CostLatencyRecord`); not all populated until the relevant experiment (E09+) actually runs.

## 12–13. Contradiction Recall and confidence intervals — audited, generalized

Audited `contradiction_recall_with_ci()` and `wilson_score_interval()` directly (not trusted
because they exist):
- Denominator is non-abstained cases of the target class only (correct — abstained cases are
  excluded from both numerator and denominator, so an abstention can't inflate recall).
- Interval method: **Wilson score interval**, z=1.96 (95%) — the standard, more-reliable-than-
  normal-approximation choice for small-n binomial proportions (Contradiction is ~11% of the
  label distribution; only 220 examples in the full TEST split). Appropriate, not over-engineered.

**Revised this phase**: rather than adding a bespoke `not_mentioned_recall_with_ci()`,
`evaluation/metrics.py` now has a generic `recall_with_ci(cls, predictions, golds)`, and
`contradiction_recall_with_ci()` is a one-line delegate to `recall_with_ci(Label.CONTRADICTION,
...)` — same return shape, same behavior, verified via `test_recall_with_ci_is_generic_across_classes`
(asserts the delegate is byte-for-byte identical to the direct generic call, and separately
verifies `Label.NOT_MENTIONED` recall/n/correct on a hand-built case). **Contradiction Recall
remains the prominently-reported class-specific headline metric** — the generic function doesn't
add a new headline field to `MetricResult`, it just removes the need for class-specific
duplication when NotMentioned (or any other class) recall+CI is needed later (e.g. E12 reporting).

## 14. Joint label+evidence metric — audited with hand-constructed sanity cases

All 5 required sanity cases verified against `joint_label_evidence_correctness()`
(`evaluation/metrics.py`), with deterministic unit tests in `tests/test_metrics.py`:

1. Correct label + correct evidence → PASS (`test_joint_correctness_passes_at_tau_boundary`).
2. Correct label + wrong evidence → FAIL (`test_joint_correctness_requires_evidence_above_tau`).
3. Wrong label + correct evidence → FAIL (`test_joint_correctness_wrong_label_correct_evidence`).
4. Wrong label + wrong evidence → FAIL (implied by the label-mismatch short-circuit; covered by
   case 3's structure — label mismatch always fails regardless of evidence).
5. NotMentioned → per §10's **revised** policy: correct label + empty evidence → PASS
   (`test_joint_correctness_not_mentioned_empty_evidence_passes`); correct label + fabricated
   evidence → FAIL (`test_joint_correctness_not_mentioned_fabricated_evidence_fails`).

Plus a majority-rule sanity check for multi-span cases
(`test_joint_correctness_majority_rule_multi_span`, see §16's threshold audit). All 53 tests in
`tests/test_metrics.py` + `tests/test_scorer.py` pass
(`experiments/E00_dataset_validation/results/metric_audit.json`).

**A0/A1 evidence-identification requirement (§11B′) resolved, not left open:** the joint metric
must be computed only from *identified* evidence per architecture, never from "evidence being
present somewhere in context." This is now the frozen policy. What remains genuinely open is
implementation — A1/A0 don't yet produce identified evidence in their current code, which blocks
scoring them on this metric until E04/E05 address it (see §11B′).

**Not yet frozen:** `tau_evidence` default (0.5) — audited this phase (§16) and found justified as
an interim majority-rule threshold, but not re-validated via sensitivity analysis; that belongs
with E06/E13, not E00.

## 15. Retrieval metric sanity tests

Evidence granularity: ContractNLI annotates evidence as **character-offset spans** per document
(`doc['spans']`, a flat list of `[start, end)` pairs; gold evidence for a case is a list of
indices into that list). Retrieval-built chunks have independent character boundaries. The
matching rule (`evaluation/scorer.py`'s `map_chunks_to_gold_span_indices()`), verified via 7
existing unit tests in `tests/test_scorer.py`:

> **A retrieved chunk counts as covering a gold span when their character ranges overlap at
> all** — `span_start < chunk.end_char and span_end > chunk.start_char`. This is interval overlap,
> not containment: a chunk need not fully contain the gold span, and a gold span need not be
> fully contained in the chunk. Adjacent-but-touching ranges (`chunk.start == span.end`) do
> **not** count (verified: `test_adjacent_non_overlapping_not_covered`). A span already covered by
> an earlier (higher-ranked) chunk is not double-counted if a later chunk also overlaps it
> (`test_span_not_duplicated_if_covered_by_multiple_chunks`).

Evidence Recall@K / Precision / MRR sanity-tested this phase with hand-computable examples,
including two previously-missing cases now added (`test_evidence_recall_at_k_no_hit`,
`test_mean_reciprocal_rank_no_hit`) — gold evidence exists but nothing retrieved overlaps it, both
correctly return 0.0 rather than being silently skipped from the denominator.

## 16. Evidence matching granularity and threshold audit

Two distinct overlap operations exist in the codebase, at two different granularities — this
audit traces both precisely rather than treating "the overlap rule" as one thing.

**Stage 1 — chunk→span mapping (`evaluation/scorer.py`'s `map_chunks_to_gold_span_indices()`).**
Converts a retrieval-built chunk (arbitrary character boundaries, from `pipeline/chunker.py`) into
membership in ContractNLI's own span-index list (`doc['spans']`, a flat, per-document list of
`[start, end)` character intervals covering the whole document; a case's gold evidence is a list
of *indices* into this list, e.g. `[38]` or `[39, 40]`). Rule, verified via 7 existing tests in
`tests/test_scorer.py`:

> A chunk **covers** a gold span index when their character ranges overlap at all —
> `span_start < chunk.end_char and span_end > chunk.start_char`. This is **binary, any-overlap**
> semantics: a chunk overlapping even one character of a span counts that whole span index as
> "covered," regardless of how much of the span's text the chunk actually contains. Interval
> overlap, not containment, in either direction. Adjacent-but-touching ranges do not count
> (`test_adjacent_non_overlapping_not_covered`). A span already covered by a higher-ranked chunk is
> not double-counted (`test_span_not_duplicated_if_covered_by_multiple_chunks`).

This produces `Prediction.retrieved_span_indices` — a flat list of gold span *indices* the
retrieved chunks were judged to cover, in rank order.

**Stage 2 — recall/threshold computation (`evaluation/metrics.py`'s `evidence_recall_at_k()` and
`joint_label_evidence_correctness()`'s `tau_evidence` check).** Operates purely on integer
span-index **sets**, no further character-level reasoning:

```
gold_set      = set(gold.gold_span_indices)        # the case's specific evidence spans
retrieved_set = set(pred.retrieved_span_indices)    # spans judged "covered" by stage 1
recall        = len(gold_set & retrieved_set) / len(gold_set)   # numerator/denominator
pass          = recall >= tau_evidence               # tau_evidence default 0.5
```

**Numerator:** count of gold span indices also present in the retrieved set. **Denominator:**
total count of gold span indices for that case (never the retrieved count — so a system can't
inflate its score by retrieving extra irrelevant spans, verified by
`test_evidence_precision` covering the separate precision-direction metric).

**Behavior for multiple gold spans, verified empirically against the real dataset (not assumed):**
gold span-index list length is not always 1 — computed directly from all three splits:

| Gold span count (n) | Share of Entailment/Contradiction cases (test split) |
|---|---|
| 1 | 43.7% (519/1,188) |
| 2 | 34.0% (404/1,188) |
| 3 | 11.2% (133/1,188) |
| 4+ | 11.1% (132/1,188) |

Mean ≈2.02 spans/case across dev and test. For **n=1** (the plurality of cases), `recall` can only
be 0.0 or 1.0, so `tau_evidence=0.5` is equivalent to requiring full coverage — no laxity there.
For n≥2, `tau_evidence=0.5` is equivalent to a **majority-of-gold-spans rule**: at least
⌈n/2⌉-ish of the referenced spans must be covered (exactly 50% passes at even n, per the existing
boundary test `test_joint_correctness_passes_at_tau_boundary`; confirmed for odd n via the new
`test_joint_correctness_majority_rule_multi_span`, n=3: 2/3 passes, 1/3 fails).

**Behavior for partial overlap:** handled entirely at Stage 1 (any character overlap = full binary
credit for that span index) — Stage 2 never sees partial credit, only whether each gold span index
is in or out of the retrieved set. This means Stage 2's "recall" is really "fraction of gold spans
touched at all," not a character-level completeness measure. This compounding of (a) generous
binary credit per span at Stage 1 and (b) a majority-rule threshold at Stage 2 is a real,
documented looseness, not a hidden one.

**Conclusion — τ=0.5 is NOT scientifically frozen; it is kept only as the historical/interim
configured default, with the reasoning for why it's not unreasonable recorded so it isn't
mistaken for an arbitrary carry-over:** "majority of the specifically-annotated gold spans were
touched" is a defensible, non-arbitrary proxy for "the retrieved/identified evidence substantially
grounds the classification," especially given ContractNLI's spans are fine-grained (often single
sentences/clause fragments) and multi-span annotations frequently include redundant or overlapping
restatements of the same underlying fact — requiring 100% coverage would likely penalize systems
for missing a redundant span while still correctly identifying the substantive one.

**What IS frozen by this audit: the matching machinery** — explicit evidence identification
(§11B′), the two-stage character-span/chunk matching semantics above, the set-based evidence-recall
calculation (numerator/denominator), and the joint label+evidence metric's overall structure
(§14). **What is NOT frozen: the exact value τ=0.5.** It has not been validated via a
threshold-sensitivity analysis (e.g. sweeping τ against downstream label-correctness correlation)
— `evidence_recall_threshold = 0.5` stands only as the historical/interim configured default.
**E06 may investigate/sensitivity-test τ using TRAIN development data. The final τ must be frozen
before architecture comparison/final TEST. Do not use TEST to select τ.**

## 17. Final test size and runtime (measurement only — no cost forecast here)

Official TEST: 123 documents, 2,091 cases (968 Entailment / 220 Contradiction / 903
NotMentioned), 100% evidence coverage for E/C cases, 0% for NotMentioned (§10). A full four-
architecture (A0–A3) run implies up to 4 × 2,091 = 8,364 inference cases if every architecture is
run on the full set once. Actual cost/runtime forecasting is E00B's job, not this phase's.

## 18. Contamination disclosure

See `docs/data_contamination_register.md` for the full historical inventory and per-experiment
TEST/DEV touch table. Standing rule adopted here: prior TEST-split knowledge may motivate a
reconstruction-v2 hypothesis but must never be cited to justify a reconstruction-v2 config choice.

## 19. Freeze-before-test rule

Role C (official TEST) runs only after: model frozen, classification prompt frozen, retrieval
configuration frozen, routing policy frozen, agent policy frozen, scoring code frozen. No change
to any of these based on a TEST result.

## 20. Invalid-run policy

A code defect discovered after a TEST run is documented, fixed, and the prior run is marked
**INVALID** in place — never silently deleted or replaced. This is not a new invention: the
historical T041 joint-metric bug (`docs/decisions.md` ADR-010) already followed exactly this
pattern (bug documented, code fixed, all affected result files backfilled and the original record
kept alongside the corrected one) — this section formalizes that precedent as a forward rule.

## Frozen vs. not-yet-frozen after E00 (this revision)

**FROZEN:**
- Official split roles — the standard ContractNLI three-way split, no fourth operational split
  invented: **TRAIN** (Role A, development/tuning), **DEV** (Role B, validation/architecture
  selection), **TEST** (Role C, final evaluation) (§3).
- TEST access policy — not touched during reconstruction-v2 tuning, disclosed historical exposure
  noted as a methodological limitation, referred to as "the final held-out benchmark under the
  reconstruction-v2 protocol," never as "blind" or "perfectly unseen" (§2, §3, §19–20).
- Case ID scheme — `f"{split}::{document_id}::{hypothesis_id}"` (§8) — for all future manifests,
  **now implemented** in `evaluation/schemas.py` (`Prediction.split`, `GoldCase.split`, both
  default `""`) and `evaluation/metrics.py`'s `_case_key()`/`_match_predictions_to_golds()`: a
  record that never sets `split` matches exactly as before (legacy compatibility, verified by
  `test_match_legacy_records_without_split_still_match`); a record with `split` set only matches
  another record with the identical split set (`test_match_same_split_qualified_records_match`,
  `test_match_different_splits_with_colliding_doc_id_do_not_match`,
  `test_match_split_qualified_does_not_cross_match_legacy_blank`).
- Label mapping (§9) — identity mapping, verified.
- Core metric definitions: classification (§11A), retrieval (§11B, only for A2/A3), evidence
  *identification* requirement for all four architectures (§11B′), joint metric (§11C, §14) —
  including the revised NotMentioned policy (§10) and the rejected "full-context = automatic
  evidence" convention.
- Contradiction Recall + Wilson CI, now via the generic `recall_with_ci()` (§12–13).
- Evidence matching *machinery* — explicit evidence identification, two-stage matching semantics
  (binary any-overlap chunk→span mapping, then set-based recall calculation), and the joint
  metric's overall structure (§16). **The exact τ value is explicitly NOT included in this
  freeze** — see NOT YET FROZEN below.
- Contamination disclosure policy, now including DEV alongside TEST (§18,
  `docs/data_contamination_register.md`).
- Repeated-trial policy: deterministic (temperature-0) component experiments run once per case;
  stochastic/agentic evaluation may use repeated trials, trial count always reported alongside any
  rate. Exact A3 repeat counts not decided here.

**NOT YET FROZEN:**
- TRAIN_WORKING/TRAIN_ORACLE/TRAIN_PROMPT manifest sizes (§4, §6).
- Oracle model choices, oversampling ratio (§6).
- **τ (`tau_evidence`) — NOT scientifically frozen.** `evidence_recall_threshold = 0.5` is kept
  only as the historical/interim configured default. E06 may investigate/sensitivity-test τ using
  TRAIN development data. The final τ must be frozen before architecture comparison/final TEST.
  Do not use TEST to select τ (§16).
- **A0/A1 evidence-identification implementation** — policy is frozen (§11B′), but
  `pipeline/classifier.py` (A1) and `pipeline/rule_baseline.py` (A0) do not yet produce identified
  evidence under this policy. Real blocker for E12, to be resolved in E04/E05, not silently
  bypassed.
- Prompt, retrieval settings (embeddings/chunking/top-K/reranking), architecture winner, routing
  threshold, agent policy.
- Reconciling `_match_predictions_to_golds()`'s matching key with the frozen split-qualified
  case-ID scheme (§8) — no current collision, but not yet implemented.

---



# Part 2 — Historical (T-series) Evaluation Practice

Unmodified below (this section's own header is the only addition — no body text below has been
edited). Describes the evaluation regime actually used before reconstruction-v2, not the protocol
in Part 1 above. Preserved as disclosure per `docs/data_contamination_register.md`.

## Dataset roles

| Data | Source | Role | Can tune on it? |
|---|---|---|---|
| Dev split (full) | `data/contractnli/dev.json`, 614 Entailment/Contradiction cases used for retrieval sweeps | Retrieval-only experiments (chunking, reranking, top-K) — no LLM calls | Yes — this is exploration |
| 150-case dev sample (seed=42) | Stratified sample of `dev.json` | Oracle, model selection, RAG e2e, prompt tuning (v1–v6), confidence/abstention, agent experiments | **Yes, repeatedly reused** — see the warning below |
| Golden regression battery (`data/golden/golden_cases.json`, `negative_cases.json`, 45 cases) | Hand-picked `dev.json` documents | Catches known behavioural regressions after a change (e.g. a prompt version) | Yes — these exist to be run after every change, by design |
| Robustness/system cases (`data/golden/injection_cases.json`, `llm_behaviour_cases.json`, `agent_cases.json`, `confidence_cases.json`, `evidence_quality_cases.json`, `logging_security_cases.json`) | Synthetic or hand-picked `dev.json` cases | Tests system *behaviour* (injection resistance, error isolation, log hygiene), not benchmark accuracy | Yes — same reasoning as regression cases |
| Architecture-validation set | — | An independent sample, untouched by any tuning decision, used once to confirm the frozen architecture choice before the final test run | **Does not currently exist.** Every architecture comparison in `docs/decisions.md` (ADR-007, ADR-008, ADR-009) was run on the same 150-case dev sample used for every earlier tuning decision. This is a real, open gap — see "What's missing" below. |
| Official test split (`data/contractnli/test.json`, 2,091 cases) | ContractNLI's own test partition | The final, locked evaluation (T041), run once after architecture freeze | **No — never tune on this.** Any change made after looking at a test-set result invalidates the freeze. |

### What's missing: an architecture-validation set

The plan called for the architecture freeze (ADR-009) to be confirmed by evidence not used for any
of the tuning decisions that led to it. In practice, every one of Rule/Full-context/RAG/RAG+agent's
compared numbers (59.9% / 91.3% / 88.0% / 90.0%) came from the same 150-case dev sample that also
drove the model choice, prompt version, and retrieval configuration decisions. There is no
untouched intermediate sample between "development" and "final locked test." This is disclosed
here rather than glossed over — it means the architecture freeze itself rests on adaptively-reused
development evidence, and the test-set run (T041) is the first genuinely independent check of it.

## Freeze protocol

**T041 is not one run at two sample sizes — it is two distinct configurations, corrected and named
here after a forensic timestamp/git-history review (`docs/decisions.md` ADR-010):**

- **T041-A** (interim, 500-case stratified subsample, run first): model
  `google/gemini-2.5-flash-lite` / local Llama, **prompt v2** / `agent_step_v1.txt`, and for RAG+agent
  the **original inline, circular routing signal** (pre-C1-fix).
- **T041-B** (the full 2,091-case test set, run later, after a commit changed the default prompt and routing — **these are the
  numbers cited everywhere in this repo as "the T041 result"**): model unchanged, **prompt v6** /
  `agent_step_v2.txt` (the current shipped default), and for RAG+agent the **decoupled routing fix**
  via `pipeline/orchestrator.py::review_requirement()` (ADR-006).

**A previously-stated caveat here was wrong and is retracted**: earlier versions of this document
said "T041 used prompt v2, not the current v6 default." That was true only for T041-A. **T041-B's
numbers — the full 2,091-case results (81.2% / 78.7% / 77.7% accuracy for full-context / RAG /
RAG+agent) — are already v6, already using the decoupled routing fix, and already reflect
everything currently shipped.** Do not describe them as predating the security fix.

What was genuinely locked before T041-B and not changed based on its results:
- Model: `google/gemini-2.5-flash-lite` (hosted), Llama 3.2 3B via Ollama (local)
- Prompt version: v6 / `agent_step_v2.txt` (already in place before T041-B started — see above)
- Retrieval configuration: sentence chunking → mpnet → retrieve-20 → rerank L-12 → top-7 →
  rule-boost RRF fusion (ADR-002)
- Routing: rule-agreement-based ACCEPT/REVIEW (ADR-005), with the decoupled independent signal
  fix already in place (ADR-006)
- Agent: 5 tools, bounded ReAct loop (ADR-007)
- Evaluation scripts: `scripts/run_final_test_evaluation.py`

**A real qualification that remains, correctly stated rather than overstated**: T041-B is not a
pristine first exposure to the test split — T041-A had already scored a 500-case subsample of the
same split before T041-B ran. The v2→v6 and routing changes were triggered by an independently
discovered live security issue and a code-audit finding, not by looking at T041-A's scores, so this
is not test-set tuning in the overfitting sense — but the split had genuinely been partially
observed before T041-B's numbers were produced, and that should be disclosed, not implied away.

## Metrics

| Metric | Definition | Used for |
|---|---|---|
| Accuracy | Fraction of exactly-correct 3-way labels | Headline comparison across architectures |
| Macro-F1 | Unweighted average F1 across Entailment/Contradiction/NotMentioned | Guards against a majority-class-dominated accuracy number |
| Contradiction recall (+ 95% Wilson CI) | Recall on the Contradiction class alone, with a confidence interval given the small class size (~11% of labels) | Headline risk metric — added after instructor feedback flagged that the earlier averaged "risk-sensitive recall" hid Contradiction-specific weakness |
| Risk-sensitive recall | (recall_Contradiction + recall_NotMentioned) / 2 | Superseded as the headline risk metric by Contradiction recall alone; still recorded |
| Evidence Recall@K / Precision / MRR | Retrieval-only metrics: does the retrieved set contain the gold span, how much of it is relevant, how high does it rank | Retrieval configuration decisions (ADR-002) |
| Joint label+evidence correctness | Label is correct AND the retrieved/available spans overlap the gold evidence span | The metric this project's rubric weighs most heavily. **Was silently broken for the entire T041 run until it was found and fixed — see `docs/decisions.md` ADR-010.** |
| Cost (USD), latency (ms) | Real measured API cost and wall-clock latency per case | Architecture/model tradeoff discussion |
| AUROC (confidence/routing signal) | Discriminative power of a candidate routing signal for correct vs. incorrect predictions | Confidence/abstention design (ADR-005) |
| McNemar's exact test | Paired significance test for two classifiers on the same cases | Agent include/exclude decision (ADR-007); do not report a small-sample accuracy delta without it |

## Development reuse warning

Because the 150-case dev sample was reused adaptively across the Oracle experiment, model
selection, every retrieval round, every prompt version, confidence/abstention design, and the
agent experiment, **development-sample metrics should be interpreted as exploratory evidence, not
as an unbiased estimate of final generalization.** Each individual decision was validated
reasonably (same sample, same seed, controlled comparisons), but the cumulative effect of many
decisions being tuned against the same 150 cases means the dev-sample numbers likely overstate
true held-out performance to an unknown degree. This is exactly why the official test split (T041)
exists and why it must never be used to make further tuning decisions.

## Case-category taxonomy

See `docs/evaluation_case_design.md` for the full breakdown of the 76-case catalogue (Categories
1–7, after a correction removed 10 non-single-case aggregate/structural entries) plus the
code-level Categories 8–10, into benchmark, regression, robustness, agent-behaviour, and system/API
categories — these are not one homogeneous benchmark and should not be reported as a single pass
rate.

## Current evaluation status

- Architecture: **frozen** (ADR-009), on repeatedly-reused development evidence (see "What's
  missing" above) — no independent architecture-validation run existed until AV01 (below). **A
  real, unresolved finding, and now a stronger one than first stated**: on T041-B (the full
  2,091-case hosted test set, already v6 + decoupled routing — see the Freeze protocol section
  above), the selective agent's accuracy (77.7%) is *below* plain RAG's (78.7%), reversing the
  dev-sample finding that justified including the agent (`docs/decisions.md` ADR-007). McNemar's
  test on T041-B: b=87, c=65, p=0.088 — not significant, but the point estimate favors plain RAG.
  **Because T041-B already uses the current shipped prompt and routing configuration, this cannot
  be explained away as "it was still running the old v2/circular-routing setup" — it wasn't.** An
  independent architecture-validation run (AV01, `data/architecture_validation_manifest.json`) has
  since produced the same qualitative finding on untouched data — see `docs/decisions.md` ADR-009's
  update and the AV01 analysis for the full breakdown.
- Official test evaluation: **run, in two distinct configurations (T041-A and T041-B — see the
  Freeze protocol section above), not one run at two sample sizes.** T041-B (full 2,091 cases,
  already v6 + decoupled routing) is what's cited as "the T041 result" throughout this repo.
  Caveats that actually apply to T041-B:
  1. **Not a pristine first exposure to the test split** — T041-A had already scored a 500-case
     subsample of the same split before T041-B ran (see the Freeze protocol section for why this
     is disclosed rather than treated as invalidating).
  2. **Joint label+evidence correctness was broken in the code that executed both phases.**
     Fixed and fully backfilled (`scripts/backfill_joint_metric.py --write`, re-run
     against all 7 T041 result files — zero LLM/API calls, retrieval is deterministic). All three
     hosted T041-B files (full 2,091-case set) now carry a corrected, trustworthy joint value:
     full-context 0.812 (matching accuracy, as it must for full-context), RAG 0.754, RAG+agent
     0.747. The local-Llama files (T041-A-scale, `sample_size: 500`) are also now corrected: rule
     0.494, full-context 0.492, RAG 0.524, RAG+agent 0.532. **Every one of these corrected values is
     a post-hoc backfilled metric** (`scripts/backfill_joint_metric.py`, applied after the fact to
     already-saved predictions), not something the original run computed correctly — that provenance
     should always be stated alongside the number, not silently presented as if the run itself got
     it right the first time. Result files: the three hosted files now live in `results/final/`; the
     local-Llama and superseded 500-case rule files moved to `results/archive/runs/` (a later
     results/ reorganization).
- Long-document stress test (RAG vs. full-context scalability): **proposed, not yet run** — see
  `docs/architecture.md`'s open questions.
- Architecture-validation run (AV01): **complete** — 340 cases, 20 documents from ContractNLI's
  training split, verified zero overlap with every prior pool (dev sample, retrieval tuning,
  golden/regression cases, agent experiment, and the official test split). Frozen at the current
  shipped configuration (v6, decoupled routing) throughout — never used to compare prompt versions
  or architectures against each other before freezing, avoiding the exact contamination this
  document warns about elsewhere. Full-context and RAG were statistically indistinguishable
  (McNemar p=1.000); RAG+agent underperformed both, with a 6.6% correction precision against a
  12.5% harm rate on routed cases.
