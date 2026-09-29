# Prompt Version History

`classify_v1.txt`–`classify_v6.txt`, `agent_step_v1.txt`, `agent_step_v1_3tools.txt`, and
`agent_step_v2.txt` were the pre-reconstruction classifier/agent prompt lineage (`pipeline/
classifier.py`, `pipeline/agent.py`). Both modules and all of these prompt files were removed in
the final legacy cleanup pass (2026-09-29) — `pipeline/classifier.py`/`pipeline/agent.py` had zero
current importers left (only legacy tests and the old B04 oracle script, also removed). The full
decision history for that lineage (why v2 was adopted over v1, why v3/v4/v5 were rejected, why v6
was adopted as the final default before removal) remains recorded in `docs/decisions.md` and
`docs/experiments.md`, which are unaffected by this cleanup.

**Current production classification prompt**: `prompts/reconstruction_v2/gpt_p0.txt`, used by
`pipeline/final_review.py` (the frozen E20 top-5 RAG path, no agent/routing) — see that file and
`prompts/reconstruction_v2/` for the live prompt set.

## Live prompts

| File | Used by |
|---|---|
| `oracle_v1.txt` | `scripts/run_e01_oracle.py`, `tests/test_oracle.py` (current E01 Oracle experiment) |
| `agent_v2_control.txt` | E10/E11 reconstruction-v2 agent experiments |
| `reconstruction_v2/**` | Live E10/E11/E12+ reconstruction runtime and experiments |
