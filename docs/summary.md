# NDATrace — Project Summary

**NTU PE6201 Emerging AI Technologies.** Full detail is in `docs/experiment_registry.md`
(final experiment ledger, E00–E20), `docs/architecture_decisions/INDEX.md`
(final ADRs, incl. historical ADR-001–ADR-011 status), and `docs/architecture.md`
(implementation) — this page is the 5-minute version of the **final, selected** result.

## Problem statement

Reviewing an NDA against a company's confidentiality requirements is manual and slow: a lawyer
reads the whole document and checks it against each requirement one by one. NDATrace tests whether
this can be automated with evidence grounding — given an NDA and a confidentiality requirement,
classify it as **Entailment**, **Contradiction**, or **Not Mentioned**, and show the exact clause
the answer rests on.

## System design (interactive prototype)

```text
NDA + requirement
    -> input validation
    -> clause-256 chunking -> BM25 top-20 -> L-12 rerank -> top-5 context
    -> GPT-5-mini + the frozen P0 prompt (no agent, no routing)
    -> structured output parser
    -> runtime evidence-source validator v2 (checks the cited evidence is a genuine
       verbatim quote from the submitted NDA text)
    -> reviewer-facing result
    -> human final decision
```

The interactive prototype uses frozen E20 RAG for bounded context, lower input-token use, and
 (evidence-grounded) success was higher than RAG's — and at TEST scale that gap is **statistically
significant** (74.6% vs 72.5%, McNemar p=0.0047), not just directionally favorable. Classification
accuracy alone was not distinguishable between the two architectures (p=0.217).

**Production-oriented direction: RAG is retained, not because it won on quality, but because of
its scaling profile.** RAG cut input tokens 50.4% and API cost 16.8% on E20's TEST run, and its
context stays bounded regardless of document length — a real advantage for larger, repeatedly-
queried enterprise contracts that this dataset (TEST median 1,836 tokens, max 7,861) is too short
to stress-test. This is an explicit, documented engineering trade-off (~2.2pp of Joint success
given up on ContractNLI) — not a claim that RAG is more accurate on long contracts, which remains
an open validation question.

The tested selective agent, separately, added orchestration and cost without a demonstrated
benefit on either the development or TEST evidence and was not selected — the tested retrieval-
agent configuration did not provide sufficient value for this task, not that agents cannot work
here in principle.

Both RAG and the agent were evaluated seriously, not dismissed by assumption — see
`docs/architecture_decisions/INDEX.md` (ADR-012, E20, and its historical ADR-001–ADR-011 status
table), plus `docs/architecture.md` §2, for the full record of what was tried and why.

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
   unacceptable review workload. Automatic uncertainty routing was evaluated but not adopted
   because the tested signal did not reliably isolate errors. The prototype escalates
   deterministic/security failures (E22's injection guard), but it cannot automatically detect
   every semantically wrong verdict — human review therefore remains mandatory. The runtime
   evidence validator remains a structural source-integrity check only, not a general uncertainty
   detector.
4. **A known, systematic weakness in exception/carve-out clause reconciliation**, originally found
   in the legacy golden battery (hand-built negative test cases found a 100% failure
   rate, 4/4, on documents where a specific exception clause overrides an apparent general rule) —
   disclosed, not re-verified against final's own case set, and not fixed.
5. **Long-document scalability is an untested design hypothesis.** ContractNLI's documents are all
   ordinary-length NDAs (TEST-split median 1,836 tokens, max 7,861 — measured directly in E20);
   full-context's cost/latency profile at much longer, noisier real contracts (50–100 page
   enterprise agreements) has not been measured. This is precisely why RAG, despite trailing FULL
   on this dataset's Joint-success quality reference (E20, ADR-012), is retained as the documented
   production-oriented direction for a real deployment at that scale, rather than discarded outright.

**Should this be deployed at all, given these numbers?** Not as a replacement for human review. A
tool whose NotMentioned recall is 62.7% will, on average, under-flag a meaningful share of cases a
careful reader would catch — for a company-audience, critical-impact task, that is not a defensible
substitute for a person reading the document. What the numbers do support is use as a **second
check alongside human review**, not instead of it: surfacing likely entailments/contradictions with
cited, source-verified evidence for a reviewer to confirm or overrule can plausibly speed up review
and catch errors a tired reader misses, without ever being the sole check. That is a narrower, more
defensible claim than "replaces review" — and it's the one these numbers support without softening
them.

## Historical note (legacy pipeline)

An earlier pass through this project (before final) built and measured a different
architecture — RAG + a selective agent, on `google/gemini-2.5-flash-lite`, reaching 78.7%/77.7%
accuracy (RAG/RAG+agent) on the same TEST split. That legacy lineage (its scripts,
prompts, and pipeline modules) has since been removed from the repository as part of the final
final cleanup — this note preserves the historical numbers only; the code that produced
them is gone. It is **not** the final quality-reference result and should not be cited as such. The
live `POST /review` and `/history` product flow uses the frozen E20 top-5 RAG runtime without the
agent; see `docs/architecture.md`.

## Where to look for more detail

- `docs/experiment_registry.md` — the final experiment ledger (E00–E23), with per-experiment status and artifact paths
- `docs/architecture_decisions/INDEX.md` — final ADRs (ADR-012: E20's quality-reference-vs-production-oriented FULL/RAG finding) plus the historical ADR-001–ADR-011 status table
- `docs/architecture.md` — current implementation, traced directly from code
- `docs/evaluation_case_design.md` — the regression/robustness/security test taxonomy
- `experiments/E18_business_course_synthesis/` — the full business/cost/course-framework synthesis, with live-computed figures
