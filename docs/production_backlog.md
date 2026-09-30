# Production Backlog / Deferred Items

Gaps identified during contract/audit work that are explicitly deferred — not implemented now,
tracked here so they aren't lost. Revisit under a later productionisation phase ("Part 10").

Current evidence referenced below: `experiments/E00B_budget_forecast/` (budget, complete), `experiments/E15_review_routing/` (routing/abstention, complete), `experiments/E20_final_rag_test/` (final architecture comparison, complete).

## Human review override/approval API

**Status: implemented (2026-09-30).** `POST /review/{review_id}/items/{item_id}/decision`
(`backend/routes/review.py`) now lets a reviewer record `approved`/`overridden`/`rejected`,
with an optional note and reviewer name, persisted append-only in the new `review_decisions`
table (`backend/database.py`). `GET /review/{review_id}` returns each item's latest decision.
The frontend (`RequirementCard.tsx`'s `DecisionControls`, wired from `app/page.tsx` and
`app/history/page.tsx`) surfaces Approve/Override/Reject buttons with a note field on every
persisted review item, and shows the recorded decision (with the option to change it) once one
exists. This is the persisted form of the product promise (`docs/project_contract.md` §10,
AUTHORITY) — the AI never auto-approves or auto-rejects (unchanged, was already true), and now
what the human actually decided is written down, not just implied.

**Verified:** `tests/test_review_decisions.py` (3 tests, isolated sqlite db) + a live curl
round-trip against the running dev backend (seed review created via `database.save_review`,
`POST .../decision`, confirmed via `GET /review/{id}`, then the seed data removed). Not verified
through an actual browser click-through — no browser tool was available in the session that
implemented this; `npx tsc --noEmit` and `next build` both pass, and the existing
`tests/test_backend.py` suite (13 tests) is unaffected.

**Not done:** no reviewer authentication exists, so `reviewer` is a free-text field the caller
supplies (or omits) — fine for a single-user academic demo, not for a multi-reviewer deployment.

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
