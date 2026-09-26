# E06 Retrieval Optimisation — TRUE FINAL RESULT (R0-R5 + matched lexical-vs-dense-rerank control)

**Status: COMPLETE.** All 4,371 evidence-bearing TRAIN cases used throughout every stage. Zero
LLM/API calls. **Three** controlled checks were required before freezing (matched BM25-vs-dense
at clause_256/K=5, the approved dense+reranker comparison, and a final matched
lexical-vs-dense-under-reranking control) — the third one **reversed the candidate-generator
choice**: `retrieval_v1` is frozen as **BM25 + reranker**, not dense + reranker, because the two
tied almost exactly and BM25 is simpler.

## Result summary

| Stage | Winner | Key numbers |
|---|---|---|
| R0 vs R1 (clause_512, saturated) | Inconclusive by design | BM25: recall 97.8%/MRR 0.197; dense(mpnet): recall 96.6%/MRR 0.182 — both saturated (~4-5 chunks/doc at K=5); **uninformative at clause-512** |
| R2 (chunking) | `clause_256` selected over 512-token/sentence chunking | clause_256: recall 87.0%/MRR 0.276/precision 5.0% vs. clause_512/fixed_512: recall ~97-98%/MRR ~0.18 (saturated) vs. sentence: recall 64.2%/MRR 0.441 (too aggressive a trade) |
| R3 (top-K) | K=5 selected | MRR essentially flat across K=3→5→10 (0.271→0.276→0.278) |
| R4 (embedding, pre-rerank) | `BAAI/bge-base-en-v1.5` selected over `all-mpnet-base-v2` | bge: recall 88.4%/MRR 0.310 vs. mpnet: recall 87.0%/MRR 0.276 — real MRR gain (+0.034) **before reranking** |
| Matched control #1 (clause_256, K=5, no rerank) | BM25 slightly beats plain dense | BM25: recall 90.5%/MRR 0.322/miss 253; dense(bge): recall 88.4%/MRR 0.310/miss 349 |
| Failure analysis (pre-rerank, dense) | 100% ranking failures, 0% retrieval absence | Median miss rank 7; 84.5% of the 349 misses at rank 6-10 |
| R5 (dense+reranker, top-20→top-5) | Decisive win over no-rerank dense | recall 88.4%→92.2%, Contradiction 88.8%→93.9%, MRR 0.310→0.376; 231 recovered vs 72 regressed (net +159) |
| **Matched control #2 (BM25+rerank vs. dense+rerank, both top-20→top-5)** | **Statistical TIE — 4,370/4,371 (99.98%) identical outcomes** | BM25+rerank: recall 92.24%/Contradiction 93.94%/MRR 0.3765/miss 189; dense+rerank: recall 92.22%/Contradiction 93.94%/MRR 0.3764/miss 190. Contradiction outcomes 100% identical (841/841). Only 1 case differs anywhere, and BM25 wins it. |

**Frozen `retrieval_v1` (TRUE FINAL, tie broken by simplicity per the predeclared rule)**:
`method=bm25 (no embedding model, no vector index), chunk_method=clause, chunk_size=256,
chunk_overlap=50, candidate_pool_size=20, top_k=5, reranking=True (ms-marco-MiniLM-L-12-v2)`.
**Final metrics: recall 92.2%, Contradiction Recall 93.9%, precision 5.4%, MRR 0.376, mean
context 1,023 tokens, mean total query latency ~176ms (candidate-gen + reranking).**

**What this means, stated plainly**: dense retrieval's embedding-choice complexity (R4) was
real and earned *before* reranking existed in the pipeline. Once reranking was added (R5), that
same complexity stopped earning anything — a free, deterministic BM25 candidate generator ties
a carefully-chosen dense embedding model almost exactly, because the cross-encoder reranker
does the real discriminating work regardless of where the initial top-20 candidates came from
(both BM25 and dense achieve ~99.9% pool-recall@20, so coverage was never the bottleneck for
either). Both findings are real and not contradictory — they describe different points in the
pipeline.

## R2 chunking semantics (exact, per the requested documentation)

