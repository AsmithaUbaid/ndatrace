# Reconstruction-v2 superseded runtime code

Code that was part of reconstruction-v2's runtime at some point but has since been superseded by
a later refactor within reconstruction-v2 itself (not pre-reconstruction history — see
`archive/pre_reconstruction/` for that). Kept for provenance, not imported by any current code.

## `orchestrator.py` (deleted 2026-09-28)

Deleted after a repo cleanup pass reconfirmed zero importers, zero test dependencies, and zero
notebook/README runtime references. This section is kept to document what it was, for provenance.

The RAG+agent request-handling module that `backend/routes/review.py` used before it was
refactored to call `pipeline/final_review.py` (built on `pipeline/frozen_rag.py`'s frozen E20 RAG
top-5 retrieval) for both `/api/review` and `/review`. Confirmed via a full import-graph trace
(2026-09-28) to have zero remaining production or test importers — `pipeline/agent.py` and
`pipeline/agent_tools.py`, which it used, are unaffected and remain in `pipeline/` since
`tests/test_agent.py`/`test_agent_tools.py` still exercise them directly for E09–E11 provenance.

Still referenced by historical prose in `docs/experiments.md` and `docs/evaluation_protocol.md`
describing what it did during the T041/ADR-006 routing-independence fix — that prose is accurate
history and was not changed.
