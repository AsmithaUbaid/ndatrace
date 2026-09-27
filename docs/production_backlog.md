# Production Backlog / Deferred Items

Gaps identified during contract/audit work that are explicitly deferred — not implemented now,
tracked here so they aren't lost. Revisit under a later productionisation phase ("Part 10").

## Human review override/approval API

**Gap:** `backend/routes/review.py` has `POST /review`, `GET /review/{id}`, `/extract-pdf`,
`/hypotheses` — no endpoint exists for a reviewer to record an override, approval, or
rejection. The product promise (`docs/project_contract.md` §10, AUTHORITY) commits to this;
the backend doesn't yet expose it.

**Status:** deferred by explicit instruction. Do not implement until productionisation phase.

## Terminology: "abstain" vs. "route to human review"

**Gap:** `pipeline/confidence.py`'s `Route` enum only has `ACCEPT`/`REVIEW` — there is no hard
`ABSTAIN` path (see ADR-005). Some docs/prose (including the project contract itself) use
"abstention" loosely, which reads as if a hard-abstain mechanism exists.

**Status:** documented here; no text edited yet. Terminology should be standardized toward
"route to human review" once E13 (abstention/review-routing calibration) re-examines the
routing design under reconstruction-v2 — don't rename prose ahead of that decision.

## Budget/spend reconciliation

**Gap:** `.env`'s `MAX_BUDGET_USD=6.99` is stale (verified 2026-09-22, predates logged T041
spend). No script currently recomputes true remaining balance from `results/runs/`/
`results/final/` cost fields.

**Status:** owned by E00B (`docs/experiment_registry.md`), gates E01 (Oracle). Not resolved in
this phase.
