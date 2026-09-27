# NDATrace

**Evidence-grounded NDA requirement review for enterprise legal operations**

NDATrace reviews an NDA against a confidentiality requirement, classifies it as Entailment,
Contradiction, or Not Mentioned, and returns the supporting source clauses for human verification.

`Python` · `FastAPI` · `Next.js` · `GPT-5-mini` · `ContractNLI`

> **Prototype runtime:** frozen top-5 RAG<br>
> **Benchmark winner:** GPT-5-mini with FULL context<br>
> **Agentic escalation:** tested and rejected

## Why NDATrace?

Enterprise legal operations analysts often need to check whether an NDA satisfies a standard
confidentiality requirement. The relevant language may be paraphrased, split across clauses, or
qualified by definitions, exceptions, and cross-references. NDATrace narrows that review to a
checkable classification and its supporting clauses, so the analyst can focus attention where it
is needed. It is a reviewer aid—not legal advice or an automated NDA approval system—and the human
reviewer remains the final authority.

## Prototype architecture

```mermaid
flowchart TD
    INPUT(["NDA + confidentiality requirement"])

    subgraph RETRIEVAL["1 · RETRIEVE"]
        direction LR
        CHUNK["Clause-aware chunking<br/>256 tokens · overlap config 50"]
        BM25["Candidate search<br/>BM25 · top-20"]
        RERANK["Cross-encoder reranking<br/>MiniLM-L-12-v2"]
        CONTEXT["Selected context<br/>top-5 clauses"]
        CHUNK --> BM25 --> RERANK --> CONTEXT
    end

    subgraph CLASSIFY["2 · CLASSIFY"]
        direction LR
        MODEL["GPT-5-mini<br/>frozen P0 · temperature 0"]
        PARSER["Structured output<br/>parser"]
        MODEL --> PARSER
    end

    subgraph VERIFY["3 · VERIFY"]
        direction LR
        VALIDATE["Evidence / source<br/>validation"]
        RESULT["Verdict + evidence<br/>ranked source clauses"]
        VALIDATE --> RESULT
    end

    REVIEW(["Human reviewer<br/>final authority"])

    INPUT --> CHUNK
    CONTEXT --> MODEL
    PARSER --> VALIDATE
    RESULT --> REVIEW

    classDef input fill:#f8fafc,stroke:#64748b,stroke-width:1.5px,color:#0f172a;
    classDef retrieval fill:#eff6ff,stroke:#93b4d8,stroke-width:1px,color:#17324d;
    classDef classify fill:#f5f3ff,stroke:#b7a8d9,stroke-width:1px,color:#312e55;
    classDef verify fill:#fffaf0,stroke:#d6b879,stroke-width:1px,color:#4a3513;
    classDef human fill:#edf8f1,stroke:#78a98a,stroke-width:1.5px,color:#163522;
    class INPUT input;
    class CHUNK,BM25,RERANK,CONTEXT retrieval;
    class MODEL,PARSER classify;
    class VALIDATE,RESULT verify;
    class REVIEW human;
    style RETRIEVAL fill:#f8fbff,stroke:#cbd9ea,stroke-width:1px
    style CLASSIFY fill:#faf9ff,stroke:#d8d0e8,stroke-width:1px
    style VERIFY fill:#fffdf8,stroke:#e5d8ba,stroke-width:1px
    linkStyle default stroke:#94a3b8,stroke-width:1.5px;
```

Both the single-requirement and batch-review endpoints use the same frozen pipeline. The batch
path builds one document index and reuses it across the selected requirements. There is no agent,
automated routing policy, rule boost, or silent FULL-context fallback in the runtime.

