# E01 Oracle — Result (Stage B complete)

**Status: COMPLETE.** All four frozen models ran the full 300-case `TRAIN_ORACLE_v1` manifest
end to end. Stage A's proposal (below, preserved unmodified as the frozen record) was executed
exactly as approved — no model, prompt, manifest, or schema changes during execution.

## Stage B summary

| Model | Macro-F1 | Balanced diagnostic accuracy | Entailment recall | Contradiction recall (95% CI) | NotMentioned recall | Parse-valid | Mean latency | Cost |
|---|---|---|---|---|---|---|---|---|
| `llama3.2:3b` | 0.601 | 60.3% | 68.7% | 25.0% [17.4%, 34.5%] | 100.0% | 94.7% (284/300) | 415ms | $0 |
| `qwen2.5:7b-instruct` | 0.638 | 66.0% | 68.0% | 30.0% [21.9%, 39.6%] | 100.0% | 100% | 960ms | $0 |
| `google/gemini-2.5-flash-lite` | 0.867 | 86.7% | 89.0% | 71.0% [61.5%, 79.0%] | 100.0% | 100% | 696ms | $0.0091 |
| `openai/gpt-5-mini` | 0.906 | 90.7% | 90.0% | 82.0% [73.3%, 88.3%] | 100.0% | 100% | 3078ms | $0.1087 |

**Reported as "balanced Oracle diagnostic accuracy"** per the frozen reporting rule — this
sample is 100/100/100 by construction, not the natural TRAIN distribution (49.1% Entailment /
11.7% Contradiction / 39.2% NotMentioned), so these numbers are never comparable to
natural-distribution benchmark accuracy.

**Total reconstruction-v2 hosted spend after E01: $0.1178** — well under the $0.3348
pre-run projection (real Gemini cost came in at $0.0091 vs. a $0.0250 projection; real
GPT-5-mini cost came in at $0.1087 vs. a $0.3098 projection). $3.63 of the $3.75 allowed
budget remains untouched; the $1.25 reserve was never approached.

**Selected primary local model — FROZEN: `qwen2.5:7b-instruct`.** Higher Macro-F1 (0.638 vs
0.601), higher Contradiction Recall (30% vs 25%), and — the deciding factor beyond raw scores —
**100% schema-parse-valid vs. llama's 94.7%** (16/300 malformed responses, all a bare quoted
string like `"NotMentioned"` instead of a JSON object). Latency is higher in absolute terms
(960ms vs 415ms mean) but still fast; not selected by accuracy alone, selected because it wins
on every criterion in the decision list (Macro-F1, Contradiction Recall, schema validity) while
losing only on latency, which is not binding at this scale.

**Hosted reference — REVISED: `openai/gpt-5-mini`** (supersedes the original provisional
nomination of Gemini). Rationale: the hosted reference for later controlled hosted-vs-local
comparison (E15) should represent the *stronger* hosted reasoning ceiling, not the cheapest
hosted inference — GPT-5-mini has materially higher Macro-F1 (0.906 vs 0.867) and, especially,
higher Contradiction Recall (82% vs 71%, non-overlapping-ish 95% CIs: [73.3%,88.3%] vs
[61.5%,79.0%]). Its absolute cost ($0.1087/300 cases) remains small relative to the $3.75
allowed budget, so the cost premium over Gemini isn't a binding constraint at this scale.

**`google/gemini-2.5-flash-lite` is preserved as the "economical hosted candidate"** — its E01
result is not discarded, just re-labeled. Documented trade-off, both directions on record: Gemini
is substantially cheaper (12x) and faster (4.4x mean latency) than GPT-5-mini; GPT-5-mini has
materially higher Macro-F1 and Contradiction Recall. Both facts stand together, not one
overriding the other.

**Oracle conclusion (revised wording)**:

> Entailment reasoning appears relatively strong under Oracle conditions. NotMentioned is
> structurally advantaged by the empty evidence representation and is not directly comparable
> as a reasoning-ceiling measure. Contradiction is the clearest reasoning bottleneck.

