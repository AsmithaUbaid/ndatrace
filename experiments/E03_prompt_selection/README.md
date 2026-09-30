```
Experiment ID: E03
Question: Which classification prompt gives qwen2.5:7b-instruct the most reliable three-way
    NDA classification behaviour under controlled conditions?
Hypothesis: explicit label definitions (P1) and a structured decision procedure (P2) will
    reduce confusion relative to a minimal prompt (P0), especially on Contradiction -- but the
    gain must be checked against added token cost, not assumed.
Why this experiment exists: E01 (Oracle) confirmed Contradiction is a genuine reasoning
    bottleneck even with perfect evidence; E03 asks whether prompt engineering alone (no
    retrieval, no architecture change) narrows that gap for the frozen primary local model
    under a realistic full-context condition.
Input dataset/split: TRAIN_PROMPT_v1 (official TRAIN only, 150 cases, 50/50/50 balanced
    diagnostic sample, seed=500)
Frozen dependencies: qwen2.5:7b-instruct (local only), full-context NDA text as the context
    condition, compact {"label": ...} output schema, temperature 0.0
Independent variable: prompt version (P0 minimal / P1 +definitions / P2 +decision procedure /
    P3 few-shot only if justified)
Controlled variables: model, manifest, context, temperature, output schema, parser, scoring
    logic, runtime environment -- identical across all prompt versions
Metrics: Macro-F1, per-class recall, Contradiction Recall (+CI), balanced diagnostic accuracy,
    parse-valid rate, confusion matrix, latency, tokens (NO retrieval metrics, no
    cross-model comparison -- model is fixed)
Expected cost: $0 (local-only, no hosted calls in E03)
Expected runtime: extrapolated ~55-65 minutes for P0+P1+P2 combined (150 cases x 3 prompts,
    see Stage A report for the calculation and its caveats)
Stop condition: Stage A ends at this proposal; Stage B ends when P0/P1/P2 (and P3 if approved)
    have each produced a complete 150-case result file
Result: COMPLETE -- P0 (minimal) wins decisively on both top-priority metrics
Decision: classification_prompt_v1 = P0, unchanged content
What becomes frozen after this: `configs/prompts/classification/classification_prompt_v1.yaml`,
    the default prompt for E05/E07/E08/E09-E11
```

## Stage A vs. Stage B

Same two-stage structure as E01. **Stage A (frozen earlier): design.** Manifest, context
condition, prompt ladder, schema, and decision rule proposed and frozen before any inference.
**Stage B (this run, 2026-09-26): execution, complete.** Resumed after E06 froze `retrieval_v1`
-- P0/P1/P2 each ran all 150 TRAIN_PROMPT_v1 cases against the frozen retrieval_v1 top-5
context (BM25/clause_256/top-20/rerank/top-5), qwen2.5:7b-instruct, temperature 0, local-only
($0 hosted spend). 450 total inference calls.

**Result**: P0 (minimal instruction, no label definitions, no decision procedure) dominates P1
(+definitions) and P2 (+decision procedure) on Contradiction Recall (22.0% vs 6.0% vs 2.0%) and
Macro-F1 (0.507 vs 0.448 vs 0.403) simultaneously -- the opposite of this experiment's own
pre-registered hypothesis that explicit structure would reduce label confusion. Adding
structure instead made the model default to NotMentioned on real Contradiction cases far more
often (Contradiction->NotMentioned: 37/50 under P0, 44/50 under P1, 46/50 under P2). Full
metrics, confusion matrices, and retrieval-vs-reasoning failure attribution: `summary.md` and
`E03_prompt_selection.ipynb`.

Full Stage A proposal: `summary.md`'s earlier sections. Reusable logic:
`evaluation/prompt_selection.py` (message construction + prompt-config loading; output parsing
and result-record shape reused directly from `evaluation/oracle.py`). Runner:
`scripts/run_e03_prompt_selection.py`. Analysis: `scripts/analyze_e03_prompt_selection.py`
(metrics + retrieval-aware failure attribution -> `results/prompt_failure_analysis.csv`).
Manifest generation: `scripts/build_train_prompt_manifest.py`. Prompt configs:
`configs/prompts/classification/classification_p0{0,1,2}.yaml` (candidates, retained) and
`classification_prompt_v1.yaml` (the frozen winner).