| Component | Frozen choice |
|---|---|
| Chunking | Clause-aware, 256-token limit |
| Overlap | 50 in the frozen configuration; clause-aware chunking preserves boundaries rather than sliding windows |
| Candidate retrieval | BM25 top-20 |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-12-v2` |
| Final context | Top-5 clauses |
| Model | `openai/gpt-5-mini` |
| Prompt | Frozen `GPT-P0` |
| Temperature | 0 |
| Agent | Not used |
| Routing | Not used |

Implementation details: [`docs/architecture.md`](docs/architecture.md).

## Every rung had to earn its complexity

The project began with the cheapest deterministic approach. Each additional layer had to justify
its quality, cost, latency, and failure modes before it could remain in the system.

A conventional fixed classifier would be cheap at inference time, but the project required
semantic reasoning over paraphrases, exceptions and evidence spans; Rules were therefore retained
as the non-AI baseline.

```mermaid
flowchart LR
    A0["A0 · Rules<br/>Start with the cheapest<br/>deterministic baseline"]
    A1["A1 · FULL<br/>Add whole-document<br/>semantic reasoning<br/>Benchmark winner"]
    A2["A2 · RAG<br/>Bound context and return<br/>clause provenance<br/>Prototype runtime"]
    A3["A3 · Agent<br/>Try tools on difficult<br/>retrieval cases<br/>Rejected"]

    A0 --> A1 --> A2 --> A3

    classDef baseline fill:#f8fafc,stroke:#94a3b8,color:#1f2937;
    classDef winner fill:#eff6ff,stroke:#93b4d8,color:#17324d;
    classDef runtime fill:#f0fdf4,stroke:#86b89a,color:#163522;
    classDef rejected fill:#fff7f7,stroke:#d6a3a3,color:#572727;
    class A0 baseline;
    class A1 winner;
    class A2 runtime;
    class A3 rejected;
