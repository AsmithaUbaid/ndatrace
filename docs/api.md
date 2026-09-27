# NDATrace API Documentation

Documents only the endpoints that actually exist in `backend/app.py` and `backend/routes/*.py`, as
CORS is currently permissive (`allow_origins=["*"]`) for local development — see `backend/app.py`'s
comment noting this should be tightened before any non-local deployment (not done, since this
project has no deployment target beyond local demo).

Two review paths exist in this file:

- **`POST /api/review`** — the final, selected reconstruction-v2 architecture (GPT-5-mini + P0 +
  FULL NDA context). One requirement at a time, no confidence score, no history. Documented first,
  below.
- **`POST /review`** and its companions (`GET /review/{review_id}`, `GET /results`,
  `GET /cost-estimate`) — the earlier RAG + selective-agent pipeline (`pipeline/orchestrator.py`,
  T031). Restored as a real, working batch-review alternative (checkbox multi-select of the 17
  fixed hypotheses, self-reported confidence, agent escalation, SQLite-backed history) — not merely
  historical. See "Legacy batch-review endpoints" further down.

---

## `POST /api/review` — the final architecture's review endpoint

Reviews one confidentiality requirement against one NDA using the final frozen NDATrace pipeline.
**File:** `backend/routes/review.py` (`create_final_review`), `pipeline/final_review.py`
(`review_final`).

**Runtime path:**

```text
NDA + requirement
        |
input validation (Pydantic: both fields required, non-empty)
        |
openai/gpt-5-mini + GPT-P0 prompt + FULL NDA context   [pipeline/final_review.py]
        |
structured output parser   [evaluation/structured_output.py]
        |
runtime evidence-source validator v2   [pipeline/evidence_validator.py]
        |
reviewer-facing result
```

No retrieval, no agent, no routing — the full NDA text is sent to the model in one call. This
endpoint does not persist results anywhere; each call is a one-shot request/response with no
saved history (unlike the legacy `POST /review`, which does).

### Request body (`FinalReviewRequest`, `backend/models.py`)

| Field | Type | Required | Constraint |
|---|---|---|---|
| `nda_text` | string | yes | `min_length=1` |
| `requirement` | string | yes | `min_length=1`, free text (not restricted to the 17 fixed ContractNLI hypotheses) |

```json
{
  "nda_text": "Receiving Party shall not disclose Confidential Information to any third party without prior written consent of the Disclosing Party.",
  "requirement": "The Receiving Party must not disclose Confidential Information to third parties."
}
```

### Response 200 (`FinalReviewResponse`)

| Field | Type | Notes |
|---|---|---|
| `label` | `"Entailment" \| "Contradiction" \| "NotMentioned" \| null` | `null` only on a provider error or an unparseable model response (see "Error handling" below) |
| `evidence` | `list[string]` | Quotes the model claims are verbatim from `nda_text`; empty for `NotMentioned` |
| `explanation` | string | A fixed, deterministic one-line template keyed on `label` (not a model-generated claim) — see "Label semantics" |
| `source_valid` | `bool \| null` | `true` only if every string in `evidence` is a genuine verbatim (or formatting-normalized) substring of the submitted `nda_text`; `null` when there was nothing to validate (provider/parse failure) |
| `needs_human_review` | bool | `true` on a provider error, an unparseable model response, non-source-grounded evidence, or a label/evidence inconsistency (see below) |
| `review_reason` | `string \| null` | Set only when `needs_human_review` is `true`; explains which of the above triggered it |
| `model` | string | Always `"openai/gpt-5-mini"` for this endpoint |
| `latency_ms`, `input_tokens`, `output_tokens`, `estimated_cost_usd` | number or `null` | `null` only when the model call itself failed (no completion to measure) |
| `trace_id` | string (uuid) | Generated per request; logged alongside metadata (see "Security / privacy" below), not returned by any other endpoint |

There is **no `confidence` field** — GPT-P0 requests only `{label, evidence}` from the model, so no
calibrated confidence is fabricated.

```json
{
  "label": "Entailment",
  "evidence": ["Receiving Party shall not disclose Confidential Information to any third party"],
  "explanation": "The quoted clause(s) above support this requirement.",
  "source_valid": true,
  "needs_human_review": false,
  "review_reason": null,
  "model": "openai/gpt-5-mini",
  "latency_ms": 812.4,
  "input_tokens": 143,
  "output_tokens": 22,
  "estimated_cost_usd": 0.000041,
  "trace_id": "a3f1e6c2-9b4d-4e21-8f0a-2d6c1b7e5a90"
}
```

