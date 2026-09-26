# E03 Controlled Prompt Selection — PENDING (resequenced after E06)

## Status: PENDING, not COMPLETE — Stage B attempt SUPERSEDED / INVALIDATED BEFORE COMPLETION

**What happened**: Stage A (below) was approved and Stage B execution began — the P0 (minimal
direct) prompt started its full 150-case run against the full-context NDA text condition.
**88 of 150 cases completed** before the run was stopped cleanly (not killed mid-write; the
last saved record is valid JSON). **P1 and P2 never started.**

**Why**: the experimental design changed before any prompt-selection conclusion was drawn.
Full-context prompt comparison is a valid, real condition — it's architecture A1's actual
production input shape — but it does not establish that the winning prompt transfers to the
fragmented, noisier retrieved-chunk context that architectures A2/A3 (the intended RAG
pipeline) will actually feed the classifier. Because reconstruction-v2 has not yet frozen a
retrieval configuration (E06 hasn't run), continuing E03 now would either implicitly optimize
the prompt for A1 specifically, or require freezing an ad hoc, unvalidated retrieval config
just to get realistic context — exactly the risk Stage A's own context-condition reasoning
flagged as worth avoiding.

**Resequencing**: `E06 Retrieval Optimisation` → freeze retrieval → **return to E03 using
identical frozen retrieved context for every prompt** → `E07 Standard RAG`. E06 can be run
independently of any classification prompt, using purely deterministic retrieval metrics
(Evidence Recall@K, Precision@K, MRR, retrieval miss analysis) — no prompt is required to
select retrieval.

**Preserved, not deleted**: `results/run_E03_prompt_selection_p00.jsonl` (88 real records) and
`results/SUPERSEDED_run_E03_prompt_selection_p00.md` (the supersession record). **No
classification metric was computed from the partial P0 run, and none was used for any
prompt-selection decision.**

**Retained for reuse once E03 resumes**:
- `TRAIN_PROMPT_v1.json` — the manifest (150 cases, 50/50/50, seed=500) — its case selection
  may be reusable once the context condition changes to frozen retrieved context, subject to
  review at that time (the manifest's `context_text` field, currently full NDA text, would
  need to be replaced with retrieved context per case — not done here).
- `configs/prompts/classification/classification_p0{0,1,2}.yaml` (P0/P1/P2) — retained as
  proposed candidates; their content is unaffected, only the *context* they'll be tested
  against changes once E06 freezes retrieval.

---

## Original Stage A Proposal (design/freeze) — preserved below, superseded by the above

**No inference had been performed as of this section.** Model, manifest, context condition,
prompt ladder, schema, and decision rule were proposed below and approved — Stage B then began
and was stopped for the resequencing reason above, before completion.

## 1–5. TRAIN_PROMPT_v1 manifest

Built by `scripts/build_train_prompt_manifest.py` (local-only, zero model calls) — already
run, output at `experiments/E03_prompt_selection/TRAIN_PROMPT_v1.json`.

**Sampling plan**: identical algorithm to E01's `TRAIN_ORACLE_v1` (document-diverse,
class-balanced, capped at 2 cases/document/class), scaled to 50/class instead of 100/class.
**Seed 500** — distinct from every other project seed (42 historical dev sample, 99 AV01, 123
PVAL01, 300 TRAIN_ORACLE_v1).

| Class | Cases | Unique documents |
|---|---|---|
| Entailment | 50 | 25 |
| Contradiction | 50 | 29 |
| NotMentioned | 50 | 25 |
| **Total** | **150** | **73** |

Case IDs use the frozen reconstruction-v2 scheme, `f"train::{document_id}::{hypothesis_id}"`.
Source: official TRAIN only — no DEV, no TEST, no historical dev sample, no AV01/PVAL01 reuse.

**Overlap with `TRAIN_ORACLE_v1` (E01), checked for transparency, not avoided**: 17 of 150
cases (and 29 of 73 documents) also appear in Oracle's manifest — expected, since both are
random draws from the same 423-document TRAIN pool, and not a problem: Oracle tests
perfect-evidence reasoning while E03 tests full-context prompt behavior — genuinely different
conditions, not a train/validation split where reuse would leak information.