Detail behind that conclusion: Entailment recall is 68-90% across all four models given perfect
evidence. NotMentioned is 100% across all four models, but this is **not** read as "NotMentioned
reasoning is strong" — `Evidence: []` is itself a distinguishing structural signal every model
can learn to exploit without engaging with the requirement's substance, so NotMentioned recall
is excluded from claims about reasoning quality. **Contradiction is the clearest, most directly
comparable reasoning bottleneck**: even with perfect gold evidence, local models reach only
25-30% Contradiction Recall, and even the strongest hosted model (GPT-5-mini) tops out at 82%.
13/100 Contradiction cases were missed by all four models — qualitative inspection shows a
recurring pattern of cases requiring an *implicit* contradiction (e.g. a definitions clause
listing categories "including but not limited to" implicitly negating a requirement that
everything be "expressly identified"), not an explicit negation — matching the historical
T-series finding (ADR-011) that exception/carve-out reconciliation is a genuine, persistent
weakness, now confirmed directly under Oracle conditions (perfect evidence), not just under RAG.
**Any future RAG/full-context Contradiction Recall gap must not be automatically attributed to
retrieval** — a substantial share of it is a reasoning ceiling problem that exists before
retrieval is even in the picture.

**NotMentioned's 100% recall across all four models must be read with the documented
structural-ease caveat**: `Evidence: []` is itself a distinguishing signal every model can
learn to exploit, separate from actually reasoning about the requirement's substance — this
is not evidence that NotMentioned reasoning is perfect, only that Oracle (by construction)
cannot distinguish "reasoned correctly" from "noticed the evidence list was empty" for this
label. Interpreted separately from Entailment/Contradiction throughout, as required.

## E02 disposition — FINAL

**E02 (Model Screening): SKIPPED / SATISFIED BY E01.**

Rationale: E01 already performed a controlled comparison of 2 local and 2 hosted models using
the same Oracle manifest, prompt semantics, and output schema. A separate model-screening
experiment would duplicate the question already answered.

**Frozen from E01:**
- Primary local model: **`qwen2.5:7b-instruct`**
- Hosted model for later comparison: **`openai/gpt-5-mini`**

`google/gemini-2.5-flash-lite` is preserved only as an economical hosted candidate/result from
E01 — it is **not** carried into core downstream experiments unless a later cost-quality
experiment explicitly requires it.

## Failure analysis

- **llama3.2:3b**: Contradiction errors split roughly evenly between mistaken-as-Entailment
  (41/96 scored cases) and mistaken-as-NotMentioned (31/96) — the weakest model can't reliably
  tell which direction a Contradiction should resolve. 16/300 schema-parse failures, all a bare
  quoted label string instead of a JSON object (`'```\n"NotMentioned"\n```'`) — a real,
  disclosed schema-reliability weakness for this model, not silently repaired (no deterministic
  repair policy was frozen before the run, so these correctly count as parse failures).
- **qwen2.5:7b-instruct**: Contradiction errors dominated by mistaken-as-NotMentioned (64/100)
  — a "default to safe/absent" failure mode, not a directionality confusion like llama's.
  Entailment errors also skew toward NotMentioned (28/100).
- **google/gemini-2.5-flash-lite**: Contradiction errors dominated by mistaken-as-NotMentioned
  (27/100) — same "default to absent" pattern as qwen, at a lower rate.
- **openai/gpt-5-mini**: Contradiction errors skew toward mistaken-as-Entailment (13/100), a
  different pattern from the other three models — even the strongest model sometimes reads a
  genuine contradiction as if it satisfied the requirement, rather than defaulting to "absent."
- **Infrastructure failures**: zero, across all 300×4 = 1,200 calls (confirmed via full run
  logs — no "retrying"/transient-failure events at all).
- Full confusion matrices and 3 worked qualitative examples: `E01_oracle_analysis.ipynb`
  sections 6 and 8.