```

| Rung | Architecture | What it added | Decision |
|---|---|---|---|
| A0 | Rules | Deterministic keyword baseline | Insufficient semantic coverage |
| A1 | FULL-context LLM | Semantic reasoning over the complete NDA | Strongest benchmark Joint result |
| A2 | RAG | Bounded context and clause provenance | Selected prototype runtime |
| A3 | Selective/full agent | Dynamic retrieval tools and additional reasoning steps | Rejected: no useful quality gain |

> **Key finding:** more autonomy did not automatically improve quality.

## Final benchmark

The final comparison used all **123 NDAs** and **2,091 document–hypothesis cases** in the official
ContractNLI TEST set. FULL and RAG used the same GPT-5-mini model, frozen P0 prompt, parser, evidence
evaluator, and TEST population; only the supplied context differed.

| Metric | FULL | RAG top-5 |
|---|---:|---:|
| Accuracy | **77.6%** | 76.8% |
| Macro-F1 | **0.727** | 0.723 |
| Joint | **74.6%** | 72.5% |
| Contradiction Recall | 75.5% | **77.3%** |
| Evidence Recall | **93.3%** | 89.0% |
| Source Validity | 98.0% | **99.2%** |
| Mean input tokens | 2,279 | **1,131** |
| Mean latency | 7.31s | **7.14s** |

- Classification accuracy difference: McNemar **p=0.217**.
- Joint difference: McNemar **p=0.0047**.

FULL achieved the stronger evidence-grounded benchmark result. RAG retained similar
classification quality while reducing classifier input context by **50.4%**. RAG did not beat
FULL overall: it gave up approximately **2.2 percentage points** of Joint success on this
benchmark.

## Why RAG powers the prototype

> **FULL remains the benchmark-quality winner on ContractNLI. RAG is the product-oriented
> prototype architecture.**

The top-5 RAG path uses about **50.4% fewer classifier input tokens** and **16.8% less raw API
inference cost** in the matched E20 comparison. Its context is bounded, every result carries
ranked clause-level provenance, and a document's retrieval index can be reused across multiple
requirements. Those properties fit an interactive reviewer workflow even though FULL remains the
stronger benchmark configuration.

This is a measured product trade-off, not a claim that RAG is more accurate or proven superior on
100-page contracts. ContractNLI's document lengths are not sufficient to establish that broader
scaling claim.

Cost-to-serve considers AI inference, expected human fallback, and fixed operating cost — not API
price alone.

## Evaluation: label correctness is not enough

NDATrace evaluates three distinct questions:

| Measure | Question |
|---|---|
| Accuracy | Was the label correct? |
| Evidence quality | Did the system identify the correct source clause? |
| Joint | Were both the label **and** evidence correct? |

> For a legal-review assistant, a correct label backed by unsupported evidence is not a successful
> result.

Joint is therefore the headline measure. The evaluation also reports Contradiction Recall,
Evidence Recall and Precision, source validity, retrieval Recall@K, latency, and token use.

Evaluation combines deterministic schema/source checks with ContractNLI's human-annotated labels
and evidence. Joint success requires both a correct label and valid supporting evidence.

## Evaluation protocol

- ContractNLI's official TRAIN/DEV/TEST partition was preserved with no re-splitting.
- TRAIN supported development and controlled, lower-cost ablations; DEV supported confirmation
  and architecture selection.
- The official TEST split was not accessed during reconstruction-v2 tuning. Model, prompt,
  retrieval, routing, agent policy, and scoring configuration were frozen before final TEST runs.
- Gold labels and evidence were hidden from normal inference and available only to the scorer.
- FULL and RAG were compared on the same 2,091 TEST cases, followed by failure analysis—not
  TEST-driven tuning.
- Fixed 150-case TRAIN subsets made agent and prompt ablations affordable; they did not replace
  the full TEST evaluation.

The project describes this as the **final held-out benchmark under the reconstruction-v2
protocol**, not as perfectly unseen data: earlier, pre-reconstruction work had historical TEST
exposure. The reconstruction pass did not use those prior TEST outcomes to tune the final system.
See [`docs/evaluation_protocol.md`](docs/evaluation_protocol.md) and the
[`data contamination register`](docs/data_contamination_register.md).

## Model selection

Before optimizing retrieval, the Oracle experiment supplied gold evidence directly to each model
to measure its reasoning ceiling. This diagnostic used a balanced 300-case TRAIN sample and must
not be mixed with normal end-to-end benchmark results.

| Model | Execution | Oracle Macro-F1 | Contradiction Recall |
|---|---|---:|---:|
| Llama 3.2 3B | Local | 0.601 | 25% |
| Qwen 2.5 7B Instruct | Local | 0.638 | 30% |
| Gemini 2.5 Flash Lite | Hosted | 0.867 | 71% |
| **GPT-5-mini** | Hosted | **0.906** | **82%** |

Qwen was also retained as the local comparator for the reconstruction-v2 full TEST evaluation.
GPT-5-mini powered the final hosted comparisons because its measured evidence-conditioned
reasoning quality was substantially stronger. Full Oracle methodology and caveats are recorded in
[`experiments/E01_oracle/summary.md`](experiments/E01_oracle/summary.md).

## Why the agent was rejected

The agent experiments tested whether additional retrieval tools and controller steps could recover
base RAG failures on a fixed 150-case TRAIN sample.

| Configuration | Joint | Cases using tools |
|---|---:|---:|
| Base RAG | **75.3%** | — |
| Agent V1 | 73.3% | 1.3% |
| Agent V2 controller prompt | 68.7% | 20.0% |

Changing the controller prompt increased tool use substantially, but produced no useful
tool-mediated recoveries. The tested retrieval-agent configuration therefore did not earn its
additional complexity. This is a finding about the tested design, not a claim that agents cannot
work in other systems.

## Where the system still fails

E20 recorded 576 non-Joint outcomes:

| Failure category | Cases |
|---|---:|
| Reasoning/classification | 448 |
| Evidence selection | 59 |
| Retrieval-limited | 55 |
| Runtime/parser/source validity | 14 |

Most remaining failures are reasoning/classification failures rather than retrieval failures.
That distribution helps explain why an additional retrieval agent had limited opportunity to add
value.

## Security & responsible use

E16 tested 20 matched clean/adversarial pairs against the frozen GPT-5-mini + P0 FULL candidate.
Four of 11 prompt-injection/adversarial-instruction cases succeeded, including **two label
hijacks**. Joint success fell from **85% clean to 75% under attack**. Attack evidence remained
source-grounded, demonstrating an important limitation: a source-valid quote can still contain
malicious instructions. E16 was a small controlled test, not a certification of the current RAG
runtime.

Silent failure means a plausible-looking verdict backed by incomplete or misleading evidence;
Joint scoring, source validation and human review are used to surface this risk.

**Implemented controls**

- Structured-output parsing and validation
- Exact evidence grounding against NDA source text
- Source-validation failures surfaced for human review
- Bounded steps, bounded tools, and duplicate-action protection in the experimental agent path
- Human final authority; no automatic NDA approval or rejection

**Not production complete**

- Strong prompt-injection isolation
- Authentication and authorization
- Rate limiting
- Comprehensive upload and malware validation
- Secrets hardening
- Enterprise retention and PII controls
- Broader adaptive adversarial testing

## Build vs reuse

| Layer | Decision |
|---|---|
| Data | Reuse ContractNLI |
| Model | Rent GPT-5-mini through OpenRouter |
| Chunking and retrieval orchestration | Build |
| BM25 | Reuse `rank_bm25` |
| Cross-encoder | Reuse pretrained `ms-marco-MiniLM-L-12-v2` |
| Evidence validation | Build |
| Evaluation harness | Build |
| API and UI | Build |

## Quick start

### 1. Install the backend

```bash
git clone https://github.com/AsmithaUbaid/ndatrace.git
cd ndatrace
git switch reconstruction

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash scripts/download_data.sh
```

The first live retrieval may download the cross-encoder model. Copy the environment template and
set `OPENROUTER_API_KEY` for live GPT-5-mini reviews:

```bash
cp .env.example .env
python scripts/verify_environment.py
uvicorn backend.app:app --reload
```

The API runs at `http://localhost:8000`.