## 6. Controlled context condition — decided, not left ambiguous

**Chosen: full-context NDA text** (option A from the reconstruction brief), not retrieved
context (option B).

**Reasoning**: option B would require freezing *some* retrieval configuration before comparing
prompts. But reconstruction-v2 has not frozen a retrieval config yet — E06 (retrieval
optimisation) hasn't run. Using it would mean either (a) reusing the **historical** T-series
retrieval config, which `docs/evaluation_protocol.md` explicitly treats as evidence only, not
a binding reconstruction-v2 decision, or (b) picking a retrieval config ad hoc just for E03,
which would itself be an unscrutinized retrieval decision smuggled into what's supposed to be
a pure prompt comparison — exactly what section 5 warns against ("do not mix prompt selection
with retrieval quality"). Full-context requires zero retrieval decisions, is deterministic and
trivially reproducible, and cleanly isolates the prompt as the only variable. This is not
treated as ambiguous enough to halt Stage A over — the case for full-context is not a coin
flip, it's the only option that doesn't presuppose a retrieval decision reconstruction-v2
hasn't made yet.

**Verified feasible**: TRAIN document length (cl100k-approx tokens): mean 2,118, median 1,905,
p90 3,899, max 11,340 — comfortably within qwen2.5:7b-instruct's 32K context window even at
the maximum.

This is explicitly **not** Oracle (real full document, not curated gold evidence) and **not**
RAG (no retrieval step at all) — a third, distinct condition that isolates prompt effects from
both perfect-evidence reasoning and retrieval quality.

## 7–11. Prompt ladder — P0, P1, P2 (exact text); P3 disposition

All three share the same user template and output schema; **only the system prompt changes**.

**P0 — Minimal Direct** (`configs/prompts/classification/classification_p00.yaml`, 84 tokens):
```
You are given an NDA requirement and the full text of the NDA.

Classify the requirement against the NDA text as exactly one of:
- "Entailment"
- "Contradiction"
- "NotMentioned"

Respond with ONLY a JSON object with this exact field:
{
  "label": "Entailment" | "Contradiction" | "NotMentioned"
}
```

**P1 — Explicit Label Definitions** (`classification_p01.yaml`, 124 tokens, +40 vs P0):
```
You are given an NDA requirement and the full text of the NDA.

Classify the requirement against the NDA text as exactly one of:
- "Entailment": the NDA text states or clearly implies that the requirement is met.
- "Contradiction": the NDA text states or clearly implies terms incompatible with the requirement.
- "NotMentioned": the NDA text does not address this requirement at all.

Respond with ONLY a JSON object with this exact field:
{
  "label": "Entailment" | "Contradiction" | "NotMentioned"
}
```

**P2 — Structured Decision Procedure** (`classification_p02.yaml`, 197 tokens, +73 vs P1, +113
vs P0):
```
You are given an NDA requirement and the full text of the NDA.

Classify the requirement against the NDA text as exactly one of:
- "Entailment": the NDA text states or clearly implies that the requirement is met.
- "Contradiction": the NDA text states or clearly implies terms incompatible with the requirement.
- "NotMentioned": the NDA text does not address this requirement at all.

Follow this procedure:
1. Determine whether the NDA text addresses the requirement.
2. If it clearly supports the requirement, output Entailment.
3. If it clearly establishes incompatible terms, output Contradiction.
4. If neither is established, output NotMentioned.
5. Do not infer facts that are not stated in the NDA text.

Respond with ONLY a JSON object with this exact field:
{
  "label": "Entailment" | "Contradiction" | "NotMentioned"
}
```

No chain-of-thought, hidden reasoning, or verbose explanation requested at any rung — P2 asks
for a structured decision *procedure*, not explanation generation, per the brief's explicit
instruction.

**P3 — Few-shot: NOT RUN / NOT JUSTIFIED at this stage.** No P0-P2 results exist yet to
identify a concrete recurring confusion for a few-shot example to target, and manufacturing a
speculative few-shot example before seeing failures would violate the "don't stack every
prompting trick together" instruction. If P0-P2 results show a specific, recurring,
few-shot-addressable failure pattern, P3 will be proposed *then*, with the failure it targets,
why P2 alone doesn't solve it, and its added token cost — not before.

## 12. Exact output schema

```json
{"label": "Entailment" | "Contradiction" | "NotMentioned"}
```

Identical across all three (four, if P3 is later justified) prompt versions — no explanation,
no confidence field. This isolates the prompt-instruction effect from output-verbosity effects
and controls token cost, per the frozen design rule.

## 13. Estimated input-token overhead per prompt

Real, measured from `TRAIN_PROMPT_v1`'s actual context text (not assumed): mean context 2,191
tokens, mean hypothesis 14.0 tokens (cl100k_base approximation, consistent with E00B's
methodology).

| Prompt | System prompt tokens | Estimated total input tokens/case (mean) |
|---|---|---|
| P0 | 84 | ~2,309 |
| P1 | 124 (+40) | ~2,349 (+40) |
| P2 | 197 (+113 vs P0) | ~2,422 (+113 vs P0) |

The definitions/procedure overhead is small relative to the dominant cost (the full NDA text
itself) — under 5% of total input tokens even at P2. Any accuracy gain from P1/P2 is unlikely
to be offset by token cost; this will be checked explicitly in the regression table per the
frozen selection rule (token overhead is criterion #6, after Contradiction Recall/Macro-F1/
parse validity/regressions).

## 14. Estimated runtime

**Extrapolated from E01's real qwen2.5:7b-instruct measurement, not independently measured for
this input size — flagged as an estimate, not a fact.** E01: mean 270.3 input + 11.3 output
tokens → 960.3ms mean latency, implying a rough combined throughput of ~293 tokens/sec.
E03's inputs are ~8-9x larger (mean ~2,300-2,420 total tokens). Applying that same rough
throughput: **~8-8.3 seconds/case**, i.e. **~20-21 minutes per prompt version for the full
150-case manifest, ~60-63 minutes for P0+P1+P2 combined.**

This is a single-point linear extrapolation (E01's one real measurement), not a validated
scaling law — local inference prefill/decode dynamics aren't guaranteed to scale linearly with
input length. **Recommend a smoke test at the start of Stage B** (as done for E01) to calibrate
before committing to the full 3-prompt run — the same practice that revealed a real
cost-tracking infra issue during E01's smoke test.

## 17. Files created

- `experiments/E03_prompt_selection/{README.md, config.yaml, summary.md, TRAIN_PROMPT_v1.json}`.
- `scripts/build_train_prompt_manifest.py` — manifest generator (already run).
- `scripts/run_e03_prompt_selection.py` — the real Stage B runner (written, syntax-checked,
  **not executed**). Reuses `evaluation.oracle.parse_oracle_output`/`build_result_record`
  rather than duplicating them.
- `evaluation/prompt_selection.py` — reusable message-construction + prompt-config loader.
- `configs/prompts/classification/classification_p0{0,1,2}.yaml` — the frozen prompt ladder,
  in the reconstruction-v2 versioned-prompt convention (`docs/experiment_protocol.md`).
- `tests/test_prompt_selection.py` — 5 unit tests (message never leaks `gold_label`, configs
  load correctly, p01/p02 contain the expected content, token-overhead ordering is monotonic).

**Not created yet (deferred to Stage B)**: `E03_prompt_selection.ipynb`, `results/*.jsonl`.

## 18. Unresolved decisions

1. **Runtime is an extrapolation from one E01 data point**, not measured for this input size —
   smoke test recommended before the full run.
2. **P3's fate is explicitly undetermined** — will only be proposed if P0-P2 reveal a concrete,
   few-shot-addressable failure pattern, per the brief's own instruction not to run it
   automatically.
3. No budget gate applies (E03 is local-only, $0 cost) — noted for completeness, not an open
   question.

---

**Waiting for explicit approval before Stage B.** No Qwen call, no hosted API call, no DEV/TEST
access, no retrieval tuning, no embeddings created, no inference — everything above is either a
local-only computation (manifest, token counts) or a frozen proposal awaiting approval.
