```
Experiment ID: E07
Question: Does retrieval_v1 improve qwen2.5:7b-instruct classification and evidence-grounding
    relative to full-context input when evaluated on the same frozen cases?
Hypothesis: retrieval_v1's compact, pre-filtered top-5 context (mean ~1,017 tokens vs. E05's
    ~2,253) should at minimum improve efficiency; whether it also improves or degrades
    classification/evidence quality is not assumed either way (retrieval coverage on this exact
    manifest, measured this pass, is high -- 90.9% Evidence Recall@5 overall -- but E05's own
    result showed full-document access alone doesn't fix Qwen's reasoning bottleneck, so a
    smaller, cleaner context could help, have no effect, or introduce its own distractor risk).
Why this experiment exists: matched architecture comparison to E05 -- same manifest
    (TRAIN_ARCH_v1), same model, same prompt, same schema, same parser -- isolating input-
    construction architecture (full document vs. retrieval_v1) as the only variable.
Input dataset/split: Official TRAIN only. TRAIN_ARCH_v1 -- the IDENTICAL 150-case manifest E05
    used (50/50/50, seed=700, 78 unique documents, zero overlap with TRAIN_PROMPT_v1). Case
    membership and ordering unchanged.
Frozen dependencies: qwen2.5:7b-instruct-ctx16k (same tag as E05 -- see summary.md section 4
    for why), classification_prompt_v1 (=P0, system prompt byte-for-byte unchanged),
    retrieval_v1 (BM25/clause_256/top-20/rerank(ms-marco-MiniLM-L-12-v2)/top-5, completely
    unmodified), evaluation.structured_output.parse_structured_output (unchanged from E05),
    pipeline.evidence_validator.validate_evidence (unchanged), temperature 0.0, 60s timeout.
Independent variable: input-construction architecture only -- E05 fed full NDA text, E07 feeds
    retrieval_v1's top-5 reranked context. Nothing else differs.
Controlled variables: manifest, case ordering, model, prompt, output schema, parser, evidence
    validator, retry policy, evidence-instruction wording, metrics, failure-analysis framework.
Metrics: Accuracy, Macro-F1, per-class recall (Contradiction Recall + CI), confusion matrix,
    strict/recovered/usable parse validity (never collapsed), Evidence Recall/Precision, joint
    label+evidence correctness (overall + by class), retrieval-limited vs. reasoning-limited vs.
    evidence-selection vs. structured-output failure counts, input-token distribution + %
    reduction vs. E05, retrieval latency (candidate generation + reranking, separate from
    generation), generation latency, paired E05-vs-E07 case-level transitions, McNemar exact
    test + paired bootstrap CI on the metric differences.
Expected cost: $0 (local-only, no hosted calls; retrieval is deterministic/local, generation is
    local Ollama).
Expected runtime: ~19 minutes for the full 150-case generation step (estimated by applying
    E05's own fitted latency-vs-input-tokens relationship to E07's real, measured, much shorter
    context-length distribution -- not a fresh guess), plus a few seconds of local retrieval
    (already measured: near-instant per case with cached indexes). See summary.md section 12
    for why no separate calibration run is proposed this time.
Stop condition: Stage A ends at this proposal -- no Qwen call has been made in E07. Stage B
    begins only after explicit approval.
Result: PENDING -- Stage A only.
Decision: PENDING.
What becomes frozen after this: PENDING -- A2_standard_rag_v1 (if approved) plus the matched
    E05-vs-E07 comparison, feeding E12's architecture comparison.
```

## Stage A vs. Stage B

Same two-stage structure as E00/E01/E03/E04/E05/E06. **Stage A (this commit's state): audit
existing RAG code, define A2's exact architecture, decide the model tag, generate and
characterize the retrieval-context artifact on TRAIN_ARCH_v1 (local-only, zero LLM calls, same
precedent as E01/E03/E05/E06's own Stage A manifest-building steps), measure real retrieval
coverage and token-reduction numbers, and propose the paired-comparison/statistical-test
design.** No benchmark has been run, no Qwen call made. **Stage B (after explicit approval):
execution.**

Full Stage A audit and proposal: `summary.md`. New artifacts created this pass (all local-only,
deterministic, zero model calls): `TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json` /
`_GOLD.json` (`scripts/generate_e07_retrieved_context.py`, retrieval_v1 run unmodified over
TRAIN_ARCH_v1's 150 cases).
