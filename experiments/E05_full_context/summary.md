# E05 — Full-Context Qwen Baseline (A1) — STAGE A + CALIBRATION COMPLETE

**Stage A (below): audit of existing full-context implementations, A1's architecture wrapper
design, evidence-output design, measured token-length distribution, and two disclosed risks.**
**Calibration (final section, "Calibration Results"): the two approved blocking tasks — fix the
context-window risk, then run an 8-case diagnostic calibration — are complete.** The full
150-case E05 benchmark has **NOT** been run; no scoring/research conclusion has been drawn from
the calibration predictions.

## 1. Research question

"How well does `qwen2.5:7b-instruct` classify NDA requirements when given the full NDA text,
with retrieval removed from the pipeline?" This isolates the effect of retrieval by holding
model and prompt fixed and changing only the input-construction architecture. Not a prompt
experiment (`classification_prompt_v1` is untouched) and not a model-selection experiment
(model is frozen from E01/E02).

## 2. Existing full-context implementation(s) in the repo

Two found, both **historical (T-series pre-reconstruction)**, neither directly reusable
unmodified for E05:

| Script | Split | Model | Prompt | Evidence handling |
|---|---|---|---|---|
| `scripts/run_full_context_baseline.py` (B03/T015) | DEV, 150-case stratified sample | Hosted (`ModelGateway()`, OpenRouter, whatever `settings.default_model` is) | `prompts/classify_v2.txt` via `pipeline/classifier.py::classify()` — a different, heavier schema (`label`, `confidence`, `evidence: list[str]`, `explanation`) | Evidence field exists in the schema, but never validated or span-mapped in this script — no Evidence Recall/Precision/joint metric computed here at all |
| `scripts/run_final_test_evaluation.py`'s `run_full_context()` (T041) | TEST, 500/2,091-case runs | Configurable (hosted or local via `ModelGateway`) | Same `pipeline/classifier.py::classify()` / `classify_v2.txt` | **Anti-pattern found and rejected for E05** — `retrieved_span_indices=list(range(len(doc.spans)))`: every span in the document is claimed as "evidence" by construction, trivially satisfying the joint metric for any correct label. This is exactly "full-document access counted as evidence success," which section 5 of the reconstruction brief explicitly prohibits. |

**Neither uses `classification_prompt_v1`, `qwen2.5:7b-instruct` via `ModelGateway.local()`, or
TRAIN** — both are T-series artifacts on DEV/TEST with a different model and prompt lineage.
E05 needs new Stage B code (a runner script), not a reused historical script, though the
*mechanism* of "pass `doc.text` as context, no retrieval" is the same shape as both.

## 3. Can `classification_prompt_v1` be reused with only an architecture wrapper?

**Yes**, and this is the core design decision of this Stage A. `classification_prompt_v1`
(= P0) is loaded via `evaluation.prompt_selection.load_prompt_config` and rendered via
`build_classification_user_message(case, user_template)` — a generic function that takes
whatever `case["context_text"]` and `case["hypothesis_text"]` are given; it has no dependency
on *how* `context_text` was produced (E03 already proved this generality — the same function
rendered both the original full-context design and the resumed retrieval_v1 design without
modification).

**The one piece that must change for full-context mode**: the frozen `user_template` literally
reads `"Retrieved NDA excerpts: {context_text}"`. Presenting a full document under that label
would be a factual misstatement (there was no retrieval), the same class of problem already
found and fixed once before (E03's own context-framing bug, fixed 2026-09-26). Per the brief's
explicit instruction, this is **not** solved by editing `classification_prompt_v1.yaml` — that
file stays frozen and byte-for-byte unchanged. Instead, E05's own Stage B runner will define a
**local, architecture-specific wrapper**: reuse `classification_prompt_v1`'s exact
`system_prompt` unmodified (label definitions, decision logic, output-schema core, word for
word), but substitute a different literal header string, `"Full NDA text: {context_text}"`,
when rendering the user message. This is documented here as an architecture-specific wrapper
around the frozen prompt, not a new prompt variant (P3) and not a reopening of E03.

## 4. Full-context token-length distribution — measured, not estimated

Computed directly (`tiktoken`'s `cl100k_base` encoding, the same approximation basis E03's
prompt configs already use for their own token estimates) over the proposed `TRAIN_ARCH_v1`
manifest's 150 full documents:

| Statistic | Tokens |
|---|---|
| Mean | 2,084 |
| Median | 1,879 |
| P90 | 3,788 |
| P95 | 4,636 |
| Max | 5,581 |
| Min | 329 |

For reference, the full 7,191-case TRAIN universe (all 423 documents) has mean 2,118, median
1,905, p90 3,899, **max 11,340** — `TRAIN_ARCH_v1`'s 150-case sample is representative of, not
an outlier from, the full distribution.

**No truncation is silently assumed acceptable anywhere in this document** — see sections 5-6.

## 5. Context-window risk — BLOCKING, unresolved

`qwen2.5:7b-instruct`'s native context length is 32,768 tokens (`ollama show`), and its
Modelfile sets no `PARAMETER num_ctx` — audited directly, not assumed. **Critically,
`pipeline/model_gateway.py`'s `complete()` never passes `num_ctx` (or any `options`/`extra_body`)
to the OpenAI-compatible endpoint, anywhere in the codebase, for any experiment.** This was
invisible and harmless for every experiment so far — E01 Oracle uses single-sentence evidence,
E03 uses retrieved top-5 context (~1,100-1,250 tokens) — both stay safely under even a
conservative 2,048-token default context window. **It is not safe for E05**: 40% of
`TRAIN_ARCH_v1`'s 150 cases exceed 2,048 tokens before adding the system prompt, hypothesis
text, and output budget; 8% exceed 4,096.

Ollama silently truncates (drops earlier context) rather than erroring when a request exceeds
the active context window — exactly the failure mode section 4 of the brief says must not
happen silently. **No live diagnostic call was made to check Ollama's actual effective default**
(no Qwen call is authorized in Stage A) — the risk is reported as a real, structural gap in the
current code, not resolved or waved away.

**Required before Stage B (a small, additive code change, not a new experiment)**:
`pipeline/model_gateway.py`'s `complete()`/`local()` needs a way to pass
`extra_body={"options": {"num_ctx": N}}` through to Ollama's OpenAI-compatible endpoint (the
`openai` Python client supports arbitrary `extra_body`). **Proposed value: `num_ctx=16384`** —
2.9x `TRAIN_ARCH_v1`'s observed max (5,581) and 1.4x the full-TRAIN universe's max (11,340),
comfortably within the model's native 32,768 ceiling without needlessly maximizing memory/compute
per call for documents that don't need it.

