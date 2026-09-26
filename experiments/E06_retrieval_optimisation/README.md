```
Experiment ID: E06
Question: Which retrieval configuration most reliably retrieves ContractNLI gold evidence
    while keeping the returned context compact enough for downstream classification?
Hypothesis: a cheap lexical baseline (BM25) already captures a meaningful share of evidence;
    dense retrieval improves ranking quality (MRR) more than raw recall; chunking granularity
    and top-K matter more than embedding model choice, but embedding choice is checked
    directly (not assumed) since no reranker exists yet at this stage of the ladder.
Why this experiment exists: E03 (prompt selection) was paused because testing prompts against
    full-context text doesn't establish that the winning prompt transfers to the fragmented,
    noisier context retrieval will actually produce. E06 freezes that retrieved context first.
Input dataset/split: official TRAIN only, all 4,371 evidence-bearing (Entailment +
    Contradiction) cases -- NotMentioned excluded from scoring (no gold evidence to retrieve
    against), but NOT excluded from the eventual E03 context-generation pass (see summary.md
    section 26 disposition).
Frozen dependencies: none yet -- E06 IS the freezing experiment
Independent variable: retrieval configuration (method, chunking, top-K, embedding model),
    staged one factor at a time (R0-R4)
Controlled variables per stage: whatever was frozen by the previous stage; query
    construction (hypothesis text only), evidence-hit semantics (E00's frozen chunk-to-span
    mapping), NDA-local search boundary
Metrics: Evidence Recall@K, Evidence Precision@K, MRR, miss count -- overall AND separately
    for Entailment/Contradiction; context-size (chunks/chars/tokens); latency (build vs query)
Expected cost: $0 (no LLM/API calls -- BM25 and local sentence-transformers embeddings only)
Expected runtime: R0 ~2s, R1 ~90s, R2 (3 configs) ~5min, R3 (cached) ~2min, R4 (if run) ~2min
    -- see summary.md for the real timing calibration this is based on
Stop condition: Stage A ends at this proposal; Stage B ends when retrieval_v1 is frozen and
    TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json exists for all 150 E03 cases
Result: PENDING -- Stage B not yet approved
Decision: PENDING
What becomes frozen after this: retrieval_v1 (chunking, embedding, similarity, query format,
    K, reranking-or-not) -- becomes the frozen context source for E03 and later E07
```

## Stage A vs. Stage B

Same two-stage structure as E01/E03. **Stage A (this commit's state): audit + design.**
Existing retrieval implementation audited, evidence-bearing universe verified, staged
experiment plan (R0-R5) proposed and frozen. **Zero retrieval benchmarks run, zero model
calls.** **Stage B (after explicit approval): execution.**

Full Stage A proposal: `summary.md`. Reusable logic: `evaluation/retrieval_eval.py` (evidence-
bearing universe construction, retriever caching, scoring via E00's frozen evidence-hit
semantics, context-size stats) — reuses `evaluation/scorer.py` and `evaluation/metrics.py`
directly, does not reinvent them. Runner: `scripts/run_e06_retrieval.py` (written,
syntax-checked, **not executed** against the real dataset). Existing production code
(`pipeline/chunker.py`, `pipeline/embedder.py`, `pipeline/indexer.py`, `pipeline/retriever.py`,
`pipeline/sparse_retriever.py`) is reused as-is, not duplicated.
