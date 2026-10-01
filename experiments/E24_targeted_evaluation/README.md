# E24 — Targeted evaluation on the checked-in golden+negative battery

Rule / FULL / RAG, all three run against the **current frozen final architecture**, on the same
49 cases (30 golden + 15 negative + 4 real evidence-quality cases). Full results, failure
analysis, and limitations: [`summary.md`](summary.md). Frozen protocol: [`config.json`](config.json).

This is a targeted regression comparison on deliberately hard, pre-existing cases — not a
replacement for the 2,091-case official TEST benchmark
(`experiments/E20_final_rag_test/`), which this experiment does not touch.

## Files

- `build_case_manifest.py` — builds `manifests/case_manifest.json` from `data/golden/golden_cases.json`,
  `negative_cases.json`, and `evidence_quality_cases.json` (zero model calls, deterministic).
- `run_classification.py` — runs Rule/FULL/RAG on the manifest. `--dry-run` (default) is a $0
  smoke test; `--live` makes real hosted calls (required for usable results). Already executed
  live for this experiment — see `results/run_E24_predictions.jsonl`.
- `analyze_e24.py` — rescan from saved predictions, zero model calls, prints the summary table
  and failure analysis. Reuses `evaluation/evidence_matching.py` directly, no alternative metric
  logic.
- `config.json` — the exact frozen architecture/evaluator configuration, asserted (not assumed)
  at runtime by `run_classification.py`'s `assert_frozen()`.
- `manifests/case_manifest.json` — the 49 cases with real NDA text, gold label, gold evidence,
  and full document span list, pulled from `data/contractnli/dev.json`.
- `results/run_E24_predictions.jsonl` — 147 rows (49 cases × 3 systems), every real executed
  call and every $0 deterministic Rule call. `results/run_E24_wall.json` — real spend/wall-time.
  `results/e24_analysis.json` — machine-readable output of `analyze_e24.py`.

## Reproduce the analysis (no paid calls)

```bash
python experiments/E24_targeted_evaluation/analyze_e24.py
```

## Provenance note

This experiment was built and the live run executed under the working directory name
`E25_golden_battery_final_architecture` before being renamed to `E24_targeted_evaluation` to
reuse the E24 identifier (the original E24, a reviewer-time pilot, was deliberately deleted
earlier and is not referenced here). Same protocol, same code, same results — only the directory
name and a few internal string constants changed post-execution; the real predictions file is
untouched. See `config.json`'s `execution.note`.