### 2. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Live reviews require hosted, billed OpenRouter inference. Unit and
integration tests mock model calls and do not require paid inference:

```bash
python -m pytest tests/
```

## Reproduce the decision journey

[`notebooks/NDATrace_Complete_Technical_Tour.ipynb`](notebooks/NDATrace_Complete_Technical_Tour.ipynb)
is an executable walkthrough of the architecture decisions: rules, Oracle/model selection,
retrieval design, prompt ablations, FULL versus RAG, routing, agent experiments, cost-to-serve,
security, and the final architecture decision.

`RUN_HOSTED_MODEL=False` by default. In that mode, the notebook reuses stored experiment outputs,
recomputes chunking and retrieval locally, and requires zero paid model calls. Setting it to `True`
enables exactly one live, billed GPT-5-mini demonstration call.

## Repository structure

```text
pipeline/      Frozen RAG runtime, model gateway, parser integration, and historical agent modules
backend/       FastAPI endpoints and SQLite-backed review history
frontend/      Next.js reviewer interface
evaluation/    Metrics, evaluators, schemas, and experiment harnesses
experiments/   Frozen reconstruction-v2 protocols, outputs, and analyses
notebooks/     Executable technical tour
docs/          Architecture, API, evaluation, decisions, and experiment registry
tests/         Unit, integration, robustness, and data-leakage tests
```

Useful entry points:

- [`docs/architecture.md`](docs/architecture.md) — current runtime and benchmark/product decision
- [`docs/architecture_decisions/INDEX.md`](docs/architecture_decisions/INDEX.md) — architecture decision records
- [`docs/experiment_registry.md`](docs/experiment_registry.md) — reconstruction-v2 experiment ledger
- [`docs/api.md`](docs/api.md) — API contract
- [`frontend/README.md`](frontend/README.md) — frontend development guide

## Limitations

- ContractNLI is a proxy dataset, not a complete enterprise legal playbook.
- Only the NDA requirements represented by ContractNLI are evaluated.
- NDATrace does not provide legal advice or autonomously approve or reject agreements.
- Quality on documents beyond ContractNLI's observed lengths is not established.
- Prompt-injection hardening is incomplete.
- Automatic uncertainty/review routing did not meet the desired reliability target and is not in
  the runtime.
- Most residual E20 errors are reasoning/classification failures; retrieval changes alone will not
  resolve them.
- Human review remains required.

## Project context

NDATrace was developed for NTU PE6201 Emerging AI Technologies using the
[ContractNLI](https://stanfordnlp.github.io/contract-nli/) dataset. Historical and rejected paths
remain in the repository for reproducibility; they are not part of the active runtime.