## Schema gap — closed, records backfilled

`evaluation/oracle.py::build_result_record()` initially lacked a dedicated `retry_count` /
`error_type` / `error_message` field split (the runner was written before the approval message
asking for them arrived, and only had a single `error` string). **Closed, not left open**:

- `evaluation/oracle.py::build_result_record()` now takes `retry_count` (default `0`),
  `error_type`, and `error_message` (both default `None`); `error_type` distinguishes
  `MODEL_ERROR` (provider/local runtime failure) from `PARSE_ERROR` (schema violation), per the
  failure-policy split.
- `scripts/run_e01_oracle.py` populates these for all future runs (`response.num_retries`;
  `"PARSE_ERROR"` when `parse_valid` is false; `"MODEL_ERROR"` on a caught `ModelError`).
- **All 4 already-saved E01 result files (1,200 records) were backfilled deterministically**
  with `retry_count: 0, error_type: null, error_message: null` — verified against the real
  execution logs (grepped all 4 full-run output logs for retry/error events: zero found across
  1,200 calls; every `error` field in the saved records is already `null`), not guessed. No
  prediction or metric field was touched by the backfill — re-running
  `scripts/analyze_e01_oracle.py` after the backfill produced byte-identical Macro-F1/recall/
  confusion-matrix numbers to before it.

---

# Stage A Proposal (pre-run freeze) — preserved unmodified below

**No inference had been performed as of this section.** Every item below is either a
local-only computation (manifest, budget gate) or the approved proposal (models, prompt,
schema) — preserved as the frozen record of what Stage B executed against.

## 1–4. Proposed models and their distinct roles

| Role | Provider | Model | Why this role |
|---|---|---|---|
| **Local Model 1** | local (Ollama) | `llama3.2:3b` | Smaller/local reasoning baseline. Already used throughout the historical T-series work (hosted-vs-local comparison, C02) — a known quantity, already installed. |
| **Local Model 2** | local (Ollama) | `qwen2.5:7b-instruct` | Stronger/local reasoning point — roughly 2.5x the parameter count of Local 1, a genuinely different capability class, still practical on this machine (~4.7GB download, ~5.5GB working memory). Chosen over a same-size alternative (e.g. another ~3B model) because the experimental question is whether a real local capability jump changes the reasoning ceiling, not just architecture variety at the same size. |
| **Hosted Model 1** | OpenRouter | `google/gemini-2.5-flash-lite` | Economical hosted reasoning — cheapest verified hosted candidate (E00B: $0.10/$0.40 per M tokens), already used throughout the T-series, real historical Oracle data exists for direct comparison. |
| **Hosted Model 2** | OpenRouter | `openai/gpt-5-mini` | Stronger/pricier hosted reasoning — a genuinely different vendor/architecture at ~2.5-20x Gemini's per-token price (E00B), tests whether hosted spend buys real reasoning improvement over the economical option. |

**Groq's free-tier `gpt-oss-20b` was considered and set aside for Oracle specifically**: it's a
real, distinct hosted capability point at $0, but its free-tier daily token limit (200,000
TPD, E00B) is tighter than a single 300-case Oracle pass would need just for input
(~678 tokens/case x 300 ≈ 203,400 input tokens alone, before any output) — a same-day 300-case
run would not reliably fit the free tier. Using it would mean falling back to its paid rate
($0.075/$0.30 per M, E00B correction), at which point it no longer offers a distinctive
"$0 hosted" role beyond what's already covered. Not chosen as one of the two hosted slots for
this reason — not a "best score wins" judgment, a real rate-limit constraint.

## 6. Already locally installed / accessible

- `ollama list` → **only `llama3.2:3b` (2.0GB) is installed.** `qwen2.5:7b-instruct` is
  **not** installed — would need `ollama pull qwen2.5:7b-instruct` (~4.7GB) in Stage B, not
  done here.
- `OPENROUTER_API_KEY` and `GROQ_API_KEY` are both configured in `.env` (verified present,
  non-empty — values not read/printed).
