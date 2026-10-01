<div align="center">

# NDATrace

### An evidence-grounded NDA review assistant. Every verdict comes with the clause it's based on.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![Model](https://img.shields.io/badge/Model-GPT--5--mini-F97316)
![Tests](https://img.shields.io/badge/Tests-433%20passing-22C55E)
![Status](https://img.shields.io/badge/Status-Academic%20prototype-6B7280)

[Persona](#tinas-problem) · [What it does](#what-ndatrace-does) · [In action](#see-ndatrace-in-action) · [Architecture](#high-level-architecture) · [Metrics](#metrics-targeted-vs-reached) · [Design decisions](#key-design-decisions) · [Quick start](#quick-start) · [Reproducibility](#reproducibility) · [Data & evals](#data-and-evals) · [Repo map](#repository-map) · [Limitations](#limitations) · [Deliverables](#project-deliverables)

</div>

---

> ### "It got the right answer without finding the right clause."
>
> That's the failure plain accuracy hides. This project's headline metric is **Joint
> correctness**: label and cited evidence both have to be right, not accuracy alone. Numbers
> below in [Metrics](#metrics-targeted-vs-reached).

---

## Tina's problem

**Tina is a legal operations analyst, not a lawyer.**

She gets a vendor NDA and has to check it against her company's standard confidentiality
checklist before a lawyer looks at it. The hard part is that relevant wording is often
paraphrased, qualified by an exception, or scattered across clauses. Keyword search misses that.
A generic LLM answer doesn't fix it either, since she has no way to check what it's actually
based on.

Today she reads the whole NDA clause by clause to make sure nothing was missed. With NDATrace
she gets a verdict per requirement, each with its supporting clause, reviews the flagged or
uncertain ones first, and records her decision. She's never asked to trust the system — she's
shown what it's based on. No review-time or productivity claim is made here; see
[What's measured](#whats-measured-whats-not).

## What NDATrace does

It labels an NDA against each of 17 fixed confidentiality requirements as Entailment,
Contradiction, or Not Mentioned, cites the supporting clause, flags anything uncertain for human
review, and records the reviewer's final decision. It doesn't approve an NDA or make a legal call
on its own.

| | |
| --- | --- |
| **Input** | An NDA (pasted or uploaded) plus one or more of 17 fixed confidentiality requirements |
| **Output** | Per requirement: label, the exact cited clause (verbatim, never paraphrased), a short explanation, and any review/security flags |

Built and evaluated on [ContractNLI](https://stanfordnlp.github.io/contract-nli/), a public NDA
benchmark. That's not a claim of performance on real confidential enterprise contracts.

## See NDATrace in action

There's no screen recorder available in this working environment, so these aren't captured yet —
listed here instead of faked:

| Asset | Status |
| --- | --- |
| `docs/screenshots/demo_case.gif` — one real case end to end (input → run → result → evidence → decision) | Not yet captured |
| `docs/screenshots/01-input.png`, `02-results.png`, `03-decision.png` | Not yet captured |

To capture these: run the app ([Quick start](#quick-start)), submit one NDA and requirement, and
record the input → verdict → evidence → Approve/Override/Reject flow.

## High-level architecture

```mermaid
flowchart TD
    IN(["NDA + Requirement"])

    subgraph RETRIEVAL["① Retrieval (deterministic)"]
        direction LR
        CHUNK["Clause-aware chunking<br/><i>256 tokens, no overlap</i>"]
        BM25["BM25 search<br/><i>top-20 candidates</i>"]
        RERANK["Cross-encoder rerank<br/><i>top-5 kept</i>"]
        CHUNK --> BM25 --> RERANK
    end

    LLM["② GPT-5-mini classification<br/><i>frozen prompt · temperature 0</i>"]

    subgraph VALIDATE["③ Validation & safety (deterministic)"]
        direction LR
        PARSE["Structured parser"]
        EVID["Evidence validator<br/><i>verbatim check</i>"]
        GUARD["Injection guard +<br/><i>rate / cost limits</i>"]
        PARSE --> EVID --> GUARD
    end

    subgraph HUMAN["④ Human review"]
        direction LR
        REVIEWER["Reviewer sees<br/><i>verdict + evidence + flags</i>"]
        DECISION(["Recorded decision<br/><b>Approve / Override / Reject</b>"])
        REVIEWER --> DECISION
    end

    IN --> RETRIEVAL --> LLM --> VALIDATE --> HUMAN

    classDef input fill:#f8fafc,stroke:#475569,stroke-width:1.5px,color:#1e293b;
    classDef stage fill:#eff6ff,stroke:#3b82f6,stroke-width:1px,color:#1e3a5f;
    classDef model fill:#fff7ed,stroke:#f97316,stroke-width:1.5px,color:#7c2d12;
    classDef control fill:#f0fdf4,stroke:#22c55e,stroke-width:1px,color:#14532d;
    classDef human fill:#fdf4ff,stroke:#c084fc,stroke-width:1.5px,color:#581c87;

    class IN input;
    class CHUNK,BM25,RERANK stage;
    class LLM model;
    class PARSE,EVID,GUARD control;
    class REVIEWER,DECISION human;

    style RETRIEVAL fill:#f8fafc,stroke:#3b82f6,stroke-width:1px
    style VALIDATE fill:#f0fdf4,stroke:#22c55e,stroke-width:1px
    style HUMAN fill:#fdf4ff,stroke:#c084fc,stroke-width:1px
```

Orange is the one LLM call. Green is deterministic code, no model involved. Purple is the human
in the loop: there's no automatic confidence gate, so every result reaches a reviewer. This
matches `pipeline/frozen_rag.py` and `pipeline/final_review.py` directly.

## Metrics: targeted vs. reached

| | Metric | Target (proposal) | Reached (measured) | Status |
| --- | --- | --- | --- | --- |
| Primary | Risk-sensitive recall gain, RAG over FULL (mean of Contradiction + NotMentioned recall) | ≥ 5.0 points | +1.2 points (69.07% → 70.25%) | ❌ Not met |
| Secondary | Joint correctness (label + evidence), FULL vs. RAG | Required to be measured and disclosed | 74.6% (FULL) / 72.5% (RAG), n=2,091 | ✅ Reported as measured |
| Secondary | Contradiction recall, reported separately (not averaged away) | Required, not fixed | 75.5% (FULL) / 77.3% (RAG) | ✅ Reported separately |

Official ContractNLI TEST split, n = 2,091, FULL and RAG on the identical population with paired
significance testing. Source: `experiments/E20_final_rag_test/results/E20_final_report.json`.

![FULL vs RAG, four headline metrics](docs/images/full_vs_rag_dumbbell.png)

FULL's Joint-correctness edge is the only statistically significant gap (McNemar p=0.0047).
Accuracy isn't significantly different (p=0.217). More detail in
[`experiments/E20_final_rag_test/summary.md`](experiments/E20_final_rag_test/summary.md).

### What's measured, what's not

Measured: API inference cost, and nothing else. RAG runs $0.00168/case, FULL $0.00202/case.

Not measured: reviewer time savings. No productivity or labor-cost claim is made anywhere in
this repository.

Modeled, not measured, and kept separate: an illustrative human-review-cost scenario lives in
[`experiments/E18_business_course_synthesis/summary.md`](experiments/E18_business_course_synthesis/summary.md).
It's labeled as a scenario there and isn't foregrounded here, so the two kinds of claim don't get
confused.

## Key design decisions

Four architectures were built and measured against each other, not assumed:

| Alternative | Verdict |
| --- | --- |
| Rule-based keyword baseline | 59.0% accuracy / 50.1% Joint, insufficient, justified an LLM |
| Full-context LLM (FULL) | Strongest measured quality, kept as the benchmark reference |
| Retrieval-augmented generation (RAG) | Bounded cost/context, kept as the served architecture |
| Selective agentic investigation | Zero tool calls on 15 real escalated cases, net benefit 0.0pp, rejected |

Automatic confidence-routing was tested too (E15). No policy hit both an acceptable review
workload and an acceptable error rate, so every result still routes to a human.

![Quality vs. cost, all four measured systems](docs/images/quality_cost_frontier.png)

Trade-offs made, explicitly:

- **Quality for cost/scale.** RAG was picked knowing FULL scores 2.1 Joint points higher, on the
  bet that bounded context matters more at real document lengths than on ContractNLI's short
  NDAs.
- **Simplicity over capability.** The agent and auto-routing were rejected after measuring them,
  not before. Both added real cost and earned nothing back on this data.
- **Precision over recall.** BM25 plus a reranker beat dense/hybrid retrieval on quality, and BM25
  needs no vector index to operate.

![Where RAG actually fails](docs/images/failure_pareto.png)

Retrieval isn't the bottleneck. Only 10% of RAG's failures are retrieval-limited; 78% are
reasoning errors on evidence it already found. Full breakdown in
[`docs/failure_analysis.md`](docs/failure_analysis.md), with one real case walked through step
by step in [`examples/case_failure/`](examples/case_failure/).

What I owned end to end: the retrieval/reranking pipeline and its chunking strategy, the
evaluation harness and all 24 experiment scripts, the reviewer decision API
(`backend/routes/review.py`), the injection guard, and the reproducibility harness
(`scripts/verify_reproducibility.py`).

The full 24-experiment ledger (E00–E23), each with its question, finding, and decision, is in
[`docs/experiment_registry.md`](docs/experiment_registry.md).

## Quick start

**Requirements:** Python 3.12, Node.js ≥20.9 + npm, internet access for the dataset and model
downloads. An OpenRouter API key is only needed for billed review calls.

```bash
# 1. Clone and set up Python
git clone https://github.com/AsmithaUbaid/ndatrace.git && cd ndatrace
python3.12 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt

# 2. Get the dataset and configure
bash scripts/download_data.sh     # downloads + checksum-verifies ContractNLI
cp .env.example .env              # safe placeholders, no key required to start
python scripts/verify_environment.py

# 3. Run the backend
uvicorn backend.app:app --reload  # http://localhost:8000

# 4. Run the frontend (new terminal)
cd frontend && npm ci && npm run dev   # http://localhost:3000
```

`GET /health` works without a key. Review endpoints return a clear config error until
`OPENROUTER_API_KEY` is set. Prefetch the reranker/embedding models with
`python scripts/download_models.py`.

To verify instead of run (tests, type-checks, full reproducibility), see
[Reproducibility](#reproducibility) below. It's kept separate so this section stays about running
the product, not proving it.

## Reproducibility

| | Cost | What it proves |
| --- | --- | --- |
| A. Reproduce metrics from saved outputs | Free | Every number on this page recomputes from committed predictions, not a live model. |
| B. Run one real request through the live pipeline | Free (stub) or ~$0.002 (`--live`) | The real code path, chunk → retrieve → rerank → classify → validate, works end to end. |
| C. Rerun large-scale paid inference | Real API cost | Not part of normal verification, not done casually. |

```bash
# A — one command: dataset checksum, full pytest (433 tests), every offline analysis
# script, byte-for-byte drift check, and in-process backend checks
python scripts/verify_reproducibility.py

# B — one real NDA through the real pipeline (pipeline/frozen_rag.py + final_review.py)
python experiments/E00_smallest_slice/run_smallest_slice.py          # dry-run, $0
python experiments/E00_smallest_slice/run_smallest_slice.py --live   # one real call, ~$0.002
```

<details>
<summary>Sample output — A</summary>

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

</details>

<details>
<summary>Sample output — B (dry-run)</summary>

```json
{
  "label": "Entailment",
  "evidence": ["shall not disclose the Confidential Information to any third party without the prior written consent of the Disclosing Party."],
  "source_valid": true,
  "needs_human_review": false,
  "model": "openai/gpt-5-mini",
  "success": true
}
```

</details>

Frontend checks: `cd frontend && npx tsc --noEmit && npm test && npm run build`.

## Data and evals

| | |
| --- | --- |
| Dataset | [ContractNLI](https://stanfordnlp.github.io/contract-nli/): 607 NDAs, 17 fixed requirements, 10,319 examples. TEST split: 2,091 examples, 123 documents. Explainer: [`data/README.md`](data/README.md). |
| Evals | An offline scoring harness that knows gold labels, kept separate from a runtime validator that never sees them. Explainer: [`evaluation/README.md`](evaluation/README.md), protocol: [`docs/evaluation_protocol.md`](docs/evaluation_protocol.md). |
| Experiments | 24 numbered, frozen experiments (E00–E23), each with its question, finding, and decision, in [`docs/experiment_registry.md`](docs/experiment_registry.md). |
| Failure analysis | What RAG actually gets wrong and what that implies for future work: [`docs/failure_analysis.md`](docs/failure_analysis.md). |
| Worked examples | One real correct case and one real failure case, walked through every pipeline stage: [`examples/case_success/`](examples/case_success/), [`examples/case_failure/`](examples/case_failure/). |
| Architecture decisions | Every frozen choice and the evidence behind it: [`docs/architecture_decisions/INDEX.md`](docs/architecture_decisions/INDEX.md). |

Gold labels and evidence are withheld from the model at inference time and scored only
afterward. The TEST split wasn't tuned against during this project's own development, though a
superseded earlier run did score it once; that's disclosed in
[`docs/data_contamination_register.md`](docs/data_contamination_register.md) and not described
as "blind."

## Repository map

```text
pipeline/      Frozen RAG runtime: chunking, retrieval, reranking, parsing, validation
backend/       FastAPI endpoints, persisted review history, reviewer decision API
frontend/      Next.js reviewer interface and Project Story
evaluation/    Metrics, evaluators, schemas, and harnesses
experiments/   Frozen E00–E23 protocols, outputs, and analyses
examples/      One worked success case and one worked failure case
notebooks/     Executable Technical Tour (saved artifacts by default)
data/          Public-dataset instructions and tracked regression fixtures
results/       Canonical cross-experiment result tables
scripts/       Setup, offline analysis, experiment, and chart/report utilities
docs/          Architecture, evaluation protocol, ADRs, experiment registry, images
tests/         Unit, integration, robustness, and leakage checks
```

## Limitations

| Distinction | What's actually true here |
| --- | --- |
| Evidence-source verification | Cited text is checked to appear verbatim in the NDA. |
| Semantic classification correctness | A separate question. Source-valid evidence doesn't mean the label is correct. |
| Prompt-injection detection | Partial, not solved. 4 of 11 tested attack patterns still bypass the guard (E16). |
| Human verification | Every result is shown for review; nothing auto-finalizes. |

No authentication: scoped to public or synthetic NDA text only, not approved for confidential
documents. ContractNLI is a public benchmark, not evidence of performance on long (50–100 page)
real enterprise contracts. No production deployment, no production-readiness claim, no complete
prompt-injection protection claim.

## Project deliverables

NTU PE6201 (Emerging AI Technologies) end-of-course project.

- Trade-off report: submitted separately, not included in this public repository ahead of the
  submission deadline.
- GitHub implementation: this repository, reproducible end to end via
  [`scripts/verify_reproducibility.py`](#reproducibility).
- Problem statement and course materials: submitted separately through the course platform.
- Recorded demonstration: not yet recorded.

NDATrace was developed for NTU PE6201 using the
[ContractNLI](https://stanfordnlp.github.io/contract-nli/) dataset. It's an evidence-grounded
reviewer-assist prototype, not legal advice or a production approval system.
