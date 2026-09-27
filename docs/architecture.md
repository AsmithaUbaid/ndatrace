# NDATrace Architecture

This describes the **final, currently-selected** architecture (reconstruction-v2, frozen in E19),
verified directly against `pipeline/final_review.py` and `backend/routes/review.py` —
`POST /api/review` is the sole review endpoint the backend serves. For the superseded RAG +
selective-agent architecture (removed from the active product; preserved in
`archive/pre_reconstruction/pipeline/` for historical reproduction), see
`docs/archive/architecture_pre_reconstruction.md`. For the full reasoning and every rejected
alternative, see `docs/decisions.md`.

## 1. Request flow (`POST /api/review`, `backend/routes/review.py`)

```text
NDA + requirement
        |
input validation
        |
openai/gpt-5-mini + GPT-P0 prompt + FULL NDA context   [pipeline/final_review.py]
        |
structured output parser   [evaluation/structured_output.py]
        |
runtime evidence-source validator v2   [pipeline/evidence_validator.py]
        |
reviewer-facing result   { label, evidence, explanation, source_valid, needs_human_review }
        |
human final decision
```

No retrieval and no agent sit in this path — the full NDA text is sent to the model directly. The
GPT-P0 prompt requests only `{label, evidence}`; there is no model-reported confidence, so none is
fabricated by the frontend or backend. The evidence validator checks only that the cited evidence
is a genuine verbatim quote from the submitted NDA text — it is a source-integrity check, not a
correctness or uncertainty signal.

## 2. Why this architecture was selected

- **Full-context is the selected prototype architecture.** On the full 2,091-case official
  ContractNLI TEST set, GPT-5-mini + P0 + FULL scored accuracy 77.6%, macro-F1 0.727, joint
  label+evidence correctness 74.6%, Contradiction recall 75.5% (n=2,091; see `docs/decisions.md`
  ADR entries for E17/E17B).
- **RAG was evaluated but not selected as the primary path.** Retrieval reduced input tokens
  substantially on longer documents but did not demonstrate a quality advantage over full context
  on the matched architecture comparison; it remains a measured alternative, not the shipped path.
- **The selective agent was evaluated but did not demonstrate useful tool-use benefit and was not
  selected.** Net effect was small and statistically inconclusive across every sample tested.
- **E15 did not establish a sufficiently effective general selective-routing policy.** Every
  routing signal tested either left a large share of failures unreviewed or required an
  unacceptable review workload; no ACCEPT/REVIEW or ACCEPT/ABSTAIN policy is active in this path.
- **The human reviewer remains the final authority.** This system produces a checkable label plus
  cited evidence for a reviewer to confirm or overrule — it does not auto-approve or auto-reject
  an NDA.
- **The system is evidence-grounded but not prompt-injection-hardened.** The evidence validator
  confirms a quoted string came from the source document; it does not confirm the document's
  content is trustworthy. A disclosed, unpatched injection limitation is recorded in
  `docs/decisions.md`.

## 3. Final held-out TEST metrics (n=2,091, one-shot, official TEST split)

| System | Accuracy | Macro-F1 | Joint (label+evidence) | Contradiction recall |
|---|---:|---:|---:|---:|
| **GPT-5-mini + P0 + FULL (selected)** | **77.6%** | **0.727** | **74.6%** | **75.5%** |

Full breakdown, comparators (rule baseline, local Qwen), and provenance: `results/final/README.md`,
`docs/experiment_registry.md` (E17/E17B), `docs/decisions.md`.

## 4. Legacy path (removed from the active product)

The earlier RAG + selective-agent pipeline (`archive/pre_reconstruction/pipeline/orchestrator.py`)
and its endpoints (`POST /review`, `GET /review/{review_id}`, `GET /results`,
`GET /cost-estimate`) were removed from the active backend and frontend during final submission
cleanup — there is no `/history` feature in the current product. The legacy pipeline code, its
tests, and the SQLite persistence layer it used are preserved under `archive/pre_reconstruction/`
for historical reproduction only; see `docs/archive/architecture_pre_reconstruction.md`.