- **clause_256 / clause_512** (`pipeline/chunker.py::clause_aware_chunk`): splits on
  paragraph/clause boundaries first (regex-based, tuned to NDA numbering like "1.", "(a)"),
  then merges consecutive small units up to the token budget (256 or 512 **tiktoken
  cl100k_base tokens**, not characters or words), and further splits any single paragraph that
  alone exceeds the budget at sentence boundaries. Never cuts a clause mid-sentence unless one
  sentence alone exceeds the budget. No overlap between chunks.
- **fixed_512** (`fixed_size_chunk`): a sliding 512-token window with 50-token overlap, no
  clause/sentence awareness at all — can and does cut mid-sentence.
- **sentence** (`sentence_chunk`): one chunk per sentence/clause fragment, no merging, no size
  parameter — maximal granularity.

## Post-rerank failure breakdown (dense+rerank arm; BM25+rerank is ~1 case different, see below)

Of the original 349 pre-rerank (dense) misses: **231 recovered**, and of the 190 still-missing-
after-rerank cases, 72 are **new regressions** (control hit, rerank missed) and 118 are
genuinely still unresolved — 117 where the gold chunk was visible in the top-20 pool but the
cross-encoder still didn't surface it in its top-5 (a real, disclosed cross-encoder limitation,
not eliminated by reranking), and exactly 1 case beyond the top-20 pool entirely (a true
coverage ceiling reranking cannot fix). Representative fix/harm/still-unsolved examples are in
`E06_retrieval_optimisation.ipynb` section 10c. **BM25+rerank's failure set (189 misses) is
functionally identical** — the final matched control found only 1 case differs between the two
arms anywhere in the 4,371-case universe (case `train::249::nda-18`, Entailment, which BM25+
rerank solved and dense+rerank missed) — so this failure characterization applies to the frozen
BM25+rerank config as-is, not just to the superseded dense+rerank one.

## E03 frozen-context artifact — REGENERATED TWICE, final version uses BM25+rerank

**The artifact was generated twice and regenerated a second time after the final matched
control reversed the candidate-generator choice.** The first version (dense+rerank) is fully
superseded. `experiments/E03_prompt_selection/TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json` now
reflects the TRUE FINAL frozen config (BM25 clause_256 → retrieve top-20 → cross-encoder rerank
→ top-5, no embedding model at all), run over all 150 `TRAIN_PROMPT_v1` cases, **including 50
NotMentioned cases** (retrieval never sees the gold label; NotMentioned received whatever
`retrieval_v1` naturally returned, no artificial empty context).

**Verified** (per the required checks): 150/150 cases present; `retrieval_config` in the file
matches the final frozen config exactly (`method: bm25, embedding_model: null, reranking: true,
reranker_model: cross-encoder/ms-marco-MiniLM-L-12-v2, candidate_pool_size: 20`); zero gold
fields (`gold_label`, `gold_span_indices`, etc.) present in any of the 150 model-facing case
records. Gold truth lives separately in `TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1_GOLD.json`
(scorer-side only).

**Context size for E03 (final)**: mean 1,018 tokens (median 1,026, p90 1,167, max 1,649) —
dramatically more compact than E03's earlier full-context condition (mean ~2,300 tokens),
directly serving the experiment question's "compact enough for downstream classification"
goal. Reranking (and BM25 vs. dense as the candidate source) changes which 5 chunks are
returned but not materially the context size (1,009 pre-rerank → 1,018-1,023 post-rerank mean
tokens, still K=5 throughout).

## Files created (final, including this and the prior correction pass)

- `experiments/E06_retrieval_optimisation/{README.md, config.yaml, summary.md,
  E06_retrieval_optimisation.ipynb}` (notebook re-executed with the matched-control, R5, and
  final lexical-vs-dense-rerank sections, zero errors).
- `experiments/E06_retrieval_optimisation/results/run_E06_{R0,R1,R2_clause256,R2_fixed512,
  R2_sentence,R3_k3,R3_k10,R4_bge,R0_matched_clause256}.json` + matching `*_cases.jsonl`
  per-case files.
- `experiments/E06_retrieval_optimisation/results/run_E06_R5_rerank_comparison.json` and
  `run_E06_R5_per_case_outcomes.jsonl` (4,371 control-vs-rerank outcomes, dense arm).
