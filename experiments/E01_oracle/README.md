```
Experiment ID: E01
Question: If NDATrace is given the correct gold evidence, how well can candidate models
    perform the three-way NDA classification task? (Reasoning ceiling, not retrieval, not
    architecture, not prompt tuning.)
Hypothesis: Reasoning is already strong given perfect evidence -- the real question is
    whether/how much it differs across smaller-local, stronger-local, economical-hosted, and
    stronger-hosted model capability points.
Why this experiment exists: separates reasoning failure from retrieval failure before any
    retrieval/prompt/architecture work begins (docs/project_contract.md, reconstruction brief).
Input dataset/split: TRAIN_ORACLE_v1 (official TRAIN only, 300 cases, 100/100/100 balanced
    diagnostic sample, seed=300)
Frozen dependencies: prompts/oracle_v1.txt (single baseline prompt, no tuning), compact
    {"label": ...} output schema, temperature 0.0
Independent variable: model (4 candidates: 2 local, 2 hosted)
Controlled variables: manifest, prompt, schema, label definitions -- identical across all 4 models
Metrics: Macro-F1, per-class recall, Contradiction Recall (+CI), confusion matrix,
    schema/parse-valid rate, latency, tokens, cost (NO retrieval metrics -- Oracle has no
    retrieval step)
Expected cost: ~$0.33 total hosted (2 hosted models x 300 cases, historical-actual-cost basis)
Expected runtime: local models, low tens of minutes (see Stage A report); hosted models, well
    under an hour
Stop condition: Stage A ends at this proposal; Stage B ends when all 4 models have produced a
    complete 300-case result file with no unresolved MODEL ERRORs
Result: PENDING -- Stage B not yet approved
Decision: PENDING
What becomes frozen after this: PENDING (see summary.md's Stage A section for the proposal)
```

## Stage A vs. Stage B

This experiment has two stages (reconstruction brief section 0):
- **Stage A (this commit's state): pre-run freeze.** Manifest, prompt, schema, and model
  identifiers proposed and frozen. **No inference performed.**
- **Stage B (after explicit approval): execution.** Runs all 4 models, logs hosted spend,
  evaluates results, builds the analysis notebook.

Full Stage A proposal: `summary.md`. Reusable logic: `evaluation/oracle.py` (input
construction + output parsing, provider-agnostic) and `scripts/run_e01_oracle.py` (the real
runner — written and syntax-checked, **not executed**, per the Stage A stop condition).
Manifest generation: `scripts/build_train_oracle_manifest.py` (already run — local-only,
deterministic, no model calls).
