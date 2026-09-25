# Retrieval configs

Versioned retrieval configuration (chunking strategy, embedding model, top_k, pool size,
reranker, rule-fusion on/off) as reviewed and frozen by E06 (retrieval optimisation). Empty
until E06 runs.

The historical retrieval config (sentence chunking → mpnet → retrieve-20 → rerank L-12 →
top-7 → RRF rule-fusion, `docs/decisions.md`'s retrieval ADR) is prior evidence that may
motivate E06's starting hypothesis, per `docs/experiment_protocol.md` rule 20 — it is not
carried over as the reconstruction-v2 config without being re-run.