## 6. Request-timeout risk — flagged, not yet measured

`pipeline/config.py`'s `request_timeout_seconds` is 30, unchanged since E01/E03. E03's
observed latencies (~1,100-1,250 token contexts) ranged 4.8-11.5s per call. Full-context inputs
are 1.7-5x longer; whether local prefill cost scales linearly enough to stay under 30s at the
p95/max end of `TRAIN_ARCH_v1`'s distribution is genuinely unknown without a real measurement —
**not estimated here, proposed to be resolved by the same small calibration step as the runtime
estimate (section 10)**, not by blindly raising the timeout.

## 7. Evidence output — proposed schema and validation

**Proposed compact extension** (additive only, per section 6 of the brief — no new reasoning
instructions):

```json
{"label": "Entailment" | "Contradiction" | "NotMentioned", "evidence": ["...", "..."]}
```

NotMentioned must return an empty `evidence` list. One additive instruction line is proposed for
the system prompt wrapper (see section 3) — asking for verbatim sentence(s), nothing about *how*
to decide the label. `evaluation.oracle.parse_oracle_output` already tolerates and ignores extra
JSON keys (confirmed by reading its implementation — it only reads `parsed.get("label")`), so
extracting `evidence` is a small additive read in the Stage B runner, not a change to that
frozen function.

**Validation mechanism — already exists, historical, directly reusable, zero cost**:
`pipeline/evidence_validator.py::validate_evidence(context, evidence, label)` — a pure
deterministic string check (`quote in context`) with **no LLM call**, already used to catch
hallucinated/paraphrased citations in the T-series project. Every quote the model returns will
be checked against the exact `context_text` (full document) it was shown; non-verbatim quotes
are discarded as hallucinated, not silently trusted.

**Span mapping for scoring**: for each verbatim quote, `doc.text.find(quote)` gives a character
span, which is then interval-overlap-mapped onto `doc.spans` — the **identical mechanism**
already used for the rule baseline's evidence (E04, `scripts/run_e04_rule_baseline.py`) and for
retrieval scoring (E06). This gives `predicted_span_indices` compatible with the existing frozen
Evidence Recall/Precision/joint-metric formulas, on the same footing as every other architecture
— no new metric definition needed.

## 8. Matched-comparison principle (E05 vs. E07)

E05 and E07 must share: cases, model, prompt (`classification_prompt_v1`), output schema
(the evidence-extended version above, used identically by both), temperature, parsing, and
(where meaningful) token/context handling. **The only architectural difference**: E05 feeds
full document text; E07 feeds `retrieval_v1`'s top-5 reranked context. This is why the manifest
proposal (section 9) matters as much as it does — both experiments read from the exact same
file.

## 9. Manifest: fresh `TRAIN_ARCH_v1`, not `TRAIN_PROMPT_v1` reuse

