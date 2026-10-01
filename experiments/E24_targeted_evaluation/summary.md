# E24 — Targeted evaluation: Rule / FULL / RAG on the checked-in golden+negative battery

**Status: COMPLETE.** Real, live hosted calls against the current frozen final architecture
(see `config.json` for the full frozen protocol). Not a replacement for the 2,091-case official
TEST benchmark (`experiments/E20_final_rag_test/`), which is unchanged by this experiment — this
is a smaller, deliberately curated regression comparison on cases this project already
hand-designed to be hard.

## What this is, and is not

- **Is**: the first time the checked-in golden/negative case battery (previously only scored
  against the superseded legacy pipeline, see `docs/test_coverage_summary.md`) has been run
  against the **current** frozen architecture (GPT-5-mini + P0, Rule/FULL/RAG).
- **Is not**: a statistically representative benchmark. 49 cases, deliberately including the
  hardest known failure family (exception/carve-out clauses). Not powered for significance
  testing, and not a claim of generalization beyond ContractNLI.

## Case set

49 cases: 30 golden (ordinary, easy/medium/hard tiers across Entailment/Contradiction/
NotMentioned) + 15 negative (misleading wording, wrong-section evidence, conflicting clauses,
keyword absence, long documents) + 4 evidence_quality (real, non-synthetic cases only).
`injection_cases.json`/`llm_behaviour_cases.json` excluded — every entry in both references a
synthetic document with no stored source text, not reproducible. `agent_cases.json`/
`confidence_cases.json` excluded — both test rejected features (E11, E15) not in the shipped
architecture. All 49 cases verified drawn from ContractNLI **dev.json**, zero overlap with
`test.json` document IDs.

## Results

| System | n | Accuracy | Macro-F1 | Joint correctness | Contradiction recall | NotMentioned recall | Cost | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Rule (A0) | 49 | 51.0% | 0.457 | 44.9% | 13.3% | 92.9% | $0 | 0 ms |
| FULL (A1) | 49 | 73.5% | 0.720 | **73.5%** | 46.7% | 71.4% | $0.1282 | 7,984 ms |
| RAG (A2) | 49 | 71.4% | 0.708 | 67.3% | **53.3%** | 71.4% | $0.0902 | 7,302 ms |

Directionally consistent with the full 2,091-case TEST result (FULL ahead on Joint correctness;
both far ahead of Rule) — this curated set is harder for every system (lower absolute numbers
across the board, by design, since it deliberately includes known-hard cases), not a
contradiction of the headline benchmark.

Real cost this run: **$0.2184** (98 real hosted calls, 0 errors, 0 null predictions — see
`results/run_E24_wall.json`).

## Failure analysis

**All three systems wrong (7 cases): 001, 011, 019, 034, 036, 039, 040.**

**Case 001 — debatable ground-truth annotation, not a model failure.** Catalogued "easy
entailment — single clause, short NDA, obvious match." Hypothesis: "Confidential Information
shall only include technical information." Gold evidence is an **export-control clause**
(U.S. Dept. of Commerce technical-data transmission restrictions), which does not substantively
address the hypothesis. Re-derived RAG's actual retrieval offline (deterministic, zero model
calls): the gold clause **is** in the retrieved top-3 context for every system, so this is not a
retrieval problem for any architecture. This matches a pre-existing, independent finding —
`docs/experiment_registry.md`'s T012 entry already flagged this exact case: *"the model's
disagreement with gold there is arguably more defensible than the label itself."* Counted here as
an evaluation-validity caveat, not a reasoning failure.

**FULL right, RAG wrong (3 cases): 005, 017, 045.**

**RAG right, FULL wrong (2 cases): 013, 038.** Case 038 ("conflicting clauses — evidence spans
multiple locations, approximating one clause granting [a right] while another limits it," gold
Contradiction) traced at the clause level: FULL cited a real clause reading *"may disclose VA
sensitive information... in only two situations: (1) court order, (2) VA's prior written
authorization"* and predicted Entailment, apparently over-weighting that one permissive-sounding
clause against the document's overall restrictive framing ("only to the extent necessary... only
for the purpose of performing the contract"). RAG's narrower top-5 retrieval did not surface the
court-order/authorization clause at all, foregrounded the restrictive clauses instead, and
predicted Contradiction — correct. Direct, traceable evidence that full-document access can be a
liability when the document contains a distractor clause, not only an asset.

**The ADR-011 exception/carve-out weakness persists under the current architecture.** Case 034
("except as required by law" carve-out limiting an apparently firm requirement, gold
Contradiction) is predicted Entailment by **both** FULL and RAG — the same failure mode the
legacy pipeline showed 100% failure on for this case family. This is a real, unresolved
weakness, not something the current GPT-5-mini architecture incidentally fixed. Of the 4
documented ADR-011 exception cases in this battery (034, 038, 039, 040), only 038 is now
correctly handled (by RAG only) — 3 of 4 remain failures under the current architecture.

**Correct label, incorrect/insufficient evidence (007, 043 — RAG only; FULL has 0 in this set).**
Diagnosed at the gold-span-coverage level, not just scored pass/fail. The joint metric requires
≥50% of gold spans covered (`TAU_EVIDENCE = 0.5`):

| Case | Gold spans | RAG retrieved (re-derived) | RAG cited → coverage | FULL cited → coverage |
| --- | --- | --- | --- | --- |
| 007 (evidence scattered across 3+ spans) | 4 spans | 2 of 4 present in top-5; **2 of 4 never retrievable** | 1 of 4 (25%) — below threshold | 3 of 4 (75%) — passes |
| 043 (keyword absence) | 3 spans | 2 of 3 present in top-5; **1 of 3 never retrievable** | 1 of 3 (33%) — below threshold | 2 of 3 (67%) — passes |

Both cases are a **combined retrieval-coverage and evidence-selection failure**, not purely one
or the other: some gold spans were structurally outside RAG's top-5 context in both cases, *and*
in case 007, RAG's model output didn't cite a gold span (033) that **was** retrieved. Attributing
either case to "RAG's evidence selection is bad" alone would ignore the retrieval-coverage gap;
attributing it to "retrieval failed" alone would ignore the uncited-but-retrieved span. n=2 — not
a basis for a general evidence-quality claim between the two architectures.

## Reproducibility

Re-score from the saved predictions, zero model calls:
```bash
python experiments/E24_targeted_evaluation/analyze_e24.py
```
Every aggregate number above is recomputed by that command from `results/run_E24_predictions.jsonl`
(the real executed calls) and `manifests/case_manifest.json` (gold labels/evidence), using
`evaluation/evidence_matching.py`'s existing `evidence_to_span_indices()`/`joint_success()` —
the same functions E17B/E20 use for the 2,091-case TEST scoring, not a reimplementation.

## Limitations

- 49 cases, not statistically representative; deliberately includes the hardest known family.
- Single run per case, temperature 0, no repeated-sampling variance estimate.
- Behavioral (`llm_behaviour_cases.json`) and security (`injection_cases.json`) checks from the
  original battery were **not** re-executed here (see "Case set" above) — security robustness
  remains characterized by E16/E21/E22/E23, unchanged and not retroactively altered by E24.
- Case difficulty tiers ("easy"/"medium"/"hard") in the source files were assigned under the
  legacy pipeline's design process and are not re-validated as accurate for the current
  architecture by this experiment (see case 001 above).
