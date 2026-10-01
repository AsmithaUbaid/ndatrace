# Failure analysis

Concise summary of where RAG's errors actually come from on the full TEST set, and what that
implies for future engineering effort. All counts are from the real, verified E20 run — see
`experiments/E20_final_rag_test/summary.md` section C for the full breakdown and methodology;
this file does not restate that document, only its conclusion and one concrete example.

## Failure categories (n=576 non-Joint cases, out of 2,091 total)

| Category | Count | % of failures | What it means |
|---|---:|---:|---|
| Reasoning / classification | 448 | 77.8% | Gold evidence was retrievable; the model read it and drew the wrong conclusion (wrong label despite having the right clause). |
| Evidence selection | 59 | 10.2% | Label was correct; the cited evidence didn't match the gold span closely enough. |
| Retrieval-limited | 55 | 9.5% | The gold evidence was not in the top-5 retrieved chunks at all. |
| Runtime parser / source-validity | 14 | 2.4% | A parse or evidence-sourcing issue at the output layer. |

Source: `experiments/E20_final_rag_test/results/E20_final_report.json`'s `failure_taxonomy`,
computed by `scripts/analyze_e20_rag_test.py` directly from the frozen TEST run — not estimated.

## One representative case

`examples/case_failure/` walks through one real case end to end
(`test::77::nda-20`, category `reasoning_classification`): the retriever found the exact clause
the gold label is based on, the model's cited quotes are genuine and verbatim (the runtime
validator passes the case cleanly), and the model still got the label wrong — it read a mandatory
"return or destroy" obligation as implicitly permitting retention, inverting the clause's actual
polarity. See that directory for the full input/retrieval/output/validation trail.

## What this implies for future engineering work

**Reasoning errors, not missing evidence, are the dominant failure mode (77.8%).** The practical
consequence: the highest-leverage next step is not retrieval tuning — it's improving how the
model interprets clauses it already has, particularly negation and conditional/exception language
("unless," "provided that," "as an alternative to"). This echoes a pattern found independently
multiple times across this project's experiments (E03's prompt-structure test, E04's rule-baseline
analysis, E17's C→E failure review) — exception and polarity handling is a recurring, specific
weakness, not a one-off.

**Retrieval-limited failures are real but secondary (9.5%).** Retrieval tuning (E06: chunk size,
BM25 vs. dense, reranking) already closed most of the gap that's closeable this way; the
remaining 55 cases are a smaller target than the 448 reasoning failures.

## Why more retrieval, or more agentic complexity, may not help

This isn't a hypothesis — it was tested twice and failed both times:

- **E09** manually reviewed all 39 residual GPT failures on a dev sample and found the agentic
  "dynamic information acquisition" opportunity (cases where an agent fetching more context could
  plausibly fix the error) was **1 case out of 39** — a 0.67-point ceiling, vs. a 4.0-point ceiling
  from simply fixing the 6 retrieval-filtering cases statically. The agent's addressable surface
  was tiny even in the best case.
- **E11** built and ran the selective agent anyway, on 15 real escalated cases. It made **zero
  tool calls** on every single triggered case, and its net joint-success benefit across all
  transitions was **exactly 0.0 percentage points** (one recovery cancelled by one regression),
  for real added API spend. It was not carried into the runtime.

Both results point the same direction as this file's own case study: the errors are reasoning
errors on evidence the system already has, not evidence-access problems an agent or deeper
retrieval would fix. More retrieval depth or agentic tool use would be solving a problem this
system mostly doesn't have.

## A smaller-scale, mechanism-level complement (E24)

This file's taxonomy is TEST-scale (n=2,091) and category-level. A separate, smaller targeted
evaluation (`experiments/E24_targeted_evaluation/`, 49 cases, current architecture, Rule/FULL/RAG)
traced individual failures down to the clause level — not a replacement for the counts above, a
finer-grained look at a handful of real cases:

- **Case 038**: a traceable instance of FULL's full-document access acting as a liability, not an
  asset — FULL over-weighted a real distractor clause; RAG's narrower retrieved context avoided
  it and predicted correctly. One data point, not a general claim that RAG's evidence selection
  beats FULL's.
- **Cases 007/043**: RAG's "evidence selection" failures (predicted label correct, cited evidence
  insufficient) decomposed into exact gold-span coverage fractions — both cases had gold evidence
  partially outside RAG's top-5 retrieved context (a genuine retrieval-coverage gap) *and* a gold
  span RAG didn't cite despite it being retrieved. Neither "pure retrieval miss" nor "pure
  selection failure" describes these cases accurately on its own.
- **Exception/carve-out cases (ADR-011)**: re-confirmed under the current architecture — 3 of 4
  documented cases still fail on both FULL and RAG, consistent with this file's point that
  exception/polarity handling, not retrieval, is the recurring weakness.

Full diagnostic detail: `experiments/E24_targeted_evaluation/summary.md`.