- `experiments/E06_retrieval_optimisation/results/run_E06_lexical_vs_dense_rerank.json` and
  `run_E06_lexical_vs_dense_rerank_cases.jsonl` (the final matched control, 4,371 cases,
  BM25+rerank vs. dense+rerank).
- `experiments/E06_retrieval_optimisation/results/retrieval_failure_analysis.csv` (349
  pre-rerank rows, dense arm) and `failure_analysis_summary.json`.
- `experiments/E03_prompt_selection/TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json` (**regenerated
  twice — final version uses BM25+rerank, no embedding model**) + `..._GOLD.json`.
- `scripts/run_e06_rerank_comparison.py` (the R5 dense+rerank comparison).
- `scripts/run_e06_lexical_vs_dense_rerank.py` (the final matched control, new this pass).
- `scripts/analyze_e06_failures.py`, `scripts/generate_e03_retrieved_context.py` (the latter
  updated this pass to use BM25 instead of dense as the final candidate generator).
- `evaluation/retrieval_eval.py`, `scripts/run_e06_retrieval.py` (from Stage A, executed for
  real in Stage B — no changes needed to either).

---

## Original Stage A Proposal (audit + design) — preserved below

**Zero retrieval benchmarks had been run as of this section.** Everything below is either a
direct code audit, a local dataset verification, a small runtime-calibration probe (timing
only, no recall/precision computed), or the proposal that was then approved (with the R2/R5
corrections reflected in the Stage B results above) and executed.

## 1–5. Existing retrieval architecture — full audit

