# AV01 — architecture validation set (historical)

Historical experiment retained for provenance. It is not part of the final evaluation and must
not be used for final metrics.

## What it was

An independent check of the (pre-reconstruction) architecture freeze, run on data untouched by
any prior tuning decision: whole documents sampled first (`random.Random(99)` over document IDs
from official `train.json`), then all their cases included — 20 documents, 340 cases, seed=99
(deliberately distinct from the seed=42 dev sample). Verified zero overlap with the dev sample,
golden cases, and `test.json`.

## Where its result files live

The AV01 *result* JSONL files (`run_AV01_architecture_validation_{full_context,rag,rag_agent}.jsonl`)
were **not** moved — they remain in `results/runs/` and `results/final/legacy/`, because
`backend/routes/experiments.py`'s `GET /cost-estimate` endpoint globs `results/runs/*.jsonl` at
request time (see that file's module docstring). Removing them would require updating that route
first, which is a separate, deliberate code change, not an archive move. In practice the endpoint
always selects the larger-sample T041 file over AV01's (2,091 cases vs. 340), so AV01's file is
present but never actually selected.

Only the **manifest** (`architecture_validation_manifest.json`, the list of sampled document/case
IDs used to build the AV01 run) has been consolidated here, since nothing reads it at runtime —
only historical docs and the frozen builder script cite its path.

## Why it's kept at all

Its seed (99) and document-level sampling methodology are cited as reproducibility precedent by:
- `docs/data_contamination_register.md` (contamination audit table, §2 sampling-method finding)
- `docs/evaluation_protocol.md` (routing-reversal finding on T041-B, cross-checked against AV01)
- `scripts/build_train_oracle_manifest.py` (comment: seed=300 chosen to stay disjoint from AV01's 99)

The original builder/runner scripts (`build_architecture_validation_set.py`,
`run_architecture_validation.py`) remain in `archive/pre_reconstruction/scripts/` and still
reference `data/architecture_validation_manifest.json` by their original path — they are frozen
historical code, not re-run, so their internal paths were left as originally written rather than
edited to point here.

## Does not feed into the current architecture decision

Not referenced by root `README.md`, `notebooks/NDATrace_Complete_Technical_Tour.ipynb`, or
`docs/architecture_decisions/INDEX.md`'s ADR-012 (the current, canonical architecture freeze).
