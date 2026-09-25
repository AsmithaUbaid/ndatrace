# NDATrace — Project Summary

**NTU PE6201 Emerging AI Technologies.** Full detail is in `docs/decisions.md` (decision log),
`docs/evaluation_protocol.md` (dataset/metric discipline), and `docs/architecture.md`
(implementation) — this page is the 5-minute version.

## Problem statement

Reviewing an NDA against a company's confidentiality requirements is manual and slow: a lawyer
reads the whole document and checks it against each requirement one by one. NDATrace tests whether
this can be automated with evidence grounding — given an NDA and one of ContractNLI's 17 standard
confidentiality requirements, classify it as **Entailment**, **Contradiction**, or **Not Mentioned**,
and show the exact clause the answer rests on.

## System design

```text
NDA + requirement
    -> retrieve relevant clauses (sentence chunking -> dense retrieval -> rerank -> rule-boost)
    -> classify: Entailment / Contradiction / Not Mentioned
    -> return the cited evidence (validated as a verbatim quote, not a paraphrase)
    -> if a routing signal flags the case as uncertain: escalate to a bounded,
       tool-using agent before answering
```

Three architectures were compared throughout: **Full-context** (whole document, no retrieval),
**RAG** (retrieve → rerank → classify), and **RAG + selective agent** (RAG, escalated on uncertain
cases to a 5-tool investigation loop). Model: `google/gemini-2.5-flash-lite` (hosted, via
OpenRouter). Full request-flow diagram, including why the production path makes two classifier
calls per requirement (to keep the routing decision independent of the retrieval it's judging):
`docs/architecture.md`.

## How the final configuration was chosen

Model, prompt, and retrieval configuration were each selected through dedicated experiments on a
150-case development sample (model bake-off, 6 prompt versions, 10 rounds of retrieval tuning).
The architecture itself (RAG + selective agent) was frozen on 2026-09-23 based on that same
development evidence, then checked against the full 2,091-case official ContractNLI test set and,
separately, against a 340-case set built from documents no tuning decision had ever touched
(architecture-validation run "AV01"). Full reasoning and every rejected alternative:
`docs/decisions.md`.

## Final results (official ContractNLI test set, 2,091 cases, frozen configuration)

| Architecture | Accuracy | Macro-F1 | Contradiction Recall | Joint Label+Evidence | Cost/case |
|---|---:|---:|---:|---:|---:|
| Rule (no LLM) | 59.0% | 0.479 | 16.8% | 0.501 | $0.000000 |
| Full-context | 81.2% | 0.760 | 59.1% (n=220) | 0.812 | $0.000328 |
| RAG | 78.7% | 0.738 | 63.6% (n=220) | 0.754 | $0.000152 |
| RAG + agent | 77.7% | 0.727 | 60.5% (n=220) | 0.747 | $0.000405 |

Recomputed directly from `results/final/run_T041_final_test_*.jsonl` on 2026-09-25, not quoted from
memory. Joint label+evidence correctness required a retroactive, zero-cost fix
(`scripts/backfill_joint_metric.py` — deterministic retrieval recomputation, no new API calls) after
a bug was found where evidence spans were never recorded for any architecture; all three hosted
values above are the corrected numbers.

## The one key finding

**The selective agent does not outperform plain RAG, and this was confirmed on two independent case
sets, not just one.** On the full 2,091-case official test (above), RAG+agent's accuracy (77.7%)
and Contradiction recall (60.5%) both trail plain RAG (78.7%, 63.6%). On the separate 340-case AV01
validation set (documents never touched by any tuning decision), the agent corrected 10 of 152
routed cases while introducing 19 new errors — a net loss. **Neither result reaches statistical
significance** (McNemar's exact test: p=0.088 on the official test set, comparable p-values on
AV01) — the finding is a consistent, repeated *pattern* across independent samples, not a proven
effect, and is reported at that strength, not overstated.

## Limitations

1. **Contradiction recall is the weakest metric for every architecture** (16.8–63.6% on the
   official test set), and it is the metric this project treats as highest priority — missing a
   real contradiction is the costliest kind of error a review tool can make. RAG's 63.6% is the
   best achieved; none of the three architectures reach a level that would justify unsupervised
   deployment.
2. **The architecture freeze was made on a repeatedly-reused 150-case development sample**, not an
   independent set — the freeze decision itself was not validated on fresh data until after the
   fact (AV01, built afterward specifically to check this).
3. **Long-document scalability is an untested design hypothesis.** RAG was kept over full-context
   partly on the argument that full-context's advantage should erode on longer, noisier real
   contracts — no experiment in this project has tested that; ContractNLI's documents are all
   ordinary-length NDAs.
4. **A known, systematic weakness in exception/carve-out clause reconciliation**: hand-built
   negative test cases found a 100% failure rate (4/4) on documents where a specific exception
   clause overrides an apparent general rule — the pipeline currently has no mechanism that
   reliably catches this pattern.

## Where to look for more detail

- `docs/decisions.md` — every architecture/prompt/retrieval decision, with evidence and rejected alternatives
- `docs/evaluation_protocol.md` — dataset roles, freeze discipline, development-reuse caveats
- `docs/architecture.md` — current implementation, traced directly from code
- `docs/evaluation_case_design.md` — the regression/robustness/security test taxonomy
- `notebooks/09_complete_experiment_story.ipynb` — the full experiment narrative with live-computed tables
