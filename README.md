# NDATrace

NDATrace helps legal reviewers compare confidentiality requirements with an NDA and inspect the source evidence behind each verdict.

`Python` · `FastAPI` · `Next.js` · `GPT-5-mini` · `ContractNLI` · `Human-in-the-loop`

## 1. What it does

```text
NDA + requirement → verdict → supporting clause → human review
```

Each requirement receives one of three labels:

- **Entailment** — the agreement supports the requirement.
- **Contradiction** — the agreement conflicts with the requirement.
- **Not Mentioned** — the agreement does not establish either conclusion.

The reviewer sees the verdict, a concise explanation, and verbatim evidence when evidence is required. NDATrace is a reviewer aid, not an autonomous legal decision-maker.

## 2. Final decision at a glance

| Component | Final role |
| --- | --- |
| Rule | Baseline |
| FULL | Quality reference |
| RAG | Prototype runtime |
| Agent | Tested and rejected |
| Human | Final authority |

The shipped review path is the frozen RAG pipeline. FULL is retained as the strongest measured quality reference, not as the prototype runtime.

## 3. Final test result

Official ContractNLI **TEST** split, **n = 2,091**. The Rule values below are TEST results, not TRAIN results.

| Metric | Rule | Qwen | FULL | RAG |
| --- | ---: | ---: | ---: | ---: |
| Accuracy | 59.0% | 49.9% | **77.6%** | 76.8% |
| Joint success | 50.1% | 39.7% | **74.6%** | 72.5% |
| Contradiction recall | 16.8% | 25.5% | 75.5% | **77.3%** |

On paired cases, the FULL–RAG classification difference was not significant (`p = 0.217`), while the Joint difference was (`p = 0.0047`). FULL therefore remains the quality reference; RAG accepts a measured evidence-grounding trade-off for a more bounded runtime.

For scale, a deterministic [majority-class TEST sanity check](experiments/E04B_majority_baseline/README.md) reaches 46.3% accuracy and 0% Joint. It is a trivial baseline, not an architecture rung.

## 4. Why RAG is the prototype

FULL achieved the higher Joint score. RAG was selected for the prototype because it uses bounded context, returns a clause-level evidence path, reduced mean input tokens by **50.4%**, and reduced raw API inference cost by **16.8%** in the matched E20 TEST run.

This is an engineering trade-off, not a claim that RAG outperformed FULL on overall quality.

## 5. Final architecture

```mermaid
flowchart LR
    A[NDA + requirement] --> B[Clause-aware chunks<br/>256 tokens / 50 overlap]
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
| Chunking | Clause-aware, 256 tokens, 50-token overlap |
| Candidate generation | BM25 top-20 |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-12-v2` |
| Model context | Top-5 reranked clauses |
| Model | `openai/gpt-5-mini`, temperature 0 |
| Prompt | P0, single shot |
| Output controls | Structured parser + verbatim evidence validation |
| Decision authority | Human reviewer |

See [the architecture guide](docs/architecture.md) and [architecture decisions](docs/architecture_decisions/INDEX.md).

## 6. What we tested and rejected

| Question | Decision |
| --- | --- |
| Would prompt variants reliably beat P0? | No variant justified replacing frozen P0. |
| Would static context expansion justify its added context? | No; keep top-5. |
| Would a targeted agent recover residual failures? | No; added investigation did not create enough recovery value. |
| Would automatic confidence routing safely reduce work? | Tested, not adopted. |

The causal experiment story is available in the app at `/project`. Exact protocols, artifacts, and decisions are indexed in the [experiment registry](docs/experiment_registry.md).

## 7. Security posture

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

See [E21](experiments/E21_owasp_llm_top10/summary.md) and [E22](experiments/E22_targeted_security_remediation/summary.md).

## 8. Important agent correction

The reconstruction agent experiment exposed only two targeted, read-only tools:

- `FOLLOW_CROSS_REFERENCE` — retrieve a bounded excerpt from a named provision in the same NDA.
- `GET_MORE_CANDIDATES` — reveal a bounded slice below the frozen top-5 from the existing ranked candidate pool.

It had no web search, filesystem access, external database access, write actions, or autonomous legal authority. In the tested architecture, these tools did not create enough recovery value to justify the added cost, latency, and control complexity.

**The agent is experimental and is not in the live runtime.** Saved E10/E11 artifacts remain for reproducibility.

## 9. Cost-to-serve

The modeled workflow uses:

```text
C_total = C_AI + (1 - p_joint) × C_human
```

API cost is not total workflow cost: failed Joint cases still require human handling. All business figures are **MODELED scenarios**, not realized production savings. Assumptions and sensitivity analysis are documented in [E18](experiments/E18_cost_to_serve/summary.md).

## 10. Limitations

- ContractNLI is a proxy dataset; performance on real enterprise NDA distributions is not established.
- Long-document and organizational distribution shift remain open risks.
- Automatic uncertainty routing was tested but not adopted.
- Prompt-injection detection remains incomplete.
- The system cannot grant autonomous legal approval.
- A human remains the final authority.

## 11. Quick start

### Backend

```bash
git clone https://github.com/AsmithaUbaid/ndatrace.git
cd ndatrace
git switch reconstruction

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash scripts/download_data.sh
cp .env.example .env
python scripts/verify_environment.py
uvicorn backend.app:app --reload
```

The live runtime uses `openai/gpt-5-mini`. Set `OPENROUTER_API_KEY` in `.env` only when intentionally running a billed review. The API is served at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

### Tests

```bash
pytest

cd frontend
npx tsc --noEmit
npm run lint
npm test
npm run build
```

Standard automated tests mock model calls and make **zero paid hosted calls**.

## 12. Repository map

```text
pipeline/      Frozen RAG runtime, retrieval, parsing, and validation
backend/       FastAPI endpoints and persisted review history
frontend/      Next.js reviewer interface and Project Story
evaluation/    Metrics, evaluators, schemas, and harnesses
experiments/   Frozen E00–E22 protocols, outputs, and analyses
docs/          Architecture, evaluation protocol, ADRs, and registry
tests/         Unit, integration, robustness, and leakage checks
```

Historical artifacts are retained for reproducibility but do not define the live runtime.

## 13. Reproduce the project

- [Smallest working slice](experiments/E00_smallest_slice/README.md) — one input through retrieval, one model call, parsing, validation, and reviewer output.
- [Technical Tour notebook](notebooks/NDATrace_Complete_Technical_Tour.ipynb) — executable walkthrough using saved artifacts by default.
- [Experiment registry](docs/experiment_registry.md) — canonical E00–E22 ledger.
- [Evaluation protocol](docs/evaluation_protocol.md) — split, metric, and evidence rules.
- [Architecture decisions](docs/architecture_decisions/INDEX.md) — frozen decisions and rationale.
- [E21 security baseline](experiments/E21_owasp_llm_top10/summary.md) — original 10-category assessment.
- [E22 targeted remediation](experiments/E22_targeted_security_remediation/summary.md) — verification of the two baseline failures.

The Technical Tour defaults to saved outputs and zero hosted calls. Enable any live demonstration only deliberately and with a configured provider key.

## 14. Project context

NDATrace was developed for NTU PE6201 Emerging AI Technologies using the [ContractNLI](https://stanfordnlp.github.io/contract-nli/) dataset. It is an evidence-grounded reviewer-assist prototype, not legal advice or a production approval system.
