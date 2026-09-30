# E13B — Evidence Evaluator Hardening (evidence_evaluator_v2)

```
Experiment ID: E13B
Question: Can the evidence evaluator be made robust to harmless formatting differences without changing the semantic standard for what counts as supporting evidence?
Nature: evaluator CORRECTION; zero model calls; no TEST access. Prompted by E13's post-hoc scoring artefact. Must complete before the final TEST benchmark.
Canonical implementation: evaluation/evidence_matching.py (v1 kept for reproducibility; v2 = exact-first + formatting-normalized fallback with original-offset recovery).
Scope: stored TRAIN/DEV outputs (E05, E07, E08B, E11, E12A, E12B, E12C, E13) + 40 new unit tests. Historical raw outputs are never modified.
Outcome: A - EVIDENCE_EVALUATOR_V2 APPROVED (see summary.md). Not committed; awaiting review.
```
