# Experiment Registry — Reconstruction-v2

Rules for using this registry are in `docs/experiment_protocol.md`. Every experiment here
starts `PLANNED` and is not authorized to run by virtue of being listed — see
`docs/project_contract.md` for what's actually approved to proceed.

## Reconstruction-v2 sequence (provisional IDs)

| ID | Name | Status |
|---|---|---|
| E00 | Dataset and split validation | **COMPLETE** — local-only, no model calls; see `experiments/E00_dataset_validation/summary.md` |
| E00B | Budget, token and runtime forecast | **COMPLETE** — live pricing verified, historical ledger + token estimates + hosted forecast + runtime forecast + budget plan all produced, zero model calls; see `experiments/E00B_budget_forecast/summary.md` |
| E01 | Oracle reasoning ceiling | **COMPLETE** — all 4 frozen models (llama3.2:3b, qwen2.5:7b-instruct, gemini-2.5-flash-lite, gpt-5-mini) ran the full 300-case TRAIN_ORACLE_v1 manifest; Contradiction confirmed as the clearest reasoning bottleneck (25-82% recall across models, even with perfect evidence) — Entailment reasoning relatively strong, NotMentioned structurally advantaged and not a reasoning-ceiling measure; primary local model **frozen** (qwen2.5:7b-instruct); hosted reference **gpt-5-mini** (stronger reasoning ceiling), with gemini-2.5-flash-lite preserved as the economical hosted candidate; total hosted spend $0.1178; see `experiments/E01_oracle/summary.md` |
| E02 | Model screening | **SKIPPED / SATISFIED BY E01** — E01 already performed a controlled comparison of 2 local and 2 hosted models using the same Oracle manifest, prompt semantics, and output schema; a separate model-screening experiment would duplicate the question already answered. Frozen from E01: primary local model `qwen2.5:7b-instruct`, hosted model for later comparison `openai/gpt-5-mini`. Gemini 2.5 Flash Lite preserved only as an economical hosted candidate/result from E01 — not carried into core downstream experiments unless a later cost-quality experiment explicitly requires it. See `experiments/E01_oracle/summary.md`. |
| E03 | Prompt selection | **COMPLETE — `classification_prompt_v1` FROZEN = P0 (minimal instruction).** Resumed 2026-09-26 after E06 froze retrieval_v1; the original pre-E06 full-context attempt (P0: 88/150 cases) was SUPERSEDED before any metric was computed — preserved for traceability, not used. Resumed run: 450 real local calls (150 cases x P0/P1/P2, qwen2.5:7b-instruct, $0), identical frozen retrieval_v1 top-5 context for every prompt. A pre-existing wording bug ("full text of the NDA"/"NDA text:", stale from the pre-E06 design) was fixed identically across all three prompts before running. **Result**: P0 dominates P1 (+label definitions) and P2 (+decision procedure) on both top-priority metrics — Contradiction Recall 22.0% [95% CI 12.8–35.2%] vs 6.0% vs 2.0%, Macro-F1 0.507 vs 0.448 vs 0.403 — the opposite of the pre-registered hypothesis that explicit structure would reduce confusion. Confusion matrices show a monotonic mechanism: Contradiction→NotMentioned rose 37→44→46 (of 50) as instruction structure increased. Of 88 error cases, only 6 are retrieval-limited (gold evidence absent from the top-5 context); 82 are reasoning/prompt-limited, and 43/46 non-retrieval-limited Contradiction failures co-occur with an exception/carve-out keyword in the retrieved context (heuristic-flagged candidate, not a confirmed manual read per case) — echoing the T-series historical finding that exception/carve-out clauses are a real, recurring weakness (`docs/decisions.md`'s "Golden battery Categories 1-2" entry). **Selection**: no threshold needed — P0 wins priority #1 (Contradiction Recall) outright, and also wins priority #2 (Macro-F1) and priority #7 (simplicity, fewest tokens). `classification_prompt_v1` becomes the default for E05/E07/E08/E09-E11; prompt selection and architecture comparison remain separate questions (E12). See `experiments/E03_prompt_selection/summary.md` and `E03_prompt_selection.ipynb`. |
| E04 | Rule baseline (A0) | **COMPLETE — `A0_rule_baseline_v1` FROZEN = `pipeline/rule_baseline.py` unmodified**, the pre-existing implementation exactly as it was (no rebuild, no new rules, no threshold tuning, no R1/R2 rule variants added in reconstruction-v2). Input = **full NDA document text** — deliberately NOT routed through `retrieval_v1` (a separate, cheaper architecture by design). **No LLM/model calls anywhere in E04** ($0 cost). Full TRAIN evaluated (423 docs × 17 hypotheses, 7,191 cases, natural distribution 3,530/2,820/841 verified directly) — no DEV/TEST touched in E04 itself. **Result**: accuracy 56.8%, Macro-F1 0.471, Contradiction Recall 17.2% [95% CI 14.8–19.9%], NotMentioned Recall 92.2% (driven almost entirely by the default-fallback path, 92.2% of true NotMentioned cases never trigger any rule at all — not genuine detection). **Caveat: high NotMentioned recall is primarily driven by the default-to-NotMentioned fallback and should not be interpreted as strong semantic understanding.** Evidence Recall 29.0%, Evidence Precision 64.8%, joint label+evidence correctness 48.2% overall (21.8%/11.5%/92.2% by class). Overall rule-fire rate 27.2% (72.8% default to NotMentioned via no match). **Failure analysis (3,105 errors, all classified from observed data, no forced categories)**: 84.9% are plain lexical/paraphrase coverage gaps (hypothesis's keyword list never matched anything in the document — NOT primarily an exception/carve-out or negation problem, unlike E03's LLM-based finding on a different architecture); 7.1% false-positive fires on true-NotMentioned documents; 8.0% wrong-direction positive/negative phrase conflicts. Separately, 361/4,086 correct predictions (8.8%) have the right label but a misaligned evidence span. Evidence-span mechanism confirmed working correctly, no repair needed. Historical DEV/TEST exposure disclosed in full (B02 on full DEV, T041 on full TEST) — this is a reconstruction-v2 characterization of a pre-existing, unmodified baseline, never called "blind" or "unseen." Cost $0, mean latency 0.062ms/case, total wall time 0.67s for all 7,191 cases. E03 comparison shown for context only (different populations — 150 balanced vs. 7,191 natural-distribution cases — not a valid architecture verdict; that is E12's job). See `experiments/E04_rule_baseline/summary.md` and `E04_rule_baseline.ipynb`. |
| E05 | Full-context baseline (A1) | PLANNED |
| E06 | Retrieval optimisation | **COMPLETE — retrieval_v1 TRUE FINAL FROZEN AS BM25+RERANK (not dense).** All 4,371 evidence-bearing TRAIN cases used throughout. R0/R1 saturated at clause-512 (uninformative); R2 selected `clause_256`; R3 selected K=5 (MRR flat K=3→10); R4 selected `BAAI/bge-base-en-v1.5` over mpnet **pre-reranking**. **Matched BM25-vs-dense control at clause_256/K=5 (pre-rerank)**: BM25 (recall 90.5%/MRR 0.322) slightly beat plain dense (recall 88.4%/MRR 0.310) — disclosed, real finding. Failure analysis: 100% ranking failures, median miss rank 7 → **R5 (reranking, top-20→top-5) approved and run on the dense arm**: decisive win (recall 88.4%→92.2%, Contradiction 88.8%→93.9%, MRR 0.310→0.376; 231 recovered/72 regressed, net +159; Contradiction 53 recovered/9 regressed) for ~122ms/query. **Final required check (matched control #2): does dense candidate generation still earn its complexity once reranking exists?** Ran BM25+rerank vs dense+rerank on the identical 4,371-case universe, same candidate pool (20), same reranker, same K=5. Result: a **near-total tie** — recall 92.24% (BM25) vs 92.22% (dense), Contradiction recall identical at 93.94% for both, MRR 0.3765 vs 0.3764, 4,370/4,371 (99.98%) identical case outcomes, 100% identical on all 841 Contradiction cases (only 1 case differs anywhere, and BM25 wins it). Candidate-generation latency: BM25 ~0.16ms vs dense ~1.1ms; reranking latency identical (~175ms) for both since the same cross-encoder dominates. Per the predeclared tie-break rule ("if tied, prefer BM25 for simplicity"), **BM25 is selected — no embedding model or vector index needed**. Reconciles with R4: embedding choice matters *before* reranking (candidate generator is the whole system); it stops mattering *after* reranking (the cross-encoder does the discriminating work once pool coverage is adequate — both methods hit ~99.9% pool-recall@20). **Final frozen `retrieval_v1`**: BM25/clause_256/top-20→rerank(ms-marco-MiniLM-L-12-v2)→top-5 — recall 92.2%, Contradiction recall 93.9%, MRR 0.376, miss count 189, mean context ~1,023 tokens. E03 context artifact regenerated a second time from this true final config (`TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json`, 150/150 cases incl. NotMentioned, verified zero gold-info leakage, BM25-based). See `experiments/E06_retrieval_optimisation/summary.md`. |
| E07 | Standard RAG (A2) | PLANNED |
| E08 | RAG failure analysis | PLANNED |
| E09 | Agent justification | PLANNED |
| E10 | Agent/tool-policy selection | PLANNED |
| E11 | Selective agent evaluation (A3) | PLANNED |
| E12 | Four-architecture comparison (A0–A3) | PLANNED |
| E13 | Abstention / review-routing calibration | PLANNED |
| E14 | Full local blind evaluation | PLANNED |
| E15 | Hosted-vs-local comparison | PLANNED |
| E16 | Robustness evaluation | PLANNED |
| E17 | Security / red-team evaluation | PLANNED |
| E18 | Production / load / observability tests | PLANNED |

These IDs are provisional labels for future work, not permission to run anything. Each
becomes non-`PLANNED` only when it actually runs, per the protocol.

## Historical evidence / prior experiments (T-series — not reconstruction-v2)

The following already-completed work is preserved as historical exploratory evidence. It
informed the project contract but is **not** the reconstruction-v2 record, and reconstruction
experiments (above) must independently re-derive their own conclusions rather than assume
these:

| Historical area | Where recorded |
|---|---|
| Dataset/harness (T005–T008) | `docs/decisions.md`, `results/runs/run_B0*` |
| Oracle + model bake-off (T016–T017, ADR-001) | `docs/decisions.md` ADR-001 |
| Retrieval tuning, 10 rounds (T020–T023, ADR-002) | `docs/decisions.md` ADR-002 |
| Standard RAG E2E (T024, ADR-003) | `docs/decisions.md` ADR-003 |
| Prompt versions v1–v6 (T018, ADR-004) | `docs/decisions.md` ADR-004 |
| Confidence/abstention design (T026–T027, ADR-005) | `docs/decisions.md` ADR-005 |
| Routing-signal independence fix (ADR-006) | `docs/decisions.md` ADR-006 |
| Agent include/exclude (T028–T030, ADR-007) | `docs/decisions.md` ADR-007 |
| Full-context ceiling (T015, ADR-008) | `docs/decisions.md` ADR-008 |
| Architecture freeze — historical only (T031, ADR-009) | `docs/decisions.md` ADR-009 |
| Final locked test-set eval (T041, ADR-010) | `docs/decisions.md` ADR-010, `results/final/run_T041_*.jsonl` |
| Golden battery Categories 1–2 (ADR-011) | `docs/decisions.md` ADR-011 |
| Full chronological ledger | `docs/experiments.md` |
| Original day-by-day planning (not used for execution order) | `docs/archive/initial_project_plan.md` |

**ADR-009 in particular is historical evidence only** — per `docs/project_contract.md`, it is
not treated as the architecture freeze for reconstruction-v2. E12 independently re-evaluates
A0–A3.
