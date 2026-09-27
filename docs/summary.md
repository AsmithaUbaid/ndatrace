# NDATrace — Project Summary

**NTU PE6201 Emerging AI Technologies.** Full detail is in `docs/decisions.md` (pre-reconstruction
decision log), `docs/experiment_registry.md` (reconstruction-v2 experiment ledger, E00–E19), and
`docs/architecture.md` (implementation) — this page is the 5-minute version of the **final,
selected** result.

## Problem statement

Reviewing an NDA against a company's confidentiality requirements is manual and slow: a lawyer
reads the whole document and checks it against each requirement one by one. NDATrace tests whether
this can be automated with evidence grounding — given an NDA and a confidentiality requirement,
classify it as **Entailment**, **Contradiction**, or **Not Mentioned**, and show the exact clause
the answer rests on.

## System design (final, selected)

```text
NDA + requirement
    -> input validation
    -> GPT-5-mini + the frozen P0 prompt + FULL NDA context (no retrieval, no agent, no routing)
    -> structured output parser
    -> runtime evidence-source validator v2 (checks the cited evidence is a genuine
       verbatim quote from the submitted NDA text)
    -> reviewer-facing result
    -> human final decision
```

Full-context GPT-5-mini is the selected prototype architecture. RAG and a selective agent were
both evaluated during reconstruction-v2 (E06–E11) and **not selected** — see "The one key finding"
below and `docs/architecture.md`/`docs/decisions.md` for the full reasoning. Full request-flow
detail: `docs/architecture.md`.

## How the final configuration was chosen

Reconstruction-v2 (E00–E19) re-derived the model, prompt, and architecture choice independently
under corrected discipline: E01 (Oracle/model diagnostic) selected `openai/gpt-5-mini`; E03
selected the frozen `P0` classification prompt over 3 alternatives; E05–E09 compared full-context,
RAG, and a selective agent on a matched development sample; E12–E13 re-confirmed full-context GPT
as the strongest candidate; E15 tested (and did not adopt) a deterministic review-routing policy;
E16 ran a robustness/injection check; **E17 + E17B ran the one-shot final locked TEST evaluation**
(150-case sample, then the remaining 1,941 cases) — this is the headline number below. Full
reasoning and every rejected alternative: `docs/experiment_registry.md`, `docs/decisions.md`.

## Framework

PE6201's Class 1 framework asks four questions before treating an AI system as fit for a task: what
output do you need, how much labelled data do you have, what does being wrong cost and who does it
hit, and can you check the answer. Mapped onto NDATrace: **Output** — a checkable label plus a
cited clause, not free text. **Data** — zero-shot against a fixed, engineered prompt, not thousands
of labelled examples. **Cost of being wrong** — high enough that it drove the evidence-grounding
design (see Limitations for who bears that cost). **Checkability** — the evidence citation *is*
the answer to this question, not a bolted-on feature: a reviewer verifies any output in seconds by
reading the cited clause, rather than trusting the label alone.

## Final results (official ContractNLI TEST set, n=2,091, one-shot, frozen configuration)

| System | Accuracy | Macro-F1 | Joint (label+evidence) | Contradiction Recall | NotMentioned Recall | Cost |
|---|---:|---:|---:|---:|---:|---:|
| Rule (no LLM) | 59.0% | 0.479 | 50.1% | 16.8% | 90.5% | $0 |
| Local Qwen (ctx16k) | 49.9% | 0.431 | 39.7% | 25.5% | 59.7% | $0 (API); local compute not monetized |
| **GPT-5-mini + P0 + FULL (final, selected)** | **77.6%** | **0.727** | **74.6%** | **75.5%** | **62.7%** | ≈$4.23 total |