### Label semantics

- **`Entailment`** — the quoted clause(s) support the requirement.
- **`Contradiction`** — the quoted clause(s) conflict with the requirement.
- **`NotMentioned`** — "No explicit supporting or contradicting provision was identified in the
  agreement." This does **not** claim the NDA has been proven not to address the requirement
  anywhere — only that the model, given the full document, did not identify explicit language
  either way.

### Evidence validation

`source_valid` and `needs_human_review` are driven by `pipeline/evidence_validator.py`'s runtime
validator (v2), which checks only that each returned evidence string is a genuine occurrence in the
`nda_text` the model was given (exact substring, then a formatting-normalized fallback — NFC,
zero-width-character removal, whitespace collapse). This is **source-presence validation only**:

- It does **not** verify that the model interpreted the clause correctly — a verbatim quote can
  still support the wrong label.
- It does **not** use ContractNLI's gold evidence spans at runtime — this endpoint has no notion of
  gold labels; that only exists in offline evaluation (`evaluation/`), never in the live request
  path.
- A label/evidence inconsistency (`label == "NotMentioned"` but `evidence` is non-empty) also sets
  `needs_human_review = true`, independent of source-grounding.

### Error handling

- **`422 Unprocessable Entity`** — Pydantic validation failure: `nda_text` or `requirement` missing
  or empty (`min_length=1`).
- **A malformed/unparseable model response, non-source-grounded evidence, or a model-provider
  error (e.g. a transient API failure after retries) is NOT surfaced as an HTTP error** — the
  endpoint still returns `200` with `label: null` (or a low-trust label) and
  `needs_human_review: true` plus a `review_reason`, so a partial/uncertain result is never silently
  dropped.
- **`503 Service Unavailable`** — no model provider is configured (`OPENROUTER_API_KEY` missing).
  The route constructs the model gateway before calling `review_final()`; a construction failure
  there returns `{"detail": "Review service is not configured."}` — no environment variable names,
  key values, or stack trace are included in the response.

---

## `GET /experiments` — final TEST comparison

Reads `results/final/reconstruction_v2/full_test_comparison.csv` — the already-computed
Rule/Qwen/GPT-5-mini comparison on the identical n=2,091 official TEST population (E17/E17B).
Never recomputes a metric and does not read `results/runs/*.jsonl` (the pre-reconstruction
experiment log). **File:** `backend/routes/experiments.py`.

**Response 200** (`FinalTestResult[]`):
```json
[
  {
    "system": "rule",
    "n": 2091,
    "accuracy": 0.5901482544237207,
    "macro_f1": 0.47930265224634533,
    "joint": 0.5007173601147776,
    "entailment_recall": 0.3925619834710744,
    "contradiction_recall": 0.16818181818181818,
    "notmentioned_recall": 0.9047619047619048,
    "evidence_recall": 0.29292929292929293,
    "evidence_precision": 0.6083916083916084,
    "source_valid_quote_rate": null,
    "api_cost_usd": 0.0
  }
]
```

Three rows are returned: `rule`, `qwen_ctx16k` (local, free), and `gpt5mini_p0_full` (the final
selected architecture).

---

## Legacy batch-review endpoints

The earlier RAG + selective-agent pipeline (`pipeline/orchestrator.py`) is not the final, selected
architecture — but it's restored here as a real, working alternative flow, not just historical
record: batch-review multiple requirements in one call, with a self-reported confidence score and
selective-agent escalation, backed by SQLite history.

### `POST /review`

