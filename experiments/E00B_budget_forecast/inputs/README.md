# E00B frozen historical cost/latency inputs

`historical_cost_inputs.json` freezes the specific numbers `scripts/build_e00b_forecast.py`
computed from 9 pre-reconstruction legacy result files (`results/archive/runs/` and
`results/final/legacy/`), before those directories were deleted in the final legacy cleanup pass
(2026-09-29). The raw per-prediction JSONL files are gone; only the already-derived scalar values
below survive, which is all `build_e00b_forecast.py` ever read from them (it never inspected
individual predictions, only each file's final summary `metrics` block or its `predictions[*].
cost_latency.latency_ms` list, reduced to a mean).

Each entry's `source_file_removed` names exactly which now-deleted legacy run file the numbers
came from, for provenance.

## `per_case` (used by `historical_per_case_costs()`)

Each value is `{n_cases, total_cost_usd, usd_per_case}` read from that run's last JSONL record's
`metrics.total_cases` / `metrics.total_cost_usd`.

| Key | What it is |
|---|---|
| `oracle_v1_gemini` | B04 Oracle experiment, Gemini 2.5 Flash Lite, prompt v1, 150 dev cases |
| `oracle_v1_gpt5mini` | B04 Oracle experiment, GPT-5 mini, prompt v1, 150 dev cases |
| `rag_v2_gemini` | T024 standard RAG, Gemini, prompt v2, 150 dev cases |
| `full_context_test_gemini` | T041 final locked test-set eval, full-context architecture, Gemini, full 2,091-case TEST split |
| `rag_test_gemini` | T041 final locked test-set eval, RAG architecture, Gemini, full 2,091-case TEST split |
| `rag_agent_test_gemini` | T041 final locked test-set eval, RAG+agent architecture, Gemini, full 2,091-case TEST split |

## `latency` (used by `local_runtime_measurements()`)

Each value is `{n, mean_latency_ms}` — `n` predictions had a `cost_latency` block, and
`mean_latency_ms` is the mean of their `latency_ms` field.

| Key | What it is |
|---|---|
| `local_llama3.2_3b_full_context` | T041, full-context, local Llama 3.2 3B (Ollama), 500-case TEST subsample |
| `local_llama3.2_3b_rag` | T041, RAG, local Llama 3.2 3B, 500-case TEST subsample |
| `local_llama3.2_3b_rag_agent` | T041, RAG+agent, local Llama 3.2 3B, 500-case TEST subsample |
| `hosted_gemini_full_context` | T041, full-context, hosted Gemini, full 2,091-case TEST split |
| `hosted_gemini_rag` | T041, RAG, hosted Gemini, full 2,091-case TEST split |
| `hosted_gemini_rag_agent` | T041, RAG+agent, hosted Gemini, full 2,091-case TEST split |

Note the two Gemini-full-2091 entries appear in both sections (`full_context_test_gemini`/
`hosted_gemini_full_context` etc. are the same underlying run, read for two different derived
numbers — cost in one case, latency in the other) — this mirrors exactly how the original script
read the same 3 `results/final/legacy/run_T041_*_google_gemini-2.5-flash-lite.jsonl` files twice,
for two different purposes.

Verified byte-for-byte identical `results/budget/budget_plan.json` output before and after
`build_e00b_forecast.py` was switched to read from this file instead of the legacy paths
(2026-09-29 legacy cleanup pass; see `audit/00_modification_log.md` for the resolution record).
