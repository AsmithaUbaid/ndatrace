# Course coverage matrix

| Class | Concept | NDATrace evidence | Conclusion | Figure/table |
|---|---|---|---|---|
| 1 | Rules vs AI | E04 rule baseline (full TEST): 59.0% acc, 16.8% Contradiction recall | Deterministic rules are a cheap floor, not a solution — 90.5% NM recall by defaulting, ~0 semantic understanding | Fig 1, 6 |
| 1 | Foundation model vs deterministic baseline | E01 Oracle (gold evidence): GPT 0.906 macro-F1 vs rule ~0.48 | Foundation model reasoning materially exceeds keyword rules even before retrieval is involved | Fig 2 |
| 1 | Unpredictable/confident failure | E17 failure analysis: 10/35 failures are confident, evidence-grounded, wrong reasoning; E16: model complies with in-document instructions | The system fails silently and confidently, not just "randomly" | Fig 12, 13 |
| 2 | Modern AI stack | Seven-layer table below | Every layer was a real build/rent/use decision, revisited multiple times (embedding model, reranker, model vendor) | §Seven-layer stack |
| 2 | Retrieval/RAG | E06/E13: 9 retrieval rounds, RAG vs FULL comparison | RAG cut tokens 15–70% by document length but did not beat FULL on this DEV comparison (frozen E13 rule: outcome B) | Fig 5 |
| 2 | Build/rent/own | Local Qwen (own compute) vs hosted GPT (rent) vs OpenRouter/Groq (rent, free tier) | Explicit historical decision log (ADR-style) for each swap | §Seven-layer stack, §29 |
| 2 | Observability/evals | evaluation/harness.py, structured JSONL logs, evidence_evaluator_v2/v1 | Built early, reused every experiment; separate from runtime validation (E14) | §Observability plan |
| 3 | Prompting | E03/E12B/E12C: P0 vs P1/P2/P3 | P0 (simplest) won on Qwen; P3 won in development then reversed on confirmation for GPT — P0 retained | §30 |
| 3 | Token economics | E13 input token distributions (mean 2,455 FULL / 1,139 RAG) | Input tokens dominate cost, not output/explanation length | Fig 5, 6 |
| 3 | Output-length/input-length cost | E17 GPT ops: input mean 2,383 tok ($0.25/M) vs output mean 790 tok ($2/M) — output still ~2/3 of per-case cost despite 3x fewer tokens | Output pricing multiplier matters even at moderate output length | §Cost-to-serve |
| 3 | Complexity does not guarantee quality | E12B/E12C P3 regression; E13 FULL beating RAG; E15 R2 near-random | Added complexity (prompt elaboration, retrieval, naive routing) repeatedly failed to earn its cost | Fig 1, 5, 10 |
| 4 | Agent loop | pipeline/agent.py, agent_v2.py; E09-E11 | Bounded ReAct loop built, evaluated, and REJECTED for production (E11: net effect not worth the risk at scale) | §26 |
| 4 | Step caps | E10 config: max_agent_steps=3, max_tool_calls=2 | Hard limits enforced in code, never model-controlled | Fig 3 |
| 4 | Tool calls | pipeline/agent_tools.py (5 tools); E11 traces | All 15 real E11 traces concluded at step 1 — the agent never actually needed a tool call in this measured sample | Fig 3 |
| 4 | Trajectory reliability | E11 A2-vs-A3 recovery/regression; McNemar p=0.51→0.058 across sample sizes | Recovery beat regression ~2:1 but was not statistically significant even at n=500 | §25 |
| 4 | Quadratic token growth | Input(T) ≈ B·T + D·T(T-1)/2, B=2,004 tok (measured prompt+context), D≈1,000 tok/turn (config-derived, not measured) | Formula demonstrated; NDATrace's own agent never exercised turns 2-3 | Fig 3 |
| 5 | Cost per task | E17: GPT $0.00218/case; Qwen/rule $0 API | Sub-cent inference cost; human fallback dominates total cost-to-serve | Fig 6, 7 |
| 5 | Expected human fallback | Cost-to-serve model, §Human-review scenarios | (1−p_safe)·C_H term; illustrative scenario only | Fig 7 |
| 5 | Hosted vs local | E17 full-TEST: GPT $0.00218/case, ~7s; Qwen $0 API, 7.13h/2091 cases | Local is not "free" — compute/time cost is real, just not monetized here | §29 |
| 5 | Break-even success | p_BE formula | Qwen's real p (39.7%) falls far short of matching GPT's all-in cost under any tested scenario | Fig 8 |
| 5 | Sensitivity analysis | Cost-to-serve grid (3 systems × 12 C_H scenarios × 3 volumes × 2 fixed-cost scenarios) | Human-review assumption dominates the ranking more than the AI cost does | Fig 7 |
| 6 | Abstention/review | E15 Stage A + fresh DEV_ROUTING_v1 validation | No candidate policy met both provisional targets (review≤40%, residual<10%) | Fig 9, 10, 11 |
| 6 | Silent failure | Routing safety analysis | R0 (no review): 29.0% silent failure; even R3's 51.3% review load leaves 5.1% unsafe-automated | Fig 9 |
| 6 | Escalation/guardrails | R1 structural-integrity floor; runtime validator v2 | Guardrails catch source-grounding violations, not confident wrong reasoning | Fig 9-11 |
| 6 | Prompt injection | E16: 20 pairs, 4/11 injection successes, 2 regressions | Evidence-grounding is not injection-hardening; disclosed, not patched, before TEST | Fig 12 |
| 6 | Auditability | Append-only ledger, structured logs, frozen manifests/hashes, Decisions Log | Every final-architecture decision and dollar is traceable to a committed artifact | §Governance timeline |
| 6 | Eval→production feedback loop | §Feedback loop diagram | Offline eval knows ground truth pre-deployment; production only gets delayed human-resolved labels | §28 diagram |