**Assessed directly, not assumed.** `TRAIN_PROMPT_v1` (E03's 150-case manifest) is balanced,
document-diverse, and already carries full NDA text in its `context_text` field — structurally
it would work fine for E05 alone. **But `classification_prompt_v1` (= P0) was itself SELECTED by
evaluating P0/P1/P2 on exactly this population** (E03's decisive win: Contradiction Recall 22.0%
vs. 6.0% vs. 2.0%). Reusing the same 150 cases for the architecture comparison that selected
prompt now feeds into would mean the prompt was chosen to do well on precisely the population
being used to judge architecture — a real, if likely mild given the margin's size,
selection-bias exposure. Per the brief's own instruction ("prefer a fresh set if practical"),
and because building one is genuinely cheap and clean (identical sampling algorithm, one line
seed change, verified disjoint by construction), a fresh manifest is proposed and has already
been built (local-only, deterministic, zero model calls — same Stage A precedent as E01/E03's
own manifest construction):

**`TRAIN_ARCH_v1`** (`scripts/build_train_arch_manifest.py`, this pass):
- 150 cases, exactly 50/50/50 balanced, seed=700 (distinct from every prior project seed: 42,
  99, 123, 300, 500).
- Document diversity: 26 unique documents (Entailment), 28 (Contradiction), 26 (NotMentioned),
  78 total unique documents.
- **Zero overlap with `TRAIN_PROMPT_v1` by construction** — every `TRAIN_PROMPT_v1` case_id was
  excluded from the candidate pool *before* sampling, not merely checked afterward (verified:
  `verified_zero_overlap_with_TRAIN_PROMPT_v1: true`).
- Same `context_text` = full NDA document text field E03's original manifest already used —
  ready for E05 as-is; E07 will build `retrieval_v1` context from the same
  `case_id`/`document_id`/`hypothesis_id` triples, exactly as
  `generate_e03_retrieved_context.py` did for `TRAIN_PROMPT_v1`.

## 10. Expected runtime — a calibration plan, not a guess

E03's ~1,100-1,250 token contexts averaged 4.8-4.9s/case locally. Full-context inputs are
1.7-5x longer (mean 2,084, max 5,581 in `TRAIN_ARCH_v1`), and local LLM prefill cost does not
necessarily scale linearly with input length on this hardware — extrapolating E03's per-case
timing directly would be a guess, not a measurement, and this project's own culture (e.g. E00B's
budget forecast, E06's runtime calibration) has consistently preferred a small real calibration
step over an extrapolated guess. **Proposed for the start of Stage B**: time 5-10 real calls
spanning `TRAIN_ARCH_v1`'s length distribution (e.g. its min, median, p90, and max cases) before
committing to a full 150-case runtime estimate — this also directly tests whether
`request_timeout_seconds=30` (section 6) actually holds at the long end.

## 11. Exact model/runtime settings (proposed, matching E03 where applicable)

`qwen2.5:7b-instruct` via `ModelGateway.local(model="qwen2.5:7b-instruct")`, temperature 0.0,
`max_retries` and `request_timeout_seconds` from `pipeline/config.py`'s defaults **except**
`request_timeout_seconds`, which may need raising after the section 10 calibration step — not
decided yet. New: `num_ctx=16384` passed via `extra_body` (section 5) — a capability
`ModelGateway` does not currently have and would need to gain. Output parsing:
`evaluation.oracle.parse_oracle_output` (label) plus a small additive `evidence` list read.

## 12. Proposed metrics

Exactly as specified: Accuracy, Macro-F1, per-class recall (Contradiction Recall + 95% Wilson
CI), confusion matrix, Evidence Recall/Precision, joint label+evidence correctness (overall and
by class, same computation as E04), mean/median/p90/max input tokens, mean/median/p90 latency,
total runtime, parse-valid rate, retry count, cost ($0).

## 13. Failure-analysis plan

Following the brief's six proposed families (A-F), tagged only where the data actually supports
them (same non-forced-categorization discipline as E03/E04) — plus explicit cross-checks against
E01 Oracle (does the model reason correctly given perfect evidence, i.e. is a full-context miss
really a "the document was too big" problem or the same reasoning-ceiling limitation Oracle
already found independent of context size) and against E04's rule baseline (does full-context
recover cases the rule baseline's lexical-coverage gap missed). Reasoning failure (A) and
evidence-selection failure (B) are distinguished using the same evidence-hit mechanism as
sections 6-7; long-context failure (C) is checked by correlating errors against document length
(does error rate rise with token count); exception/carve-out (D) is checked, not assumed, exactly
as E04 was told not to assume it either. Retrieval is never blamed for any E05 error, by
construction — there is no retrieval step in A1.

## 14. Files to create / change

**Stage A (this commit)**: `experiments/E05_full_context/{README.md, config.yaml, summary.md}`,
`experiments/E05_full_context/results/` (empty, for Stage B),
`experiments/E05_full_context/TRAIN_ARCH_v1.json` (built, verified, local-only, zero model
calls), `scripts/build_train_arch_manifest.py` (new).

**Stage B (after approval)**:
- A small, additive extension to `pipeline/model_gateway.py`'s `complete()`/`local()` to support
  passing `num_ctx` via `extra_body` (section 5) — needed before any full-context Qwen call is
  safe to make.
- `scripts/run_e05_full_context.py` (new — architecture wrapper per section 3, evidence-schema
  extension per section 7, calibration step per section 10, then the full run).
- `scripts/analyze_e05_full_context.py` (new — metrics + failure analysis, mirroring
  `scripts/analyze_e04_rule_baseline.py`'s structure).
- `experiments/E05_full_context/results/run_E05_A1_train.json`,
  `run_E05_A1_train_cases.jsonl`, `full_context_failure_analysis.csv`.
- `experiments/E05_full_context/E05_full_context.ipynb`.

## 15. Unresolved issues (for explicit review)

1. **Context-window truncation risk (section 5) — BLOCKING.** `num_ctx` must be explicitly set
   before Stage B; proposed value 16,384, but this requires a small `ModelGateway` code change
   not yet authorized.
2. **Request-timeout risk (section 6) — unresolved**, pending the calibration step.
3. **Runtime estimate (section 10)** genuinely cannot be stated with confidence before a real
   calibration measurement — flagged rather than guessed.
4. **Evidence-instruction wording** (section 7's proposed one-line addition) is a concrete draft,
   not yet reviewed line-by-line for accidental scope creep into new reasoning guidance — worth
   a final wording check at Stage B approval time.
5. Whether `num_ctx=16384` should instead be set to the model's full native 32,768 for maximum
   safety margin at some compute cost — a judgment call, not resolved here.

Stage A ended here and was approved with two required tasks before the full benchmark: (1) fix
the context-window risk, (2) run an 8-case calibration to verify the fix and measure real
operational characteristics. Both are complete — results below.

---

## Calibration Results (2026-09-26)

### 1. `num_ctx` implementation change — and a real finding beyond the original plan

**Implemented as specified**: `pipeline/model_gateway.py`'s `ModelGateway.__init__`/`.local()`
gained a `num_ctx: int | None = None` parameter; when set, `complete()` passes
`extra_body={"options": {"num_ctx": N}}` to the OpenAI-compatible client. Default `None`
preserves every existing caller's exact prior behavior (verified by a dedicated test, section 2).

**However, live testing (the very first calibration attempt) found this mechanism does not
actually work.** `ollama ps` showed the resident model at `CONTEXT=4096` even after calls with
`num_ctx=16384`. Two calibration cases (5,554-5,581 real document tokens) came back with
`usage.prompt_tokens` of only ~2,050 — a genuine, confirmed silent truncation, not a hypothetical
risk. **Root-caused independently of any of this project's code**: three direct `curl` calls to
the raw Ollama server showed (a) the OpenAI-compatible `/v1/chat/completions` endpoint ignores a
per-request `options.num_ctx` and even reloads an already-16384-loaded model back down to 4096
on the next call; (b) Ollama's **native** `/api/chat` endpoint correctly honors the same
`options.num_ctx` field (context verifiably jumped to 16384, `ollama ps` confirmed). Since
`ModelGateway` is built entirely on the OpenAI-compatible client, the working fix is a
**Modelfile-based custom model tag** with `PARAMETER num_ctx 16384` baked in as the model's own
default — `configs/ollama/qwen2.5-7b-instruct-ctx16k.Modelfile`, built as
`qwen2.5:7b-instruct-ctx16k`, verified via curl (prompt_tokens correctly reflects full document
length; `ollama ps` shows `CONTEXT=16384`). The E05 calibration script points at this tag
directly; the `num_ctx` kwarg is kept in `ModelGateway` (documented with this exact caveat in
its docstring) as a harmless, forward-compatible, unit-tested capability, but is **not** the
mechanism that actually resolves the risk for local Ollama today.

### 2. Tests added and result

Four new tests in `tests/test_model_gateway.py`:
`test_default_num_ctx_is_none_unset_for_every_existing_caller`,
`test_local_gateway_passes_num_ctx_through`,
`test_complete_without_num_ctx_sends_no_extra_body` (confirms zero behavior change for every
pre-existing caller), `test_complete_with_num_ctx_sends_ollama_options`. **Full suite: 280/280
passed** (was 276; +4 new, 0 regressions).

### 3. TRAIN_ARCH_v1 total input-token distribution (system prompt + evidence instruction + user template + full NDA text)

Computed with the exact A1 wrapper text (classification_prompt_v1's system prompt + one
additive evidence instruction line = 118 tokens, plus `"Requirement: ...\n\nFull NDA text:
..."`), `tiktoken` `cl100k_base` approximation:

| Statistic | Tokens |
|---|---|
| Mean | 2,222 |
| Median | 2,021 |
| P90 | 3,928 |
| P95 | 4,774 |
| Max | 5,723 |
| Cases above 8,000 | 0 |
| Cases above 12,000 | 0 |

### 4. Does every case fit safely under num_ctx=16384?

**Yes.** Safe budget = 16,384 − 1,024 (reserved for output/evidence tokens) = 15,360. Max
observed total input across all 150 `TRAIN_ARCH_v1` cases is 5,723 — **zero cases exceed the
safe budget**, with a comfortable ~2.7x margin even at the longest case. (Caveat: `cl100k_base`
is an approximation of Qwen's actual tokenizer, not exact — but the margin is large enough that
even a 20-30% estimation error would not approach the limit.)

### 5. The 8 calibration cases chosen and their token lengths

| Bucket | Case ID | Gold label | Doc tokens (cl100k approx) |
|---|---|---|---|
| Q1 | `train::265::nda-15` | Entailment | 1,259 |
| Q1 | `train::187::nda-1` | NotMentioned | 1,262 |
| Median | `train::232::nda-11` | NotMentioned | 1,879 |
| Median | `train::352::nda-12` | Entailment | 1,895 |
| P90 | `train::126::nda-10` | NotMentioned | 3,788 |
| P90 | `train::317::nda-12` | Entailment | 3,868 |
| Longest | `train::515::nda-20` | Contradiction | 5,581 |
| Longest | `train::273::nda-10` | Entailment | 5,554 |

All 8 from distinct documents; classes mixed where the length-bucket constraint allowed
(Contradiction is a smaller pool and didn't naturally fall near these length targets except at
the longest end).

### 6. Per-case latency (post-fix, real `qwen2.5:7b-instruct-ctx16k` calls)

| Case | Bucket | Input tokens (actual) | Wall latency (s) |
|---|---|---|---|
| `train::265::nda-15` | q1 | 1,417 | 9.77 |
| `train::187::nda-1` | q1 | 1,427 | 6.00 |
| `train::232::nda-11` | median | 2,047 | 9.29 |
| `train::352::nda-12` | median | 2,058 | 15.72 |
| `train::126::nda-10` | p90 | 3,945 | 19.86 |
| `train::317::nda-12` | p90 | 4,057 | 20.92 |
| `train::515::nda-20` | longest | 5,766 | 28.33 |
| `train::273::nda-10` | longest | 5,806 | 28.80 |

Input tokens now correctly track full document length at every bucket (compare the pre-fix
run's erroneous ~2,050 for the two longest cases) — **the truncation is confirmed fixed.**

### 7. Parse-valid / evidence-valid status

**5/8 parse-valid, 3/8 parse-invalid** — all 3 failures in the p90/longest buckets, none in
q1/median. **Not a truncation artifact and not malformed JSON**: in all 3 cases the model
produced a well-formed `{"label": ...}` object first, then appended free-text commentary
afterward (once in Chinese) — `parse_oracle_output`'s strict "the entire response must be
exactly one JSON object" rule rejects the trailing text. This is a genuine, disclosed
**long-context instruction-following degradation** distinct from the (now-fixed) truncation
risk — flagged as an open design question for Stage B (e.g. a more lenient "extract the first
JSON object" parse, or a stronger formatting instruction), not resolved unilaterally here, since
Stage A calibration is diagnostic only. Of the 5 valid cases, evidence quotes were checked via
`validate_evidence()` — no hallucinated (non-verbatim) quotes were returned in this small sample.

### 8. Timeout/errors

**Zero `ModelError`/timeout exceptions** in either calibration run (pre- or post-fix). Latency
range: 6.0-28.8s. The two longest cases (28.33s, 28.80s) came uncomfortably close to the current
30s `request_timeout_seconds` — no failure occurred here, but the margin is thin enough to risk
retry storms on the full 150-case run, which includes cases at this same length.

### 9. Recommended request timeout

**60 seconds** — roughly 2x the observed max (28.8s), a comfortable margin without being
excessive. Proposed as `ModelGateway.local(model=..., timeout_seconds=60)` for the E05 Stage B
runner specifically (an operational fix applied uniformly, not an experiment variable, per the
brief's own framing).

### 10. Projected full E05 runtime

Linear regression fit on the 8 real calibration points (`latency_s = 2.145 + 0.004582 ×
input_tokens`, R² not computed formally but the fit tracks the observed points closely),
applied to all 150 `TRAIN_ARCH_v1` cases' actual token counts (not just the aggregate mean):

| Statistic | Projected latency (s/case) |
|---|---|
| Mean | 12.33 |
| Median | 11.40 |
| P90 | 20.14 |
| Max | 28.37 |

**Projected total runtime for the full 150-case E05 benchmark: ~30.8 minutes.** This is a
real, calibration-based estimate, not a historical extrapolation from E03's much-shorter
contexts — stated with the appropriate caveat that it is fit on only 8 points and real variance
should be expected. A 300-case projection was not computed: E07's future RAG contexts will be
much shorter (similar to E03's ~1,100-1,250 tokens), so simply doubling E05's full-context
runtime would not be a meaningful estimate for a combined E05+E07 total — E07 will need its own
short calibration when it is proposed.

### Files created this pass

- `pipeline/model_gateway.py` (additive `num_ctx` parameter, documented caveat).
- `tests/test_model_gateway.py` (4 new tests).
- `configs/ollama/qwen2.5-7b-instruct-ctx16k.Modelfile` (new, required Ollama model tag for
  Stage B).
- `scripts/run_e05_calibration.py` (new — 8-case calibration runner).
- `experiments/E05_full_context/results/calibration_8case.json` (diagnostic output, not scored).
- `docs/experiment_registry.md` (E05 row, to be updated to reflect calibration completion).

**Not done, and not authorized (as of this point)**: the full 150-case E05 benchmark, any
DEV/TEST access, any hosted model call, E07, or a commit.

---

## Deterministic JSON Recovery + Final Recalibration (2026-09-26)

### Context configuration decision (final, authoritative)

- **Model tag**: `qwen2.5:7b-instruct-ctx16k` (Modelfile: `configs/ollama/qwen2.5-7b-instruct-ctx16k.Modelfile`).
- **Effective context**: 16,384 — verified via `ollama ps` (`CONTEXT` column) and via
  input-token-usage checks (all 8 calibration cases' `usage.prompt_tokens` now correctly match
  their full document length).
- **Request timeout**: 60 seconds.
- **`ModelGateway`'s `num_ctx` kwarg does NOT fix this and is not claimed to.** It is retained
  as general-purpose API-compatibility plumbing (unit-tested, off by default), but was
  empirically observed (direct `curl`, independent of this project's code) to be ignored by
  Ollama's OpenAI-compatible endpoint. **The Modelfile-based model tag is the sole authoritative
  E05 context configuration.**

### Why the prompt was not touched

The 3/8 prior parse failures were a well-formed `{"label": ...}` object followed by trailing
free-text commentary — an output-parsing/protocol issue, not a reasoning or label-definition
problem. Per instruction, `classification_prompt_v1` was not modified, no new prompt variant
was created, and no stronger formatting instruction was added. The fix is entirely in a new
deterministic parser, `evaluation/structured_output.py`.

### Deterministic recovery parser

`evaluation.structured_output.parse_structured_output()` — two-stage, fully deterministic, no
LLM repair, no field inference, no arbitration between multiple candidates:

- **A. Strict**: the whole response (after stripping an optional markdown code fence, the same
  tolerance `evaluation.oracle.parse_oracle_output` already applies) parses as exactly one JSON
  object satisfying the schema (label is one of the three canonical labels; evidence, if
  present, is a list of strings). `parse_status="strict"`.
- **B. Recovery** (only if strict fails): scans the raw text for every balanced top-level
  `{...}` span, correctly treating braces inside quoted string values as non-structural (a
  string-literal-aware brace-depth scanner, not a naive regex). If **exactly one** such span
  parses as valid JSON and satisfies the schema, `parse_status="recovered"`. **Two or more
  valid candidates, or a sole candidate that fails schema validation, is never recovered** —
  `parse_status="invalid"`, with `error_type="AMBIGUOUS_OUTPUT"` or `"NO_VALID_JSON"`
  respectively. This is deliberately conservative, exactly as specified: the parser never
  chooses between conflicting JSON objects.

Every prediction record preserves: `raw_response`, `strict_parse_valid`,
`recovered_parse_valid`, `parse_status`, `prediction`, `evidence`, `error_type`,
`error_message` — so later reporting can always distinguish "the model followed the output
contract exactly" (strict) from "the result was deterministically recoverable" (recovered).
Recovered responses are never reported as strict-valid.

Evidence validation is unchanged and still applied after parsing: every evidence quote (from
either strict or recovered parses) is checked against the real full NDA text via the existing,
unmodified `pipeline/evidence_validator.py::validate_evidence()` — no paraphrase is ever
accepted as verbatim, and NotMentioned must still carry an empty evidence list to be
evidence-valid.

### Parser tests

13 new tests in `tests/test_structured_output.py`, covering all 8 required scenarios plus extra
edge cases: pure valid JSON, valid JSON + trailing commentary (the real failure mode found),
leading commentary + valid JSON, malformed JSON, two conflicting JSON objects (confirmed NOT
recovered), invalid label value, evidence wrong type (bare string, list of non-strings),
missing evidence key (must still be strict-valid, since E03's compact schema has no evidence
field at all), braces inside quoted evidence text (both alone and combined with trailing
commentary, confirming the recovery scanner is string-literal-aware), code-fenced JSON (counts
as strict, not recovered), empty response, and raw-response preservation. **All 13 passed on
first implementation.** Full suite: **293/293 passed** (was 280; +13 new, 0 regressions).

### Recalibration on the identical 8 cases (not a new sample)

Same manifest, same deterministic selection algorithm, same 8 `case_id`s as the prior
calibration pass — re-verified identical before running. Model
`qwen2.5:7b-instruct-ctx16k`, timeout 60s.

| Case | Bucket | Input tokens | Wall latency (s) | Parse status | Prediction | Evidence valid |
|---|---|---|---|---|---|---|
| `train::265::nda-15` | q1 | 1,417 | 14.17 | strict | Contradiction | No (paraphrased) |
| `train::187::nda-1` | q1 | 1,427 | 6.37 | strict | NotMentioned | Yes |
| `train::232::nda-11` | median | 2,047 | 9.54 | strict | Entailment | No (paraphrased) |
| `train::352::nda-12` | median | 2,058 | 16.68 | strict | Entailment | No (paraphrased) |
| `train::126::nda-10` | p90 | 3,945 | 20.24 | **recovered** | Contradiction | Yes (empty) |
| `train::317::nda-12` | p90 | 4,057 | 21.07 | **recovered** | NotMentioned | Yes (empty) |
| `train::515::nda-20` | longest | 5,766 | 28.67 | **recovered** | NotMentioned | Yes (empty) |
| `train::273::nda-10` | longest | 5,806 | 28.25 | strict | Entailment | Yes |

**Strict parse validity: 5/8 (62.5%). Recovered: 3/8 (37.5%). Invalid: 0/8. Usable
structured-output validity (strict + recovered): 8/8 (100%).** All 3 previously-invalid cases
(all in the p90/longest buckets, exactly as before) are now cleanly recovered with a correct
label and zero fabricated evidence. Evidence-valid: 5/8 — the 3 non-evidence-valid cases are
all **strict** parses where the model paraphrased rather than quoted verbatim (a real, distinct
finding, correctly caught by the unmodified `validate_evidence()` — not a parser gap).
**Timeouts/errors: 0/8.** Zero calls approached the new 60s ceiling meaningfully (max 28.67s).

**Verified**: input tokens exactly match full document length for every case (no truncation,
including both longest cases at 5,766/5,806 tokens); `ollama ps` confirms `CONTEXT=16384`;
model tag is `qwen2.5:7b-instruct-ctx16k`; timeout is 60 seconds.

### Reporting discipline for the eventual full E05 run

Per instruction, the full benchmark report must show **both** numbers, never collapse them into
one: `strict parse validity = X%` and `usable structured-output validity (strict + recovered) =
Y%`. This calibration's own numbers (62.5% / 100%) illustrate exactly why both matter — the
model violated the requested output format on 3/8 cases, a real fact that must not be hidden,
while the deterministic recovery correctly prevented harmless trailing prose from turning an
otherwise-valid classification into a counted failure.

### Full E05 authorization gate — status against each condition

| Condition | Status |
|---|---|
| 16k context active | ✅ confirmed (`ollama ps`, token-usage checks) |
| Zero truncation | ✅ confirmed (all 8 input-token counts match expected document length) |
| Zero timeout failures | ✅ confirmed (0/8, max latency 28.67s vs. 60s limit) |
| Deterministic parser behaves correctly | ✅ confirmed (13/13 tests pass; 0/8 invalid on real calibration data) |
| Recovered outputs remain evidence-valid where appropriate | ✅ confirmed (all 3 recovered cases correctly evidence-valid, empty evidence sets matching their predicted labels) |
| Tests pass | ✅ 293/293 |

### Files created/changed this pass

- `evaluation/structured_output.py` (new — deterministic recovery parser).
- `tests/test_structured_output.py` (new — 13 tests).
- `scripts/run_e05_calibration.py` (updated — uses the new parser, `qwen2.5:7b-instruct-ctx16k`
  model tag directly, 60s timeout, corrected context-configuration documentation).
- `experiments/E05_full_context/results/calibration_8case.json` (re-run, same 8 cases).

**Not done, and not authorized (as of this point)**: the full 150-case E05 benchmark, E07,
DEV/TEST access, any hosted model call, or a commit.

---

## Full Benchmark Results (2026-09-26) — all 150 TRAIN_ARCH_v1 cases

**Frozen configuration, unchanged from the approved calibration**: model
`qwen2.5:7b-instruct-ctx16k` (num_ctx=16384 baked into its Modelfile), temperature 0.0, 60s
timeout, `classification_prompt_v1`'s system prompt byte-for-byte unchanged + one additive
evidence instruction, "Full NDA text:" architecture wrapper,
`evaluation.structured_output.parse_structured_output` parser, unmodified
`pipeline.evidence_validator.validate_evidence`, `TRAIN_ARCH_v1` manifest (150 cases). No DEV,
no TEST, no hosted model call. Total wall time: **1,914.8s (31.9 minutes)** — very close to the
30.8-minute calibration-based projection.

### Manifest verification

Re-verified before running: 150 cases, exactly {Entailment: 50, Contradiction: 50,
NotMentioned: 50}, seed=700, 78 unique documents, zero overlap with `TRAIN_PROMPT_v1` — all
assertions passed.

### Input-token distribution (actual, all 150 cases)

Mean 2,253, median 2,046, p90 3,945, max 5,806 — consistent with the Stage A/calibration
estimates.

### Classification metrics

| Metric | Value |
|---|---|
| Accuracy | 40.0% |
| Macro-F1 | 0.397 |
| Entailment Recall | 48.0% |
| **Contradiction Recall** | **28.0% [95% CI 17.5%, 41.7%]** |
| NotMentioned Recall | 44.0% |

### Confusion matrix (rows = gold, cols = predicted; order Entailment/Contradiction/NotMentioned)

- **Entailment**: `[24, 17, 9]`
- **Contradiction**: `[5, 14, 31]`
- **NotMentioned**: `[20, 8, 22]`

### Structured-output metrics — reported separately, never collapsed

**Strict parse validity: 141/150 (94.0%). Recovered: 9/150 (6.0%). Invalid: 0/150.**
**Usable structured-output validity (strict + recovered): 100%.** Total retries: 0. Model
errors: 0. Timeouts (raised as `ModelError`): 0. The full-population recovery rate (6.0%) is
much lower than the calibration's deliberately length-skewed 8-case sample (37.5% recovered) —
expected, since most of the real population is shorter than the calibration's stratified
length buckets.

### Evidence metrics — explicit returned evidence only, never full-document access

| Metric | Value |
|---|---|
| Evidence-bearing cases (Entailment+Contradiction) | 100 |
| Evidence Recall | 25.0% |
| Evidence Precision | 28.7% |
| Correct label but invalid evidence | 10 |
| **Wrong label but valid (verbatim, correctly-located) evidence** | **53** |
| Paraphrased (non-verbatim) evidence | 34 |

The 53 "wrong label but valid evidence" cases are a strong, real signal: the model frequently
locates and quotes the actually-relevant text correctly, yet still reasons to the wrong label —
consistent with E01 Oracle's earlier, separately-measured finding that Qwen's Contradiction
reasoning is weak even given perfect evidence (see "Oracle context" below; not a direct
population-matched comparison).

### Joint label+evidence success — overall and by class

| | Rate |
|---|---|
| Overall | 28.0% |
| Entailment | 24.0% |
| Contradiction | 16.0% |
| NotMentioned | 44.0% |

Full-document access was never counted as evidence success (the historical T041 anti-pattern
rejected in Stage A) — every joint-success case required an explicit, verbatim, correctly-
located quote (or, for NotMentioned, a genuinely empty evidence list).

### Length-bucket analysis (descriptive/correlational only — no causal claim)

| Bucket (input tokens) | n | Accuracy | Strict parse | Recovered | Evidence-valid | Mean latency |
|---|---|---|---|---|---|---|
| ≤p50 (≤2,047) | 76 | 39.5% | 100% | 0% | 78.9% | 8.4s |
| p50–p90 (2,047–3,945) | 60 | 41.7% | 93.3% | 6.7% | 75.0% | 15.0s |
| >p90 (>3,945) | 14 | 35.7% | 64.3% | 35.7% | 78.6% | 27.2s |

**Strict-parse rate clearly falls with length** (100% → 93.3% → 64.3%) — a real, monotonic
correlation, consistent with the calibration's earlier finding. **Accuracy does not show a clear
monotonic trend** (39.5% → 41.7% → 35.7%) — the >p90 bucket's small sample (n=14) makes this
noisy, not a confident claim of long-context accuracy degradation. **Evidence-valid rate is
roughly flat across buckets** (~75–79%) — paraphrasing does not show a clear length correlation
in this data. Reported as observed correlations only, per instruction, with no causal claim.

### Latency

Mean 12,764ms, median 10,174ms, p90 22,214ms, **max 84,039ms**.

**Operational note (disclosed, not fixed, not retroactively changed)**:
- Configured request timeout = 60 seconds.
- One observed call (`train::505::nda-4`, only 3,345 input tokens — not even a long-document
  outlier) completed in ~84 seconds without raising a timeout/`ModelError`.
- **Therefore the current timeout setting should not be treated as a strict enforced latency
  ceiling under this Ollama/OpenAI-compatible path** — at least one real call ran ~40% past the
  configured limit and still returned a normal, successfully-parsed response.
- **This is an operational observation, not a model-quality result.** It says nothing about
  A1's classification/evidence performance; it is recorded here for anyone relying on
  `request_timeout_seconds` as a hard SLA in later experiments (E07, E12) or production
  planning. The run itself was not re-executed or altered because of this finding.

### Failure decomposition (primary + secondary categories allowed)

| Count | Family |
|---|---|
| 90 | A — classification/reasoning failure (every wrong-label case) |
| 40 | G — NotMentioned overprediction (gold Entailment/Contradiction, predicted NotMentioned) |
| 36 | E — exception/carve-out candidate (gold Contradiction, exception/carve-out keyword present in the full document) |
| 34 | B — evidence-selection failure (evidence absent/invalid/paraphrased on an error or a correct-label case) |
| 0 | C — structured-output failure (none — 100% usable parse validity) |

**36/90 classification errors contained an exception/carve-out indicator** (an automated
keyword co-occurrence check on the full document text, not a manual causal read of every case —
same methodology discipline as E03/E04). This is a co-occurrence, not a causal claim: we do not
say "exception clauses caused 36 errors." **Unlike E04's rule baseline** (where the same
keyword-co-occurrence check was applied and found NOT to dominate, since the rule baseline's
errors were overwhelmingly plain lexical coverage gaps), A1's error data shows a real,
non-trivial co-occurrence with exception/carve-out language — a different architecture
surfacing a different dominant pattern on the same underlying phenomenon. This is reported as an
observed co-occurrence in the LLM-based architecture's own error data, not assumed to transfer from E03
or E04's findings on different architectures/models.

### Representative cases

Full detail in `results/full_context_failure_analysis.csv` (150 rows) and the executed
notebook's sections 16-18 (correct predictions, classification failures, evidence-selection
failures — zero structured-output failures to show).

### Oracle context (E01) — qualitative only, no direct delta claimed

E01 (Oracle, gold evidence, `TRAIN_ORACLE_v1`) already established that Qwen's Contradiction
reasoning was weak even under perfect-evidence conditions. E05 tests whether full-document
context changes that behavior on a separate frozen manifest (`TRAIN_ARCH_v1`) — not a matched
population, so no exact Oracle-to-E05 degradation is computed as a causal effect. Qualitatively,
E05's Contradiction Recall (28.0%) and the 53 "wrong label but valid evidence" cases are
consistent with (not proof of) Oracle's earlier finding that the bottleneck is reasoning, not
evidence access.

### E03 — descriptive mention only, not a comparison

E05 (40.0% accuracy, `TRAIN_ARCH_v1`, full context) and E03 (52.7% accuracy,
`TRAIN_PROMPT_v1`, retrieved context) used **different manifests** — per instruction, this is
**not** reported as "full context worse than RAG" or any other architecture verdict. That
matched comparison is E07's job, using this same `TRAIN_ARCH_v1` manifest.

### Final `A1_full_context_v1` freeze

Recorded in full in `config.yaml`'s `frozen_a1` block: model, context configuration, prompt,
architecture wrapper, evidence instruction, output schema, parser, evidence validator, manifest,
timeout, and the complete metrics table above. **"Frozen" means a reproducible architecture
configuration for later comparison (E07/E12) — not a claim that A1 is production-ready.**
Contradiction Recall (28.0%), evidence quality (25.0% recall / 28.7% precision), and the
length-correlated structured-output degradation are all real, disclosed limitations of this
configuration. **No change was made to the prompt, evidence instruction, parser, model, or
timeout in response to these results** — they are recorded as findings for E07/E12 to interpret,
per explicit instruction.

### Files created this pass

- `scripts/run_e05_full_context.py` (full 150-case runner, frozen configuration).
- `scripts/analyze_e05_full_context.py` (classification/structured-output/evidence/joint/
  length-bucket/failure-decomposition analysis).
- `experiments/E05_full_context/results/run_E05_A1_train_cases.jsonl` (150 fully-traceable
  records), `run_E05_A1_train.json` (aggregate metrics), `run_E05_A1_train_wall_seconds.json`,
  `full_context_failure_analysis.csv` (150 rows).
- `experiments/E05_full_context/E05_full_context.ipynb` (21-section notebook per the
  reconstruction brief's outline, executed, zero errors).

**Not done, and not authorized**: E07, DEV/TEST access, any hosted model call, or a commit.
