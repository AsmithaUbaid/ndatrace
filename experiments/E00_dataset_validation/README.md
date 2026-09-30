```
Experiment ID: E00
Question: Do we have one trustworthy, leakage-aware, reproducible evaluation universe before
    any model experiment begins?
Hypothesis: The official ContractNLI train/dev/test splits are clean (no doc-level overlap),
    label/evidence conventions are unambiguous, and the existing metric implementations
    (evaluation/metrics.py, evaluation/scorer.py) are correct -- but historical sample reuse
    (dev split used for both tuning and validation) needs to be disclosed and not repeated.
Why this experiment exists: docs/project_contract.md and the reconstruction brief require one
    coherent data/evaluation protocol before any experiment (Oracle onward) runs, instead of
    the historical pattern of ad hoc, differently-seeded samples per script.
Input dataset/split: data/contractnli/{train,dev,test}.json (official, read-only)
Frozen dependencies: none (pure local validation, no model/prompt/retrieval config involved)
Independent variable: none (this is a validation pass, not a comparison)
Controlled variables: n/a
Metrics: split sizes, label distribution, evidence-availability by class, doc-id/filename
    overlap between splits, metric unit-test pass rate
Expected cost: $0 (no LLM/API calls, no embedding-model downloads)
Expected runtime: minutes (JSON parsing + pytest)
Stop condition: all official-split checks and metric audits complete; no model call attempted
Result: see summary.md and results/
Decision: see summary.md
What becomes frozen after this: see docs/evaluation_protocol.md Part 1, "Frozen vs. not-yet-frozen"
```

## What this experiment does

Local-only dataset and evaluation-protocol validation. No LLM calls, no embedding-model calls, no
retrieval benchmarks, no hosted services. Produces:

- `results/split_validation.json` — official split sizes, label distribution per split,
  evidence-availability by class, and train/dev/test overlap checks.
- `results/metric_audit.json` — audit of `evaluation/metrics.py`/`evaluation/scorer.py` against
  hand-constructed sanity cases, plus the 3 new unit tests added to close gaps found.
- `results/contamination_summary.json` — pointer + summary of `docs/data_contamination_register.md`.
- `E00_dataset_validation.ipynb` — executed analysis notebook (per `docs/experiment_protocol.md`'s
  notebook convention): split counts, NotMentioned evidence-policy verification, overlap checks,
  the τ=0.5 span-count audit, metric sanity cases, and the case-ID split-qualification demo, all
  imported from `evaluation/` rather than reimplemented. Local-only, no model/API calls.

Full protocol write-up: `docs/evaluation_protocol.md` (Part 1). Full historical sample inventory
and TEST/DEV contamination disclosure: `docs/data_contamination_register.md`.
