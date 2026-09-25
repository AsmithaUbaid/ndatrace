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

## TRAIN_WORKING / TRAIN_ORACLE / TRAIN_PROMPT manifest generation rule

Reconstruction-v2 uses the official ContractNLI TRAIN/DEV/TEST split as-is — no fourth
operational split (`docs/evaluation_protocol.md` Part 1 section 3). Fixed TRAIN subsets
(`TRAIN_WORKING` and further subsets of it, e.g. `TRAIN_ORACLE`/`TRAIN_PROMPT`) may be created
only for cost/runtime control, never as a substitute for DEV's validation/architecture-selection
role. When these are eventually created (E00B informs feasible sample size/runtime, but does not
decide the partition — **model performance must never be used to determine the partition**):

- Partition at NDA **document** level first, then include all of that document's hypothesis
  cases (§5 of `docs/evaluation_protocol.md` Part 1) — never scatter one document's cases across
  differently-purposed subsets.
- Use a fixed, recorded random seed (distinct from any other manifest's seed, per the existing
  convention of seed=99/123 for AV01/PVAL01).
- Generate the manifests **once**, before Oracle or any model result exists — not derived from,
  or adjusted in response to, any model output.
- Never resample either manifest because a result was inconvenient. A bad result is a finding, not
  grounds for a new random draw (rule 19 above).

## Notebook convention

Every major reconstruction-v2 experiment (E00–E17) should have a reproducible analysis notebook
where useful, at `experiments/E##_short_name/E##_short_name.ipynb`. The notebook's job:
experiment walkthrough, loading the frozen manifest/config, displaying counts/results, analysis,
plots/tables, failure inspection, and stating the conclusion/decision reached. **Reusable system
logic stays in Python modules/scripts** (`pipeline/`, `evaluation/`, `scripts/`) that the notebook
imports — never reimplemented in notebook cells (§0A of the planning document; same rule the
historical T-series notebooks were meant to follow).

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
