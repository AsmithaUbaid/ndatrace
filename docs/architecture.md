# NDATrace Architecture

This describes the **currently implemented** system, verified directly against
`pipeline/orchestrator.py`, `backend/routes/*.py`, and `backend/app.py` as of 2026-09-25 — not an
aspirational design. See `docs/decisions.md` for why each component looks the way it does, and
`docs/evaluation_protocol.md` for what evidence backs the architecture choice.

## 1. System overview

Synchronous modular monolith:

- **Pipeline** (`pipeline/`): parser → chunker → embedder → retriever → reranker → rule-baseline →
  classifier → confidence/routing → selective agent, orchestrated by `pipeline/orchestrator.py`.
- **Backend** (`backend/`): FastAPI app (`backend/app.py`), Pydantic request/response models
  (`backend/models.py`), SQLite persistence (`backend/database.py`) for live product usage, plus
  read-only access to offline experiment result files.
- **Frontend** (`frontend/`): Next.js + React + TypeScript client.
- **Persistence**: SQLite for live reviews (product usage), append-only JSONL under `results/runs/`
  for experiment records (never overwritten — see `docs/evaluation_protocol.md`).
- **Vector search**: FAISS-free — retrieval is done with in-process sentence-transformer embeddings
  and cosine similarity (`pipeline/retriever.py`, `pipeline/embedder.py`), no external vector DB.

## 2. Request flow (`POST /review`, `backend/routes/review.py`)

```text
POST /review  { nda_text, hypothesis_ids? }
  |
load_hypotheses() -- all 17 fixed ContractNLI hypotheses, or the requested subset
  |
ModelGateway() -- fails fast (503) if no provider is configured
  |
review_document(doc_text, hypotheses, gateway)   [pipeline/orchestrator.py]
  |  one Retriever built once, reused across every hypothesis for this document
  |  each hypothesis processed independently (see "Per-hypothesis error isolation" below)
  |
  for each hypothesis --> review_requirement(...)   [see Section 3]
  |
database.save_review(...)  -- persisted to SQLite
  |
ReviewResponse  { review_id, results: [...], total_cost_usd, total_latency_ms }
```

## 3. Per-requirement flow (`review_requirement()`, the actual classification+routing logic)

This is the real, current implementation — including a detail that is easy to miss from a diagram
alone: **the system makes two classifier calls per requirement before deciding whether to invoke
the agent**, not one.

```text
Document + one hypothesis
        |
   Sentence chunking (pipeline/chunker.py)
        |
   Dense retrieval (embedder + cosine similarity, top-20)
        |
   Cross-encoder reranking (ms-marco-MiniLM-L-12-v2, keep top-7)
        |
        +-- rule_result = classify_by_keywords(hypothesis, doc_text)   [pipeline/rule_baseline.py]
        |
   +----+----------------------------------------------------------+
   |                                                                 |
   RULE-BOOSTED PATH                                       PLAIN PATH (no rule fusion)
   retriever.query_rerank_and_boost()                      retriever.query_and_rerank()
   (rule match RRF-fused into the ranking                  (same retrieve+rerank, but the rule's
    when it fires - docs/decisions.md ADR-002)               matched chunk is NOT boosted in)
        |                                                        |
   classify() --> rag_result                                classify() --> plain_result
   (THIS IS THE PRODUCTION ANSWER                            (used ONLY to compute the routing
    if the case is accepted)                                  signal below - docs/decisions.md
        |                                                      ADR-006)
        +--------------------+------------------------------------+
                              |
             route(self_confidence=rag_result.confidence,
                   rule_agrees=(rule_result == plain_result.label))
                   [pipeline/confidence.py]
                              |
              +---------------+----------------+
              |                                 |
           ACCEPT                            REVIEW
              |                                 |
     return rag_result as final       run_agent(retriever, hypothesis,
     (label, confidence, evidence,      initial_chunks=rag_result's chunks,
      explanation all from the          gateway) [pipeline/agent.py]
      rule-boosted classification)             |
                                       bounded ReAct loop over 5 tools
                                       (pipeline/agent_tools.py), step/
                                       time/duplicate-call limits
                                                |
                                       agent's final label/confidence/
                                       evidence/explanation returned
                                       instead of rag_result's
```

