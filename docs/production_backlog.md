# Production Backlog / Deferred Items

Gaps identified during contract/audit work that are explicitly deferred — not implemented now,
tracked here so they aren't lost. Revisit under a later productionisation phase ("Part 10").

Current evidence referenced below: `experiments/E00B_budget_forecast/` (budget, complete), `experiments/E15_review_routing/` (routing/abstention, complete), `experiments/E20_final_rag_test/` (final architecture comparison, complete).

## Human review override/approval API

**Gap:** `backend/routes/review.py` has `POST /review`, `GET /review/{id}`, `/extract-pdf`,
`/hypotheses` — no endpoint exists for a reviewer to record an override, approval, or
rejection. The product promise (`docs/project_contract.md` §10, AUTHORITY) commits to this;
the backend doesn't yet expose it.

**Status:** deferred by explicit instruction. Do not implement until productionisation phase.

**Clarification:** the human reviewer is the final authority as a **product/governance rule** -- this is implemented today (the system never auto-approves or auto-rejects an NDA; every result is presented for a human to confirm or overrule, see `docs/architecture.md` §2). What is **not** implemented is **persisting** that reviewer decision as an explicit backend action/record (override, approval, rejection) -- there is no reviewer decision-write API. Do not describe one as existing.

## Terminology: "abstain" vs. "route to human review"

**Gap:** `pipeline/confidence.py`'s `Route` enum only has `ACCEPT`/`REVIEW` — there is no hard
`ABSTAIN` path (see ADR-005). Some docs/prose (including the project contract itself) use
"abstention" loosely, which reads as if a hard-abstain mechanism exists.

**Status:** resolved. E15 (review-routing calibration) is complete: no reliable automatic uncertainty router was found for this task. R1 (the structural/source-integrity check) remains useful only as a safeguard, not a generic uncertainty detector; R3 (keyword-disagreement) captured most failures but required ~51% review workload, well above the provisional target. **The current runtime has no active automatic routing or hard abstain policy.** Docs/prose should say "route to human review" for what is conceptually intended, never imply a calibrated, hard `ABSTAIN` mechanism exists, and never present raw reranker score or self-reported model confidence as trustworthy prediction confidence. See `docs/experiment_registry.md`'s E15 row and `experiments/E15_review_routing/summary.md`.

## Budget/spend reconciliation

**Gap:** `.env`'s `MAX_BUDGET_USD=6.99` is stale (verified 2026-09-22, predates logged T041
spend). No script currently recomputes true remaining balance from `results/runs/`/
`results/final/` cost fields.

**Status:** resolved/superseded by E00B (`experiments/E00B_budget_forecast/summary.md`, **COMPLETE**). E00B audited all historical hosted spend from saved per-prediction cost records (27 runs, $3.0011 total found) and established a live, user-reported planning budget ($5.00, recorded 2026-09-26) as the forward-looking constraint, explicitly superseding (not overwriting) the stale `.env` `MAX_BUDGET_USD=6.99` value. E00B does not own a future task here anymore -- this backlog item is closed. A live balance check as of this writing (OpenRouter API `/key` endpoint) shows $0.91 remaining of a $10.00 limit; if a lower-friction, always-current balance check is wanted, adding a small script that calls that endpoint directly would replace manual reconciliation -- that remains a genuinely open, but minor, nice-to-have, not a blocking gap.