Runs the legacy pipeline (`pipeline/orchestrator.py`'s `review_document`) against a submitted NDA
and persists the result to SQLite. **File:** `backend/routes/review.py`.

**Request body** (`ReviewRequest`):
```json
{
  "nda_text": "string, required",
  "hypothesis_ids": ["nda-1", "nda-2"]   // optional; all 17 fixed hypotheses if omitted
}
```

**Response 200** (`ReviewResponse`):
```json
{
  "review_id": "uuid",
  "doc_id": "string (first 8 chars of review_id)",
  "created_at": "ISO 8601 timestamp",
  "results": [
    {
      "hypothesis_id": "string",
      "hypothesis_text": "string",
      "label": "Entailment | Contradiction | NotMentioned",
      "confidence": 0.0,
      "explanation": "string",
      "evidence": ["string", "..."],
      "agent_used": false,
      "agent_steps": 0,
      "cost_usd": 0.0,
      "latency_ms": 0.0,
      "error": null
    }
  ],
  "total_cost_usd": 0.0,
  "total_latency_ms": 0.0,
  "model": "google/gemini-2.5-flash-lite"
}
```

**Error responses:**
- `400` — one or more `hypothesis_ids` not found among the 17 fixed hypotheses.
- `503` — model gateway unavailable (no configured provider), or every hypothesis failed before any
  could be processed.

**Partial failure is not an error response.** `review_document()` isolates errors per hypothesis: if
one hypothesis (of up to 17) fails after retries are exhausted, that item in `results` has
`label: "NotMentioned"`, `confidence: 0.0`, and a non-null `error` string; every other hypothesis's
real result is still returned in the same 200 response.

### `GET /review/{review_id}`

Fetches a previously created legacy review from SQLite. **File:** `backend/routes/review.py`.

**Response 200:** same `ReviewResponse` shape as `POST /review`.

**Error responses:**
- `404` — no review with that ID.

### `GET /results`

Lists past reviews created via the legacy `POST /review` (SQLite-backed history — `POST /api/review`
does not write to this store). **File:** `backend/routes/results.py`.

**Query params:** `limit` (default 50, 1–500).

**Response 200:**
```json
[
  {
    "review_id": "uuid",
    "doc_id": "string",
    "created_at": "ISO 8601 timestamp",
    "num_requirements": 17,
    "total_cost_usd": 0.0,
    "model": "string"
  }
]
```

### `GET /cost-estimate`

Real, measured average cost per requirement for the legacy RAG+agent architecture, computed from
the `rag_agent` experiment record with the largest `sample_size` in `results/runs/*.jsonl`. Used by
the batch-review UI to show an estimated cost before a review is submitted. **File:**
`backend/routes/experiments.py`.

**Response 200:**
```json
{
  "avg_cost_per_requirement_usd": 0.000395,
  "source_experiment_id": "string",
  "source_sample_size": 2091,
  "model": "string"
}
```

**Error responses:**
- `404` — no `rag_agent` experiment record exists to estimate cost from.

---

## Shared / read-only endpoints

### `GET /health`

Liveness check. **File:** `backend/app.py`.

**Response 200:**
```json
{ "status": "ok" }
```

### `POST /extract-pdf`

Extracts plain text from an uploaded PDF (multipart form upload, field name `file`), for the
frontend to pre-fill the NDA text box before submitting to either review endpoint. **File:**
`backend/routes/review.py`.

**Response 200:**
```json
{ "text": "extracted plain text" }
```

**Error responses:**
- `400` — content-type is not `application/pdf`/`application/x-pdf`.
- `413` — file exceeds the 10MB size cap (`MAX_PDF_SIZE_BYTES`).
- `422` — PDF could not be parsed (`PdfExtractionError`).

### `GET /hypotheses`

Lists all 17 fixed ContractNLI confidentiality hypotheses — the checkbox picker for the legacy
batch `POST /review`, and suggested starting text for `POST /api/review`'s free-text `requirement`
field. **File:** `backend/routes/review.py`.

**Response 200:**
```json
[
  { "hypothesis_id": "nda-1", "short_description": "string", "hypothesis_text": "string" }
]
```

---

## Human authority

NDATrace is a reviewer aid, not legal advice, and does not approve or reject an NDA. Every result
is a checkable label plus cited evidence for a human reviewer to confirm or overrule; the human
reviewer remains the final authority in every case.

## Security / privacy notes

- No endpoint returns API keys, provider credentials, or any secret material.
- `POST /api/review`'s structured log entry (`pipeline/logging_config.py`) records only metadata —
  `trace_id`, model, label, parse/validation status, latency, token counts, cost, and error type —
  never the submitted `nda_text` or `evidence` text. NDA text is not intended to be written to
  normal request logs.
- CORS is currently permissive (`allow_origins=["*"]`) — acceptable for local demo use only. Running
  this against real confidential NDAs would require appropriate access and privacy controls (auth,
  restricted CORS, log redaction review) that are **not implemented** in this project (see the root
  `README.md`'s "Do Not Build" list — no SSO/RBAC/multi-tenancy is in scope).

## Local example

```bash
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{
    "nda_text": "Receiving Party shall not disclose Confidential Information to any third party without prior written consent of the Disclosing Party.",
    "requirement": "The Receiving Party must not disclose Confidential Information to third parties."
  }'
```
