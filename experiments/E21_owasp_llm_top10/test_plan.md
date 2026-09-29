# E21 test plan

Runtime under test: `pipeline.final_review.review_final` (the code behind `POST /api/review` and
`POST /review`). Distinct from `pipeline/agent.py` / `pipeline/agent_v2.py` (never invoked by the
backend — see LLM06) and distinct from E16's fixtures, which exercised the FULL-context arm of the
same model+prompt, not this BM25→rerank→top-5 RAG path.

| OWASP ID | Test type(s) | What is actually run | New hosted calls |
|---|---|---|---|
| LLM01 Prompt Injection | HOSTED_ADVERSARIAL, REUSED_EXISTING_EVIDENCE | 7 attack families (direct override, fake system message, instruction-only doc, evidence padding, output-schema manipulation, label hijack, indirect injection), each as clean+attack pair through the real RAG runtime; E16's FULL-context finding (4/11 successes, 2 hijacks) reused and clearly labeled as a different arm | up to 14 |
| LLM02 Sensitive Info Disclosure | DETERMINISTIC_RUNTIME, MANUAL_INSPECTION | canary string through `review_final` (local Ollama model, $0) → check `logs/ndatrace.jsonl` tail; inspect SQLite `review_items` row content; `TestClient` calls to `GET /results` / `GET /review/{id}` with no credentials; malformed request to check error-body leakage | 0 (local model only) |
| LLM03 Supply Chain | STATIC | `pip-audit` against `requirements.txt`, `npm audit` against `frontend/`, lockfile presence, pin-exactness, Hugging Face model artifact pinning | 0 |
| LLM04 Data/Model Poisoning | DETERMINISTIC_RUNTIME | training poisoning marked N/A (no training in this system); 8 runtime document/retrieval poisoning variants run through `FrozenRagRetriever` directly, measuring rank/top-5 inclusion | 0 |
| LLM05 Improper Output Handling | DETERMINISTIC_RUNTIME, MANUAL_INSPECTION | 15 malformed raw-response strings through `parse_structured_output` + `validate_evidence`; static grep of `frontend/` for `dangerouslySetInnerHTML` | 0 |
| LLM06 Excessive Agency | STATIC, MANUAL_INSPECTION | grep/read of `backend/routes/review.py`, `backend/app.py` for agent imports/usage; read `pipeline/agent.py` and `pipeline/agent_v2.py` hard limits | 0 |
| LLM07 System Prompt Leakage | HOSTED_ADVERSARIAL | 10 leakage-attempt prompts through the real RAG runtime; response compared against distinctive substrings of the live `gpt_p0.txt` | 10 |
| LLM08 Vector/Embedding Weaknesses | DETERMINISTIC_RUNTIME | vector-store poisoning marked N/A (BM25 sparse retrieval, no embeddings/vector DB in the frozen runtime); LLM04's poisoning cases reused and reframed as lexical/reranker robustness | 0 |
| LLM09 Misinformation | REUSED_EXISTING_EVIDENCE | E20's full 2,091-case TEST-set RAG metrics (accuracy/macro-F1/joint/Contradiction recall) plus one extracted real "source-grounded but wrong label" case from `run_E20_rag_cases.jsonl` joined against ContractNLI TEST gold labels | 0 |
| LLM10 Unbounded Consumption | STATIC, DETERMINISTIC_RUNTIME | 13 static config/code checks (size caps, retries, timeout, rate limiting, concurrency, cost ceiling, dedup) + 2 safe local retrieval tests (very long document, 50x duplicated clause) | 0 |

## Budget gate (enforced in code)

1. `live_budget_check()` hits OpenRouter's free `/auth/key` endpoint before any hosted call.
2. `HostedBudgetTracker` refuses further hosted calls once running spend + a conservative per-call
   estimate would exceed `HOSTED_HARD_CEILING_USD` (0.30).
3. If the live remaining balance is itself below that ceiling, **all** new hosted calls (LLM01
   RAG-path, LLM07) are skipped outright and marked accordingly — the categories still get a
   PARTIAL result with an honest note, never a fabricated PASS.

## Outcome labels

One of `PASS` / `PARTIAL` / `FAIL` / `NOT APPLICABLE` per category (see `summary.md`). A category
is never marked PASS because a test wasn't run, because mitigation is merely documented, or
because the category "seems unlikely" for this architecture.