- Disk: 725GB available — no constraint on pulling `qwen2.5:7b-instruct`.

## 7–10. TRAIN_ORACLE_v1 manifest

Built by `scripts/build_train_oracle_manifest.py` (local-only, zero model calls) — already
run, output at `experiments/E01_oracle/TRAIN_ORACLE_v1.json`.

**Sampling algorithm**: for each of the three classes, group official TRAIN cases by document,
sort documents by ID (for reproducibility) then shuffle with `random.Random(seed=300)`, take
up to 2 cases per document (deterministic hypothesis-ID order within a document) walking the
shuffled document order until 100 cases are selected for that class. Final manifest ordering
is sorted by `(class, document_id, hypothesis_id)`, independent of shuffle iteration order —
byte-for-byte reproducible. Seed **300**, deliberately distinct from every other project seed
(42 = historical dev sample, 99 = AV01, 123 = PVAL01).

**Why document-diverse sampling worked cleanly here, unlike a naive concern going in**:
checked the real per-document case-count distribution before designing the cap — Contradiction
(the minority class) already spans 392 of TRAIN's 423 documents (max 5 Contradiction cases
from any single document), so a document-level cap of 2 cases/class/document comfortably
avoids concentration without needing an unusual number of documents.

| Class | Cases | Unique documents |
|---|---|---|
| Entailment | 100 | 51 |
| Contradiction | 100 | 58 |
| NotMentioned | 100 | 51 |
| **Total** | **300** | **145** (some documents contribute to more than one class) |

No pathological concentration: no class relies on fewer than 51 distinct documents, and no
single document contributes more than 2 cases to any one class.

**This is an intentionally balanced diagnostic sample, not the natural TRAIN distribution**
(natural TRAIN: 49.1% Entailment / 11.7% Contradiction / 39.2% NotMentioned). Per the freeze
rule: Oracle's overall/balanced accuracy will be reported only as **"balanced Oracle
diagnostic accuracy,"** never compared directly to natural-distribution benchmark accuracy.
Primary metrics are Macro-F1, per-class recall, Contradiction Recall, and the confusion
matrix.

## 11. Exact baseline Oracle prompt

`prompts/oracle_v1.txt` (verbatim):

```
You are given a confidentiality requirement and the exact evidence a legal annotator identified in an NDA when judging that requirement. Decide the relationship between the evidence and the requirement using only the evidence supplied. Do not invent facts not present in the evidence.

Classify as exactly one of:
- "Entailment": the supplied evidence establishes that the NDA satisfies the requirement.
- "Contradiction": the supplied evidence establishes terms incompatible with the requirement.
- "NotMentioned": the supplied material does not establish either entailment or contradiction for the requirement.

Respond with ONLY a JSON object with this exact field:
{
  "label": "Entailment" | "Contradiction" | "NotMentioned"
}

No explanation, no evidence quotation, no additional fields.
```

Label definitions cross-checked against the reconstruction brief's canonical wording (used
near-verbatim) and against ContractNLI's own task framing ("entailed by, contradicting to, or
not mentioned by the contract") — not rewritten into generic legal judgement.

**NotMentioned input handling — corrected after review**
(`evaluation/oracle.py::build_oracle_user_message`): every case, regardless of label, renders
through the **exact same template and field structure**:

```
Requirement: {hypothesis text}

Evidence: {gold evidence, as a JSON list}
```

For Entailment/Contradiction, `Evidence:` is a single-element list containing the gold
evidence text. For NotMentioned (empty gold evidence by construction, E00 §10), `Evidence:`
is an **empty list, `[]`** — not an explanatory sentence.

**This is a real correction, not a stylistic tweak**: an earlier version of this function
rendered NotMentioned cases with the sentence "No supporting NDA evidence was identified in
the annotation for this requirement." That sentence never used the word "NotMentioned," but it
was still a label-revealing shortcut — a model could learn "explanatory sentence present →
not NotMentioned" without reasoning about the requirement's content at all, which would have
inflated NotMentioned recall for a reason unrelated to reasoning quality. Structural parity
(same field, same type, across all three labels) removes that shortcut.

