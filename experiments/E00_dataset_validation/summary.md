# E00 — Dataset and Split Validation — Summary

**Result: PASS, after two review/correction passes.** One trustworthy, leakage-aware evaluation
universe exists before any model experiment begins. This is the third and final version of the
role-structure decision specifically — recorded plainly below rather than silently overwritten.

## Findings

1. **Official splits are clean.** 423/61/123 documents (train/dev/test), 7,191/1,037/2,091 cases.
   Zero document-ID overlap and zero filename overlap between every split pair.
2. **NotMentioned evidence policy, data-derived and now correctly enforced**: 100% of NotMentioned
   cases have empty gold-evidence spans, 100% of Entailment/Contradiction cases have non-empty
   spans, across all three splits. `joint_label_evidence_correctness()` requires
   `retrieved_span_indices` be empty for a NotMentioned case to pass jointly (claimed evidence for
   a genuinely absent topic is fabrication, not grounding). Confirmed both directions with tests.
3. **Label mapping is a verified identity mapping.**
4. **Metric code audited and extended, not assumed correct.** All 5 required joint-metric sanity
   cases pass as explicit unit tests, plus a majority-rule multi-span test. Wilson-interval
   Contradiction Recall confirmed correctly denominatored, and generalized into a
   `recall_with_ci(cls, ...)` function usable for any class instead of a bespoke per-class
   function — Contradiction Recall remains the prominently-reported headline. Evidence-threshold
   (τ=0.5) fully audited: two-stage matching (binary any-overlap chunk→span mapping, then
   set-based recall vs. τ), confirmed to act as a majority-of-gold-spans rule given the real
   dataset's span-count distribution (43.7% of cases have exactly 1 gold span, mean ≈2.0).
   64/64 tests pass (`test_metrics.py` + `test_scorer.py` + `test_harness.py`).
5. **Split-role structure — final.** Reconstruction-v2 uses the **official ContractNLI
   three-way split as-is** — no fourth operational split. **TRAIN** (Role A, development/tuning:
   Oracle, model screening, prompt selection, retrieval tuning, agent development; fixed TRAIN
   subsets like `TRAIN_WORKING`/`TRAIN_ORACLE`/`TRAIN_PROMPT` may be created only for
   cost/runtime-controlled diagnostics, never as a validation substitute) / **DEV** (Role B,
   validation and architecture/configuration selection, used only after candidate configs are
   sufficiently frozen from TRAIN development — after DEV-based selection, freeze the
   configuration before TEST) / **TEST** (Role C, final held-out benchmark under the
   reconstruction-v2 protocol, not accessed during tuning, no tuning after viewing results). DEV's
   historical exposure is disclosed in `docs/data_contamination_register.md` as a **methodological
   limitation**, not treated as disqualifying DEV from its standard role — the same logic, applied
   consistently, would also disqualify TEST (which has its own real historical exposure).
   Reconstruction-v2 disqualifies historical *outcomes* from influencing new decisions, not the
   *splits* from their roles. (An earlier draft of this document briefly considered a separate
   held-out subset of TRAIN for validation instead of DEV; that was rejected — see
   `docs/data_contamination_register.md` §4.)
6. **TEST terminology corrected.** Do not describe TEST as "perfectly unseen" or "blind" — it has
   disclosed historical exposure (T041-A/B, rule baseline, hosted comparison) that cannot be
   undone. Use **"final held-out benchmark under the reconstruction-v2 protocol"** instead. What
   reconstruction-v2 does guarantee: TEST is not accessed during reconstruction-v2's own tuning,
   and no reconstruction-v2 decision may be justified by reference to a historical TEST outcome.
7. **A0/A1 evidence-identification requirement — resolved, not left as an open question.** The
   historical convention ("full-context sees everything, so evidence is automatically present") is
   **rejected**: every architecture must explicitly identify the evidence it relied on as span/
   clause IDs. This is frozen policy. What remains open is implementation — `pipeline/
   classifier.py` (A1) and `pipeline/rule_baseline.py` (A0) don't yet produce identified evidence
   under this policy, which blocks scoring A0/A1 on the joint metric until E04/E05 address it. Not
   built this phase (explicitly out of scope — no pipeline changes).
8. **Case ID frozen and implemented**: `f"{split}::{document_id}::{hypothesis_id}"` for all future
   reconstruction-v2 manifests. `Prediction`/`GoldCase` (`evaluation/schemas.py`) gained an
   optional `split` field, default `""`. `evaluation/metrics.py`'s new `_case_key()` makes
   matching split-qualified when `split` is set, and identical to the old
   `(doc_id, hypothesis_id)`-only behavior when it's left blank — so no historical result file
   changes interpretation. Tests confirm: legacy records still match, same-split records match,
   different-split records with a colliding `doc_id` do **not** match, and a split-qualified
   record does not silently cross-match a legacy blank one.
9. **τ=0.5 is NOT scientifically frozen.** Only the evidence-identification requirement, the
   two-stage matching semantics, and the joint metric's structure are frozen.
   `tau_evidence`/`evidence_recall_threshold=0.5` remains the historical/interim configured
   default. E06 may investigate/sensitivity-test τ using TRAIN development data. The final τ must
   be frozen before architecture comparison/final TEST. Do not use TEST to select τ.
10. **Manifest-generation rule and notebook convention added** (`docs/experiment_protocol.md`):
    `TRAIN_WORKING`/`TRAIN_ORACLE`/`TRAIN_PROMPT` must be partitioned at document level with a
    fixed recorded seed, generated once before any model result exists, and never resampled for
    convenience — E00B may inform feasible sizes but must never use model performance to decide a
    partition. Every major experiment E00–E17 should have an analysis notebook that imports
    reusable logic rather than reimplementing it; `E00_dataset_validation.ipynb` is the first
    example, executed with real (local-only) outputs.

## Decision

Proceed to E00B (budget/runtime forecast) once approved. E00 itself required no model calls and
made none, across all revisions.

## What becomes frozen (see `docs/evaluation_protocol.md` Part 1 for the full list)

Official TRAIN/DEV/TEST split roles (no fourth split), TEST access policy with disclosed exposure
and corrected terminology ("final held-out benchmark under the reconstruction-v2 protocol"), case
ID scheme (implemented), label mapping, core metric definitions including the
evidence-identification requirement and revised NotMentioned joint policy, Contradiction Recall +
generic CI method, the evidence-matching *machinery* (identification requirement, two-stage
semantics, joint metric structure — **not** the exact τ value), contamination disclosure policy,
repeated-trial policy, manifest-generation rule, notebook convention.

**Not frozen**: TRAIN_WORKING/TRAIN_ORACLE/TRAIN_PROMPT manifest sizes, Oracle design specifics,
**the exact τ value** (interim default only — E06 must sensitivity-test it on TRAIN/DEV before
it's frozen), A0/A1 evidence-identification *implementation* (policy is frozen; pipeline code is
not built), prompt/retrieval/routing/agent config.
