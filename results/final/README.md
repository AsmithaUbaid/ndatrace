# results/final/ — canonical convenience summaries

These files are **convenience summaries generated from existing source artifacts** — they are not
a new measurement and never take priority over the original experiment outputs they were built
from. If a number here ever looks wrong, trust the source artifact, not this file.

## Structure

- **`reconstruction_v2/`** — the canonical source for the final report/demo (`docs/architecture.md`).
  Final story: **Rule** is the zero-cost baseline, **FULL** (GPT-5-mini + P0, whole document) is
  the strongest *measured benchmark* configuration on the official TEST set, **RAG** (GPT-5-mini +
  P0 + retrieved top-5) is the **retained interactive prototype/runtime** architecture actually
  served by the product, and the **selective agent was tested and rejected** (small, statistically
  inconclusive effect — see `docs/decisions.md`). FULL is a benchmark ceiling, not the served
  architecture.
- **`legacy/`** — retained only for historical provenance (the pre-reconstruction T041/AV01
  pipeline run described in the top-level `README.md`'s "Experiment progression (original
  pre-reconstruction pipeline — historical)" section). Not part of the reconstruction-v2 final
  result. **Kept in place, not moved to `archive/`**: `scripts/build_e00b_forecast.py` (part of the
  live E00B budget-forecast reproduction) reads these files directly by this path, and several
  `docs/*.md` files cite it — moving it would break reproducibility for a change that only saves a
  few MB of already-duplicated data. The one exact duplicate of this directory, `results/runs/`,
  was removed since nothing in the current runtime reads it (see `docs/api.md`'s removed
  `GET /cost-estimate` section).
- In both cases, **the original experiment directories under `experiments/` remain the
  authoritative raw sources** — these are convenience summaries and must never replace the raw
  experimental evidence they were generated from.

## Reconstruction-v2 files (E15–E18; `reconstruction_v2/` — this directory's current, final-facing content)

| File | Source experiment | Source artifact | Source commit | Measured / scenario | Population | Generated |
|---|---|---|---|---|---|---|
| `full_test_comparison.csv` | E17 + E17B | `experiments/E17B_full_test_completion/results/final_full_test_metrics.json#rule_qwen_gpt_full_comparison_2091` | 3b2167a, 270b006 | measured | n=2,091 (all TEST) | 2026-09-27 |
| `gpt_full_test_metrics.json` | E17 + E17B | `experiments/E17B_full_test_completion/results/final_full_test_metrics.json#full_gpt_2091` | 3b2167a, 270b006 | measured | n=2,091 | 2026-09-27 |
| `qwen_full_test_metrics.json` | E17 | `experiments/E17_final_test/results/final_metrics.json#qwen_full_2091` | 3b2167a | measured (API cost=$0; local compute/time NOT monetized) | n=2,091 | 2026-09-27 |
| `rule_full_test_metrics.json` | E17 | `experiments/E17_final_test/results/final_metrics.json#rule_full_2091` | 3b2167a | measured | n=2,091 | 2026-09-27 |
| `contradiction_analysis.json` | E17B (full), E17 (sample, consistency check only) | `experiments/E17B_full_test_completion/results/final_full_test_metrics.json#full_gpt_contradiction_220` | 270b006 | measured | n=220 (full); n=50 (sample) | 2026-09-27 |
| `cost_summary.json` | E17 + E17B ledger | `results/budget/reconstruction_spend_ledger.csv`, `experiments/E17B_full_test_completion/results/run_E17B_wall.json` | 270b006 | measured (AI cost); scenario (human-review/cost-to-serve terms — see E18) | n=2,091 GPT calls | 2026-09-27 |
| `routing_summary.json` | E15 | `experiments/E15_review_routing/results/validation_results.json` | dcdee80 | measured | n=138 (fresh DEV_ROUTING_v1 validation) | 2026-09-27 |
| `robustness_summary.json` | E16 | `experiments/E16_robustness_security/results/hosted_results.json` | 5717bdf | measured (small n) | n=20 matched pairs | 2026-09-27 |

All paths above are relative to `reconstruction_v2/` (e.g. `full_test_comparison.csv` is
`results/final/reconstruction_v2/full_test_comparison.csv`). Full detail, uncertainty intervals,
and every caveat live in each source experiment's own `summary.md` and `results/`.
`docs/experiment_registry.md` indexes all of E00–E19.

## Legacy files (`legacy/` — pre-reconstruction pipeline, historical, unrelated)

`carveout_examples.md`, `run_AV01_architecture_validation_*.jsonl`, and
`run_T041_final_test_*.jsonl` predate the reconstruction (branch `reconstruction`, E00–E19) and
belong to the **original** pipeline history described in the top-level `README.md`'s "Experiment
progression (original pre-reconstruction pipeline — historical)" section. They are kept as
scientific provenance for that earlier work and are **not** part of the reconstruction-v2 final
result. No reconstruction-v2 file overwrites or is named the same as any of these.