Real rendered examples from `TRAIN_ORACLE_v1.json` (verified, not illustrative):
```
Entailment:     Requirement: Receiving Party shall not disclose...
                Evidence: ["EFCA agrees to keep the existence and nature..."]

NotMentioned:   Requirement: Receiving Party shall not reverse engineer...
                Evidence: []
```

**Verified**: `gold_label` is never read by the message-builder; no model-visible message
(for any of the three labels) contains any of the forbidden substrings `gold`,
`NotMentioned`, `no supporting evidence`, `annotation`, `expected label` — checked by 4 tests
in `tests/test_oracle.py` (structural-parity check, empty-list-with-no-leak check, and an
all-labels sweep of the full forbidden-substring list) plus the module's own `demo()`
self-check.

**Documented interpretive limitation (kept, not hidden)**: NotMentioned Oracle performance is
still partly **structurally** easier than Entailment/Contradiction, even after this
correction — ContractNLI provides no annotated evidence for NotMentioned by definition, so
every NotMentioned case renders with an empty evidence list, which is itself a real
distinguishing structural signal (a model can learn "empty list → NotMentioned is plausible"
without engaging with the requirement's substance), separate from genuinely reasoning about
requirement content. **NotMentioned Oracle recall must be interpreted separately from
Entailment/Contradiction reasoning performance** in the Stage B analysis — not folded into one
combined "Oracle accuracy" number as if all three labels were equally hard to reach from the
rendered input alone. This limitation cannot be fully removed without changing what Oracle
fundamentally is (gold evidence, and ContractNLI genuinely has none for NotMentioned) — it is
recorded here as a permanent caveat on how to read the NotMentioned results, not a bug to fix.

Same prompt, same schema, same label definitions across all four models — no provider gets
customized instructions.

## 12. Exact output schema

```json
{"label": "Entailment" | "Contradiction" | "NotMentioned"}
```

No `confidence` field — not required by any planned E01 analysis (Macro-F1/recall/confusion
matrix don't need it), so omitted per the "prefer the smallest schema" instruction. No
explanation, no evidence quotation — Oracle already receives gold evidence, so asking the
model to reproduce it adds cost without informing the reasoning-ceiling question. Documented
as a deliberate experimental control (not an oversight): E01 measures classification reasoning
given perfect evidence, not explanation quality, retrieval, or citation generation — that
separation is real and load-bearing for what E01 can and can't tell us.

## 13–14. Projected hosted cost and total

Using this project's own real historical **actual** per-case Oracle cost (E00B; more reliable
than a token formula alone — it already captures GPT-5-mini's hidden reasoning-token
inflation):

| Model | Real historical per-case cost | x 300 cases |
|---|---|---|
| Hosted Model 1 (Gemini 2.5 Flash Lite) | $0.0000834 | **$0.0250** |
| Hosted Model 2 (GPT-5 mini) | $0.0010326 | **$0.3098** |
| **Total projected E01 hosted spend** | | **$0.3348** |

(2 local models: $0 API cost by construction — runtime is the real cost, see §16.)

## 15. Budget-gate result

`evaluation/budget.py::check_budget_against_ledger()`, run locally (no network call):

```
current reconstruction-v2 ledger spend: $0.00  (confirmed empty, header-only)
projected E01 hosted spend:             $0.3348
protected reserve (25% of $5.00):       $1.25
allowed budget:                         $3.75
projected total:                        $0.3348 <= $3.75  ->  ALLOWED
```

Historical T-series spend ($3.0011, audited in E00B) is **not** deducted again — the gate
reads only the reconstruction-v2 running ledger, per the "don't double-count" rule.

## 16. Estimated local runtime

**Not yet empirically calibrated for this exact call shape** — flagged plainly rather than
presented as precise. Oracle's per-case footprint (short evidence block, ~678 tokens input
mean, ~5-10 tokens output) is meaningfully smaller than every historical local-Llama
measurement on record, all of which involved larger contexts and more verbose output:

