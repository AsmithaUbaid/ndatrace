# archive/pre_reconstruction/

This directory contains the **original, pre-reconstruction ("T-series") development history** of
NDATrace — the notebooks, scripts, and figures from the first pass through the project (dataset
validation → Oracle → model/retrieval tuning → RAG → confidence/abstention → selective agent →
architecture freeze → the original T041 final test-set evaluation).

**These artifacts are retained for provenance only.** They are:

- **not** the canonical reconstruction-v2 implementation or results,
- **not** to be cited as the project's final numbers,
- kept because they document real, genuine experimental work (including real findings and a real,
  disclosed prompt-injection vulnerability) that shaped the reconstruction that followed.

## Where the canonical, current material lives instead

| What | Where |
|---|---|
| Reconstruction-v2 experiments (E00–E19) | `experiments/E00_dataset_validation/` … `experiments/E18_business_course_synthesis/` (E19 is the frontend/backend integration itself, not a data-producing experiment directory) |
| Canonical final results | `results/final/reconstruction_v2/` |
| Canonical runtime architecture | `docs/architecture.md` |
| Canonical API | `docs/api.md` |
| Experiment ledger / decision log | `docs/experiment_registry.md`, `docs/decisions.md` |

## Contents of this directory

| Path | What it is |
|---|---|
| `notebooks/` | The original `01_data_validation.ipynb` … `10_cost_to_serve_analysis.ipynb` notebook sequence (plus its own `README.md`) — all pre-reconstruction, development-stage work. |
| `scripts/` | The pre-reconstruction ("T-series") experiment driver/analysis scripts that produced the results now split between `results/archive/runs/`, `results/final/legacy/`, and `data/*.json`. Each script's role is still traceable from `docs/decisions.md`'s ADR entries, which cite these scripts by name. |
| `results/comparisons/` | Pre-reconstruction dev-sample plots (Oracle, retrieval tuning, prompt tuning, model comparison, cost-to-serve) referenced by the notebooks above — distinct from `experiments/E18_business_course_synthesis/figures/`, which holds the reconstruction-v2 equivalents. |

Nothing here was deleted or rewritten — only moved out of the top-level `notebooks/`/`scripts/`/
`results/comparisons/` locations to make the active, reconstruction-v2-facing repository easier to
navigate for a reviewer.