Additional GPT-5-mini quality metrics (not architecture-comparison metrics, but part of the
evidence-grounding design's own checkability claim): **Evidence recall 93.3%**, **evidence
precision 74.7%**, **source-valid quote rate 98.0%** (98.0% of returned evidence quotes are
verified verbatim substrings of the submitted NDA text by the runtime validator — a source-
integrity check, not a correctness check).

Recomputed directly from `results/final/reconstruction_v2/{gpt_full_test_metrics,
rule_full_test_metrics,qwen_full_test_metrics}.json` and `full_test_comparison.csv` — not quoted
from memory. Source experiments: `experiments/E17_final_test/`, `experiments/E17B_full_test_
completion/`. The original E17 n=150 balanced hosted sample is **historical/superseded** for
headline metrics — E17B completed the remaining 1,941 TEST cases and the table above is the full
n=2,091 population result, not the n=150 sample.

## The one key finding

**Neither retrieval (RAG) nor a selective agent was needed, and full-context alone reached the
best measured result on every headline metric** on the matched reconstruction-v2 development
comparison (E06–E11) — RAG's context compression solves a token-budget problem this dataset's
short, curated NDAs (median ~2,300 tokens) don't actually have, and the tested selective agent
added orchestration and cost without a demonstrated benefit. Both were evaluated seriously, not
dismissed by assumption — see `docs/decisions.md`'s ADR entries and `docs/architecture.md` §2 for
the full record of what was tried and why it wasn't selected.

## Limitations

1. **"Not Mentioned" over-inference is the main residual weakness.** NotMentioned recall is 62.7%
   on the final TEST result, and it is the largest single failure bucket — the model too often
   infers a relationship the NDA doesn't actually address. In the course's audience-x-impact terms:
   NDATrace's realistic audience is a **company** (an in-house legal/business team), not an
   individual's one-off check, and the impact of a missed contradiction is **critical**, not low or
   medium — a contradicted confidentiality obligation wrongly reported as satisfied or silent is a
   real legal/business risk, and the person who relies on that answer instead of re-reading the
   document is who it directly harms.
2. **The system is evidence-grounded but not prompt-injection-hardened** (E16, disclosed, not
   patched). In a small controlled test (20 matched clean/attack pairs), 4 of 11 injection-type
   attacks succeeded, including two cases where the model's answer flipped to match an instruction
   embedded in the NDA text. The runtime evidence-source validator does not detect this — it
   confirms a quote came from the document, not that the document's content is trustworthy.
3. **No selective-review/abstention policy was adopted** (E15) — every deterministic routing
   policy tested either left a large share of failures silently unreviewed or required an
   unacceptable review workload. The runtime evidence validator remains a structural
   source-integrity check only, not a general uncertainty detector.
4. **A known, systematic weakness in exception/carve-out clause reconciliation**, originally found
   in the pre-reconstruction golden battery (hand-built negative test cases found a 100% failure
   rate, 4/4, on documents where a specific exception clause overrides an apparent general rule) —
   disclosed, not re-verified against reconstruction-v2's own case set, and not fixed.
5. **Long-document scalability is an untested design hypothesis.** ContractNLI's documents are all
   ordinary-length NDAs (median ~2,300 tokens); full-context's cost/latency profile at much longer,
   noisier real contracts has not been measured.

**Should this be deployed at all, given these numbers?** Not as a replacement for human review. A
tool whose NotMentioned recall is 62.7% will, on average, under-flag a meaningful share of cases a
careful reader would catch — for a company-audience, critical-impact task, that is not a defensible
substitute for a person reading the document. What the numbers do support is use as a **second
check alongside human review**, not instead of it: surfacing likely entailments/contradictions with
cited, source-verified evidence for a reviewer to confirm or overrule can plausibly speed up review
and catch errors a tired reader misses, without ever being the sole check. That is a narrower, more
defensible claim than "replaces review" — and it's the one these numbers support without softening
them.

## Historical note (pre-reconstruction pipeline)

An earlier pass through this project (before reconstruction-v2) built and measured a different
architecture — RAG + a selective agent, on `google/gemini-2.5-flash-lite`, reaching 78.7%/77.7%
accuracy (RAG/RAG+agent) on the same TEST split. That work is preserved for provenance in
`docs/decisions.md`, `docs/experiments.md`, and `archive/pre_reconstruction/` — it is **not** the
final, selected result and should not be cited as such. That pipeline's code and endpoints
(`POST /review`, `/history`) remain live as a restored, working batch-review alternative — not
the selected architecture, but not merely historical either — see `docs/architecture.md`'s
"Legacy path" section.

## Where to look for more detail

- `docs/experiment_registry.md` — the reconstruction-v2 experiment ledger (E00–E19), with per-experiment status and artifact paths
- `docs/decisions.md` — the pre-reconstruction decision log, with evidence and rejected alternatives (historical, cross-referenced by reconstruction-v2 docs where relevant)
- `docs/architecture.md` — current implementation, traced directly from code
- `docs/evaluation_case_design.md` — the regression/robustness/security test taxonomy
- `experiments/E18_business_course_synthesis/` — the full business/cost/course-framework synthesis, with live-computed figures
