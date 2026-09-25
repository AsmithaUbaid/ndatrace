# NDATrace API Documentation

Documents only the endpoints that actually exist in `backend/app.py` and `backend/routes/*.py`, as
CORS is currently permissive (`allow_origins=["*"]`) for local development — see
`backend/app.py`'s comment noting this should be tightened before any non-local deployment (not
done, since this project has no deployment target beyond local demo).

## `GET /health`

Liveness check. **File:** `backend/app.py`.

**Response 200:**
```json
{ "status": "ok" }
```

---

## `POST /review`

Runs the frozen production pipeline (`pipeline/orchestrator.py`'s `review_document`) against a
submitted NDA and persists the result to SQLite. **File:** `backend/routes/review.py`.

**Request body** (`ReviewRequest`, `backend/models.py`):
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
  could be processed (the provider is down entirely — this is distinct from a single hypothesis
  failing, see below).

**Partial failure is not an error response.** `review_document()` isolates errors per hypothesis
(fixed — see `docs/decisions.md` ADR-004's second bug finding): if one hypothesis (of up
to 17) fails after retries are exhausted, that item in `results` has `label: "NotMentioned"`,
`confidence: 0.0`, and a non-null `error` string; every other hypothesis's real result is still
returned in the same 200 response.

---

## `GET /review/{review_id}`

Fetches a previously created review from SQLite. **File:** `backend/routes/review.py`.

**Response 200:** same `ReviewResponse` shape as `POST /review`.

**Error responses:**
- `404` — no review with that ID.

---

## `POST /extract-pdf`

Extracts plain text from an uploaded PDF (multipart form upload, field name `file`), for the
frontend to pre-fill the NDA text box. **File:** `backend/routes/review.py`.

**Response 200:**
```json
{ "text": "extracted plain text" }
```

**Error responses:**
- `400` — content-type is not `application/pdf`/`application/x-pdf`.
- `413` — file exceeds the 10MB size cap (`MAX_PDF_SIZE_BYTES`, added as a real gap fix —
  no size limit existed at all before then; see `docs/decisions.md`'s WBS T040/K05 note).
- `422` — PDF could not be parsed (`PdfExtractionError`).

---

## `GET /hypotheses`

Lists all 17 fixed ContractNLI confidentiality hypotheses. **File:** `backend/routes/review.py`.

**Response 200:**
```json
[
  { "hypothesis_id": "nda-1", "short_description": "string", "hypothesis_text": "string" }
]
```

---

## `GET /results`

Lists past live reviews created via `POST /review` (SQLite-backed product usage history — distinct
from the offline experiment records below). **File:** `backend/routes/results.py`.

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

---

## `GET /experiments`

Lists offline experiment results from `results/runs/*.jsonl` (research/evaluation records, never
written by the live API — only read). **File:** `backend/routes/experiments.py`.

Reads only the **last** JSON record per file (files are append-only; a corrected/backfilled record
supersedes an earlier one in the same file — see `docs/evaluation_protocol.md`). Excludes
`checkpoint_*.jsonl` files (in-progress harness state, not finalized records).

**Response 200:**
```json
[
  {
    "experiment_id": "string",
    "experiment_name": "string",
    "model": "string",
    "split": "dev | test | null",
    "sample_size": 150,
    "accuracy": 0.88,
    "macro_f1": 0.858,
    "contradiction_recall": 0.857,
    "contradiction_recall_ci_low": 0.601,
    "contradiction_recall_ci_high": 0.96,
    "joint_label_evidence_correctness": 0.813,
    "total_cost_usd": 0.0216,
    "timestamp": "ISO 8601 timestamp"
  }
]
```

---

## `GET /experiments/{experiment_id}`

Fetches one experiment record by ID. **File:** `backend/routes/experiments.py`.

**Response 200:** same shape as one entry of `GET /experiments`.

**Error responses:**
- `404` — no experiment record with that ID.

---

## `GET /cost-estimate`

Real, measured average cost per requirement for the production architecture, computed from the
`rag_agent` experiment record with the largest `sample_size` on file (reasoning: a bigger sample
averages out per-case cost variance from agent escalation better than a small one). Used by the
frontend to show an estimated cost before a review is submitted. **File:**
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
