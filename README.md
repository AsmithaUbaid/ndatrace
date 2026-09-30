# NDATrace

NDATrace helps legal reviewers compare confidentiality requirements with an NDA and inspect the source evidence behind each verdict.

`Python` · `FastAPI` · `Next.js` · `GPT-5-mini` · `ContractNLI` · `Human-in-the-loop`

**Current report draft:** [reports/NDATrace_Final_Report.md](reports/NDATrace_Final_Report.md) ([PDF](reports/NDATrace_Final_Report.pdf), [HTML](reports/NDATrace_Final_Report.html)). A newer uncommitted HTML version found during branch consolidation is preserved separately as [reports/NDATrace_Business_Technical_Tradeoff_Draft.html](reports/NDATrace_Business_Technical_Tradeoff_Draft.html). The report remains a draft; repository stabilization did not rewrite it.

## 1. What it does

```text
NDA + requirement → verdict → supporting clause → human review
```

Each requirement receives one of three labels:

- **Entailment** — the agreement supports the requirement.
- **Contradiction** — the agreement conflicts with the requirement.
- **Not Mentioned** — the agreement does not establish either conclusion.

The reviewer sees the verdict, a concise explanation, and verbatim evidence when evidence is required. NDATrace is a reviewer aid, not an autonomous legal decision-maker.

**Human authority is recorded, not just implied.** Every result carries a needs-human-review flag, and the reviewer records **Approve**, **Override**, or **Reject** with an optional note against it (`POST /review/{id}/items/{id}/decision`, persisted append-only in `review_decisions`). This closes the gap between the project's standing human-review promise (`docs/project_contract.md` §10) and what the backend actually records — before this, a human could disagree with a result, but nothing captured that they had.

## 2. Business problem and persona

Legal operations teams spend hours per NDA checking it against standard confidentiality requirements, because supporting or conflicting evidence is often paraphrased or scattered across clauses and exceptions. Vendor survey data (LegalOn Technologies, 2025, n=286 — cited as vendor research, not independently verified) reports 52% of organizations handle 101–1,000 contracts a year at 2–4 hours of review each; for a team handling 500 contracts, a 30% reduction in review effort is roughly 450 staff-hours a year. That figure motivates the problem; it is not evidence this project measured.

**Persona:** Tina, a legal operations analyst who is not a lawyer. She needs to know, for each requirement, whether the NDA satisfies it, contradicts it, or is silent — and to see the exact clause before she acts on that answer. NDATrace does not approve or reject NDAs; it retrieves evidence, classifies each requirement, and hands the decision to Tina, who records Approve / Override / Reject against the result (§1).

A keyword search misses paraphrase; a general-purpose LLM given the whole document can reason but gives Tina no way to verify where its answer came from. NDATrace is narrower than either.

## 3. Final decision at a glance

| Component | Final role |
| --- | --- |
| Rule | Baseline |
| FULL | Quality reference |
| RAG | Prototype runtime |
| Agent | Tested and rejected |
| Human | Final authority |

The shipped review path is the frozen RAG pipeline. FULL is retained as the strongest measured quality reference, not as the prototype runtime.

## 4. Final test result

Official ContractNLI **TEST** split, **n = 2,091**. The Rule values below are TEST results, not TRAIN results.

| Metric | Rule | Qwen | FULL | RAG |
| --- | ---: | ---: | ---: | ---: |
| Accuracy | 59.0% | 49.9% | **77.6%** | 76.8% |
| Joint success | 50.1% | 39.7% | **74.6%** | 72.5% |
| Contradiction recall | 16.8% | 25.5% | 75.5% | **77.3%** |

On paired cases, the FULL–RAG classification difference was not significant (`p = 0.217`), while the Joint difference was (`p = 0.0047`). FULL therefore remains the quality reference; RAG accepts a measured evidence-grounding trade-off for a more bounded runtime.

For scale, a deterministic [majority-class TEST sanity check](experiments/E04B_majority_baseline/README.md) reaches 46.3% accuracy and 0% Joint. It is a trivial baseline, not an architecture rung.

## 5. Why RAG is the prototype

FULL achieved the higher Joint score. RAG was selected for the prototype because it uses bounded context, returns a clause-level evidence path, reduced mean input tokens by **50.4%**, and reduced raw API inference cost by **16.8%** in the matched E20 TEST run.

