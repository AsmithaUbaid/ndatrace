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

## Current status — final selected architecture (reconstruction-v2)

This project went through a full **reconstruction** (branch `reconstruction`, experiments E00–E18,
`docs/experiment_registry.md`) that reran the experimental program end to end under corrected
discipline (evaluator/validator hardening, a routing-independence fix, and a one-shot final TEST
evaluation) and is the authoritative, final result. The original pre-reconstruction pipeline
history below ("Experiment progression", "Key development findings") remains as documented record
of earlier work and is **not** the final architecture.

**Final selected architecture: `openai/gpt-5-mini` + the frozen `GPT-P0` prompt + FULL NDA context
+ structured JSON output + a runtime evidence-source validator.** No retrieval, no agent, and no
automated review-routing policy are part of the selected path — all three were built, measured, and
explicitly **not selected** (see below).

**Final held-out TEST result (n=2,091, all official TEST cases, one-shot):**

| System | Accuracy | Macro-F1 | Joint (label+evidence) | Contradiction recall | Cost |
|---|---|---|---|---|---|
| Rule baseline | 59.0% | 0.479 | 50.1% | 16.8% | $0 |
| Local Qwen (ctx16k) | 49.9% | 0.431 | 39.7% | 25.5% | $0 API (local compute not monetized) |
| **GPT-5-mini + P0 + FULL (final)** | **77.6%** | **0.727** | **74.6%** | **75.5%** | ≈$4.23 total |

Full detail: `experiments/E17_final_test/`, `experiments/E17B_full_test_completion/`,
`experiments/E18_business_course_synthesis/`.

- **Why RAG was not selected**: RAG cut input tokens substantially on longer NDAs (up to ~70% on
  the longest documents) but did not beat full context on the matched dev-sample architecture
  comparison (E13) — full context is the frozen candidate, RAG is a measured alternative kept for a
  long-document scalability scenario that was never validated.
- **Why the agent was not selected**: the tested selective agent (E09–E11) showed a small,
  statistically inconclusive net effect and added orchestration and cost without a demonstrated
  benefit; it is not part of the final path.
- **No selective-review/abstention policy was adopted** (E15): every deterministic routing policy
  tested either left a large share of failures silently unreviewed or required an unacceptable
  review workload. The runtime evidence validator remains as a structural source-integrity check
  only — it flags non-source-grounded evidence, not general uncertainty.
- **Main residual limitation: "Not Mentioned" over-inference.** NotMentioned recall is 62.7% on the
  final TEST result, and it is the largest single failure bucket (323 of 531 full-TEST joint
  failures) — the model too often infers a relationship the NDA doesn't actually address.
- **Prompt-injection limitation (E16, disclosed, not patched)**: the system is evidence-grounded but
  **not** prompt-injection-hardened. In a small controlled test (20 matched clean/attack pairs), 4
  of 11 injection-type attacks succeeded, including two cases where the model's answer flipped to
  match an instruction embedded in the NDA text. Evidence-source validation does not detect this —
  it confirms a quote came from the document, not that the document's content is trustworthy.

## Architecture

Synchronous modular monolith: Python AI pipeline (`pipeline/`) served by a FastAPI backend
(`backend/`) and a Next.js frontend (`frontend/`). The live product path is
`pipeline/final_review.py` → `POST /api/review` (see `backend/app.py`); the earlier RAG + selective
agent pipeline (`pipeline/orchestrator.py`) is kept only for `/history`'s previously-saved records
and is not the selected architecture. Full request-flow detail (including the superseded RAG+agent
path, documented for history): **`docs/architecture.md`**.

## Experiment progression (original pre-reconstruction pipeline — historical)

The material in this section and "Key development findings" below describes the **original**
pipeline history, before the reconstruction described in "Current status" above superseded it as
the final result. Kept as documented record, not as the current final claim.

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
  entirely an injected instruction, no real clause content) — fixed in the current prompt version,
  with higher overall accuracy than the prior default but one fewer correct Contradiction case
  (a real, disclosed trade-off, traced to a single specific misread case, not overall noise). See
  the prompt-version decision in `docs/decisions.md`.
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
| `pipeline/` | Production AI pipeline. `final_review.py` is the final selected path (GPT-5-mini + P0 + FULL + runtime validator); `orchestrator.py`/`agent.py`/retrieval modules are the superseded RAG+agent pipeline, kept for `/history` |
| `experiments/` | Reconstruction-v2 experiment record (E00–E18), including the final TEST evaluation (E17/E17B) and business/course synthesis (E18) — see `docs/experiment_registry.md` |
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
uvicorn backend.app:app --reload            # backend, http://localhost:8000
cd frontend && npm install && npm run dev   # frontend, http://localhost:3000
```

Open `http://localhost:3000`, paste or upload an NDA, pick or type a requirement, and click
"Review NDA". This calls `POST /api/review` — the final architecture described above — and makes a
real, billed OpenRouter call per review.

## Known limitations

- **"Not Mentioned" over-inference is the main residual weakness** (62.7% recall on the final TEST
  result; the largest single failure category). See "Current status" above.
- **The system is evidence-grounded but not prompt-injection-hardened** — see the E16 disclosure
  above; adversarial NDA content is a known, disclosed limitation, not fixed in this project.
- **No selective-review/abstention policy was adopted** — the runtime evidence validator is a
  structural source-integrity check only, not a general uncertainty detector.
- Exception/carve-out clause reconciliation is a known, disclosed weakness (originally found in the
  pre-reconstruction golden battery; see `docs/decisions.md`).
- Long-document scalability (the core argument for RAG over full-context) remains untested — RAG
  saved tokens on longer documents but was not shown to improve quality.
- This is a reviewer aid, not legal advice, and not an autonomous approval/rejection system — a
  human reviewer remains the final authority in every case.

## License

Academic project — NTU PE6201.
