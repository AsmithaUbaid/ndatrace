# Retrieval configs

**E06 (retrieval optimisation) is COMPLETE.** Final frozen `retrieval_v1`:
**BM25 → clause_256 chunking → retrieve top-20 → cross-encoder rerank (ms-marco-MiniLM-L-12-v2) →
keep top-5** (recall 92.2%, Contradiction recall 93.9%, MRR 0.376 on the full 4,371-case
evidence-bearing TRAIN set). A matched BM25-vs-dense control found a near-total tie once reranking
is applied, so BM25 was selected over a dense embedding model for simplicity (no embedding model
or vector index needed) — see `docs/experiment_registry.md`'s E06 row for the full round-by-round
record.

This directory never received the actual versioned config file `retrieval_v1` was meant to leave
here — the frozen configuration exists in prose (`experiments/E06_retrieval_optimisation/summary.md`)
and in the retrieval-building code paths of E07/E08/E12A/E12B/E12C, not as a standalone file in
this directory. Note as a known gap, not a "not yet run" placeholder.

The pre-reconstruction retrieval config (sentence chunking → mpnet → retrieve-20 → rerank L-12 →
top-7 → RRF rule-fusion, `docs/architecture_decisions/INDEX.md`'s ADR-002) is unrelated prior evidence from the
earlier pipeline — not reconstruction-v2's config, and not superseded by it (they're independent
lineages).
