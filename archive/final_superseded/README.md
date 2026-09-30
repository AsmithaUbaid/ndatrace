# Final superseded runtime code

Code that was part of final's runtime at some point but has since been superseded by
a later refactor within final itself (not legacy history — that lineage,
`archive/legacy/` and `archive/legacy_experiments/`, was itself deleted in the
2026-09-29 legacy cleanup pass — confirmed zero code imports at the time, doc-citation-only; see
`audit/00_modification_log.md` for the resolution record). Kept for provenance, not imported by
any current code.

## `orchestrator.py` (deleted 2026-09-28)

Deleted after a repo cleanup pass reconfirmed zero importers, zero test dependencies, and zero
notebook/README runtime references. This section is kept to document what it was, for provenance.

The RAG+agent request-handling module that `backend/routes/review.py` used before it was
refactored to call `pipeline/final_review.py` (built on `pipeline/frozen_rag.py`'s frozen E20 RAG
top-5 retrieval) for both `/api/review` and `/review`. Confirmed via a full import-graph trace
(2026-09-28) to have zero remaining production or test importers — `pipeline/agent.py` and
`pipeline/agent_tools.py`, which it used, were themselves deleted 2026-09-29 in the same legacy
cleanup pass (also zero remaining importers by then, confirmed independently).

Still referenced by historical prose in `docs/experiments.md` and `docs/evaluation_protocol.md`
describing what it did during the T041/ADR-006 routing-independence fix — that prose is accurate
history and was not changed.