This is an engineering trade-off, not a claim that RAG outperformed FULL on overall quality.

## 6. Final architecture

```mermaid
flowchart LR
    A[NDA + requirement] --> B[Clause-aware chunks<br/>256 tokens, no overlap]
    B --> C[BM25<br/>top-20]
    C --> D[Cross-encoder<br/>reranking]
    D --> E[Top-5 clauses]
    E --> F[GPT-5-mini<br/>P0 prompt]
    F --> G[Structured parser]
    G --> H[Evidence validator]
    H --> I[Human reviewer]

    classDef input fill:#f8fafc,stroke:#64748b,color:#1f2937;
    classDef retrieval fill:#eff6ff,stroke:#60a5fa,color:#1e3a5f;
    classDef model fill:#fff7ed,stroke:#fb923c,color:#7c2d12;
    classDef control fill:#f0fdf4,stroke:#4ade80,color:#14532d;
    class A input;
    class B,C,D,E retrieval;
    class F model;
    class G,H,I control;
```

| Setting | Frozen value |
| --- | --- |
| Chunking | Clause-aware, 256 tokens, no token overlap (boundaries follow clause breaks) |
| Candidate generation | BM25 top-20 |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-12-v2` |
| Model context | Top-5 reranked clauses |
| Model | `openai/gpt-5-mini`, temperature 0 |
| Prompt | P0, single shot |
| Output controls | Structured parser + verbatim evidence validation |
| Decision authority | Human reviewer |

See [the architecture guide](docs/architecture.md) and [architecture decisions](docs/architecture_decisions/INDEX.md).

## 7. Experiments: what we tested and why

Twenty-four numbered experiments (E00–E23) form the evidence trail; these are the ones that materially shaped the final architecture:

| Experiment | Question | Measured finding | Decision |
| --- | --- | --- | --- |
| Rule baseline (E04) | Does keyword matching suffice? | 59.0% accuracy / 50.1% Joint, full TEST n=2,091 | Insufficient; justified an LLM |
| Oracle (E01) | Model or retrieval bottleneck? | 90.6% macro-F1 given gold evidence (n=300) | Model not the bottleneck; invest in retrieval + prompting |
| Prompt selection (E03) | Which prompt classifies best? | Minimal (P0) beat elaborated prompts on Contradiction recall and macro-F1 | Froze P0 |
| Retrieval optimization (E06) | Does dense/hybrid beat BM25? | All converge to ~92% Recall@5 once reranked | Froze BM25 + reranker (simplest, tied) |
| Matched FULL vs RAG (E17/E20) | Does RAG match FULL's quality? | FULL wins Joint (p=0.0047); accuracy not significantly different | Kept RAG for cost/context-scaling; gap disclosed |
| Selective agent (E11) | Do extra tools recover mistakes? | Zero tool calls used; net Joint benefit 0.0pp | Rejected; not in runtime |
| Auto review-routing (E15) | Can the system self-flag uncertainty? | No policy reached ≤40% review workload and <10% residual error together | Rejected; every case routes to a human |
| Injection guard live check (E23) | Does the guard hold on a real adversarial call? | Model did not comply; guard fired correctly (1 real hosted call) | Confirms E16/E22, not a new coverage claim |

The causal experiment story is available in the app at `/project`. Exact protocols, artifacts, and decisions for all 24 experiments are indexed in the [experiment registry](docs/experiment_registry.md).

## 8. Security posture

E21 was a baseline assessment, not the current post-remediation state:

| E21 baseline | Count |
| --- | ---: |
| PASS | 3 |
| PARTIAL | 5 |
| FAIL | 2 |

E22 then targeted the two E21 failures:

| Area | E21 | E22 targeted result |
| --- | --- | --- |
| Prompt Injection | FAIL | **PARTIAL** |
| Unbounded Consumption | FAIL | **PASS** |

Current controls include an injection guard, request-length limits, enforced cost/budget checks, an in-process rate limit, a concurrency cap, structured parsing, verbatim evidence validation, explicit security/human-review flags, and human final authority.

Residual risks remain: injection detection is incomplete; authentication and data-governance controls are not production-complete; per-process limits are not distributed controls; and semantic errors cannot all be detected automatically. This prototype does not claim OWASP compliance.

See [E21](experiments/E21_owasp_llm_top10/summary.md) and [E22](experiments/E22_targeted_security_remediation/summary.md). [E23](experiments/E23_injection_guard_live_check/summary.md) is a single-case live-fire confirmation of the guard, run through the real production path with a real hosted call.

## 9. Important agent correction

The agent experiment exposed only two targeted, read-only tools:

- `FOLLOW_CROSS_REFERENCE` — retrieve a bounded excerpt from a named provision in the same NDA.
- `GET_MORE_CANDIDATES` — reveal a bounded slice below the frozen top-5 from the existing ranked candidate pool.

It had no web search, filesystem access, external database access, write actions, or autonomous legal authority. In the tested architecture, these tools did not create enough recovery value to justify the added cost, latency, and control complexity.

**The agent is experimental and is not in the live runtime.** Saved E10/E11 artifacts remain for reproducibility.

## 10. Cost-to-serve and trade-offs

The modeled workflow uses:

```text
C_total = C_AI + (1 - p_joint) × C_human
```

API cost is not total workflow cost: failed Joint cases still require human handling. All business figures are **MODELED scenarios**, not realized production savings. Assumptions and sensitivity analysis are documented in [E18](experiments/E18_business_course_synthesis/summary.md).

## 11. Limitations

- ContractNLI is a proxy dataset; performance on real enterprise NDA distributions is not established.
- Long-document and organizational distribution shift remain open risks.
- Automatic uncertainty routing was tested but not adopted.
- Prompt-injection detection remains incomplete.
- The system cannot grant autonomous legal approval.
- A human remains the final authority.


## 12. Prerequisites and installation

- Python 3.12 (verified with 3.12.14).
- Node.js 20.9 or newer (the Next.js requirement; verified here with Node 26.9.0) and npm.
- Internet access for the public ContractNLI dataset and first-time Hugging Face model downloads.
- An OpenRouter API key only for intentional, billed review calls. Startup, tests, and saved-result reproduction do not require one.

From a fresh clone of `main`:

```bash
git clone https://github.com/AsmithaUbaid/ndatrace.git
cd ndatrace

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
bash scripts/download_data.sh
cp .env.example .env
python scripts/verify_environment.py