**Why two classifier calls exist**: an earlier version compared the rule's label against
`rag_result` directly (the rule-boosted classification). That comparison is circular — the rule's
own matched chunk had already been fused into `rag_result`'s context, so "agreement" partly
measured whether the LLM noticed the chunk the rule handed it, not independent corroboration
(`docs/decisions.md` ADR-006, code-audit finding C-1). The fix classifies a second, plain
(non-rule-boosted) context purely to compute the routing signal, while still returning the
rule-boosted `rag_result` as the actual answer whenever the case is accepted. Real, measured cost on
the full 2,091-case official test set: RAG (accepted cases, two classifier calls) $0.000152/case;
RAG+agent (REVIEW-routed cases also pay for the agent's own tool calls) $0.000405/case — about 2.7x
plain RAG, not merely a rough estimate. See `docs/decisions.md`'s routing-independence fix entry for
the full breakdown.

## 4. Rule-baseline logic (`pipeline/rule_baseline.py`)

Deterministic keyword/phrase matching per hypothesis, zero LLM cost. Used in three distinct roles
in the current system, not just as a standalone baseline architecture:

1. **Standalone comparison point** — the "Rule" row in every architecture comparison table.
2. **Retrieval booster** — its matched chunk (when it fires) is fused into the RAG retrieval
   ranking via Reciprocal Rank Fusion (`docs/decisions.md` ADR-002, round 7).
3. **Routing signal input** — its label is compared against the plain (non-boosted) classification
   to decide ACCEPT vs. REVIEW (`pipeline/confidence.py`).

## 5. Evidence handling

- Retrieved chunks are joined into a single context string passed to the classifier
  (`" ".join(r.chunk.text for r in retrieved)`); the classifier's returned `evidence` field is
  meant to be a verbatim quote from that context, checked (not silently trusted) by
  `pipeline/evidence_validator.py` for substring match — catches hallucinated/paraphrased
  citations.
- For the joint label+evidence correctness metric (used only in offline experiment scripts, not in
  the live backend), the retrieved chunks are mapped back to ContractNLI's own gold span indices
  via `evaluation/scorer.py`'s `map_chunks_to_gold_span_indices`. **This mapping was not being
  populated at all in `scripts/run_final_test_evaluation.py` until 2026-09-24** — see
  `docs/decisions.md` ADR-010 for the full bug writeup; it does not affect the live `/review`
  endpoint, only offline evaluation scripts.

## 6. Known implementation files

| Concern | File |
|---|---|
| Chunking | `pipeline/chunker.py` |
| Embedding | `pipeline/embedder.py` |
| Retrieval (dense, reranked, rule-boosted) | `pipeline/retriever.py`, `pipeline/reranker.py`, `pipeline/sparse_retriever.py` (BM25, not adopted) |
| Rule baseline | `pipeline/rule_baseline.py` |
| Classification | `pipeline/classifier.py` |
| Evidence validation | `pipeline/evidence_validator.py` |
| Confidence/routing | `pipeline/confidence.py` |
| Selective agent | `pipeline/agent.py`, `pipeline/agent_tools.py` |
| Per-requirement + per-document orchestration | `pipeline/orchestrator.py` |
| Model access (hosted + local) | `pipeline/model_gateway.py` |
| FastAPI app + routes | `backend/app.py`, `backend/routes/review.py`, `backend/routes/results.py`, `backend/routes/experiments.py` |
| SQLite persistence | `backend/database.py` |

## 7. Architecture concerns / open questions

Documented plainly, not fixed as part of this cleanup — see `docs/decisions.md` for full context
on each:

- **The second classification call for routing independence roughly doubles LLM cost** for every
  accepted case, and triples it for REVIEW-routed cases once the agent's calls are added. This was
  a deliberate trade for methodological correctness (ADR-006), not an oversight, but it is a real,
  ongoing cost the current design pays.
- **The routing signal has limited predictive power.** Best AUROC measured across every signal
  tried (self-confidence, retrieval score, retrieval margin, rule-agreement) is 0.657–0.660 — short
  of the 0.7 target that would have justified hard abstention (ADR-005). The entire ACCEPT/REVIEW
  split, and therefore the entire selective-agent architecture, rests on this imperfect signal.
- **The selective agent's benefit is statistically inconclusive, and the full-scale hosted test-set
  result actually points the opposite direction from the dev-sample rationale.** McNemar's test
  never reaches significance in any sample tested (dev: p=0.51; hosted 500-case: p=0.058; hosted
  full 2,091-case: p=0.088 — recomputed 2026-09-25 in `notebooks/07_selective_agent_
  experiments.ipynb`, where regression now numerically exceeds recovery). See ADR-007's 2026-09-25
  update for the full disclosure.
- **Full-context remains competitive, and on the hosted full test-set is the single
  highest-accuracy architecture measured (81.2%).** It was excluded from production on a
  scalability *hypothesis* (documents will get longer/noisier in real use), not because it
  underperformed on any data collected so far. See the long-document stress test proposal below.
- **Full-context's advantage is not universal**: on local Llama 3.2 3B, full-context (49.2%)
  actually underperforms the zero-cost rule baseline (57.6%) — a real, measured finding that a
  weaker model does not benefit from full-context the way the hosted model does.
- **Long-document scalability requires validation.** No experiment in this repository has tested
  any architecture on documents longer than ContractNLI's own NDAs (median ~2,300 tokens). The
  central design argument for RAG over full-context depends entirely on an assumption about
  longer-document behavior that has not been tested.

## 8. Proposed future experiment: long-document stress test

**Status: PROPOSED — NOT YET RUN.** No results exist for this; nothing below should be read as a
finding.

**Purpose:** determine whether RAG (with or without the agent) is actually justified over
full-context once documents get longer than this dataset's short, curated NDAs — the open
scalability hypothesis noted above.

**Method:** take existing test-split documents with known gold labels/evidence, and construct
controlled-length variants (1x original, 2x, 4x, 8x) by appending irrelevant but realistic
contractual boilerplate sections, while preserving the original evidence spans and labels exactly.
Run Full-context, RAG, and RAG+agent against each length tier.

**Metrics:** accuracy, macro-F1, Contradiction recall, joint label+evidence correctness, input
token count, cost, p50 latency, p95 latency — tracked per length tier to see where (if anywhere)
full-context's cost/accuracy trade-off actually crosses over against RAG's.
