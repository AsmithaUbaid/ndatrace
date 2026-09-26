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
Result: PENDING -- Stage B not yet approved
Decision: PENDING
What becomes frozen after this: PENDING (see summary.md's Stage A section)
```

## Stage A vs. Stage B

Same two-stage structure as E01. **Stage A (this commit's state): design/freeze.** Manifest,
context condition, prompt ladder, schema, and decision rule proposed and frozen. **No
inference performed.** **Stage B (after explicit approval): execution.**

Full Stage A proposal: `summary.md`. Reusable logic: `evaluation/prompt_selection.py` (message
construction + prompt-config loading; output parsing and result-record shape are reused
directly from `evaluation/oracle.py`, not duplicated). Runner: `scripts/run_e03_prompt_selection.py`
(written, syntax-checked, **not executed**). Manifest generation:
`scripts/build_train_prompt_manifest.py` (already run — local-only, deterministic, no model
calls). Prompt configs: `configs/prompts/classification/classification_p0{0,1,2}.yaml`.