cd frontend
npm ci
cd ..
```

The live RAG path uses the public `cross-encoder/ms-marco-MiniLM-L-12-v2` reranker. Dense-retrieval research tests also use `sentence-transformers/all-mpnet-base-v2`. They download into the standard Hugging Face cache on first use; prefetch both deliberately with `python scripts/download_models.py`. Model weights and caches are not tracked.

`.env.example` contains safe placeholders. Set `OPENROUTER_API_KEY` only when a billed call is intended, and choose `MAX_BUDGET_USD` for your own local run. Use `python scripts/verify_environment.py --require-api-key` before a live call.

## 13. Run the application

### Backend

```bash
source .venv/bin/activate
uvicorn backend.app:app --reload
```

The API is served at `http://localhost:8000`; `GET /health` and documentation are available without a model key. Review endpoints return a clear service-configuration error until a real key is set. SQLite initializes automatically at `DATABASE_URL` (default `ndatrace.db`, ignored by Git).

### Frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`.

### Tests

```bash
source .venv/bin/activate
pytest

cd frontend
npx tsc --noEmit
npm run lint
npm test
npm run build
```

Standard automated tests make **zero paid hosted calls**. Some retrieval tests load the two public Hugging Face models named above, so prefetch them before testing offline. If Turbopack cannot create a local worker in a restricted sandbox, the supported fallback `npx next build --webpack` performs the same production build check.

## 14. Repository map

```text
pipeline/      Frozen RAG runtime, retrieval, parsing, and validation
backend/       FastAPI endpoints and persisted review history
frontend/      Next.js reviewer interface and Project Story
evaluation/    Metrics, evaluators, schemas, and harnesses
experiments/   Frozen E00–E23 protocols, outputs, and analyses
data/          Public-dataset instructions and tracked regression fixtures
results/       Canonical cross-experiment result tables
scripts/       Setup, offline analysis, experiment, and report utilities
docs/          Architecture, evaluation protocol, ADRs, and registry
tests/         Unit, integration, robustness, and leakage checks
reports/       Current report draft plus preserved earlier versions
```

