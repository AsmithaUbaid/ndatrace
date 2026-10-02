# NDATrace — Product Documentation

One-page reference: who this is for, what goes in and out, how input becomes output, and what
was targeted versus reached. Full detail, reproducibility steps, and the complete evaluation
story live in [`README.md`](README.md); this file exists so the persona/input/output/architecture
/metrics are each findable in one place without reading the whole README.

## Persona

**Tina, a legal operations analyst, not a lawyer.** She gets a vendor NDA and has to check it
against her company's standard confidentiality checklist before a lawyer looks at it. Relevant
wording is often paraphrased, qualified by an exception, or scattered across clauses — keyword
search misses that, and an unsupported LLM answer gives her nothing to check it against. Today
she reads the whole NDA clause by clause. With NDATrace she gets a verdict per requirement, each
with its supporting clause, reviews the flagged or uncertain ones first, and records her
decision. She is never asked to trust the system; she is shown what it is based on.

## Input / Output

| | |
| --- | --- |
| **Input** | One NDA (pasted or uploaded as PDF), checked against one or more of 17 fixed confidentiality requirements (ContractNLI's hypothesis set) |
| **Output** | One verdict per requirement checked: label (Entailment / Contradiction / Not Mentioned), the exact cited clause (verbatim, never paraphrased), a short explanation, and any review/security flags |

Each requirement is scored independently — one model call per requirement, nothing about
Requirement 1's evidence or verdict influences Requirement 2's — so partial selections (just the
3 that matter for a given deal) work the same way a full 17-requirement run does. The reviewer's
final Approve/Override/Reject decision is persisted and auditable; the model never auto-approves.

## High-level architecture

The current interactive prototype is RAG. FULL is retained as the quality-reference comparator;
the existing Rule-based system remains the non-AI baseline. The baseline definition and its
reported results are unchanged.

```mermaid
flowchart TD
    IN(["NDA + Requirement"])

    subgraph RETRIEVAL["① RAG retrieval (deterministic code)"]
        direction LR
        CHUNK["Clause-aware chunking<br/><i>256-token target</i>"]
        BM25["BM25 retrieval<br/><i>top-20 candidates</i>"]
        RERANK["Cross-encoder rerank<br/><i>top-5 context</i>"]
        CHUNK --> BM25 --> RERANK
    end

    GUARD["Request limits +<br/>injection guard"]
    LLM["② GPT-5-mini + frozen P0<br/><i>temperature 0 · RAG prototype</i>"]

    subgraph VALIDATE["③ Validation & safety (deterministic code)"]
        direction LR
        PARSE["Structured parser"]
        EVID["Runtime evidence-source validator v2<br/><i>verbatim source check</i>"]
        PARSE --> EVID
    end

    subgraph HUMAN["④ Human review"]
        direction LR
        REVIEWER["Reviewer sees<br/><i>verdict + evidence + flags</i>"]
        DECISION(["Human final decision<br/><b>Approve / Override / Reject</b>"])
        REVIEWER --> DECISION
    end

    IN --> GUARD --> RETRIEVAL --> LLM --> VALIDATE --> HUMAN

    classDef input fill:#f8fafc,stroke:#475569,stroke-width:1.5px,color:#1e293b;
    classDef stage fill:#eff6ff,stroke:#3b82f6,stroke-width:1px,color:#1e3a5f;
    classDef model fill:#fff7ed,stroke:#f97316,stroke-width:1.5px,color:#7c2d12;
    classDef control fill:#f0fdf4,stroke:#22c55e,stroke-width:1px,color:#14532d;
    classDef human fill:#fdf4ff,stroke:#c084fc,stroke-width:1.5px,color:#581c87;

    class IN input;
    class CHUNK,BM25,RERANK,GUARD stage;
    class LLM model;
    class PARSE,EVID control;
    class REVIEWER,DECISION human;

    style RETRIEVAL fill:#f8fafc,stroke:#3b82f6,stroke-width:1px
    style VALIDATE fill:#f0fdf4,stroke:#22c55e,stroke-width:1px
    style HUMAN fill:#fdf4ff,stroke:#c084fc,stroke-width:1px
```

Orange is the hosted model call. Blue and green are deterministic, project-owned code. Purple is
the human in the loop: no general automatic uncertainty gate was adopted, so every result is
reviewed by a person. The runtime source check verifies that cited text occurs in the submitted
NDA; it does not prove that the classification is semantically correct. See
`pipeline/final_review.py` and `docs/architecture.md`.

## Metrics: targeted vs. reached

| | Metric | Target | Reached (measured) | Status |
| --- | --- | --- | --- | --- |
| Primary | Joint correctness (label + evidence), FULL vs. RAG | Required to be measured and disclosed | 74.6% (FULL) / 72.5% (RAG), n=2,091 | Reported as measured |
| Secondary | Risk-sensitive recall gain, RAG over **Rule-based (non-AI baseline)** | ≥ 5.0 points | **+16.6 points** (53.6% → 70.3%) | Met, by a wide margin |
| Secondary | Risk-sensitive recall, RAG vs. **FULL quality-reference comparator** | Comparative result, reported separately | **+1.2 points** (69.1% → 70.3%) | Measured comparison; FULL is not the non-AI baseline |
| Secondary | Contradiction recall, reported separately (not averaged away) | Required, not fixed | 75.5% (FULL) / 77.3% (RAG) | Reported separately |

Official ContractNLI TEST split, n = 2,091, all three systems (Rule / FULL / RAG) on the
identical population. RAG is the current prototype; FULL is the quality-reference comparator;
Rule-based keyword retrieval remains the project's non-AI baseline (Problem Statement Section 4)
and the comparison point for the risk-sensitive recall success criterion. The measured FULL
comparison is reported separately as quality-reference context, not substituted for the baseline.
Source:
`experiments/E20_final_rag_test/results/E20_final_report.json`,
`results/final/v2/full_test_comparison.csv`.

Full targeted-vs-reached discussion, the two-population distinction (TEST n=2,091 vs. the
49-case targeted battery), and business-economics modeling: see
[`README.md#metrics-targeted-vs-reached`](README.md#metrics-targeted-vs-reached) and the
[authoritative final submission report](NDATrace_Final_Report.pdf).
