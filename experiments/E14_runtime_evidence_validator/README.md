# E14 — Runtime Evidence Validator Alignment

Zero model calls, no TEST. Aligns (for future pipeline use; no live caller today) `pipeline/evidence_validator.py` (runtime v2) to the frozen `evidence_evaluator_v2` formatting rules.
Shared normalization lives in `pipeline/evidence_text.py` (evaluation -> pipeline dependency direction already exists; pipeline never imports evaluation).
Replay: `scripts/e14_replay_runtime_validator.py` -> `results/`. Tests: `tests/test_evidence_validator.py`. Outcome: see summary.md. Approved (Outcome A).
