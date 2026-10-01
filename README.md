<div align="center">

# NDATrace

### An evidence-grounded NDA review assistant. Every verdict comes with the clause it's based on.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![Model](https://img.shields.io/badge/Model-GPT--5--mini-F97316)
![Tests](https://img.shields.io/badge/Tests-433%20passing-22C55E)
![Status](https://img.shields.io/badge/Status-Academic%20prototype-6B7280)

![NDATrace end-to-end NDA review demo](docs/screenshots/demo_case.gif)

*One NDA requirement from input → retrieved evidence → verdict → reviewer decision.*

[Persona](#tinas-problem) · [What it does](#what-ndatrace-does) · [Architecture](#high-level-architecture) · [Metrics](#metrics-targeted-vs-reached) · [Design decisions](#key-design-decisions) · [Quick start](#quick-start) · [Reproducibility](#reproducibility) · [Data & evals](#data-and-evals) · [Repo map](#repository-map) · [Limitations](#limitations) · [Deliverables](#project-deliverables)

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

| | Metric | Target | Reached (measured) | Status |
| --- | --- | --- | --- | --- |
| Primary | Risk-sensitive recall gain, RAG over **Rule-based (non-AI baseline)** | ≥ 5.0 points | **+16.6 points** (53.6% → 70.3%) | ✅ Met, by a wide margin |
| Secondary | Joint correctness (label + evidence), FULL vs. RAG | Required to be measured and disclosed | 74.6% (FULL) / 72.5% (RAG), n=2,091 | ✅ Reported as measured |
| Secondary | Contradiction recall, reported separately (not averaged away) | Required, not fixed | 75.5% (FULL) / 77.3% (RAG) | ✅ Reported separately |

Official ContractNLI TEST split, n = 2,091, all three systems on the identical population.
Source: `experiments/E20_final_rag_test/results/E20_final_report.json`,
`results/final/v2/full_test_comparison.csv`. Rule-based keyword retrieval is the project's
non-AI baseline (Problem Statement Section 4) and the target's comparison point.

![FULL vs RAG, four headline metrics](docs/images/full_vs_rag_dumbbell.png)

**Takeaway:** FULL's Joint-correctness edge is the only statistically significant gap (McNemar
p=0.0047); accuracy isn't significantly different (p=0.217). More detail in
[`experiments/E20_final_rag_test/summary.md`](experiments/E20_final_rag_test/summary.md).

### Two populations, never merged into one number

| Population | Rule | FULL | RAG |
| --- | ---: | ---: | ---: |
| **2,091-case official TEST benchmark** (headline numbers above) | 59.0% acc / 50.1% joint | 77.6% acc / 74.6% joint | 76.8% acc / 72.5% joint |
| **49-case targeted evaluation** (E24 — golden + negative + evidence-quality battery, deliberately includes the hardest known case family) | 51.0% acc / 44.9% joint | 73.5% acc / 73.5% joint | 71.4% acc / 67.3% joint |

The targeted set is a regression check on cases this project already hand-curated to be hard, run
against the current architecture for the first time — not a second benchmark, and lower numbers
here don't revise the TEST result above. It surfaced findings the TEST-scale numbers can't: the
exception/carve-out weakness documented in ADR-011 persists today (3 of 4 known cases still
fail); one case (038) was traced to the exact clause FULL over-weighted and RAG's narrower
context avoided — direct evidence that full-document access isn't strictly safer than retrieval;
and RAG's two evidence-grounding failures (correct label, insufficient cited evidence) were
diagnosed down to exact gold-span coverage, not just scored pass/fail — both are retrieval
coverage gaps, not pure model errors. Full case-level detail:
[`experiments/E24_targeted_evaluation/summary.md`](experiments/E24_targeted_evaluation/summary.md).

### What's measured, what's not

NDATrace measures inference cost and model quality directly: RAG runs $0.00168/case, FULL
$0.00202/case (`experiments/E20_final_rag_test/results/E20_final_report.json`). End-to-end
reviewer time savings have not been measured in this project — no productivity study was run. No
sources are compared for this app, this is a modeled, explicit scenario, not a result.

Business impact is therefore modeled using a published contract-review-time benchmark and
explicit scenario assumptions, kept in three separate, clearly labeled categories:

| Category | What it is |
| --- | --- |
| **Measured by NDATrace** | Inference cost/case, input tokens, latency — all read from saved run artifacts. |
| **Externally sourced baseline** | LegalOn Technologies, *2025 State of Contracting Survey* (n=286, published 15 Jan 2025): 52% of organizations handle 101–1,000 contracts/year at 2–4 hours of review per contract. Vendor research (LegalOn sells AI contract review software) — not independently verified academic evidence. [Source](https://www.legalontech.com/press-releases/2025-survey), citation review: [`docs/citation_fixes.md`](docs/citation_fixes.md). |
| **Modeled / illustrative** | Assumed effort-reduction percentage, assumed hourly rate, resulting hours and labor-cost scenarios. Explicit assumptions, not fitted to any target. |

**Scenario example** (midpoint of the published 2–4 hour range → 3 hours/contract; 500
contracts/year; $40/hour — all stated assumptions, not measurements):

| Assumed effort reduction | Hours saved/year | Modeled labor savings/year |
| --- | ---: | ---: |
| 10% | 150 | $6,000 |
| 20% | 300 | $12,000 |
| 30% | 450 | $18,000 |

Formula, fully transparent: `annual_hours = contracts/year × baseline_hours/contract`;
`hours_saved = annual_hours × assumed_reduction_rate`; `labor_savings = hours_saved × assumed_hourly_rate`.
Reproduce or change the assumptions: `python scripts/business_economics_scenario.py`.

No productivity study was conducted. These numbers show potential economic scale under stated
assumptions, not a realized or proven ROI — treat the percentages as illustrative inputs, not
findings.

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

**Takeaway:** Rule → RAG → FULL is the real Pareto frontier; the local Qwen comparator is
strictly dominated (same $0 cost, lower Joint correctness).

Trade-offs made, explicitly:

- **Quality for cost/scale.** RAG was retained as the prototype runtime because it provides
  bounded context and lower measured inference cost, while accepting a measured 2.1-point
  Joint-correctness gap to FULL. Long-document scalability remains untested.
- **Simplicity over capability.** The agent and auto-routing were rejected after measuring them,
  not before. Both added real cost and earned nothing back on this data.
- **Operational simplicity over retrieval complexity.** BM25 plus a reranker tied dense/hybrid
  retrieval on quality, and BM25 needs no vector index to operate.

![Where RAG actually fails](docs/images/failure_pareto.png)

**Takeaway:** Retrieval was not the dominant failure source in E20 — only 10% of RAG's failures
are retrieval-limited; 78% are reasoning errors on evidence it already found. Full breakdown in
[`docs/failure_analysis.md`](docs/failure_analysis.md), with one real case walked through step
by step in [`examples/case_failure/`](examples/case_failure/).

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
<summary>Which 7 scripts step 3 runs</summary>

```bash
python experiments/E04B_majority_baseline/run_majority_baseline.py
python scripts/e17_analyze_final_test.py --metrics
python scripts/e17b_merge_and_analyze.py
python scripts/analyze_e20_rag_test.py
python scripts/analyze_e11_selective_agent.py
python scripts/analyze_e15_validation.py
python scripts/e18_business_analysis.py
```

Each one recomputes its experiment's metrics from saved predictions, zero model calls. Listed
here so this isn't a black box — see `scripts/verify_reproducibility.py`'s `ANALYSIS_SCRIPTS`.

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
| Dataset | [ContractNLI](https://stanfordnlp.github.io/contract-nli/) (Koreeda & Manning, EMNLP 2021 Findings), CC BY 4.0, a public benchmark — not confidential company contracts. 607 NDAs, 10,319 examples across the official train/dev/test roles; TEST (2,091 examples, 123 documents) is reserved for the one-time final evaluation. Download + checksum-verify: `bash scripts/download_data.sh`; files live in `data/contractnli/`. |
| Evals | An offline scoring harness that knows gold labels, kept separate from a runtime validator that never sees them. |
| Experiments | 24 numbered, frozen experiments (E00–E23), each with its question, finding, and decision. |

Gold labels and evidence are withheld from the model at inference time and scored only
afterward. The TEST split wasn't tuned against during this project's own development, though a
superseded earlier run did score it once; that's disclosed in
[`docs/data_contamination_register.md`](docs/data_contamination_register.md) and not described
as "blind."

### Evaluation cases checked into the repo

| Eval set | Cases | Purpose | File |
| --- | ---: | --- | --- |
| Golden / ordinary | 30 | Representative regression cases across Entailment, Contradiction and NotMentioned | `data/golden/golden_cases.json` |
| Negative / hard cases | 15 | Known difficult behaviours such as exceptions, conflicting clauses, misleading wording and long documents | `data/golden/negative_cases.json` |
| Prompt injection | 11 | Robustness against instruction override, role spoofing, output-format spoofing and related attacks | `data/golden/injection_cases.json` |
| LLM behaviour | 7 | Model-output and reasoning-behaviour checks | `data/golden/llm_behaviour_cases.json` |
| Agent behaviour | 7 | Selective-agent behaviour checks | `data/golden/agent_cases.json` |
| Confidence / abstention | 2 | Confidence and escalation-behaviour checks | `data/golden/confidence_cases.json` |
| Evidence quality | 4 | Evidence-quality and source-grounding checks | `data/golden/evidence_quality_cases.json` |

These checked-in cases are regression, robustness and behavioural evals used to catch known
failure modes during development; they are not treated as the project's unbiased headline
benchmark. Most are drawn from ContractNLI DEV, with some synthetic security cases. Final quality
numbers come from the official TEST evaluation under the documented final protocol (see
[Metrics](#metrics-targeted-vs-reached) above).

Pass/fail results for every row above are in
[`docs/test_coverage_summary.md`](docs/test_coverage_summary.md) — **measured against the legacy
pipeline (RAG + selective agent), not the current final architecture** (GPT-5-mini + FULL); that
distinction is called out in the summary itself and repeated here so it isn't lost in a link.

- Data explainer: [`data/README.md`](data/README.md)
- Eval-case design: [`docs/evaluation_case_design.md`](docs/evaluation_case_design.md)
- Eval harness explainer: [`evaluation/README.md`](evaluation/README.md)
- Final evaluation protocol: [`docs/evaluation_protocol.md`](docs/evaluation_protocol.md)
- Data/split contamination disclosure: [`docs/data_contamination_register.md`](docs/data_contamination_register.md)
- Experiment registry: [`docs/experiment_registry.md`](docs/experiment_registry.md)
- Failure analysis: [`docs/failure_analysis.md`](docs/failure_analysis.md)
- Worked examples (one real success, one real failure case): [`examples/case_success/`](examples/case_success/), [`examples/case_failure/`](examples/case_failure/)
- Architecture decisions: [`docs/architecture_decisions/INDEX.md`](docs/architecture_decisions/INDEX.md)

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

**Author note.** Built end to end by one author: the retrieval/reranking pipeline and its
chunking strategy, the evaluation harness and all 24 experiment scripts, the reviewer decision
API (`backend/routes/review.py`), the injection guard, and the reproducibility harness
(`scripts/verify_reproducibility.py`).