| Historical local-Llama reference point (E00B, real n=500 measurements) | Mean latency/case |
|---|---|
| RAG (smallest historical local call shape) | 4.53s |
| Full-context | 7.68s |
| RAG+agent | 9.19s |

Oracle's input is comparable in size to RAG's but its output is far smaller (a handful of
tokens vs. ~106 historically) — expected to be at or below the RAG reference point, not above
it. **Conservative estimate: 2-5 seconds/case**, i.e. **~10-25 minutes per local model for the
full 300-case manifest**, ~20-50 minutes for both local models sequentially. Recommend Stage B
begin with a small smoke-test (`scripts/run_e01_oracle.py --limit 5`) on Local Model 1 to
calibrate this estimate for real before committing to the full 300-case runs on both local
models — cheap (a few seconds either way) and removes the guesswork.

Hosted-model runtime is not a practical concern: E00B's real measured hosted per-case latency
(Gemini, RAG-scale calls) was ~1.0s/case; 300 cases x 2 hosted models is on the order of
minutes, not hours.

## 17. Files created/modified to prepare the experiment

**Created:**
- `experiments/E01_oracle/{README.md, config.yaml, summary.md, TRAIN_ORACLE_v1.json}` — this
  directory.
- `scripts/build_train_oracle_manifest.py` — manifest generator (already run).
- `scripts/run_e01_oracle.py` — the real Stage B runner (written, syntax-checked, **not
  executed**).
- `evaluation/oracle.py` — reusable input-construction/output-parsing logic (provider-agnostic,
  imported by the runner and will be imported by the Stage B notebook).
- `prompts/oracle_v1.txt` — the frozen baseline Oracle prompt.
- `tests/test_oracle.py` — 8 unit tests (message construction never leaks the label, JSON
  parsing strictness, result-record shape).

**Modified:** none outside the above (no pipeline/model code touched; no other experiment's
files touched).

**Not created yet (deferred to Stage B, since they require real results)**:
`E01_oracle_analysis.ipynb`, `results/*.jsonl`.

## 18. Unresolved issues

1. **Local runtime is an estimate, not a measurement** (§16) — recommend a 5-case smoke-test
   at the start of Stage B before committing to the full run.
2. **`qwen2.5:7b-instruct` is not yet downloaded** — Stage B's first step for Local Model 2 is
   `ollama pull qwen2.5:7b-instruct` (~4.7GB), which itself is not inference and doesn't spend
   API budget, but does take real time/disk and should happen only after Stage B is approved.
3. **Thermal risk on repeated local runs**: a full local run previously overheated the dev
   laptop once (docs/decisions.md, C02 history) — worth monitoring during Stage B, especially
   if both local models run back-to-back.
4. **`pipeline/model_gateway.py`'s own `PRICING_PER_MILLION` table is a separate source from
   `configs/pricing/*.yaml`** (E00B) — both currently agree on Gemini/GPT-5-mini numbers, but
   they're not the same file. Not reconciled this phase (would be a pipeline code change,
   out of scope for Stage A prep) — `scripts/run_e01_oracle.py` uses `ModelResponse.cost_usd`
   (from `pipeline/model_gateway.py`'s pricing) for the real per-call cost recorded to the
   ledger, which is consistent with the verified E00B numbers but sourced from a different file.
5. **Groq was set aside for Oracle** (§1-4) but remains available as a future hosted-vs-local
   comparison candidate (E15) where its rate limits are less binding against a smaller
   per-experiment case count — not a permanent exclusion, just not chosen for this
   300-case Oracle pass.

---

**Waiting for explicit approval before Stage B.** No Ollama call, no OpenRouter call, no Groq
call, no model download, no inference, and no money spent have occurred in preparing this
proposal.
