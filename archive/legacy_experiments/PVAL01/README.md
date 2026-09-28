# PVAL01 — prompt validation set (historical)

Historical experiment retained for provenance. It is not part of the final evaluation and must
not be used for final metrics.

## What it was

Same rationale as AV01 (see `../AV01/README.md`), for prompt-version comparison on untouched
data: document-level sample from official `train.json`, seed=123 (distinct from the dev sample's
42 and AV01's 99), 26 documents, verified disjoint from AV01 and every other pool. Used to compare
full-context prompt versions v2/v5/v6 without touching any previously-tuned-on data.

## Contents of this directory

- `prompt_validation_manifest.json` — the sampled document/case ID manifest, moved from `data/`.
- `run_PVAL01_full_context_v2.jsonl`, `_v5.jsonl`, `_v6.jsonl` — the three prompt-version result
  runs, moved from `results/archive/runs/` (which otherwise holds genuinely still-cited
  supporting/decision-journey experiments — B01-B04, T018, T024, T041-Llama — left untouched).

Nothing in this repository reads these files at runtime; only historical docs and the frozen
builder script cite their paths.

## Why it's kept at all

Cited as reproducibility precedent for document-level, seed-disjoint sampling methodology by:
- `docs/data_contamination_register.md` (contamination audit table, §2 sampling-method finding)
- `scripts/build_train_oracle_manifest.py` (comment: seed=300 chosen to stay disjoint from
  PVAL01's 123)

The original builder/runner scripts (`build_prompt_validation_set.py`, `run_prompt_validation.py`)
remain in `archive/pre_reconstruction/scripts/` and still reference `data/prompt_validation_manifest.json`
by their original path — they are frozen historical code, not re-run, so their internal paths were
left as originally written rather than edited to point here.

## Does not feed into the current architecture decision

Not referenced by root `README.md`, `notebooks/NDATrace_Complete_Technical_Tour.ipynb`, or
`docs/architecture_decisions/INDEX.md`'s ADR-012 (the current, canonical architecture freeze).
