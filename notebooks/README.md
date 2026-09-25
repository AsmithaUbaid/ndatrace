# Experiment Notebooks

Experiments were conducted iteratively as the project progressed, not in one planned pass — some
notebooks contain multiple chronological "Round 1 / Round 2 / ..." explorations reorganized after
the fact for readability. All are **development-stage** work unless noted otherwise: results were
used to make tuning decisions and should be read as exploratory evidence, not as an unbiased
estimate of final generalization (see `docs/evaluation_protocol.md`'s development-reuse warning).

| # | Notebook | Purpose | Data role |
|---|----------|---------|-----------|
| 01 | `01_data_validation.ipynb` | Dataset quality checks (A01–A07) | Development setup |
| 02 | `02_oracle_experiment.ipynb` | Oracle ceiling measurement (B04) | Development |
| 03 | `03_model_comparison.ipynb` | Model selection (C01) | Development |
| 04 | `04_retrieval_experiments.ipynb` | Chunking, embedding, reranking, top-K/pool sweeps (D01–D07) | Development |
| 05 | `05_rag_e2e.ipynb` | Standard RAG end-to-end, prompt selection | Development |
| 06 | `06_confidence_abstention.ipynb` | Threshold/signal selection (F01–F06) | Development |
| 07 | `07_selective_agent_experiments.ipynb` | Selective agent vs. frozen RAG baseline | Development |
| 08 | `08_architecture_selection.ipynb` | Cross-architecture comparison and freeze rationale | Development / architecture analysis |
| 09 | `09_complete_experiment_story.ipynb` | Full narrative: problem → every experiment → decision → what's established/uncertain → T041 status → architecture-validation status | Reads saved results only — the capstone summary of 01–08, includes the live status of the untouched architecture-validation run (AV01) |
| 10 | `10_cost_to_serve_analysis.ipynb` | Cost-to-serve / break-even analysis | Post-freeze business analysis (uses T041 test-set cost figures) |

None of these notebooks reports the official final test-set (T041) result as its headline number —
that lives in `results/runs/run_T041_*.jsonl` and is summarized in `docs/decisions.md` (ADR-010) and
`docs/evaluation_protocol.md`. Notebook 10 is the one exception that uses a T041-derived cost figure
as an input, but its own analysis (break-even point, savings projection) is a downstream business
calculation, not itself part of the accuracy evaluation.

**Renumbering note:** `10_cost_to_serve_analysis.ipynb` was previously numbered `09` —
moved to make room for `09_complete_experiment_story.ipynb`, which caps the technical experiment
ladder (01–08) with one coherent narrative, before the cost analysis's downstream business framing.

## Notebooks 07 and 08 — reconstruction note

These two notebooks did not exist as notebooks until this documentation cleanup,
despite being referenced in an earlier version of this README. The underlying experiments were real
and were run — as standalone scripts (`scripts/run_agent_experiment.py`,
`scripts/run_hosted_comparison.py`, `scripts/run_final_test_evaluation.py`,
`scripts/run_golden_battery_cases.py`, etc.) rather than as notebooks — with results saved to
`data/agent_experiment.json`, `results/runs/run_T041_*.jsonl`, and the full reasoning recorded in
`docs/decisions.md`'s ADR-007 (agent), ADR-008/ADR-009 (architecture selection). Notebooks 07 and 08
were built directly from those already-saved result files — **no new model or API calls were made
to create them.** See each notebook's introduction cell for its exact inputs.
