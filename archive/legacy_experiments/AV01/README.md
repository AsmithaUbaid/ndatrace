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
lived in both `results/runs/` and `results/final/legacy/` (byte-identical copies) while
`backend/routes/experiments.py`'s `GET /cost-estimate` endpoint globbed `results/runs/*.jsonl` at
request time. That endpoint was removed in the final submission cleanup (it was dead in the current
product UI — the frontend never called it), so `results/runs/`'s copies were deleted as pure
duplicates rather than moved (`results/final/legacy/` still holds the canonical copy, since
`scripts/build_e00b_forecast.py` reads it directly by that path).

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