Historical T-series materials are archived and retained as evidence; the active final program is E00–E23. ADR-001 through ADR-011 are historical. ADR-012 is the current final benchmark/product decision.

## 15. Reproduce and verify

**One command, after installation (§12):**

```bash
source .venv/bin/activate
python scripts/verify_reproducibility.py
```

This is the actual check, not a description of one — it runs and asserts, exits non-zero on any
failure:

1. ContractNLI present and SHA-256 checksum-verified against the frozen release.
2. The full `pytest` suite (433 tests, zero paid calls).
3. Every offline analysis script that recomputes metrics from saved predictions (majority
   baseline, E17/E17B TEST merge, E20 RAG comparison, E11 agent, E15 routing, E18 business
   synthesis).
4. `git diff --exit-code` on everything those scripts wrote — proves the recomputation is
   byte-for-byte identical to what's committed, not just "the script didn't crash."
5. The actual FastAPI backend, started in-process (no separate server, no paid calls):
   `/health`, `/hypotheses`, `/experiments`, `/experiments/e20` all asserted to return real,
   correctly-shaped data read from the files step 4 just verified.

Sample output:

```text
============================================================
REPRODUCIBILITY CHECK SUMMARY
============================================================
  [PASS] 1. Dataset present and checksum-verified
  [PASS] 2. Full test suite (zero paid calls)
  [PASS] 3. Offline analysis scripts recompute without error
  [PASS] 4. Recomputed results match committed files exactly (git diff --exit-code)
  [PASS] 5. Backend serves real computed data (in-process, no paid calls)
============================================================
ALL CHECKS PASSED
```

This reproduces scoring, cost calculations, and live API behavior from saved predictions; it does
**not** rerun the paid inference that created those predictions. Live experiment runners remain
available for provenance but must not be invoked casually. The individual analysis commands step 3
runs are listed below if you want to run one in isolation:

```bash
python experiments/E04B_majority_baseline/run_majority_baseline.py
python scripts/e17_analyze_final_test.py --metrics
python scripts/e17b_merge_and_analyze.py
python scripts/analyze_e20_rag_test.py
python scripts/analyze_e11_selective_agent.py
python scripts/analyze_e15_validation.py
python scripts/e18_business_analysis.py
```

- [Smallest working slice](experiments/E00_smallest_slice/README.md) — one input through retrieval, one model call, parsing, validation, and reviewer output.
- [Technical Tour notebook](notebooks/NDATrace_Complete_Technical_Tour.ipynb) — executable walkthrough using saved artifacts by default.
- [Experiment registry](docs/experiment_registry.md) — canonical E00–E23 ledger.
- [Evaluation protocol](docs/evaluation_protocol.md) — split, metric, and evidence rules.
- [Architecture decisions](docs/architecture_decisions/INDEX.md) — frozen decisions and rationale.
- [E21 security baseline](experiments/E21_owasp_llm_top10/summary.md) — original 10-category assessment.
- [E22 targeted remediation](experiments/E22_targeted_security_remediation/summary.md) — verification of the two baseline failures.

The Technical Tour defaults to saved outputs and zero hosted calls. Enable any live demonstration only deliberately and with a configured provider key.

Report renderers refuse to overwrite an existing artifact by default. Use a new path such as `python scripts/render_final_report_html.py --output /tmp/ndatrace-report.html`; `--force` is required to replace a named report intentionally.

## 16. Known prototype limitations

- No authentication or authorization; saved evidence/history is local plaintext SQLite.
- Permissive development CORS and in-process rate/concurrency controls are not production infrastructure.
- Prompt-injection detection is partial, and model output can still be wrong despite source-valid evidence.
- ContractNLI is public benchmark data, not evidence of performance on confidential enterprise NDAs or long contracts.
- Provider availability, provider pricing, the external dataset URL, and public model downloads are external dependencies.
- Use only public or synthetic NDA text in this prototype. It is not approved for confidential production documents.

## 17. Project context

NDATrace was developed for NTU PE6201 Emerging AI Technologies using the [ContractNLI](https://stanfordnlp.github.io/contract-nli/) dataset. It is an evidence-grounded reviewer-assist prototype, not legal advice or a production approval system.