| Component | Current implementation | Historical config(s) (hypothesis only) | Reusable in reconstruction-v2? |
|---|---|---|---|
| Chunking | `pipeline/chunker.py`: 3 methods — `fixed_size_chunk` (token-window+overlap, unit = **tiktoken cl100k_base tokens**, not chars/words), `clause_aware_chunk` (paragraph/clause-boundary split, merges up to a token budget), `sentence_chunk` (one chunk per sentence/clause fragment, no merging). All track exact `(start_char, end_char)` offsets. | Historical winner: sentence chunking (ADR-002, round 2-3) | Yes — reused as-is, all 3 methods already correct and tested |
| Embedding | `pipeline/embedder.py`: local `sentence-transformers`, default `all-mpnet-base-v2` (`pipeline/config.py`), L2-normalized, `lru_cache` on both model load and the 17 fixed query embeddings | Historical: mpnet default; round 4 found embedding barely matters **once reranking is applied** | Yes — reused as-is; the "barely matters" finding is historical evidence only, re-checked at R4 under E06's own (pre-reranking) conditions |
| Indexing | `pipeline/indexer.py`: FAISS `IndexFlatIP` (exact inner-product = cosine, since embeddings are normalized), **one index per document** | n/a (unchanged since introduction) | Yes |
| Similarity metric | Cosine (via normalized inner product) | Unchanged | Yes |
| Retriever orchestration | `pipeline/retriever.py`: `Retriever` class takes one `doc_text` at construction, chunks+embeds+indexes it once; `.query()` searches only that document's index. Also has `.query_and_rerank()` and `.query_rerank_and_boost()` (adds cross-encoder rerank + rule-based RRF fusion) — **not used in E06's R0-R3**, reranking is R5-gated. | Production path was `query_rerank_and_boost` (ADR-002 round 7) | Reranking/fusion methods reusable later (R5), not invoked in early stages |
| Reranking | `pipeline/reranker.py`: cross-encoder `ms-marco-MiniLM-L-12-v2`, already cached locally, `lru_cache`d model loader | Historical winner over L-6 and 2 other rerankers tried (ADR-002 round 4, round 10) | Reusable, gated behind R5's predeclared trigger — not run in R0-R4 |
| Lexical/BM25 | `pipeline/sparse_retriever.py`: `BM25Okapi` (via `rank_bm25`), **one index per document**, word-boundary tokenizer (a real punctuation-stripping bug was found and fixed here on 2026-09-24, per the module's own comment) | Used historically only as part of hybrid BM25+dense fusion (not adopted — "no measured benefit over dense+rerank once reranking is in the pipeline") | **Yes — this is R0's implementation.** Already correct, already bug-fixed, no need to invent a keyword rule |
| Hybrid fusion | `pipeline/sparse_retriever.py::reciprocal_rank_fusion` — standard RRF, rank-based not score-based (BM25 and cosine scores aren't comparable) | Historical: not adopted as production default | Available for R5 if hybrid is ever justified; not used in R0-R4 |
| Query construction | `Retriever.query(query_text, top_k)` — `query_text` is the caller's responsibility; `embedder.py`'s own docstring confirms in production it's always one of the 17 fixed ContractNLI hypothesis texts, cached | Unchanged | Query construction for E06 is frozen as hypothesis text only — see section 7 |
| Caching | `cache/{embeddings,indexes,parsed}/` directories exist (per `docs/experiment_protocol.md`'s repo layout) but are **currently empty** — no caching layer was ever actually wired up in production code | n/a | New for E06 — `evaluation/retrieval_eval.py`'s cache design (section 20) is the first real use of these directories |
| Rule baseline (A0) | `pipeline/rule_baseline.py::classify_with_span` — a deterministic keyword rule producing one best-match span per hypothesis, not a ranked top-K retriever | Historical: 72.6% precision / 20.4% recall standalone (high-precision, low-recall) | **Not used as R0** — it doesn't produce a ranked list comparable via Evidence Recall@K/MRR the way BM25 does; it's the separate A0 architecture, a different concern from R0's lexical-retrieval-rung question |

**Historical notebooks/scripts found**: `notebooks/04_retrieval_experiments.ipynb`,
`scripts/sweep_top_k.py`, `scripts/sweep_pool_size.py`, `scripts/compare_*retrieval*.py`,
`scripts/compare_stronger_rerankers.py`, `data/retrieval_experiment_results.json`,
`data/full_retrieval_comparison.json`, `data/top_k_sweep.json`, `data/pool_size_sweep.json`,
`data/rule_boosted_retrieval.json`, `data/parent_child_retrieval.json`,
`data/overlapping_chunks_comparison.json`, `data/stronger_reranker_comparison.json` — all
T-series (historical), summarized in `docs/decisions.md`'s retrieval ADR (10 rounds).

**Which historical findings are used only as hypotheses (never inherited as a decision)**:
sentence chunking as the historical winner; mpnet vs. BGE vs. MiniLM "barely differs once
reranking is applied"; retrieve-20/rerank-L-12/top-7/rule-RRF as the historical production
config; parent-child and overlapping-window chunking as rejected. **None of these are assumed
true for reconstruction-v2** — R0-R4 re-derive independently, per
`docs/evaluation_protocol.md` Part 1's standing rule.

## 6. NDA-local search — verified in code, not assumed

`pipeline/retriever.py::Retriever.__init__` takes a single `doc_text` and builds its own
private `FAISS`/`SparseIndex` from that document's chunks alone. There is no code path that
merges indices across documents or searches a shared corpus — cross-document search is
**structurally impossible**, not just conventionally avoided. Confirmed by reading the class,
not inferred from usage patterns.

## 8. Verified evidence-bearing TRAIN case count

**4,371** — verified directly by parsing `data/contractnli/train.json` and counting
Entailment (3,530) + Contradiction (841) annotations, independent of E00's report
(`evaluation/retrieval_eval.py::build_evidence_bearing_train_cases`, unit-tested in
`tests/test_retrieval_eval.py`). Matches E00 exactly — not merely assumed because E00 said so.

## 9–10. Full-universe practicality — real timing calibration, not a guess

Ran a **timing-only calibration probe** (no recall/precision computed, not a benchmark result)
directly against real TRAIN documents:

| Stage | Measured cost | Basis |
|---|---|---|
| Dense index build (clause-512, mpnet), warm model | **~0.21s/document** (mean of 10 real documents) | `Retriever(doc_text, chunk_method="clause", chunk_size=512)` |
| Dense model one-time load | ~4.1s | first `SentenceTransformer` instantiation only |
| BM25 index build (clause-512) | **~0.0044s/document** (mean of 20 real documents) | `SparseIndex(clause_aware_chunk(doc_text, 512))` |
| Query (dense, cached query embedding) | ~0ms | FAISS exact search on a tiny (single-digit to tens of chunks) per-doc index |

**Extrapolated to all 423 TRAIN documents**: dense index build ≈ 423 × 0.21s ≈ **89 seconds**
(+ ~4s one-time model load); BM25 build ≈ 423 × 0.0044s ≈ **1.9 seconds**. Querying all 4,371
cases is near-instant on top of an already-built index (cached query embeddings + exact search
on tiny indices).

**Conclusion: evaluating all 4,371 cases is clearly practical — using the full universe, no
reduction needed.** Estimated wall-clock for the full staged plan (R0 + R1 + R2's 3 configs +
R3's cached top-K sweep + R4's 1 extra embedding pass) is on the order of **10-15 minutes
total**, not hours — retrieval is, as expected, substantially cheaper than any LLM experiment
in this project.

## 7. Query construction — audited and frozen

`Retriever.query(query_text, top_k)` takes `query_text` as a plain argument — the caller
decides its content. Production code (`pipeline/orchestrator.py`, historical) always passes
the hypothesis text. **Frozen for E06**: query = `case["hypothesis_text"]` only (the
ContractNLI requirement string) — verified to never contain `gold_label`, gold evidence text,
or the annotation choice (`tests/test_retrieval_eval.py::test_query_text_is_hypothesis_only_no_gold_leakage`).
Gold information exists only in the case dict's `gold_label`/`gold_span_indices` fields, read
exclusively by the scorer (`evaluation/retrieval_eval.py::score_retrieval`), never passed into
any query or retriever call.

## 8 (evidence semantics — reused, not reinvented)

`evaluation/retrieval_eval.py::score_retrieval` calls `evaluation.scorer.map_chunks_to_gold_span_indices`
directly — the exact same binary any-character-overlap chunk-to-gold-span mapping already
audited and frozen in E00 (`docs/evaluation_protocol.md` Part 1 §16). No new evidence
definition was written. The classification joint-metric's τ threshold is explicitly **not**
used here — retrieval relevance for E06 is the raw gold-span-index overlap from
`evidence_recall_at_k`/`evidence_precision`/`mean_reciprocal_rank` (`evaluation/metrics.py`,
also reused unmodified), not a substitute.

## 11. Proposed R0 — cheap lexical baseline

**BM25** (`pipeline/sparse_retriever.py::SparseIndex`, already implemented, already
bug-fixed) — not a custom keyword rule (`pipeline/rule_baseline.py` is a different thing, the
A0 architecture, not a ranked retriever). Config: clause chunking, size 512 (the codebase's
existing default, not chosen because history favored it), K=5 (the codebase's existing
`settings.default_top_k` default) — same universe, same query, same NDA-local boundary, same
evidence-hit semantics as R1.

## 12. R1 — dense retrieval baseline, exact comparison to R0

Same clause-512 chunking, same K=5, same query, same scorer — only the retrieval **method**
changes (BM25 → dense bi-encoder, `all-mpnet-base-v2`, the codebase's existing default
embedding model, no download needed — already cached locally). This isolates "does dense
retrieval earn its complexity over free lexical matching" as the only variable in the R0→R1
step.

## 13. R2 — exact chunking candidates

**Corrected at approval to 4 candidates (added `fixed_512`)** — see the Stage B result summary
above for the actual comparison run. Original (superseded) reasoning kept below.

Freeze the R0-vs-R1 winning **method** (expected: dense, but not presumed — R1 must actually
beat R0 to be selected). Then vary **only** chunking, holding embedding model and K fixed:

1. `clause_aware_chunk(size=256)` — finer clause granularity
2. `clause_aware_chunk(size=512)` — current default (baseline continuity from R1)
3. `sentence_chunk()` — maximal granularity, no size parameter, one chunk per sentence

Three candidates, not more — spans the meaningful design space (coarse clause / finer clause /
maximal fragmentation) without a large grid. `fixed_size_chunk` is deliberately not included as
a fourth candidate: clause-aware chunking already fixes fixed-size's core defect (cutting a
clause mid-sentence) by construction, so a fixed-vs-clause comparison at equal size would test
a question the code's own design already answers architecturally, not empirically. Flagged as
an optional addition if a reviewer wants it, not run by default.

## 14. R3 — top-K candidates

Freeze the winning chunking from R2. Sweep **K = [3, 5, 10]** (the reconstruction brief's own
example ladder — a reasonable, low/mid/high spread, not arbitrary). Report Δ overall recall, Δ
Contradiction recall, Δ precision, Δ MRR, Δ retrieved tokens, Δ latency at each step; look for
diminishing returns rather than mechanically picking K=10.

## 15. R4 — embedding comparison: JUSTIFIED

**Correction applied at approval (see the Stage B result summary above for the actual
trigger used)**: the arbitrary "Contradiction Recall < 60%" trigger proposed in section (a)
below was **removed** on review — there was no pre-established evidence 60% was the right
threshold. It was replaced with four concrete, evidence-based conditions (ranking problem /
lexical mismatch / distractor-ranking / context-efficiency), and R5 was ultimately justified by
condition (a)-equivalent "ranking problem" evidence from the real failure analysis (median miss
rank 7), not by any recall threshold. The original (superseded) text is kept below for the
historical record, not as the rule actually applied.


**Why justified, not skipped**: the historical "embedding barely matters" finding (ADR-002
round 4) was measured **after reranking was already in the pipeline** — reconstruction-v2's R0-
R3 explicitly does not use a reranker yet, so whether embedding choice matters *before*
reranking is a genuinely open, not-yet-answered question for this project. **Candidate**:
`BAAI/bge-base-en-v1.5` — a different architecture/training lineage from mpnet, **already
cached locally** (no download needed, verified: `~/.cache/huggingface/hub/models--BAAI--bge-base-en-v1.5`
exists), a meaningfully different capability point rather than a near-identical variant.
Freeze chunking (from R2) and K (from R3); change only the embedding model.

**Predeclared condition that would justify R5 (advanced retrieval)** — decided now, before any
result exists, per the brief's explicit instruction not to decide this after seeing results:

> R5 (reranking / hybrid / query transforms) is triggered only if, after R0-R4, **any** of the
> following holds: (a) Contradiction Evidence Recall remains below 60% (a large, material gap
> from overall recall, not a rounding difference), (b) gold evidence's median rank sits just
> outside the frozen top-K (i.e. within K+1 to K+3), suggesting a ranking-quality problem a
> reranker could plausibly fix rather than a coverage problem it can't, or (c) a specific,
> recurring miss family (e.g. lexical mismatch/paraphrase) accounts for a clear majority of
> misses in the failure analysis. If none of these hold, R5 = NOT RUN / NOT JUSTIFIED, reported
> explicitly as a valid negative outcome, not silently skipped.

## 16. Cache strategy

`evaluation/retrieval_eval.py::retriever_cache_key(document_id, chunk_method, chunk_size,
chunk_overlap, embedding_model, retrieval_method)` → SHA1 hash → pickle file under
`cache/indexes/e06/`. **`top_k` is deliberately excluded from the key** — changing K only
changes how many already-ranked results are read off an index, never requires rebuilding it,
so R3's top-K sweep reuses R2's frozen chunking+embedding index without recomputation.
Invalidation is automatic and structural: any real config change (chunking, embedding,
method) produces a different key, so a stale cache can never silently be reused across a
genuine change — there is no separate manual invalidation step to forget. Verified via
`tests/test_retrieval_eval.py::test_cache_key_changes_with_chunking_or_embedding_not_top_k`.

## 17. Exact metrics

**Primary** (per configuration, overall + separately for Entailment/Contradiction): Evidence
Recall@K, Evidence Precision@K, MRR, miss count. **Context-size**: mean chunks returned, mean
retrieved characters, mean/median/p90/max retrieved tokens (cl100k_base approximation,
consistent with E00B's methodology). **Latency**: index/preprocessing time (chunk+embed+index
build) separately from query time (mean/median/p90), and cold-build vs. cached-reuse
distinguished via the cache hit/miss path.

## 18. Failure-analysis plan

For the best simple retriever (after R0-R4, before any R5 decision), inspect actual misses
(cases where no retrieved chunk overlaps any gold span) and near-misses (gold evidence present
but ranked outside a "should have found it" threshold). Categorize using open, data-driven
categories (not forced): gold evidence split across a chunk boundary, semantic
paraphrase/lexical mismatch, a distractor clause outranking the real one, the relevant
definition located in a different section, an exception/carve-out clause, a cross-reference,
an unusually long clause, multiple scattered evidence spans, other distractor wording. New
categories added if observed failures don't fit these. Output:
`experiments/E06_retrieval_optimisation/results/retrieval_failure_analysis.csv` (columns:
`case_id, label, requirement, gold_span_count, gold_evidence_excerpt, top_retrieved_chunk_ids,
top_retrieved_excerpt, gold_best_rank, failure_family, notes`) — **evaluator-facing, contains
gold evidence, and must never be passed to a classifier** (documented explicitly in the file
itself once created).

## 19. Planned E03 frozen-context artifact

Once `retrieval_v1` is frozen: run it over all 150 `TRAIN_PROMPT_v1` cases (**including
NotMentioned** — retrieval never sees the gold label, so NotMentioned cases get whatever
`retrieval_v1` naturally returns, removing E03's earlier Oracle-shortcut risk). Save
`TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json` with, per case: `case_id`, `document_id`,
`hypothesis_id`, `retrieval_config_version`, ranked chunk IDs, chunk text, source character
offsets, retrieval scores — **no gold label, no gold relevance flag, no gold span ID, no
expected answer** in this model-facing artifact. Gold/evaluation truth stays in a separate
scorer-side file, matching E01/E03's existing gold-label-isolation pattern. P0/P1/P2 are
**not** run in E06 — that resumes in E03 proper.

## 20. Files prepared

- `experiments/E06_retrieval_optimisation/{README.md, config.yaml, summary.md}`.
- `evaluation/retrieval_eval.py` — reusable universe-construction, caching, and scoring logic
  (reuses `evaluation.scorer`/`evaluation.metrics` directly). `demo()` self-check passes,
  confirms the real 4,371 count.
- `scripts/run_e06_retrieval.py` — the real Stage B runner (written, syntax-checked, **not
  executed** against the dataset). Reuses `pipeline/chunker.py`, `pipeline/embedder.py`,
  `pipeline/indexer.py`, `pipeline/sparse_retriever.py` directly — no duplicate retriever
  implementation.
- `tests/test_retrieval_eval.py` — 8 unit tests, all pass (evidence-bearing count, class
  composition, no-empty-spans invariant, query-text gold-isolation, cache-key behavior,
  scoring correctness on hand-built cases, empty-input handling).

**Not created yet (deferred to Stage B)**: `E06_retrieval_optimisation.ipynb`,
`results/run_E06_*.json` (real benchmark results), `results/retrieval_failure_analysis.csv`,
`TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json`.

## 21. Unresolved issues

1. **R2's chunking candidates deliberately exclude `fixed_size_chunk`** as a fourth option —
   flagged as an optional addition, not run by default, since clause-aware already
   architecturally dominates it.
2. **R4's second embedding candidate (`bge-base-en-v1.5`) is a specific proposal**, not the
   only reasonable choice — `all-MiniLM-L6-v2` (also already cached) would be a valid
   alternative if a smaller/faster comparison point is preferred instead of a same-size
   different-architecture one. Flagged for approval, not decided unilaterally.
3. **Reranking (R5) is explicitly not decided** — only the predeclared trigger condition is
   frozen; whether R5 actually runs depends on R0-R4's real results, which don't exist yet.
4. Runtime estimates are extrapolated from a 10-document (dense) / 20-document (BM25) timing
   sample, not the full 423-document run — expected to scale near-linearly given each
   document's retriever is fully independent (no shared state), but not measured at full
   scale yet.

---

**Waiting for explicit approval before Stage B.** No retrieval benchmark computed, no Qwen
call, no hosted call, no DEV/TEST access, no E03 resumption — everything above is either a
direct code audit, a verified local count, a small timing calibration, or a frozen proposal
awaiting approval.
