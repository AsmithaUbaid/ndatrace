# Experiment Protocol — Reconstruction-v2

Governance rules for every experiment run under the reconstruction-v2 lineage (`E00` onward,
see `docs/experiment_registry.md`). These apply going forward; they do not retroactively
re-grade the historical T-series experiments (`docs/decisions.md`, `docs/experiments.md`).

## Rules

1. One experiment = one question.
2. Change one major variable at a time.
3. Record the git commit hash for every run.
4. Record model/provider/version.
5. Record prompt version.
6. Record dataset manifest/split used.
7. Record random seed where applicable.
8. Record retrieval configuration where applicable.
9. Record token usage.
10. Record cost.
11. Record latency.
12. Save raw predictions.
13. Save retrieved evidence IDs.
14. Save aggregate metrics separately from raw outputs.
15. Define the stop condition before running.
16. State the decision after the experiment.
17. State what becomes frozen as a result.
18. Do not tune on the blind test.
19. Negative results are valid findings — report them, don't discard the experiment.
20. Historical experiment results (T-series) may motivate a reconstruction-v2 hypothesis but
    may not silently determine a reconstruction-v2 config value. If a historical number is
    used as a starting point, say so explicitly and re-verify it under E00–E12, not assume it.

## Where things live

- Per-experiment write-up: `experiments/E##_short_name/README.md` (template:
  `experiments/_template/README.md`).
- Run output (once an experiment actually executes): `results/runs/E##/YYYYMMDD_HHMMSS_<id>/`
  — config snapshot, git commit, predictions, metrics, token/cost log, runtime log. Never
  overwritten; each run gets a new timestamped directory.
- Aggregate/comparison tables across runs: `results/aggregate/` (reconstruction-v2) —
  distinct from the historical `results/comparisons/`.
- Budget reconciliation: `results/budget/` (see its README — populated by E00B, not before).

## Data immutability

Raw ContractNLI data (`data/contractnli/`) is never altered. Generated/derived files
(processed text, new splits, eval-case selections) go in `data/processed/`, `data/splits/`,
`data/eval_cases/` once those are created by an experiment that needs them — none are created
in this phase. The existing flat `data/golden/` and top-level analysis JSON files
(`data/*.json`) are historical outputs, left in place.

## Results immutability

Past raw experiment outputs (`results/runs/`, `results/final/`) are never overwritten. Future
reconstruction-v2 runs write to a new, uniquely identifiable directory per run
(`results/runs/E##/YYYYMMDD_HHMMSS_<short-id>/`), never reusing a path. No such directories
exist yet.

## Notebooks vs. source code

Notebooks are for exploration, visualisation, analysis, and sanity checking. Reusable logic
belongs in Python modules (`pipeline/`, `evaluation/`) that notebooks and experiments both
import — never copy/pasted into a notebook. Known deviation to clean up later, not now: per
`experiments/README.md`, this project's actual historical pattern was standalone
`scripts/run_*.py`/`scripts/compare_*.py` files rather than notebook-driven or
config-driven experiments — reconstruction-v2 experiments should call the same reusable
`pipeline/`/`evaluation/` modules those scripts already use, not reintroduce duplicated logic.

## Production code boundary

- `frontend/` and `backend/` are downstream of architecture selection (E12) — they should not
  drive it.
- `frontend/` must not contain model/retrieval logic.
- Experimental notebooks/scripts are not production service code.
- `backend/` may reuse frozen research components (`pipeline/`, `evaluation/`) only after
  reconstruction-v2 selects them — it currently reuses the historical T-series selections,
  which is expected to continue working during this phase (no product code changes here) but
  is understood to be provisional pending E12.

## Relationship to historical work

The T-series experiments already in this repo (`docs/decisions.md`, `docs/experiments.md`,
`results/runs/run_T*.jsonl`, `results/final/run_T041_*.jsonl`) are **historical evidence**,
preserved as-is. They are not held to this protocol retroactively, and reconstruction-v2
experiments must not silently inherit their conclusions (see `docs/project_contract.md` §16
and the reconstruction ADR index at `docs/architecture_decisions/INDEX.md`).
