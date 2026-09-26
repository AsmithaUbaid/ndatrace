# SUPERSEDED / INVALIDATED BEFORE COMPLETION

**File:** `run_E03_prompt_selection_p00.jsonl`
**Status:** SUPERSEDED / INVALIDATED BEFORE COMPLETION — not used for any prompt-selection
decision.
**Completed cases:** 88 of 150 (stopped cleanly mid-run, file not corrupted — last record is
valid JSON).
**Reason:** the E03 experimental design changed before this run finished. Reconstruction-v2
was resequenced: **E06 (Retrieval Optimisation) now runs before E03 (Prompt Selection)** — see
`docs/experiment_registry.md`. E03's controlled context condition will use frozen retrieved
context (from E06) instead of full-context NDA text, since full-context prompt comparison
(this run's condition) is valid for architecture A1 specifically but does not establish that
the selected prompt transfers to fragmented/noisy retrieved evidence — the condition actually
relevant to the intended RAG pipeline.

**Not deleted.** Preserved as a historical record of the abandoned full-context attempt. No
classification metric was computed from this file, and none should be — its 88 predictions are
not scored, not compared across prompts, and not used to justify any decision.

**What is retained for reuse:**
- `TRAIN_PROMPT_v1.json` (the manifest) — its case selection may be reusable once E03 resumes
  under the new retrieved-context condition, subject to review at that time.
- `configs/prompts/classification/classification_p0{0,1,2}.yaml` (P0/P1/P2) — retained as
  proposed candidates; their content is unaffected by this supersession, only the *context*
  they'll be tested against changes.

E03 status: **PENDING**, not COMPLETE. No prompt-selection decision was made.
