# NDATrace Architecture

This describes the interactive prototype runtime, verified directly against
`pipeline/frozen_rag.py`, `pipeline/final_review.py`, and `backend/routes/review.py`. Both the
single-requirement endpoint (`POST /api/review`) and the batch UI endpoint (`POST /review`) use the
same frozen E20 RAG pipeline. For quality-reference conclusions and rejected alternatives, see
`docs/architecture_decisions/INDEX.md`.

## 1. Request flow (`POST /api/review`, `backend/routes/review.py`)

```text
NDA + requirement
        |
input validation
        |
clause-aware chunking (256 tokens; frozen overlap config 50)
        |
BM25 top-20 -> ms-marco-MiniLM-L-12-v2 rerank -> top-5 context
        |
openai/gpt-5-mini + frozen GPT-P0 prompt   [pipeline/final_review.py]
        |
structured output parser   [evaluation/structured_output.py]
        |
runtime evidence-source validator v2   [pipeline/evidence_validator.py]
        |
reviewer-facing result   { label, evidence, source clauses, source_valid, needs_human_review }
        |
human final decision
```

The classifier receives only the retrieved top-five context, never the full NDA. There is no
agent, routing policy, rule boost, or silent FULL fallback. GPT-P0 requests only
`{label, evidence}`; there is no model-reported confidence, so none is fabricated. The batch API
retains its historical confidence field as `null` with `confidence_available: false`.

## 2. Product runtime decision versus the quality-reference result

NDATrace's interactive prototype uses the frozen top-5 RAG pipeline because it offers a
bounded-context architecture, lower input-token usage, and clause-level retrieval suitable for
interactive NDA review.

FULL-context GPT remains the strongest measured quality-reference configuration on the ContractNLI
evaluation dataset's TEST split, achieving higher Joint evidence-grounded correctness. Therefore
the prototype runtime choice is an engineering/productization decision, not a claim that RAG
achieved higher quality.

- **Full-context is the strongest measured quality-reference configuration.** On the full 2,091-case official
  ContractNLI TEST set, GPT-5-mini + P0 + FULL scored accuracy 77.6%, macro-F1 0.727, joint
  label+evidence correctness 74.6%, Contradiction recall 75.5% (n=2,091; see
  `docs/experiment_registry.md`'s E17/E17B rows).
- **RAG is the interactive prototype runtime.** On the matched development-sample
  comparison (E13), retrieval reduced input tokens substantially but did not demonstrate a quality
  advantage over full context. **E20 repeated this as a same-population, all-2,091-TEST-case
  comparison with paired significance testing**: RAG's classification accuracy was statistically
  indistinguishable from FULL (76.8% vs 77.6%, McNemar p=0.217), but FULL's Joint (evidence-
  grounded) success was significantly higher (74.6% vs 72.5%, p=0.0047) — a real, not noise-level,
  gap. RAG cut input tokens 50.4% and API cost 16.8% on the same run. It is the
  **quality-reference-losing but production-oriented** runtime: bounded context cost regardless of
  document length, and reusable per-document retrieval indexing across the 17 requirement checks —
  a scaling argument this dataset (median 1,836 / max 7,861 TEST tokens) is too short to itself
  validate against real 50–100 page contracts. Full record: ADR-012,
  `docs/architecture_decisions/INDEX.md`.
- **The selective agent was evaluated but did not demonstrate useful tool-use benefit and was not
  selected.** Net effect was small and statistically inconclusive across every sample tested.
- **E15 did not establish a sufficiently effective general selective-routing policy.** Every
  routing signal tested either left a large share of failures unreviewed or required an
  unacceptable review workload; no ACCEPT/REVIEW or ACCEPT/ABSTAIN policy is active in this path.
  Automatic uncertainty routing was evaluated but not adopted because the tested signal did not
  reliably isolate errors. The prototype escalates deterministic/security failures (parse errors,
  invalid labels, unsupported quotes, E22's prompt-injection guard) via the `security_review_required`
  flag, but it cannot automatically detect every semantically wrong verdict. Human review therefore
  remains mandatory on every case, not just flagged ones.
- **The human reviewer remains the final authority.** This system produces a checkable label plus
  cited evidence for a reviewer to confirm or overrule — it does not auto-approve or auto-reject
  an NDA.
- **The system is evidence-grounded but not prompt-injection-hardened.** The evidence validator
  confirms a quoted string came from the source document; it does not confirm the document's
  content is trustworthy. A disclosed injection limitation is recorded in
  `docs/experiment_registry.md`'s E16 and E21 rows.

## 3. Final held-out TEST metrics (n=2,091, one-shot, official TEST split)

| System | Accuracy | Macro-F1 | Joint (label+evidence) | Contradiction recall |
|---|---:|---:|---:|---:|
| **GPT-5-mini + P0 + FULL (quality reference)** | **77.6%** | **0.727** | **74.6%** | **75.5%** |

Full breakdown, comparators (rule baseline, local Qwen), and provenance: `results/final/README.md`,
`docs/experiment_registry.md` (E17/E17B).

A same-population RAG comparator (frozen `retrieval_v1` top-5, identical model/prompt/evaluator)
was also run on the full TEST split (E20) for a paired statistical comparison — FULL's Joint
advantage held and is statistically significant there too. The interactive prototype nevertheless
uses that unchanged RAG configuration for the product reasons in §2; see ADR-012 for the record.

## 4. Batch and single-requirement entry points

`POST /api/review` reviews one free-text requirement. `POST /review` reuses one BM25 index to review
any selected subset of the 17 standard requirements and persists the results for `/history`.
Both call `pipeline/final_review.py`; neither calls `pipeline/orchestrator.py`, the agent, or a
routing policy. The older agent code remains only for historical experiment reproducibility.
