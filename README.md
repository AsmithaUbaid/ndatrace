# NDATrace

Reviewing an NDA against a company's required confidentiality terms is manual, slow, and
inconsistent — a lawyer has to read the whole document and check it against each requirement one by
one. NDATrace evaluates whether that process can be reliably automated with evidence grounding:
given an NDA and a specific confidentiality requirement, it classifies whether the NDA
**Entails**, **Contradicts**, or does **Not Mention** that requirement, and shows the exact clause
it based that answer on — so a reviewer can verify the answer in seconds rather than re-reading the
document.

**Course:** NTU PE6201 Emerging AI Technologies — End-of-Course Project
**Dataset:** [ContractNLI](https://stanfordnlp.github.io/contract-nli/) — 607 NDAs, 17 standard
confidentiality hypotheses each, with gold labels and evidence spans.

## What the system does

```text
NDA + one of 17 standard confidentiality requirements
        |
Retrieve relevant clauses (sentence chunking -> embed -> rerank -> rule-boost)
        |
Classify: Entailment / Contradiction / Not Mentioned
        |
Return the cited evidence (verbatim, validated against the source text)
        |
If the routing signal flags the case as uncertain: selectively
investigate further with a bounded, tool-using agent before answering
```

See `docs/architecture.md` for the full, currently-implemented request flow (including a detail
worth knowing up front: the production path makes **two** classifier calls per requirement, not
one, to keep the routing decision independent of the retrieval it's judging — see the
routing-independence fix in `docs/decisions.md` for why).

## Current status (2026-09-25)

- **Architecture: frozen** (RAG + selective agent — see the final architecture-freeze decision in
  `docs/decisions.md`) — but frozen on
  repeatedly-reused development-sample evidence, not an independent validation run. See
  `docs/evaluation_protocol.md` for exactly what that means.
- **The official ContractNLI test-set evaluation (the final, locked benchmark run): completed**,
  but with two disclosed caveats — it used prompt v2, not
  the current v6 security-hardened default, and only one of the seven result files (hosted
  full-context, full 2,091-case set) has a fully verified evidence-correctness metric. See
  `docs/evaluation_protocol.md`'s "Current evaluation status" section for the exact per-file state.
- **A real, unresolved contradiction**: at full test-set scale, the selective agent's accuracy
  (77.7%) is now measured *below* plain RAG's (78.7%) on the hosted model — the opposite of the
  development-sample finding that justified including it. Not statistically significant either way
  (p=0.088), and the architecture freeze is not being retroactively reversed over it, but it is
  disclosed plainly rather than hidden — see the agent include/exclude decision in
  `docs/decisions.md` and `notebooks/07_selective_agent_experiments.ipynb`.
- **Long-document scalability is an untested design hypothesis**, not a validated result — see
  `docs/architecture.md`'s proposed (not yet run) stress test.

## Architecture

Synchronous modular monolith: Python AI pipeline (`pipeline/`) served by a FastAPI backend
(`backend/`) and a Next.js frontend (`frontend/`). Full current implementation, request flow, and
open concerns: **`docs/architecture.md`**.

## Experiment progression (development / experimentation)

```text
Data Validation
  -> Oracle / Full-Context ceiling
  -> Model Selection
  -> Retrieval Experiments
  -> RAG end-to-end
  -> Prompt Tuning (v1 -> v6)
  -> Confidence & Routing Analysis
  -> Selective-Agent Experiment
  -> Architecture Comparison
  -> Architecture Freeze
  -> Official ContractNLI Test-Set Evaluation (the final, locked benchmark run)
```

This was not a neat, planned-in-advance sequence — retrieval configuration and prompt version were
each revised multiple times in response to earlier results on the same dev sample. Full
chronological ledger: `docs/experiments.md`. Reasoning and status (ADOPTED/REJECTED/SUPERSEDED) per
decision: `docs/decisions.md`. Corresponding notebooks: `notebooks/` (see `notebooks/README.md`).

## Key development findings (verified repository values, positive and negative)

- Oracle (gold evidence given directly) reaches 95.3% accuracy — the model reasons well when
  evidence is unambiguous; the real bottleneck is retrieval, not model reasoning.
- **Full-context beats RAG and RAG+agent on raw accuracy** on both the dev sample (91.3% vs. 88.0%
  / 90.0%) and the full hosted test set (81.2% vs. 78.7% / 77.7%). It was excluded from production
  on a documented scalability *hypothesis* — see the full-context exclusion decision in
  `docs/decisions.md` — not because it underperformed on any data collected so far.
- **Cost, measured on the official test set (2,091 cases, real dollars spent)**: Full-context
  $0.000328/case, RAG $0.000152/case, RAG+agent $0.000405/case (RAG+agent costs ~2.7x plain RAG —
  two classifier calls for routing independence plus the agent's own calls on REVIEW-routed cases;
  full-context costs ~2.2x RAG per case despite skipping retrieval, since the whole document goes to
  the model every time). All three are cheap in absolute terms at this document length — cost alone
  did not drive the architecture decision away from full-context; the long-document scalability
  hypothesis did.
- Full-context's advantage is not universal: on local Llama 3.2 3B, full-context (49.2%) actually
  *underperforms* the zero-cost rule-based baseline (57.6%).
- The selective agent's dev-sample gain (88.0%→90.0%) was never statistically significant
  (McNemar p=0.51 on 67 cases), and the full 2,091-case hosted test-set result reverses the
  direction entirely (regression 87 vs. recovery 65, p=0.088) — see the contradiction noted above.
- Confidence/abstention: no signal tested cleared the 0.7 AUROC target (best: rule-agreement,
  0.657–0.660) — hard abstention was rejected in favor of ACCEPT/REVIEW routing. See the
  confidence/abstention design decision in `docs/decisions.md`.
- A real prompt-injection vulnerability was found live through the product UI (a document that was
  entirely an injected instruction, no real clause content) — fixed in the current prompt version
  at zero accuracy cost. See the prompt-version decision in `docs/decisions.md`.
- A real, systematic weakness was found in exception/carve-out clause reconciliation: 4/4 such
  cases in the negative-case battery failed. See the golden-battery finding in `docs/decisions.md`.
- A real bug silently broke the joint label+evidence correctness metric — headlined throughout this
  project as the key rubric metric — for the entire official test-set evaluation. Root-caused,
  fixed, and partially (not fully) retroactively corrected. See the joint-metric bug entry in
  `docs/decisions.md`.

## Evaluation discipline

Development, regression, robustness, architecture-validation, and final-test evidence are
**different categories that answer different questions** and should never be reported as one
number. Full definitions, dataset roles, and freeze protocol: **`docs/evaluation_protocol.md`**.
Case-category taxonomy (benchmark vs. regression vs. robustness vs. agent-behaviour vs.
system/API): **`docs/evaluation_case_design.md`**.

## Repository map

| Path | Purpose |
|---|---|
| `pipeline/` | Production AI pipeline (parser, chunker, embedder, retriever, classifier, confidence, agent, orchestrator) |
| `prompts/` | Versioned prompt templates — see `prompts/README.md` |
| `evaluation/` | Metrics, scoring, evaluation harness — reused by pipeline, scripts, and notebooks |
| `backend/` | FastAPI application — see `docs/api.md` |
| `frontend/` | Next.js application — see `frontend/README.md` |
| `notebooks/` | Development-stage experiment notebooks — see `notebooks/README.md` |
| `scripts/` | Standalone experiment/evaluation/utility scripts (the actual pattern used, not `experiments/configs/`) |
| `results/` | Append-only experiment results (`runs/*.jsonl`) and comparison charts |
| `data/` | ContractNLI dataset + golden/regression/robustness case files — see `data/README.md` |
| `tests/` | Unit, integration, and data-leakage-prevention tests |
| `docs/` | Architecture, decisions, evaluation protocol, API, experiment ledger, and archived planning material |

## Reproduction

Commands that work without any paid API calls:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash scripts/download_data.sh          # ContractNLI dataset
python scripts/verify_environment.py
python -m pytest tests/                # 230 tests, no network/API calls (mocked model calls)
```

To run the live product (requires an OpenRouter API key in `.env`, copied from `.env.example`):

```bash
uvicorn backend.app:app --reload        # backend, http://localhost:8000
cd frontend && npm install && npm run dev   # frontend, http://localhost:3000
```

## Known limitations

- No architecture-validation sample independent of the repeatedly-tuned dev sample exists
  (`docs/evaluation_protocol.md`).
- The routing signal that gates the selective agent is weak (AUROC 0.657–0.660).
- The selective agent's net benefit is unresolved at full test-set scale (see "Current status"
  above).
- Exception/carve-out clause reconciliation is a known, disclosed weakness (see the golden-battery
  finding in `docs/decisions.md`).
- Long-document scalability (the core argument for RAG over full-context) is untested.
- The joint label+evidence correctness metric for the official test-set run is fully corrected for
  only one of seven result files as of this writing (`docs/evaluation_protocol.md`).

## License

Academic project — NTU PE6201.
