> **Historical planning document, written before implementation.** Some architecture choices, file
> paths, schedules, thresholds, and assumptions described below were superseded by later
> experiments — see the root `README.md`, `docs/architecture.md`, `docs/decisions.md`, and
> `docs/experiments.md` for the current state. This document is preserved unmodified below (aside
> from two inline historical-status annotations) as the real record of what was planned at project
> start; it is not authoritative for current status.

# NDATrace — Evidence-Grounded NDA Requirement Review
## Complete Project Planning Document
 
**Project:** NTU PE6201 Emerging AI Technologies — End-of-Course Project  
**Author:** Asmitha Ubaidulla  
**Date:** 20 September 2026  
**Status (as of original authoring, 20 Sep 2026):** GREENFIELD — No existing repository found. All
planning is from scratch. **This status is now historical** — the repository has since been built
out (pipeline/backend/frontend, dozens of completed experiments). For current status, see the root
`README.md` and `docs/decisions.md`, not this line.  
**Deadline:** 4 October 2026  
**Working days available:** 10 (Mon–Fri, 21 Sep – 2 Oct; weekends are buffer only)
 
---
 
# SECTION 0 — YOUR TWO QUESTIONS ANSWERED FIRST
 
## 0A — Experiments in Notebooks vs Final Architecture in Python Files
 
Here is how a real startup (and how you should) organise the relationship between experimental notebooks and production code:
 
**Phase 1: Exploration (Notebooks)**
You run experiments in Jupyter notebooks (`.ipynb`). Each notebook tests one hypothesis: "Does Oracle evidence give better accuracy than RAG retrieval?" or "What chunk size gives best Evidence Recall@K?" Notebooks are messy, exploratory, and disposable. They produce *results* (JSON files, CSV metrics) but the *code* in them is not production code.
 
**Phase 2: Proven Logic Extracted to Python Modules**
Once an experiment proves that a technique works (e.g., clause-aware chunking beats fixed-size), you extract the proven logic into a clean Python module:
```
notebooks/exp_05_chunking.ipynb  →  proved clause-aware chunking wins
pipeline/chunker.py              →  clean, tested, importable module
```
 
**Phase 3: Both Coexist**
The notebook *calls* the module. The API *calls* the same module. This means:
```
# In notebook:
from pipeline.chunker import clause_aware_chunk
chunks = clause_aware_chunk(nda_text, config)
 
# In FastAPI endpoint:
from pipeline.chunker import clause_aware_chunk
chunks = clause_aware_chunk(nda_text, config)
```
 
**The rule:** Notebooks are for *deciding*. Python modules are for *doing*. Results are *recorded* in JSON/JSONL files that never get overwritten.
 
**Your concrete workflow:**
```
1. Notebook explores  →  produces results/run_<id>.jsonl
2. You decide          →  "clause-aware chunking wins"
3. Extract to module   →  pipeline/chunker.py
4. Notebook now IMPORTS the module (no duplicated logic)
5. FastAPI IMPORTS the same module
6. Both produce results in the same schema
```
 
**Experiment trace:** Every run records a config snapshot (model, prompt version, chunk size, etc.) + results + cost. The notebook doesn't "disappear" — it stays as the *narrative explanation* of why you chose what you chose. Your professor can read the notebook to understand your reasoning, then look at `results/` to see the numbers, then look at `pipeline/` to see the clean code that the API uses.
 
## 0B — Structured JSON Logging with Request/Trace IDs
 
Build this from Day 1 as a thin utility module. It is ~50 lines of Python and pays for itself immediately in debugging.
 
**What you build now (prototype):**
```python
# pipeline/logging_config.py
import logging, json, uuid, time, contextvars
 
# Context variable: set once per request, visible everywhere in that request
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('request_id', default='no-request')
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('trace_id', default='no-trace')
 
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "request_id": request_id_var.get(),
            "trace_id": trace_id_var.get(),
            "component": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log)
```
 
**What you NEVER log:** Raw NDA text, prompts containing NDA text, API keys, user-uploaded file contents, gold labels during prediction.
 
**What you DO log:** request_id, trace_id, component name, stage (parsing/chunking/retrieval/classification/agent), latency_ms, token counts, cost estimate, error codes, model name, config hash.
 
**How this becomes production later (you don't build this now):**
- Replace `logging.FileHandler` → ship logs to Grafana Loki, Datadog, or CloudWatch
- Add OpenTelemetry spans around each pipeline stage
- Trace IDs become distributed trace IDs across services
- Same JSON structure, same field names — zero rewrite
**For your project:** Logs go to `logs/ndatrace.jsonl`. Each line is a JSON object. You can grep them, load them in pandas, or point a log viewer at them. The request_id links every log line from one user request together. The trace_id links a parent request to agent sub-calls.
 
---
 
# SECTION 1 — EXECUTIVE STRATEGY
 
## What Must Be Built
 
A modular Python AI pipeline that takes an NDA document and a confidentiality requirement, retrieves relevant clauses, classifies the requirement as Entailment / Contradiction / Not Mentioned, and shows the exact evidence supporting that classification. A FastAPI backend serves this pipeline. A Next.js frontend lets a legal operations analyst use it. Results and experiment records persist in SQLite.
 
## What Should Not Be Built
 
Kubernetes, multi-region deployment, enterprise SSO, complex RBAC, CI/CD pipelines, managed vector databases, Celery/Redis workers, microservices, model training, model fine-tuning, SOC 2 compliance, automatic NDA approval, support for contract types other than NDAs, or a full production observability platform.
 
## What Must Be Learned Experimentally
 
1. **Is the performance ceiling set by retrieval or by reasoning?** — The Oracle experiment answers this on Day 2.
2. **Which model gives the best quality-per-dollar?** — Oracle + model comparison answers this by Day 3.
3. **Does clause-aware chunking beat fixed-size?** — Retrieval experiments answer this by Day 4.
4. **Does the selective agent actually recover cases that RAG misses?** — Agent experiments answer this by Day 6.
5. **What confidence threshold balances coverage and accuracy?** — Abstention experiments answer this by Day 6.
6. **Is synchronous processing fast enough for a full 17-requirement NDA?** — Performance measurement answers this by Day 8.
## What Must Be Decided Early
 
1. **Model choice** — by end of Day 3 (Wed 24 Sep). If the Oracle ceiling is low, you need to switch models before building RAG on top of a weak reasoner.
2. **Budget allocation** — Day 1 task. Your professor flagged this: calculate projected API spend across all experiments before running them.
3. **Retrieval strategy** — by end of Day 4. Everything downstream depends on chunk quality.
## What the Final Prototype Should Contain
 
- Working document upload and parsing
- Requirement selection (ContractNLI hypotheses or free text)
- Evidence retrieval with clause-aware chunking
- Three-way classification with evidence display
- Confidence scoring and abstention
- Selective agent for hard cases (if justified by experiments)
- Latency, cost, and architecture display per request
- Experiment results browser
- Structured logging
- Reproducible evaluation on the held-out test set
## What Makes This More Than a Notebook Demo
 
- A real API with typed contracts (FastAPI + Pydantic)
- A real frontend (Next.js) that a non-technical user could navigate
- Persistent results that survive server restarts
- Error handling, timeouts, rate-limit retries
- Structured logging with trace IDs
- Reproducible experiments with configuration snapshots
- Progressive architecture comparison with cost analysis
## What Makes This Less Than Production
 
- Single-user (no auth, no multi-tenancy)
- SQLite not PostgreSQL (fine for prototype; would need migration)
- FAISS not a managed vector DB (fine for prototype)
- No CI/CD pipeline
- ContractNLI data only (not real company NDAs)
- No formal security audit
- No SLA, no HA, no disaster recovery
## Recommended Order of Work
 
```
Pre-Phase 0 (TODAY, Sun 20 Sep): Verify API key + balance. Curate 50 golden eval cases from ContractNLI (30 ordinary + 20 negative) + define 10 injection cases + define 10 system behaviour cases → freeze as expected_outcomes.json. These cases ARE the spec.
Day 1: Budget calc + dataset validation + evaluation harness + golden test battery loader
Day 2: Oracle experiment + rule baseline + full-context baseline
Day 3: Model comparison + prompt tuning → MODEL DECISION
Day 4: Retrieval experiments (chunking, embedding, top-K) → RETRIEVAL DECISION
Day 5: Standard RAG end-to-end + confidence/abstention
Day 6: Selective agent experiments → AGENT DECISION → ARCHITECTURE FREEZE
Day 7: FastAPI backend + persistence
Day 8: Frontend (Next.js target, Streamlit fallback if >1 day) + performance testing
Day 9: Final locked evaluation + reliability tests + documentation
Day 10: Demo prep + submission packaging + reproducibility test
```
 
## Largest Project Risks
 
1. **Budget exhaustion** — Your professor's #1 red flag. If you burn API budget on early experiments, you can't run final evaluation.
2. **Retrieval quality** — If chunking is poor, every downstream component suffers.
3. **Scope creep** — 21 sections of planning is already ambitious. Resist adding features.
4. **Frontend time sink** — Next.js can eat days. Keep it minimal.
5. **Late model switch** — If you discover on Day 5 that your model is weak, switching costs 2 days.
## Safest Path to Completion
 
Run Oracle experiment on Day 2. This one experiment tells you whether your model can reason at all (given perfect evidence). If Oracle accuracy is below 75%, switch models immediately — before building anything else on top. Then lock retrieval by Day 4, lock architecture by Day 6, and give yourself 4 full days for the product layer + final eval + packaging.
 
---
 
# SECTION 2 — CURRENT-STATE ASSESSMENT
 
**Status: GREENFIELD — No repository exists.** *(Historical — this was the real state on
20 Sep 2026, the day this section was written. Frozen as-is since it's the actual gap analysis
that drove the WBS. See `docs/decisions.md` for what has since been built.)*
 
All items below are "does not exist" with "N/A" for reusability. This table serves as the gap analysis.
 
| Area | Existing State | Reusable? | Problem/Gap | Required Action | Priority |
|---|---|---|---|---|---|
| Dataset handling | None | N/A | ContractNLI not downloaded, splits not validated | Download, validate schema, check NDA-level split isolation | P0 — Day 1 |
| Preprocessing | None | N/A | No chunking, no parsing pipeline | Build clause-aware chunker + fixed-size chunker for comparison | P0 — Day 4 |
| Baselines | None — problem statement showed one screenshot | Concept only | No majority-class, rule-based, or full-context baseline | Implement all three baselines | P0 — Day 2 |
| Oracle experiment | None | N/A | Professor's top priority — determines ceiling | Implement and run on dev set | P0 — Day 2 |
| Retrieval | None | N/A | No embedding pipeline, no FAISS index | Build embedding + indexing + retrieval pipeline | P0 — Day 4 |
| Models | None — GPT-5 mini mentioned in proposal | API key likely exists | No model gateway, no structured output parsing | Build model gateway with cost tracking | P0 — Day 2 |
| Prompts | None | N/A | No classification prompt, no explanation prompt | Design and version prompts | P0 — Day 2 |
| Evaluation | None | N/A | No metric implementations, no harness | Build eval harness with all required metrics | P0 — Day 1 |
| Agent | None | N/A | No agent framework, tools, or routing | Build only if experiments justify it | P0 — Day 6 |
| API | None | N/A | No FastAPI app | Build after architecture freeze | P1 — Day 7 |
| Frontend | None | N/A | No Next.js app | Build after backend works | P1 — Day 8 |
| Persistence | None | N/A | No database, no result storage | SQLite + JSONL for experiment results | P0 — Day 1 (JSONL), P1 — Day 7 (SQLite) |
| Testing | None | N/A | No tests at all | Unit tests for metrics + golden regression set | P0 — Day 1 (metric tests), P1 — Day 9 |
| Performance measurement | None | N/A | No latency/throughput tracking | Instrument pipeline stages | P1 — Day 8 |
| Cost tracking | None — proposal showed $0.001059 estimate | Cost model only | No actual per-call cost tracking | Track tokens + cost per request from Day 1 | P0 — Day 1 |
| Documentation | Problem statement + professor feedback | Reuse for README | No technical docs, no setup instructions | Write alongside code | P1 — Day 10 |
| Reproducibility | None | N/A | No environment files, no seed management | requirements.txt, .env.example, fixed seeds | P0 — Day 1 |
| Logging | None | N/A | No structured logging | Build JSON logger with request/trace IDs | P0 — Day 1 |
 
**Observed facts:** Only the professor's feedback and problem statement exist. The screenshot in the problem statement shows one successful RAG call but no repository was submitted with it.
 
**Assumption:** The student has an OpenRouter API key with some remaining budget. This must be verified on Day 1.
 
---
 
# SECTION 3 — SCOPE DEFINITION
 
## 1. Minimum Viable Academic Submission
 
- ContractNLI dataset loaded with leakage-safe splits
- Evaluation harness computing: accuracy, macro-F1, risk-sensitive recall, joint label+evidence correctness
- Rule-based keyword baseline results
- Full-context LLM baseline results
- Oracle experiment results (determines ceiling)
- Standard RAG pipeline with evidence retrieval
- Confidence threshold + abstention
- Results persisted in JSONL
- Final locked evaluation on held-out test set
- Reproducible environment (requirements.txt, .env.example, seeds)
- Architecture comparison table with cost/latency/quality
- Demo-ready (can run end-to-end for video)
## 2. Target Near-Production Prototype
 
Everything in (1), plus:
- FastAPI backend with Pydantic request/response contracts
- Next.js frontend with document upload, requirement selection, evidence display
- Selective agent (if experiments justify it)
- SQLite persistence for reviews and experiment records
- Structured JSON logging with request/trace IDs
- Per-stage latency and cost display
- Experiment results browser in frontend
- Docker Compose packaging
- Error handling: model timeouts, rate limits, invalid documents
- Golden regression test suite (12 cases)
## 3. Optional Stretch Features
 
- Hybrid retrieval (BM25 + dense)
- Reranking stage
- Hosted vs local model comparison
- Content-hash caching for embeddings/chunks
- PDF upload with OCR fallback
- Export results as CSV/JSON
- Concurrent request handling
## 4. Deferred Production Features
 
- PostgreSQL migration
- pgvector or Qdrant migration
- Redis caching layer
- Celery background workers
- OpenTelemetry distributed tracing → Grafana/Datadog
- Enterprise SSO / RBAC / multi-tenancy
- CI/CD pipeline
- Kubernetes deployment
- Real NDA support (beyond ContractNLI)
- Model fine-tuning
## 5. Explicit Non-Goals
 
- Legal advice or automatic NDA approval
- Model training or fine-tuning
- Other contract types (leases, employment agreements)
- Real confidential NDA processing
- SOC 2 / ISO certification
- Multi-region deployment
- Formal AI governance framework implementation
## Definition of "Near-Production Prototype"
 
A system is "near-production" for this project if it meets ALL of:
- Typed API contracts (not notebook-only)
- Real frontend (not Streamlit)
- Handles errors gracefully (no stack traces to users)
- Persists results across server restarts
- Runs reproducibly on another machine via documented setup
- Produces auditable experiment records
- Demonstrates the pipeline on at least one complete 17-requirement NDA review
- Shows measurable quality metrics against baselines
---
 
# SECTION 4 — KEY PRODUCT FLOWS
 
## Flow 1: Single Requirement Review
 
| Aspect | Detail |
|---|---|
| **Input** | NDA document (ContractNLI JSON or uploaded text) + one confidentiality requirement |
| **Processing** | Parse → Chunk → Embed → Retrieve top-K → Classify (Entailment/Contradiction/Not Mentioned) → Confidence check → If low confidence: route to agent or abstain → Generate explanation |
| **Output** | Label, confidence score, retrieved evidence spans with clause numbers, short explanation, latency, cost, architecture used |
| **Failure states** | Model timeout → retry once → return error with partial results; Model 429 → exponential backoff (max 3 retries) → return error; Invalid document → return validation error; Empty retrieval → flag as "insufficient evidence" |
| **Data persisted** | Prediction record (all fields from Section 19 schema), cost/latency record |
| **Acceptance criteria** | Returns valid JSON response within 30 seconds; label is one of three valid values; evidence field is non-empty for Entailment/Contradiction; confidence score is between 0 and 1 |
 
## Flow 2: Complete NDA Review (17 Requirements)
 
| Aspect | Detail |
|---|---|
| **Input** | One NDA document + all 17 ContractNLI hypotheses |
| **Processing** | Parse + chunk + embed + index ONCE → For each of 17 requirements: retrieve → classify → confidence check → agent if needed → explain |
| **Output** | Summary table: 17 rows with label, confidence, evidence preview, latency, cost. Aggregate stats: total time, total cost, abstention count, agent-routing count |
| **Failure states** | If one requirement fails, continue with remaining 16; mark failed requirement as "error" |
| **Data persisted** | All 17 prediction records, aggregate review record, total cost |
| **Acceptance criteria** | All 17 requirements produce a result (label or error); total time < 10 minutes; total cost < $0.50 |
 
## Flow 3: Standard RAG Success
 
| Aspect | Detail |
|---|---|
| **Input** | Parsed NDA chunks + requirement |
| **Processing** | Query formulation → Dense retrieval (FAISS) → Top-K evidence → LLM classification + explanation |
| **Output** | High-confidence label + matching evidence |
| **Failure states** | Low retrieval scores → route to agent or abstain |
| **Data persisted** | Retrieval scores, retrieved chunk IDs, classification result |
| **Acceptance criteria** | Confidence ≥ threshold AND retrieval score ≥ minimum AND valid structured output |
 
## Flow 4: Selective Agent Investigation
 
| Aspect | Detail |
|---|---|
| **Input** | Initial RAG result flagged as low-confidence / weak evidence / conflicting |
| **Processing** | Agent receives initial evidence + requirement → selects tools (search_clauses, find_defined_term, search_exceptions, etc.) → iterates with max 5 steps, max 3000 tokens, max 30 seconds → classify or abstain |
| **Output** | Updated label + additional evidence + agent trace (tools used, queries made, tokens consumed) |
| **Failure states** | Agent exceeds step/token/time limit → force-stop → return last best result or abstain; Agent loops (duplicate queries detected) → early-stop → abstain |
| **Data persisted** | Full agent trace, tool calls, token counts, decision at each step |
| **Acceptance criteria** | Agent terminates within bounds; trace is complete and parseable; no duplicate tool calls; result is classify or abstain (never "still investigating") |
 
## Flow 5: Abstention and Human Review
 
| Aspect | Detail |
|---|---|
| **Input** | Any classification result where confidence < threshold OR evidence is conflicting OR agent was unable to resolve |
| **Processing** | Mark as "Human Review Required" → display retrieved evidence anyway → explain why system is uncertain |
| **Output** | "Abstained" status + retrieved evidence + uncertainty reason + recommendation to review specific clauses |
| **Failure states** | None — abstention is itself the safe failure mode |
| **Data persisted** | Abstention flag, reason code, evidence retrieved but insufficient |
| **Acceptance criteria** | Abstention rate between 5% and 40% on dev set; abstained cases are disproportionately cases the system would have gotten wrong |
 
## Flow 6: Invalid or Unsupported Document
 
| Aspect | Detail |
|---|---|
| **Input** | Empty file, corrupt file, password-protected PDF, oversized file, unsupported format |
| **Processing** | Validate file type → validate file size (max 10MB) → attempt parsing → return specific error |
| **Output** | HTTP 422 with specific error message (e.g., "File is empty", "Unsupported format: .xlsx", "File exceeds 10MB limit") |
| **Failure states** | Parser crash on corrupt file → catch exception → return "Unable to parse document" |
| **Data persisted** | Error record with file metadata (name, size, type) — NOT file contents |
| **Acceptance criteria** | Never crashes on bad input; always returns a meaningful error message; never logs file contents |
 
## Flow 7: External Model Failure
 
| Aspect | Detail |
|---|---|
| **Input** | API call to LLM provider returns error (timeout, 500, invalid response) |
| **Processing** | Retry with exponential backoff (1s, 2s, 4s) up to 3 retries → if all fail, return error |
| **Output** | HTTP 503 with "Model service temporarily unavailable" |
| **Failure states** | All retries exhausted → error response; Invalid JSON from model → parse error → retry with instruction to use JSON |
| **Data persisted** | Error record with attempt count, error codes, latency of each attempt |
| **Acceptance criteria** | Retries don't exceed 3; total wait never exceeds 30 seconds; error message is user-friendly |
 
## Flow 8: Rate Limit or Timeout Failure
 
| Aspect | Detail |
|---|---|
| **Input** | API returns 429 (rate limited) or request exceeds timeout |
| **Processing** | 429: read Retry-After header → wait → retry (max 3 attempts). Timeout: cancel request → return partial results if available |
| **Output** | HTTP 429 with estimated retry time, or HTTP 504 with partial results |
| **Failure states** | Repeated 429s → stop processing → return error with "Provider rate limit exceeded" |
| **Data persisted** | Rate limit event with timestamp, retry count, wait time |
| **Acceptance criteria** | Never sends more requests after 3 consecutive 429s; timeout is configurable (default 30s) |
 
## Flow 9: Repeated/Cached Request
 
| Aspect | Detail |
|---|---|
| **Input** | Same NDA + same requirement as a previous request |
| **Processing** | (Phase 1 — no cache) Process normally. (Phase 2 — if cache implemented) Check content-hash cache → if hit: return cached result with "cached" flag → if miss: process normally and cache |
| **Output** | Same as normal result, with `cached: true` flag if from cache |
| **Failure states** | Cache corruption → ignore cache → process normally |
| **Data persisted** | Cache hit/miss event |
| **Acceptance criteria** | Cached results are identical to fresh results for same input+config; cache key includes config hash so different settings don't collide |
 
## Flow 10: Exporting or Reviewing Saved Results
 
| Aspect | Detail |
|---|---|
| **Input** | Request to view past review results or export them |
| **Processing** | Query SQLite for reviews by NDA, date, or status → return paginated results |
| **Output** | JSON array of review records, or CSV export |
| **Failure states** | Database unavailable → return cached results from JSONL files |
| **Data persisted** | N/A (read-only) |
| **Acceptance criteria** | Results load within 2 seconds; pagination works; export produces valid CSV/JSON |
 
---
 
# SECTION 5 — ARCHITECTURE OPTIONS
 
## Option 1: Synchronous Modular Monolith (RECOMMENDED)
 
One FastAPI process handles everything: HTTP requests, AI pipeline, persistence. The pipeline is modular (separate Python modules for parsing, chunking, retrieval, classification, agent) but runs in-process.
 
| Dimension | Assessment |
|---|---|
| Complexity | Low — one process, one codebase |
| Time to build | 2–3 days for backend |
| Local reproducibility | Excellent — `pip install` + `python -m uvicorn` |
| Scalability | Single-user fine; multi-user needs async or workers |
| Latency | No inter-process overhead; total = pipeline time |
| Failure handling | Simple try/catch; no distributed failure modes |
| Cost | Zero infrastructure cost |
| Deployment difficulty | Trivial — one Docker container |
| Academic deadline suitability | **Best** — minimum moving parts |
| Later productionisation | Add workers/queue when needed; pipeline modules are already separated |
 
## Option 2: Modular Monolith + Background Jobs (asyncio + in-process queue)
 
Same as Option 1, but full-NDA review (17 requirements) runs as a background task using Python's `asyncio` or a simple `BackgroundTasks` from FastAPI. Frontend polls for status.
 
| Dimension | Assessment |
|---|---|
| Complexity | Low-Medium — adds task tracking, polling endpoint |
| Time to build | 3–4 days for backend |
| Local reproducibility | Good — still one process |
| Scalability | Better for long-running NDA reviews |
| Latency | Same pipeline latency; user gets immediate "processing" response |
| Failure handling | Must handle task failure, partial completion |
| Cost | Zero infrastructure cost |
| Deployment difficulty | Trivial — one Docker container |
| Academic deadline suitability | Good — but adds complexity |
| Later productionisation | Replace in-process queue with Celery/Redis if needed |
 
## Option 3: Separated Services (FastAPI + separate worker process)
 
API server and AI pipeline run as separate processes communicating via Redis/RabbitMQ.
 
| Dimension | Assessment |
|---|---|
| Complexity | Medium-High — inter-process communication, message queue, two containers |
| Time to build | 5–6 days |
| Local reproducibility | Fair — needs Docker Compose, Redis |
| Scalability | Good — independent scaling |
| Latency | Adds queue overhead (50–200ms) |
| Failure handling | Complex — distributed failure modes |
| Cost | Redis server cost |
| Deployment difficulty | Moderate — Docker Compose with 3 containers |
| Academic deadline suitability | **Poor** — too much infrastructure for 10 days |
| Later productionisation | Already separated; add more workers easily |
 
## Recommendation: Option 1 (Synchronous Modular Monolith)
 
Start with Option 1. The AI pipeline modules are the same regardless — they're importable Python packages. The difference is only in how they're invoked.
 
**Upgrade trigger to Option 2:** If full-NDA review (17 requirements) takes > 3 minutes synchronously AND the frontend needs to remain responsive during processing. Measure this on Day 8. If needed, FastAPI's built-in `BackgroundTasks` provides a zero-dependency upgrade path.
 
**Experiments that would change this recommendation:**
- If 17-requirement NDA takes > 5 minutes → move to Option 2
- If concurrent users > 5 are required for demo → move to Option 2
- Never move to Option 3 for this project
---
 
# SECTION 6 — TARGET COMPONENT DESIGN
 
## Component Table
 
### 1. Web Frontend (Next.js + React + TypeScript)
 
| Aspect | Detail |
|---|---|
| Responsibility | User interface for uploading NDAs, selecting requirements, viewing results, browsing experiments |
| Inputs | User interactions: file upload, requirement selection, review history requests |
| Outputs | Rendered UI with classification results, evidence highlights, cost/latency metrics, experiment tables |
| Dependencies | Backend API (FastAPI) |
| Failure modes | API unreachable → show error banner; Slow response → show loading with progress |
| Needed for submission | Yes (target) — could fall back to minimal HTML if Next.js takes too long |
| Production only | Advanced features: saved views, team sharing, annotation interface |
 
### 2. API Layer (FastAPI + Pydantic)
 
| Aspect | Detail |
|---|---|
| Responsibility | HTTP endpoints for: review a requirement, review all requirements for an NDA, get past results, get experiment results, health check |
| Inputs | HTTP requests with JSON/multipart bodies |
| Outputs | JSON responses with typed Pydantic models |
| Dependencies | Review orchestration, result persistence |
| Failure modes | Invalid input → 422; Pipeline error → 500 with error detail; Rate limit → 429 |
| Needed for submission | Yes |
| Production only | Auth middleware, rate limiting, API versioning |
 
### 3. Review Orchestration
 
| Aspect | Detail |
|---|---|
| Responsibility | Coordinates the full pipeline: parse → chunk → retrieve → classify → confidence check → agent routing → persist |
| Inputs | Parsed NDA + requirement + config (which architecture to use) |
| Outputs | Complete review result with all metadata |
| Dependencies | All pipeline components |
| Failure modes | Any stage failure → catch, log, return partial result with error status |
| Needed for submission | Yes |
| Production only | Workflow engine, parallel requirement processing |
 
### 4. Document Parser
 
| Aspect | Detail |
|---|---|
| Responsibility | Extract text from ContractNLI JSON documents (and optionally uploaded PDFs/text files) |
| Inputs | Raw document (JSON from ContractNLI, or text/PDF upload) |
| Outputs | Structured text with clause boundaries, headings, definitions identified |
| Dependencies | None (leaf component) |
| Failure modes | Corrupt file → raise ParseError; Password-protected PDF → raise UnsupportedDocument |
| Needed for submission | Yes (ContractNLI JSON parsing); PDF parsing is stretch |
| Production only | OCR, multi-format support |
 
### 5. Chunker
 
| Aspect | Detail |
|---|---|
| Responsibility | Split parsed document into retrievable chunks, preserving clause structure |
| Inputs | Parsed document text |
| Outputs | List of chunks with metadata (clause number, section heading, position) |
| Dependencies | Document parser output |
| Failure modes | Very short document → return single chunk; Very long document → enforce max chunks |
| Needed for submission | Yes |
| Production only | ML-based segmentation |
 
### 6. Embedding / Indexing
 
| Aspect | Detail |
|---|---|
| Responsibility | Generate embeddings for chunks and build FAISS index |
| Inputs | List of text chunks |
| Outputs | FAISS index + embedding matrix + chunk-to-metadata mapping |
| Dependencies | Embedding model (sentence-transformers, runs locally) |
| Failure modes | OOM on very large NDA → reduce batch size; Model load failure → raise startup error |
| Needed for submission | Yes |
| Production only | Pre-computed index caching, incremental indexing |
 
### 7. Retriever
 
| Aspect | Detail |
|---|---|
| Responsibility | Given a requirement query, retrieve top-K most relevant chunks |
| Inputs | Requirement text + FAISS index + K |
| Outputs | Ranked list of (chunk, score, metadata) tuples |
| Dependencies | Embedding/indexing component |
| Failure modes | Empty index → return empty list with warning; All scores below minimum → flag as weak retrieval |
| Needed for submission | Yes |
| Production only | Hybrid retrieval (BM25 + dense), query expansion |
 
### 8. Optional Reranker
 
| Aspect | Detail |
|---|---|
| Responsibility | Re-score retrieved chunks using a cross-encoder model |
| Inputs | Query + candidate chunks |
| Outputs | Re-ranked chunks with new scores |
| Dependencies | Retriever output |
| Failure modes | Model failure → fall back to original ranking |
| Needed for submission | Only if experiments show significant improvement (P2) |
| Production only | Fine-tuned domain reranker |
 
### 9. Model Gateway
 
| Aspect | Detail |
|---|---|
| Responsibility | Unified interface to LLM providers (OpenRouter → GPT-5 mini, optionally local Llama). Handles retries, rate limits, token counting, cost tracking |
| Inputs | Prompt + model config |
| Outputs | Model response + token counts + latency + cost |
| Dependencies | OpenRouter API key |
| Failure modes | Timeout → retry; 429 → backoff + retry; 500 → retry; All retries fail → raise ModelError |
| Needed for submission | Yes |
| Production only | Multi-provider failover, load balancing |
 
### 10. Classifier
 
| Aspect | Detail |
|---|---|
| Responsibility | Construct classification prompt, parse structured output (label + evidence + explanation + confidence) |
| Inputs | Requirement + retrieved evidence chunks (or full context for baseline) |
| Outputs | ClassificationResult(label, confidence, evidence_ids, explanation) |
| Dependencies | Model gateway |
| Failure modes | Invalid JSON → retry with explicit JSON instruction; Label not in valid set → retry; Max retries exceeded → return error |
| Needed for submission | Yes |
| Production only | Ensemble classifiers, calibrated probabilities |
 
### 11. Evidence Validator
 
| Aspect | Detail |
|---|---|
| Responsibility | Check that cited evidence actually appears in retrieved chunks; flag hallucinated citations |
| Inputs | Classification result + retrieved chunks |
| Outputs | Validated result with unsupported_citation flag |
| Dependencies | Classifier output |
| Failure modes | All citations unsupported → flag as unreliable; Partial support → keep supported, flag others |
| Needed for submission | Yes |
| Production only | Semantic similarity validation, multi-hop verification |
 
### 12. Confidence / Abstention Component
 
| Aspect | Detail |
|---|---|
| Responsibility | Determine whether to accept the classification, route to agent, or abstain |
| Inputs | Classification result with confidence, retrieval scores, evidence validation result |
| Outputs | Decision: accept / route-to-agent / abstain |
| Dependencies | Classifier, evidence validator |
| Failure modes | Missing confidence score → default to abstain |
| Needed for submission | Yes |
| Production only | Calibrated confidence, multi-signal fusion |
 
### 13. Selective Agent Router
 
| Aspect | Detail |
|---|---|
| Responsibility | Manage agent execution with strict bounds: max steps, max tokens, max time, duplicate detection |
| Inputs | Initial RAG result + NDA chunks + requirement |
| Outputs | Agent result (improved classification or abstention) + complete trace |
| Dependencies | Agent tools, model gateway |
| Failure modes | Step limit → force-stop → return best result; Token limit → force-stop → abstain; Time limit → force-stop → abstain; Loop detection → early-stop → abstain |
| Needed for submission | Only if experiments justify agent (P0 experiment, P1 implementation) |
| Production only | Agent observability dashboard |
 
### 14. Agent Tools
 
| Aspect | Detail |
|---|---|
| Responsibility | Provide bounded search capabilities to the agent |
| Tools | search_clauses, retrieve_more_evidence, inspect_neighbouring_clauses, find_defined_term, search_exceptions, follow_cross_reference, reformulate_search_query |
| Inputs | Query/clause ID/term (varies by tool) |
| Outputs | Additional text chunks or definitions |
| Dependencies | Chunked document, FAISS index |
| Failure modes | No results found → return empty; Tool called with invalid args → return error message to agent |
| Needed for submission | Only if agent is justified |
| Production only | Additional tools, tool-use analytics |
 
### 15. Result Persistence
 
| Aspect | Detail |
|---|---|
| Responsibility | Store and retrieve experiment results and review records |
| Inputs | Prediction records, review results, experiment configs |
| Outputs | Stored records, query results |
| Dependencies | SQLite (product), JSONL (experiments) |
| Failure modes | Database locked → retry; Write failure → log error, continue serving |
| Needed for submission | Yes — JSONL for experiments from Day 1, SQLite for product on Day 7 |
| Production only | PostgreSQL migration |
 
### 16. Experiment Tracking
 
| Aspect | Detail |
|---|---|
| Responsibility | Record experiment configurations, results, and comparisons |
| Inputs | Run config + prediction results |
| Outputs | JSONL files per run, comparison tables |
| Dependencies | None (writes to filesystem) |
| Failure modes | Disk full → raise error (don't silently lose results) |
| Needed for submission | Yes |
| Production only | MLflow / Weights & Biases integration |
 
### 17. Cost / Latency Tracking
 
| Aspect | Detail |
|---|---|
| Responsibility | Record per-stage latency and per-call cost for every request |
| Inputs | Timer readings + token counts + pricing config |
| Outputs | CostLatencyRecord attached to each prediction |
| Dependencies | Model gateway (provides token counts) |
| Failure modes | Missing pricing config → log warning, estimate $0 |
| Needed for submission | Yes |
| Production only | Real-time cost dashboards |
 
### 18. Background Jobs
 
| Aspect | Detail |
|---|---|
| Responsibility | Process full-NDA reviews asynchronously if needed |
| Dependencies | Review orchestration |
| Needed for submission | Only if 17-requirement review exceeds 3 minutes synchronously |
| Decision point | Day 8 performance measurement |
 
### 19. Cache
 
| Aspect | Detail |
|---|---|
| Responsibility | Cache parsed documents, embeddings, and FAISS indexes |
| Dependencies | Parser, embedder, indexer |
| Needed for submission | Stretch feature — only if uncached performance is unacceptable |
| Decision point | Day 8 performance measurement |
 
---
 
# SECTION 7 — EXPERIMENT DEPENDENCY ORDER
 
## Stage 1: Dataset Validation (Day 1, first 2 hours)
 
- **Why now:** Everything depends on clean data. Finding corrupt documents or split leakage after building the pipeline wastes all downstream work.
- **Decision enabled:** Can we trust the dataset? Are splits document-level isolated?
- **Prevents wasting:** Building a pipeline on corrupted or leaking data.
- **Evidence required:** All 607 NDAs parse correctly; splits have zero document overlap; label distribution matches expected proportions.
- **Go/no-go:** If >5% of documents are corrupt, investigate before proceeding. If splits leak, re-split at document level.
## Stage 2: Evaluation Harness (Day 1, hours 3–6)
 
- **Why now:** You cannot measure any experiment without metrics. Build the ruler before measuring anything.
- **Decision enabled:** None directly — this is infrastructure.
- **Prevents wasting:** Running experiments whose results you can't interpret.
- **Evidence required:** Metric unit tests pass on synthetic data (hand-crafted examples with known correct results).
- **Go/no-go:** All metric unit tests pass. Harness can ingest prediction records and produce a comparison table.
## Stage 3: Budget Calculation (Day 1, hours 7–8)
 
- **Why now:** Professor's top red flag. You need to know if you can afford all planned experiments before running any.
- **Decision enabled:** How many API calls can you make? Which experiments must be run on dev-subset vs full dev set?
- **Prevents wasting:** Budget on experiments you can't afford to complete.
- **Evidence required:** Remaining API budget verified; cost per experiment estimated; total projected spend < 80% of budget.
- **Go/no-go:** If projected cost > budget, cut experiments (drop local model comparison first, then reduce dev set size).
## Stage 4: Rule Baseline (Day 2, hours 1–2)
 
- **Why now:** Cheapest possible baseline. Zero API cost. Sets the floor.
- **Decision enabled:** What accuracy can keywords alone achieve? (This is your lower bound.)
- **Prevents wasting:** Nothing — this is fast and free.
- **Evidence required:** Baseline scores on dev set.
- **Go/no-go:** Always proceed. Even if rule baseline is surprisingly good, you still need to test other approaches.
## Stage 5: Full-Context LLM Baseline (Day 2, hours 3–4)
 
- **Why now:** Tests the model's raw reasoning ability with all NDA text (no retrieval). Establishes the "throwing everything at the model" baseline.
- **Decision enabled:** How much does retrieval actually help vs just giving the model everything?
- **Prevents wasting:** Building complex retrieval if the model can handle full context well.
- **Evidence required:** Accuracy, macro-F1, per-class metrics, cost, latency on dev set.
- **Go/no-go:** If full-context accuracy > 85% and cost < $0.01/requirement, retrieval may not be necessary. (Unlikely — NDAs are long and exceed context windows.)
## Stage 6: Oracle Experiment (Day 2, hours 5–8)
 
- **Why now:** PROFESSOR'S #1 PRIORITY. Feed gold evidence directly to the model. This reveals the ceiling — if the model can't classify correctly even with perfect evidence, no retrieval improvement will help.
- **Decision enabled:** Is the ceiling set by retrieval or by reasoning?
- **Prevents wasting:** Days of retrieval tuning if the model itself is the bottleneck.
- **Evidence required:** Oracle accuracy, Oracle macro-F1, Oracle joint-correctness (should be ~100% for evidence since it's gold).
- **Go/no-go:** If Oracle accuracy < 75%, the model is too weak — switch models before proceeding. If Oracle accuracy > 90%, the model is strong and retrieval is the bottleneck — invest heavily in retrieval quality.
## Stage 7: Model Decision (Day 3)
 
- **Why now:** Oracle results reveal whether the model can reason. If not, switching models later costs 2+ days of rework.
- **Decision enabled:** Which model to use for all remaining experiments.
- **Prevents wasting:** Building RAG on a model that can't reason about legal text.
- **Evidence required:** Oracle accuracy comparison across 2–3 candidate models.
- **Go/no-go:** Choose the model with highest Oracle accuracy that fits budget. If no model exceeds 75% Oracle accuracy, increase abstention aggressively and document the limitation.
## Stage 8: Retrieval Experiments (Day 4)
 
- **Why now:** Model is locked. Now optimise what evidence the model sees.
- **Decision enabled:** Chunk strategy, embedding model, top-K value.
- **Prevents wasting:** RAG experiments with suboptimal retrieval.
- **Evidence required:** Evidence Recall@K, MRR, evidence precision across configurations.
- **Go/no-go:** Choose configuration with highest Evidence Recall@K above 70%. If no configuration achieves this, consider hybrid retrieval.
## Stage 9: Standard RAG End-to-End (Day 5, hours 1–4)
 
- **Why now:** Model locked + retrieval locked = can build the full RAG pipeline.
- **Decision enabled:** Does RAG outperform full-context baseline?
- **Prevents wasting:** Agent experiments if RAG already performs well enough.
- **Evidence required:** RAG vs full-context vs rule-baseline comparison on all metrics.
- **Go/no-go:** If RAG outperforms full-context on joint label+evidence correctness, proceed with RAG. If RAG is worse, revisit retrieval.
## Stage 10: Confidence and Abstention (Day 5, hours 5–8)
 
- **Why now:** RAG pipeline exists. Now calibrate when to trust it.
- **Decision enabled:** Confidence threshold, abstention rate.
- **Prevents wasting:** Agent investigations on cases the system should have abstained on.
- **Evidence required:** Accuracy-coverage curve, abstention effectiveness, unsafe non-abstention rate.
- **Go/no-go:** Set threshold where unsafe non-abstention rate < 10%. If this requires abstaining on > 40% of cases, revisit retrieval or prompt.
## Stage 11: Selective Agent (Day 6)
 
- **Why now:** RAG + abstention baseline exists. Now test if the agent adds value.
- **Decision enabled:** Include or exclude agent from final architecture.
- **Prevents wasting:** N/A — this is the last experiment.
- **Evidence required:** Agent recovery rate > 30%, agent regression rate < 10%, cost per recovered case < $0.05.
- **Go/no-go:** Include agent if recovery rate > regression rate AND cost is justified. Otherwise, discard agent and use RAG + abstention only.
## Stage 12: Architecture Freeze (Day 6 end)
 
- **Why now:** All experiments complete. Lock the architecture.
- **Decision enabled:** Final architecture selection.
- **Prevents wasting:** Building a product on an architecture that might change.
- **Evidence required:** Completed scorecard (Section 12) comparing all tested architectures.
- **Go/no-go:** Choose highest-scoring architecture that passes all hard gates. Document decision.
## Stage 13: Performance Tests (Day 8)
 
- **Why now:** Backend is built (Day 7). Now measure real performance.
- **Decision enabled:** Whether to add background jobs, caching.
- **Prevents wasting:** Premature optimisation.
- **Evidence required:** Single-request latency, 17-requirement NDA latency, memory usage.
- **Go/no-go:** If 17-requirement NDA < 3 minutes, stay synchronous. If > 3 minutes, add BackgroundTasks.
## Stage 14: Final Locked Evaluation (Day 9)
 
- **Why now:** Architecture frozen, product built, nothing else will change.
- **Decision enabled:** Final reported numbers.
- **Prevents wasting:** N/A — this is the final measurement.
- **Evidence required:** All metrics on held-out test set. Run once. Report as-is.
- **Go/no-go:** Report the numbers regardless. Do not re-tune based on test set results.
---
 
# SECTION 8 — COMPLETE EXPERIMENT REGISTER
 
## A. Dataset and Harness Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A01 | Data | Schema validation | Are all 607 NDAs parseable? | >99% parse correctly | — | — | All | 1 | Parse success rate | 0 / 0 | $0 | 15 min | validation_report.json | Proceed with dataset | P0 |
| A02 | Data | Missing/corrupt data | Any missing labels, empty docs? | <1% corrupt | — | — | All | 1 | Corrupt count | 0 / 0 | $0 | 10 min | data_quality.json | Data cleaning needs | P0 |
| A03 | Data | Duplicate/near-dup detection | Any duplicate NDAs? | <2% duplicates | — | — | All | 1 | Duplicate pairs | 0 / 0 | $0 | 10 min | duplicate_report.json | Dedup if needed | P0 |
| A04 | Data | NDA-level leakage test | Do any NDAs appear in both dev and test? | Zero overlap | — | — | Dev+Test | 1 | Overlap count | 0 / 0 | $0 | 5 min | leakage_report.json | Split safety | P0 |
| A05 | Data | Label distribution | What is the class balance? | Not Mentioned is majority | — | — | All splits | 1 | Class counts, proportions | 0 / 0 | $0 | 5 min | label_dist.json | Majority baseline, stratification | P0 |
| A06 | Data | Evidence span validation | Are gold evidence spans valid text ranges? | >99% valid | — | — | All | 1 | Invalid span count | 0 / 0 | $0 | 10 min | evidence_validation.json | Gold evidence reliability | P0 |
| A07 | Data | Document token-length analysis | How many tokens per NDA? | Median ~3K tokens, some >8K | — | — | All | 1 | Min/max/mean/median/p95 token counts | 0 / 0 | $0 | 15 min | token_analysis.json | Context window needs, cost estimates | P0 |
| A08 | Harness | Metric unit tests | Do metric functions compute correctly? | All pass on synthetic data | — | — | Synthetic | 1 | Test pass rate | 0 / 0 | $0 | 30 min | test_results.json | Harness reliability | P0 |
| A09 | Harness | Run resumption | Can a crashed run resume from last checkpoint? | Yes | — | — | Dev subset | 1 | Resume success | 0 / 0 | $0 | 20 min | resume_test.json | Experiment reliability | P0 |
| A10 | Harness | Append-only storage | Are results never overwritten? | Unique run IDs, no overwrites | — | — | Dev subset | 1 | Overwrite count = 0 | 0 / 0 | $0 | 10 min | storage_test.json | Result integrity | P0 |
| A11 | Harness | Config snapshot | Is full config saved with each run? | Every run has config JSON | — | — | Dev subset | 1 | Config present rate | 0 / 0 | $0 | 5 min | config_test.json | Reproducibility | P0 |
| A12 | Harness | Random-seed reproducibility | Same seed → same results? | Yes for deterministic parts | Fixed seed | — | Dev subset | 2 | Result equality | 0 / 0 | $0 | 10 min | seed_test.json | Reproducibility | P1 |
| A13 | Harness | Deterministic preprocessing | Same NDA → same chunks? | Yes | — | — | Dev subset | 2 | Chunk equality | 0 / 0 | $0 | 5 min | preproc_test.json | Pipeline reliability | P0 |
 
## B. Baseline Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B01 | Baseline | Majority-class baseline | What does always-predict-majority get? | ~40-50% accuracy, 0 F1 on minority classes | — | — | Dev | 1 | Accuracy, macro-F1, per-class | 0 / 0 | $0 | 5 min | majority_baseline.json | Lower bound | P0 |
| B02 | Baseline | Rule-based keyword baseline | Can keywords match clauses to requirements? | 30-50% accuracy | Keyword lists per hypothesis | — | Dev | 1 | Accuracy, macro-F1, retrieval recall, joint | 0 / 0 | $0 | 2 hr | rule_baseline.json | Non-AI baseline | P0 |
| B03 | Baseline | Full-context LLM | Model sees entire NDA + hypothesis | 60-75% accuracy | Model, prompt | Temperature=0 | Dev | 1 | All classification + cost/latency metrics | ~500 / ~2M | ~$1.50 | 2 hr | fullcontext_baseline.json | Is retrieval needed? | P0 |
| B04 | Baseline | Oracle-evidence LLM | Model sees gold evidence + hypothesis | >85% accuracy | Model, prompt | Temperature=0, gold evidence | Dev | 1 | All classification metrics (evidence metrics are trivially perfect) | ~500 / ~300K | ~$0.50 | 1 hr | oracle_baseline.json | **Ceiling: retrieval vs reasoning** | P0 |
 
## C. Model Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C01 | Model | Candidate model comparison | Which model has highest Oracle accuracy? | GPT-5 mini is best value | Model (GPT-5 mini, GPT-4.1 mini, Claude Sonnet) | Oracle evidence, same prompt | Dev subset (100) | 1 each | Oracle accuracy, macro-F1, cost | ~300 / ~200K | ~$1.00 | 2 hr | model_comparison.json | Model selection | P0 |
| C02 | Model | Hosted vs local | Does Llama 3.2 3B match hosted model? | No — too small for legal reasoning | Model (Llama vs GPT-5 mini) | Oracle evidence, same prompt | Dev subset (100) | 1 | Oracle accuracy, latency | ~100 / ~100K local | ~$0 local | 2 hr | hosted_vs_local.json | Whether local model is viable | P2 |
| C03 | Model | Zero-shot vs few-shot | Do examples help? | Few-shot improves 3-5% | Shot count (0, 2, 4) | Selected model | Dev subset (100) | 1 each | Accuracy, macro-F1 | ~300 / ~250K | ~$0.50 | 1.5 hr | fewshot_comparison.json | Prompt design | P0 |
| C04 | Model | Prompt variants | Which prompt structure works best? | Structured > unstructured | Prompt template (3 variants) | Selected model, zero-shot | Dev subset (100) | 1 each | Accuracy, macro-F1, valid JSON rate | ~300 / ~200K | ~$0.50 | 1.5 hr | prompt_comparison.json | Prompt selection | P0 |
| C05 | Model | Structured JSON output | Does forcing JSON output maintain quality? | <2% accuracy drop | JSON mode on/off | Selected model+prompt | Dev subset (100) | 1 each | Accuracy, valid output rate | ~200 / ~150K | ~$0.30 | 1 hr | json_output.json | Output format | P0 |
| C06 | Model | Temperature=0 consistency | Are results deterministic at temp=0? | >98% identical across runs | — | Temp=0, selected model | Dev subset (50) | 3 | Agreement rate | ~150 / ~100K | ~$0.20 | 45 min | temp_consistency.json | Reproducibility | P1 |
| C07 | Model | Not Mentioned behaviour | How does model handle absent evidence? | Tends to hallucinate entailment | Not Mentioned cases only | Selected model+prompt | Dev subset (NM cases) | 1 | NM precision, NM recall | ~100 / ~70K | ~$0.15 | 30 min | not_mentioned.json | Prompt tuning for NM | P0 |
| C08 | Model | Negation/exception handling | Can model handle "except" and "provided that"? | Lower accuracy on exception cases | Cases with exceptions | Selected model | Dev subset | 1 | Accuracy on exception cases | ~50 / ~40K | ~$0.10 | 30 min | exception_handling.json | Prompt improvements | P1 |
| C09 | Model | Explanation faithfulness | Do explanations match retrieved evidence? | >80% faithful | — | Selected model | Dev subset (50) | 1 | Faithfulness rate (manual + automatic) | ~50 / ~60K | ~$0.15 | 1 hr | explanation_faith.json | Explanation quality | P1 |
| C10 | Model | Explanation-length vs cost | How much do explanations cost? | 40-60% of output tokens | Explanation max length (50, 100, 200 tokens) | Selected model | Dev subset (50) | 1 each | Explanation tokens %, cost breakdown | ~150 / ~100K | ~$0.30 | 45 min | explanation_cost.json | Token budget allocation | P0 |
 
## D. Retrieval Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D01 | Retrieval | Clause-aware vs fixed chunking | Does respecting clause boundaries help? | +10-15% Evidence Recall | Chunking method | Same embeddings, K=5 | Dev | 1 | Evidence Recall@K, MRR | 0 (local) | $0 | 1.5 hr | chunking_comparison.json | Chunk strategy | P0 |
| D02 | Retrieval | Chunk size | Optimal chunk size? | 256-512 tokens | Size (128, 256, 512, 1024) | Clause-aware, same embeddings | Dev | 1 | Evidence Recall@K, MRR | 0 (local) | $0 | 1 hr | chunksize.json | Chunk size | P0 |
| D03 | Retrieval | Chunk overlap | Does overlap help? | Yes, 50-token overlap | Overlap (0, 25, 50) | Best chunk size | Dev | 1 | Evidence Recall@K | 0 (local) | $0 | 30 min | overlap.json | Overlap setting | P1 |
| D04 | Retrieval | Heading/clause preservation | Does keeping headings in chunks help? | +5% Evidence Recall | Heading inclusion on/off | Best chunking | Dev | 1 | Evidence Recall@K | 0 (local) | $0 | 30 min | heading_preservation.json | Chunk metadata | P1 |
| D05 | Retrieval | Definition attachment | Should defined terms be appended to chunks? | +3-5% on definition-dependent cases | Definition attachment on/off | Best chunking | Dev | 1 | Evidence Recall@K on definition cases | 0 (local) | $0 | 30 min | definition_attach.json | Chunk enrichment | P2 |
| D06 | Retrieval | Dense retrieval baseline | What does all-mpnet-base-v2 achieve? | Evidence Recall@5 ~60-70% | — | Best chunking, K=5 | Dev | 1 | Evidence Recall@K, MRR, precision | 0 (local) | $0 | 30 min | dense_retrieval.json | Retrieval baseline | P0 |
| D07 | Retrieval | Top-K comparison | What K balances recall and noise? | K=5 is optimal | K (3, 5, 7, 10) | Best chunking, same embeddings | Dev | 1 | Evidence Recall@K, downstream accuracy when fed to LLM | ~200 / ~200K (for downstream) | ~$0.40 | 1 hr | topk_comparison.json | K selection | P0 |
| D08 | Retrieval | BM25 | Does keyword retrieval have value? | Useful for exact legal terms | — | Best chunking | Dev | 1 | Evidence Recall@K, MRR | 0 (local) | $0 | 30 min | bm25.json | Hybrid retrieval value | P1 |
| D09 | Retrieval | Hybrid (BM25 + dense) | Does combining help? | +5-10% Evidence Recall over dense alone | Fusion weight (0.3, 0.5, 0.7) | Best chunking | Dev | 1 | Evidence Recall@K, MRR | 0 (local) | $0 | 1 hr | hybrid_retrieval.json | Retrieval upgrade | P1 |
| D10 | Retrieval | Embedding model comparison | Is all-mpnet-base-v2 optimal? | It is good enough | Models (mpnet, e5-base, bge-base) | Best chunking, K=5 | Dev | 1 | Evidence Recall@K | 0 (local) | $0 | 1.5 hr | embedding_comparison.json | Embedding choice | P1 |
| D11 | Retrieval | Reranking | Does a cross-encoder reranker help? | +5% Evidence Recall | Reranker on/off | Best retrieval config | Dev | 1 | Evidence Recall@K, reranking latency | 0 (local) | $0 | 1 hr | reranking.json | Whether to add reranker | P2 |
| D12 | Retrieval | Query formulation | Does reformulating the hypothesis improve retrieval? | +3-5% Evidence Recall | Query type (raw hypothesis, expanded, decomposed) | Best retrieval | Dev subset (100) | 1 | Evidence Recall@K | 0 (local) or ~100 calls for LLM expansion | ~$0.10 | 1 hr | query_formulation.json | Query strategy | P1 |
 
## E. End-to-End Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E01 | E2E | Rule baseline E2E | Complete rule baseline performance | Weakest architecture | — | — | Dev | 1 | All metrics | 0 / 0 | $0 | (from B02) | e2e_rule.json | Floor | P0 |
| E02 | E2E | Full-context E2E | Complete full-context performance | Moderate, expensive | — | — | Dev | 1 | All metrics | (from B03) | (from B03) | (from B03) | e2e_fullcontext.json | Baseline comparison | P0 |
| E03 | E2E | Standard dense RAG E2E | Complete RAG performance | Best quality/cost trade-off | — | Best retrieval, best model | Dev | 1 | All metrics inc. joint label+evidence | ~500 / ~500K | ~$1.00 | 2 hr | e2e_rag.json | RAG value | P0 |
| E04 | E2E | Hybrid RAG E2E | Does hybrid retrieval improve E2E? | +3-5% joint correctness | Hybrid vs dense retrieval | — | Dev | 1 | All metrics | ~500 / ~500K | ~$1.00 | 2 hr | e2e_hybrid_rag.json | Hybrid value | P1 |
| E05 | E2E | RAG + reranker E2E | Does reranker improve E2E? | Marginal improvement | Reranker on/off | Best RAG | Dev | 1 | All metrics | ~500 / ~500K | ~$1.00 | 2 hr | e2e_reranker.json | Reranker value | P2 |
| E06 | E2E | RAG + agent E2E | Does agent improve E2E on hard cases? | +5-10% recovery on agent-routed cases | Agent on/off | Best RAG + abstention | Dev | 1 | All metrics + agent-specific metrics | ~700 / ~700K | ~$1.50 | 3 hr | e2e_agent.json | Agent value | P0 |
| E07 | E2E | Architecture ablation | Which layer adds most value? | Each layer progressively adds value | Architecture (rule→full-context→RAG→RAG+agent) | — | Dev | 1 | Comparative table | (from above) | (from above) | — | architecture_ablation.json | Final selection | P0 |
| E08 | E2E | Joint label+evidence | What is the joint correctness? | 15-25% lower than label accuracy | — | — | Dev | 1 | Joint correctness metric | (from above) | (from above) | — | joint_correctness.json | **Professor's key metric** | P0 |
| E09 | E2E | Per-class error analysis | Where does the system fail? | Contradiction has lowest recall | — | — | Dev | 1 | Per-class precision/recall/F1 | (from above) | (from above) | — | per_class_errors.json | Error understanding | P0 |
| E10 | E2E | Cost/latency comparison | What does each architecture cost? | Agent adds 50-100% cost on routed cases | — | — | Dev | 1 | Cost per requirement, p50/p95 latency | (from above) | (from above) | — | cost_latency_comparison.json | Cost justification | P0 |
 
## F. Confidence and Abstention Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F01 | Conf | Self-reported confidence | Does model's own confidence predict correctness? | Moderate correlation (AUROC ~0.7) | — | Best RAG | Dev | 1 | AUROC, calibration curve | (from E03) | $0 (reuse) | 30 min | self_confidence.json | Confidence signal | P0 |
| F02 | Conf | Retrieval-score confidence | Does top retrieval score predict correctness? | Low-retrieval-score → more errors | — | Best RAG | Dev | 1 | AUROC on retrieval score | (from E03) | $0 (reuse) | 20 min | retrieval_confidence.json | Multi-signal confidence | P0 |
| F03 | Conf | Evidence-sufficiency signal | Does amount of retrieved evidence predict correctness? | Fewer chunks → less accurate | Chunk count threshold | Best RAG | Dev | 1 | Accuracy by retrieval quantity | (from E03) | $0 (reuse) | 20 min | evidence_sufficiency.json | Routing decisions | P1 |
| F04 | Conf | Threshold sweep | What threshold optimises accuracy-coverage trade-off? | Optimal between 0.6-0.8 | Threshold (0.5 to 0.95, step 0.05) | Best RAG | Dev | 1 | Selective accuracy, coverage, abstention rate | (from E03) | $0 (reuse) | 30 min | threshold_sweep.json | Threshold selection | P0 |
| F05 | Conf | Abstention effectiveness | Are abstained cases actually harder? | >70% of abstained cases would be wrong | Best threshold | Best RAG | Dev | 1 | Abstention effectiveness, unsafe non-abstention rate | (from E03) | $0 (reuse) | 15 min | abstention_effectiveness.json | Abstention quality | P0 |
| F06 | Conf | Accuracy vs coverage | Pareto frontier of quality vs coverage | — | Threshold range | Best RAG | Dev | 1 | Accuracy-coverage curve | (from E03) | $0 (reuse) | 15 min | accuracy_coverage.json | Trade-off visualisation | P0 |
| F07 | Conf | Multi-signal fusion | Does combining confidence signals improve routing? | +5% AUROC over single signal | Signal combination method | Best RAG | Dev | 1 | AUROC, abstention effectiveness | (from E03) | $0 (reuse) | 1 hr | multi_signal.json | Signal engineering | P1 |
| F08 | Conf | Calibration | Is reported confidence calibrated? | Overconfident by 10-15% | — | Best RAG | Dev | 1 | Expected calibration error | (from E03) | $0 (reuse) | 30 min | calibration.json | Confidence display | P1 |
 
## G. Agent Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G01 | Agent | Agent vs no-agent | Does agent improve over RAG + abstention? | +10-20% recovery on routed cases | Agent on/off | Best RAG + threshold | Dev (routed cases only) | 1 | Recovery rate, regression rate | ~200 / ~300K | ~$0.80 | 2 hr | agent_vs_noagent.json | **Agent inclusion** | P0 |
| G02 | Agent | Trigger-rule comparison | Which routing rule works best? | Confidence-based is best | Trigger rule (confidence, retrieval score, combined) | Agent with best tools | Dev | 1 | Recovery rate by trigger | ~300 / ~400K | ~$1.00 | 2 hr | trigger_rules.json | Routing strategy | P0 |
| G03 | Agent | Tool ablation | Which tools does the agent actually use? | search_clauses and find_defined_term most useful | Tools available | — | Dev (routed cases) | 1 | Tool usage frequency, recovery per tool | ~200 / ~300K | ~$0.80 | 1.5 hr | tool_ablation.json | Tool set | P1 |
| G04 | Agent | Max-step comparison | How many steps does agent need? | 3-5 steps sufficient | Max steps (3, 5, 7, 10) | — | Dev (routed cases) | 1 | Recovery rate, cost, latency by step limit | ~400 / ~500K | ~$1.20 | 2 hr | step_comparison.json | Step budget | P0 |
| G05 | Agent | Token-budget comparison | How many tokens does agent need? | 2000-3000 sufficient | Token budget (1K, 2K, 3K, 5K) | — | Dev (routed cases) | 1 | Recovery rate, cost by budget | ~400 / ~500K | ~$1.20 | 2 hr | token_budget.json | Token budget | P1 |
| G06 | Agent | Duplicate-query prevention | Does duplicate detection prevent loops? | Reduces wasted calls by 20% | Dedup on/off | — | Dev (routed cases) | 1 | Duplicate query rate, loop rate | (from G01) | $0 (reuse) | 30 min | dedup.json | Loop prevention | P1 |
| G07 | Agent | Agent regression analysis | Does agent make previously correct cases wrong? | <5% regression rate | — | — | Dev | 1 | Regression rate, regression cases | (from G01) | $0 (reuse) | 30 min | regression_analysis.json | Risk assessment | P0 |
| G08 | Agent | Cost per recovered case | Is agent recovery cost-effective? | <$0.05 per recovered case | — | — | Dev | 1 | Cost/case, latency/case | (from G01) | $0 (reuse) | 15 min | agent_cost.json | Cost justification | P0 |
 
## H. API and Performance Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H01 | Perf | Single-request latency | How fast is one requirement? | <15 seconds | — | Final architecture | 1 case | 10 | p50/p90/p95 latency | ~10 / ~10K | ~$0.02 | 15 min | single_latency.json | Latency baseline | P1 |
| H02 | Perf | Per-stage latency | Where does time go? | LLM call is 60-80% | — | Final architecture | 1 case | 5 | Parse/chunk/retrieve/classify/explain time | ~5 / ~5K | ~$0.01 | 15 min | stage_latency.json | Optimisation targets | P1 |
| H03 | Perf | Full-NDA 17-req time | How long for a full NDA? | 2-5 minutes | — | Final architecture | 1 NDA | 3 | Total time, per-req time | ~51 / ~50K | ~$0.10 | 30 min | full_nda_latency.json | **Background job decision** | P1 |
| H04 | Perf | Concurrent users (1, 5, 10) | Does it handle concurrent load? | Degrades gracefully to 5 | Concurrency (1, 5, 10) | Final architecture | 1 case per user | 1 each | p50/p95, error rate, throughput | ~50 / ~50K | ~$0.10 | 30 min | concurrency.json | Scaling needs | P2 |
| H05 | Perf | Memory usage | How much RAM? | <2GB | — | Final architecture | Full NDA | 1 | Peak RSS | 0 / 0 | $0 | 10 min | memory.json | Resource requirements | P1 |
| H06 | Perf | Provider rate limits | How close are we to limits? | Well within at single-user | — | Final architecture | Burst of 17 reqs | 1 | 429 rate, actual RPM | ~17 / ~17K | ~$0.03 | 10 min | rate_limits.json | Rate limit handling | P1 |
| H07 | Perf | Worst-case all-agent | What if every requirement triggers agent? | 5-10 minutes, $0.50+ | — | Final architecture + agent | 1 NDA, all routed | 1 | Total time, total cost | ~120 / ~200K | ~$0.50 | 15 min | worst_case_agent.json | Cost ceiling | P1 |
 
## I. Cache Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| I01 | Cache | Embedding cache | Does caching embeddings save time? | Yes, saves 30-50% on re-index | Cache on/off | — | 1 NDA | 2 | Index time with/without cache | 0 / 0 | $0 | 20 min | embed_cache.json | Cache value | P2 |
| I02 | Cache | Identical-request cache | Same request → same result without LLM call? | Yes | Cache on/off | — | 1 case | 2 | Latency with/without cache | 0 / 0 | $0 | 10 min | request_cache.json | Cache value | P2 |
| I03 | Cache | Cache invalidation | Does config change invalidate correctly? | Yes | Config change | — | 1 case | 2 | Stale cache detection | 0 / 0 | $0 | 15 min | cache_invalidation.json | Cache correctness | P2 |
 
## J. Reliability and Failure-Injection Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| J01 | Reliability | Model timeout | Does system handle model timeout? | Returns error within 35s | Simulated timeout | — | — | 3 | Recovery time, error message quality | 0 / 0 | $0 | 15 min | timeout_test.json | Error handling | P1 |
| J02 | Reliability | Model 429 | Does system handle rate limit? | Retries with backoff | Simulated 429 | — | — | 3 | Retry count, recovery success | 0 / 0 | $0 | 15 min | ratelimit_test.json | Rate limit handling | P1 |
| J03 | Reliability | Invalid JSON from model | Does system handle malformed response? | Retries with JSON instruction | Simulated bad JSON | — | — | 3 | Recovery rate | 0 / 0 | $0 | 15 min | invalid_json_test.json | Output parsing | P1 |
| J04 | Reliability | Empty model response | Does system handle empty response? | Retries once, then errors | Simulated empty | — | — | 3 | Recovery rate | 0 / 0 | $0 | 10 min | empty_response_test.json | Edge case handling | P1 |
| J05 | Reliability | Parser failure | Does corrupt PDF error gracefully? | Returns 422 with message | Corrupt files | — | — | 5 | Error message quality | 0 / 0 | $0 | 15 min | parser_failure_test.json | Document robustness | P1 |
 
## K. Document Robustness Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K01 | DocRobust | Native text ContractNLI | Does pipeline handle all 607 NDAs? | >99% success | — | — | All | 1 | Parse success rate | 0 / 0 | $0 | 15 min | doc_robustness.json | Pipeline reliability | P0 |
| K02 | DocRobust | Very short NDA | Does pipeline handle short documents? | Yes | — | — | Shortest 5 NDAs | 1 | Result validity | ~5 / ~3K | ~$0.01 | 10 min | short_nda.json | Edge case | P1 |
| K03 | DocRobust | Very long NDA | Does pipeline handle long documents? | May need chunking adjustment | — | — | Longest 5 NDAs | 1 | Result validity, latency | ~5 / ~10K | ~$0.03 | 15 min | long_nda.json | Edge case | P1 |
| K04 | DocRobust | Empty file | Does system reject gracefully? | Returns 422 | — | — | — | 1 | Error quality | 0 / 0 | $0 | 5 min | empty_file.json | Input validation | P1 |
| K05 | DocRobust | Oversized upload | Does system enforce file size limit? | Returns 413/422 | — | — | — | 1 | Error quality | 0 / 0 | $0 | 5 min | oversized.json | Input validation | P1 |
| K06 | DocRobust | Unsupported format | Does system reject .xlsx, .doc, etc? | Returns 422 | — | — | — | 3 | Error quality | 0 / 0 | $0 | 5 min | unsupported_format.json | Input validation | P1 |
 
## L. Functional Testing
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L01 | Test | Unit tests | Do metric functions work correctly? | 100% pass | — | — | Synthetic | 1 | Pass rate | 0 / 0 | $0 | 1 hr | unit_test_results.json | Code quality | P0 |
| L02 | Test | API contract tests | Do endpoints match Pydantic schemas? | 100% pass | — | — | — | 1 | Pass rate | ~10 / ~10K | ~$0.02 | 30 min | contract_test_results.json | API reliability | P1 |
| L03 | Test | Golden-case test suite (12 cases) | Do known cases produce correct results? | >10/12 correct | — | Final architecture | 12 golden cases | 1 | Correct count | ~12 / ~15K | ~$0.03 | 15 min | golden_test.json | Regression detection | P0 |
| L04 | Test | Complete 17-req NDA run | Does full pipeline work end-to-end? | Produces 17 valid results | — | Final architecture | 1 NDA | 1 | 17/17 valid outputs | ~17 / ~20K | ~$0.05 | 15 min | full_nda_run.json | Integration verification | P0 |
 
## M. Technical Security Tests
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M01 | Security | Prompt injection in NDA | Does injected instruction change behaviour? | System ignores injected instructions | Injected NDA text | — | — | 5 | Injection success rate (target: 0%) | ~5 / ~5K | ~$0.01 | 30 min | prompt_injection.json | Security | P1 |
| M02 | Security | API key exposure | Are keys in any logs, responses, or error messages? | No | — | — | — | 1 | Exposure count (target: 0) | 0 / 0 | $0 | 15 min | key_exposure.json | Security | P1 |
| M03 | Security | NDA text in logs | Is document content logged? | Not in unnecessary logs | — | — | — | 1 | Content in non-debug logs (target: 0) | 0 / 0 | $0 | 15 min | log_content.json | Privacy | P1 |
| M04 | Security | Agent spending limit | Does agent stop at cost ceiling? | Yes | Simulated expensive case | — | — | 3 | Cost exceeded count (target: 0) | ~15 / ~20K | ~$0.05 | 15 min | agent_spending.json | Cost safety | P1 |
 
## N. Cost and Capacity Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N01 | Cost | Cost per requirement | What does one requirement cost? | $0.001-0.005 | Architecture | — | Dev (100 cases) | 1 | Mean, median, p95 cost | (from E03) | (reuse) | 15 min | cost_per_req.json | Budget planning | P0 |
| N02 | Cost | Cost per NDA | What does one full NDA cost? | $0.02-0.10 | — | Final architecture | 5 NDAs | 1 | Mean, max cost per NDA | ~85 / ~100K | ~$0.20 | 30 min | cost_per_nda.json | Budget planning | P0 |
| N03 | Cost | Explanation-token cost | What fraction of cost is explanations? | 40-60% of output cost | — | — | Dev (100 cases) | 1 | Explanation token %, cost % | (from E03) | (reuse) | 15 min | explanation_cost_analysis.json | **Professor's cost driver** | P0 |
| N04 | Cost | Agent recovery cost | What does each recovered case cost? | $0.01-0.05 | — | — | Dev (routed cases) | 1 | Cost per recovery | (from G01) | (reuse) | 10 min | agent_recovery_cost.json | Agent value | P0 |
| N05 | Cost | Monthly projections | What would 100/1K/10K NDAs cost? | $2/$20/$200 per month at 100/1K/10K | Volume | — | — | 1 | Projected monthly cost | 0 / 0 | $0 | 30 min | monthly_projections.json | Business case | P1 |
 
## O. Usability Experiments
 
| ID | Category | Experiment | Research Question | Hypothesis | Variables | Fixed Controls | Split | Reps | Metrics | Est. Calls/Tokens | Est. Cost | Est. Time | Output Artifact | Decision Enabled | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O01 | Usability | Time to review one requirement | How long with system vs without? | 50% reduction | — | — | — | Self-test | Seconds per requirement | 0 / 0 | $0 | 30 min | review_time.json | Value demonstration | P2 |
| O02 | Usability | Evidence clarity | Is evidence easy to find and verify? | >80% cases evidence is immediately locatable | — | — | — | Self-test (20 cases) | Evidence findability rate | 0 / 0 | $0 | 30 min | evidence_clarity.json | UI quality | P2 |
| O03 | Usability | Abstention comprehension | Does user understand why system abstained? | >90% correct interpretation | — | — | — | Self-test (10 abstain cases) | Comprehension rate | 0 / 0 | $0 | 20 min | abstention_comprehension.json | UI quality | P2 |
 
---
 
# SECTION 9 — EXPERIMENT PRIORITISATION
 
## P0 — Required to Select Architecture and Complete Submission
 
| ID | Experiment | Duration | Cost | Prerequisite | Decision Produced | Deadline |
|---|---|---|---|---|---|---|
| A01-A07 | All dataset validation | 1 hr | $0 | ContractNLI downloaded | Dataset is clean and safe | Mon 21 Sep |
| A08-A11, A13 | Harness + storage + config tests | 1.5 hr | $0 | Metric code written | Harness works correctly | Mon 21 Sep |
| B01 | Majority baseline | 5 min | $0 | Label distribution | Lower bound | Tue 22 Sep |
| B02 | Rule-based keyword baseline | 2 hr | $0 | Dataset validated | Non-AI baseline | Tue 22 Sep |
| B03 | Full-context LLM baseline | 2 hr | ~$1.50 | Model gateway works | Full-context performance | Tue 22 Sep |
| B04 | Oracle experiment | 1 hr | ~$0.50 | Model gateway works | **Ceiling: retrieval vs reasoning** | Tue 22 Sep |
| C01 | Model comparison (Oracle) | 2 hr | ~$1.00 | Oracle experiment | **Model selection** | Wed 23 Sep |
| C03 | Zero-shot vs few-shot | 1.5 hr | ~$0.50 | Model selected | Prompt shot count | Wed 23 Sep |
| C04 | Prompt variants | 1.5 hr | ~$0.50 | Model selected | Prompt template | Wed 23 Sep |
| C05 | JSON output | 1 hr | ~$0.30 | Model + prompt selected | Output format | Wed 23 Sep |
| C07 | Not Mentioned behaviour | 30 min | ~$0.15 | Model + prompt selected | Prompt NM handling | Wed 23 Sep |
| C10 | Explanation cost | 45 min | ~$0.30 | Model + prompt selected | Explanation token budget | Wed 23 Sep |
| D01 | Clause-aware vs fixed chunking | 1.5 hr | $0 | Parser built | **Chunk strategy** | Thu 24 Sep |
| D02 | Chunk size | 1 hr | $0 | Chunker built | Chunk size | Thu 24 Sep |
| D06 | Dense retrieval baseline | 30 min | $0 | Embeddings built | Retrieval baseline | Thu 24 Sep |
| D07 | Top-K comparison | 1 hr | ~$0.40 | Retrieval working | K value | Thu 24 Sep |
| E01-E03 | Rule, full-context, RAG E2E | 4 hr total | ~$2.50 | All baselines + RAG built | **Architecture comparison** | Fri 25 Sep |
| E06-E10 | Agent E2E + ablation + errors + cost | 4 hr | ~$1.50 | RAG working + agent built | **Agent decision** | Mon 28 Sep |
| F01-F02, F04-F06 | Core confidence/abstention | 2 hr | $0 (reuse) | RAG results available | **Abstention threshold** | Fri 25 Sep |
| G01, G02, G04, G07-G08 | Core agent experiments | 5 hr | ~$3.00 | Agent built | **Agent inclusion decision** | Mon 28 Sep |
| K01 | All NDAs parse test | 15 min | $0 | Parser built | Pipeline reliability | Mon 21 Sep |
| L01 | Unit tests | 1 hr | $0 | Metric code | Code quality | Mon 21 Sep |
| L03 | Golden-case test suite | 15 min | ~$0.03 | Final architecture | Regression detection | Fri 2 Oct |
| L04 | Complete 17-req run | 15 min | ~$0.05 | Final architecture | Integration verification | Fri 2 Oct |
| N01-N04 | Core cost analysis | 30 min | $0 (reuse) | E2E results | Cost understanding | Mon 28 Sep |
| E08 | Joint label+evidence | 0 (computed from E03) | $0 | E2E RAG results | **Professor's key metric** | Fri 25 Sep |
 
**Total estimated P0 cost: ~$12–15**
 
## P1 — Required for Convincing Near-Production Prototype
 
| ID | Experiments |
|---|---|
| A12 | Seed reproducibility |
| C06 | Temperature consistency |
| C08-C09 | Exception handling, explanation faithfulness |
| D03-D04 | Overlap, heading preservation |
| D08-D10, D12 | BM25, hybrid, embedding comparison, query formulation |
| E04 | Hybrid RAG E2E |
| F03, F07-F08 | Evidence sufficiency, multi-signal, calibration |
| G03, G05-G06 | Tool ablation, token budget, dedup |
| H01-H07 | All performance experiments |
| J01-J05 | All reliability experiments |
| K02-K06 | Document robustness |
| L02 | API contract tests |
| M01-M04 | Security tests |
| N05 | Monthly cost projections |
 
## P2 — Valuable After Submission
 
| ID | Experiments |
|---|---|
| C02 | Hosted vs local model |
| D05, D11 | Definition attachment, reranking |
| E05 | RAG + reranker E2E |
| H04 | 10+ concurrent users |
| I01-I03 | All cache experiments |
| O01-O03 | All usability experiments |
 
## P3 — Full Production Work, Deferred
 
- Enterprise load testing (25+ concurrent users)
- Multi-provider failover
- Long soak tests
- Cross-user cache isolation
- Database migration stress testing
- CI/CD integration tests
---
 
# SECTION 10 — ORACLE DECISION TREE
 
## Threshold Definitions
 
| Metric | "Strong" | "Weak" |
|---|---|---|
| Oracle accuracy | ≥ 85% | < 75% |
| Oracle macro-F1 | ≥ 0.80 | < 0.70 |
| Evidence Recall@5 | ≥ 70% | < 50% |
| Standard RAG joint correctness | ≥ 50% | < 30% |
| Agent recovery rate | ≥ 30% | < 15% |
| Agent regression rate (max acceptable) | < 5% | ≥ 10% |
| p95 latency | < 20 seconds | > 45 seconds |
| Cost per requirement | < $0.01 | > $0.05 |
 
## Decision Tree
 
### 1. Strong Oracle (≥85%), Weak Retrieval (<50% Evidence Recall@5)
 
**Diagnosis:** The model CAN reason about legal text. Retrieval is the bottleneck.  
**Actions:**
1. Improve chunking strategy (clause-aware, heading preservation)
2. Try different embedding model
3. Try hybrid retrieval (BM25 + dense)
4. Increase K (retrieve more chunks)
5. If still weak after 2–3 iterations: add reranker
6. If still weak: add agent with targeted search tools
### 2. Strong Oracle (≥85%), Strong Retrieval (≥70%), Weak E2E (<30% Joint)
 
**Diagnosis:** Model reasons well, retrieval finds evidence, but integration fails. Likely a prompt problem.  
**Actions:**
1. Revise prompt structure (how evidence is presented to model)
2. Test few-shot examples
3. Check if model misinterprets multiple retrieved chunks
4. Check if Not Mentioned cases are being miscategorised
### 3. Weak Oracle (<75%), Strong Retrieval (≥70%)
 
**Diagnosis:** Model CANNOT reason about legal text, even with perfect evidence. Retrieval is fine.  
**Actions:**
1. **Switch model immediately** — try a larger/better model
2. If budget allows: try GPT-4.1, Claude Sonnet, or a stronger model
3. If budget doesn't allow a better model: increase abstention threshold aggressively (accept lower coverage)
4. Document the model limitation clearly
### 4. Weak Oracle (<75%), Weak Retrieval (<50%)
 
**Diagnosis:** Both components are broken. This is the worst case.  
**Actions:**
1. **Switch model first** (reasoning is the harder problem to fix)
2. After model switch, re-run Oracle to verify improvement
3. Then fix retrieval
4. If both remain weak after model switch: increase abstention to 30-40%, focus on only the clearest cases
5. Document the ceiling honestly
### 5. Strong Oracle (≥85%), Strong Standard RAG (≥50% Joint)
 
**Diagnosis:** The system works well without the agent. Best case for simplicity.  
**Actions:**
1. Test agent anyway — measure recovery and regression rates
2. If agent recovery < 15%: discard agent, use RAG + abstention only
3. Celebrate the simpler architecture
4. Focus remaining time on frontend and demo quality
### 6. Strong RAG, Little Agent Improvement (<15% recovery)
 
**Diagnosis:** Agent doesn't add enough value to justify its complexity.  
**Actions:**
1. **Discard the agent** from the final architecture
2. Document the experiment: "We tested whether selective investigation improves quality. It does not justify the additional cost of $X and latency of Y seconds."
3. This is a valid finding, not a failure
4. Use RAG + abstention as the final architecture
### 7. Agent Improves Recovery (≥30%) but Causes Regressions (≥5%)
 
**Diagnosis:** Agent helps on hard cases but damages easy cases.  
**Actions:**
1. Tighten routing rules — only send the hardest cases to agent
2. Increase confidence threshold for routing
3. Add a "verification pass" — check if agent answer contradicts initial RAG answer on high-confidence cases
4. If regression rate stays ≥10%: discard agent
### 8. Agent Improves Quality but Violates Latency/Cost
 
**Diagnosis:** Agent works but is too expensive or too slow.  
**Actions:**
1. Reduce agent step limit
2. Reduce agent token budget
3. Route fewer cases (raise confidence threshold for routing)
4. If latency > 45s p95 after tuning: offer agent as "detailed investigation" mode that user explicitly requests
5. If cost > $0.05/requirement: discard agent for prototype, document as future optimisation
## When to Stop Experimenting and Freeze
 
Freeze architecture when:
- Oracle experiment is complete AND model is selected
- At least 3 retrieval configurations have been compared
- Standard RAG E2E metrics are computed
- Agent has been tested at least once (include or exclude decision made)
- Confidence threshold is set
- OR it is end of Day 6 (Mon 28 Sep), whichever comes first
---
 
# SECTION 11 — METRIC DEFINITIONS
 
## Classification Metrics
 
**Label Accuracy**
```
accuracy = (number of correct predictions) / (total predictions)
```
Includes all three classes equally. Used for overall reporting but not for architecture selection (use macro-F1 instead).
 
**Per-Class Precision / Recall / F1**
```
precision_c = TP_c / (TP_c + FP_c)
recall_c = TP_c / (TP_c + FN_c)
F1_c = 2 * precision_c * recall_c / (precision_c + recall_c)
```
For each class c ∈ {Entailment, Contradiction, Not Mentioned}.
 
**Macro-F1**
```
macro_F1 = (F1_entailment + F1_contradiction + F1_not_mentioned) / 3
```
Treats all three classes equally regardless of frequency. Primary quality metric.
 
**Risk-Sensitive Recall**
```
risk_recall = (recall_contradiction + recall_not_mentioned) / 2
```
Focuses on the two classes where a miss is dangerous (missing a contradiction or falsely claiming entailment when the requirement is not mentioned). This is the metric your professor and rubric care about most — a missed contradiction means an unsupported requirement passes unnoticed.
 
## Evidence Metrics
 
**Evidence Recall@K**
```
evidence_recall_at_K = |retrieved_evidence ∩ gold_evidence| / |gold_evidence|
```
Where gold_evidence is the set of annotated evidence span IDs, and retrieved_evidence is the set of chunk IDs that overlap with gold spans. Computed only for Entailment and Contradiction (Not Mentioned has no gold evidence).
 
**Evidence Precision**
```
evidence_precision = |retrieved_evidence ∩ gold_evidence| / |retrieved_evidence|
```
Among retrieved chunks, how many actually contain gold evidence?
 
**Mean Reciprocal Rank (MRR)**
```
MRR = (1/N) * Σ (1 / rank_of_first_gold_chunk)
```
For each query, find the rank position of the first retrieved chunk that overlaps with gold evidence. Higher is better.
 
## Joint Metric (Professor's Key Metric)
 
**Joint Label-and-Evidence Correctness**
```
joint_correct(case) = {
  1  if predicted_label == gold_label AND evidence_recall@K >= τ_evidence  (for Entailment/Contradiction)
  1  if predicted_label == "Not Mentioned" AND gold_label == "Not Mentioned"  (no evidence check needed)
  0  otherwise
}
 
joint_correctness = Σ joint_correct(case) / total_cases
```
 
**How Not Mentioned contributes:** When the gold label is Not Mentioned, there are no gold evidence spans. A correct prediction of Not Mentioned counts as jointly correct without an evidence check, because the absence of evidence IS the correct finding. This means the joint metric for Not Mentioned cases reduces to label accuracy for those cases. A wrong prediction of Not Mentioned (false Not Mentioned) is always jointly incorrect.
 
τ_evidence is the minimum evidence recall required for joint correctness. Proposed initial value: 0.5 (at least half the gold evidence must be retrieved). Finalise after measuring retrieval performance in D06.
 
## Abstention and Confidence Metrics
 
**Coverage**
```
coverage = (cases where system provides a label) / (total cases)
coverage = 1 - abstention_rate
```
 
**Selective Accuracy**
```
selective_accuracy = (correct among non-abstained) / (non-abstained count)
```
The accuracy of the system on cases it chose to answer. Should be higher than overall accuracy.
 
**Abstention Rate**
```
abstention_rate = (abstained cases) / (total cases)
```
 
**Abstention Effectiveness**
```
abstention_effectiveness = (abstained ∩ would_be_wrong) / (abstained)
```
What fraction of abstained cases would actually have been wrong? Higher is better — the system is correctly identifying its failures.
 
**Unsafe Non-Abstention Rate**
```
unsafe_non_abstention = (non-abstained ∩ wrong) / (total cases)
```
Cases where the system confidently gave the wrong answer. This is the most dangerous metric — it represents silent failures. Target: < 10%.
 
## Agent Metrics
 
**Agent Routing Rate**
```
agent_routing_rate = (cases sent to agent) / (total cases)
```
 
**Agent Recovery Rate**
```
agent_recovery = (agent-routed cases where agent produced correct label AND initial RAG was wrong or abstained) / (agent-routed cases)
```
 
**Agent Regression Rate**
```
agent_regression = (agent-routed cases where agent produced wrong label AND initial RAG was correct) / (agent-routed cases)
```
 
**Valid Structured Output Rate**
```
valid_output_rate = (responses with valid JSON structure) / (total LLM calls)
```
Target: > 95%.
 
## Cost and Latency Metrics
 
**Cost per Requirement**
```
cost_per_req = Σ (input_tokens × input_price + output_tokens × output_price) for all LLM calls in one requirement
```
 
**Cost per NDA**
```
cost_per_nda = Σ cost_per_req for all 17 requirements + overhead (embedding, indexing)
```
 
**Cost per Correct Resolution**
```
cost_per_correct = total_cost / correct_non_abstained_count
```
 
**p50/p90/p95/p99 Latency**
```
Percentiles of end-to-end latency across all requests.
```
 
**Sustainable Throughput**
```
max_concurrent_requests that maintain p95_latency < target_latency (e.g., 20s)
```
 
---
 
# SECTION 12 — ARCHITECTURE SELECTION SCORECARD
 
## Weighted Scoring
 
| Metric | Weight | Scoring |
|---|---|---|
| Joint label-and-evidence correctness | 30% | Score = (actual / 0.60) × 100, capped at 100 |
| Risk-sensitive recall | 20% | Score = (actual / 0.80) × 100, capped at 100 |
| Abstention effectiveness | 10% | Score = (actual / 0.70) × 100, capped at 100 |
| p95 latency | 10% | Score = max(0, 100 - (actual_seconds - 10) × 5) |
| Cost per resolved requirement | 10% | Score = max(0, 100 - (actual_cents - 0.5) × 20) |
| Reliability (error rate) | 10% | Score = (1 - error_rate) × 100 |
| Implementation complexity | 5% | 100 = simplest, 50 = moderate, 0 = very complex |
| Reproducibility | 5% | 100 = fully reproducible, 50 = partially, 0 = not |
 
**Total = Σ (weight × score)** for each architecture candidate.
 
## Hard Gates (Override Score — Any Failure = Disqualify)
 
| Gate | Threshold | Can be Finalised After |
|---|---|---|
| No evaluation leakage | Zero test-set exposure during development | Day 1 (immediate) |
| Minimum valid structured output rate | ≥ 90% | Day 3 (after C05) |
| Minimum risk-sensitive recall | ≥ 50% | Day 5 (after E03) — may adjust after measuring baselines |
| Maximum unsupported-citation rate | ≤ 20% | Day 5 (after evidence validation) |
| Maximum p95 latency | ≤ 45 seconds per requirement | Day 8 (after H01) |
| Maximum cost per requirement | ≤ $0.05 | Day 5 (after E03 cost data) |
| Bounded agent execution | Agent terminates within limits 100% of the time | Day 6 (after G04) |
| Rate-limit compatibility | ≤ 60 RPM to provider | Day 8 (after H06) |
| Reproducible execution | Same config + seed → same results | Day 9 (after reproducibility test) |
 
**Initial thresholds that MUST be revisited:**
- Risk-sensitive recall minimum (50%) — may be too high or too low depending on baseline performance
- Maximum cost ($0.05) — depends on actual API pricing verification
- Maximum p95 latency (45s) — depends on whether synchronous or async processing is used
---
 
# SECTION 13 — RATE LIMIT, THROUGHPUT AND CAPACITY PLAN
 
## Assumptions (to be validated Day 1)
 
| Parameter | Assumed Value | Source |
|---|---|---|
| Requirements per NDA | 17 | ContractNLI fixed hypotheses |
| Normal agent-routing percentage | 15-25% | Estimate; set by confidence threshold |
| Worst-case agent-routing percentage | 100% | Stress test scenario |
| LLM calls per standard requirement | 1 | Single classification call |
| LLM calls per agent-routed requirement | 3-5 | Initial + 2-4 agent steps |
| Tokens per standard call (input) | 1,000-2,000 | Evidence chunks + prompt |
| Tokens per standard call (output) | 100-200 | Label + evidence IDs + explanation |
| OpenRouter GPT-5 mini pricing | $0.25/M input, $2/M output | Verify on Day 1 |
 
## Formulas
 
**1. Required Throughput (prototype)**
```
For demo: 1 NDA at a time, 17 sequential requirements
Required RPM = 17 / (target_minutes) + agent_calls
If target = 3 minutes: ~6 RPM + agent calls ≈ 10-15 RPM
```
 
**2. Provider Capacity**
```
OpenRouter rate limits (verify): typically 60-200 RPM depending on model
Tokens per minute: typically 100K-500K TPM
```
 
**3. Maximum Sustainable Throughput**
```
max_throughput = min(provider_RPM / calls_per_requirement, provider_TPM / tokens_per_call)
```
 
**4. Expected Queue Time**
```
If synchronous: queue_time = 0 (one at a time)
If N concurrent: queue_time = max(0, (N - max_concurrent) * avg_processing_time)
```
 
**5. Normal Cost per NDA**
```
normal_cost = 17 × [(input_tokens × input_price) + (output_tokens × output_price)]
            + (17 × agent_routing_rate × additional_agent_cost)
Example: 17 × ($0.000375 + 0.20 × $0.001) ≈ $0.010 per NDA
```
 
**6. Worst-Case Cost per NDA (all-agent)**
```
worst_cost = 17 × [standard_cost + agent_cost_per_routed]
Example: 17 × ($0.000375 + $0.001475) ≈ $0.031 per NDA
```
 
**7. Monthly Cost by Volume**
```
monthly_cost(V) = V × normal_cost_per_nda
100 NDAs:   ~$1.00/month
1,000 NDAs: ~$10.00/month
10,000 NDAs: ~$100.00/month
```
 
## Justification Thresholds
 
| Decision | Evidence Required |
|---|---|
| Remain synchronous | 17-requirement NDA completes in < 3 minutes |
| Add background jobs | 17-requirement NDA > 3 minutes AND user needs responsive UI |
| Add Redis | Multiple concurrent users need shared state (unlikely for prototype) |
| Add more workers | > 5 concurrent users needed (unlikely for prototype) |
| Add caching | Same NDA reviewed repeatedly AND uncached latency is unacceptable |
| Change provider | Current provider rate limit prevents completing a 17-req NDA without 429s |
| Reduce agent routing | Agent adds > 50% to total NDA review time |
| Shorten explanations | Explanation tokens are > 60% of total cost AND explanation quality is acceptable at shorter length |
 
---
 
# SECTION 14 — TESTING STRATEGY
 
## Test Pyramid
 
### Level 1: Unit Tests
| Aspect | Detail |
|---|---|
| What | Metric functions, parsing utilities, chunking logic, confidence calculations, cost calculations |
| Examples | `test_macro_f1_balanced()`, `test_joint_correctness_not_mentioned()`, `test_clause_aware_chunker_preserves_boundaries()` |
| Tooling | pytest |
| When | After writing each module, before using it in experiments |
| Pass/fail | All tests pass |
| Blocks release | Yes |
 
### Level 2: Component Tests
| Aspect | Detail |
|---|---|
| What | Each pipeline stage in isolation (parser, chunker, retriever, classifier, agent) |
| Examples | `test_parser_handles_contractnli_json()`, `test_retriever_returns_k_chunks()`, `test_classifier_returns_valid_json()` |
| Tooling | pytest + mocked model responses for fast tests |
| When | After building each component |
| Pass/fail | All components produce expected output types |
| Blocks release | Yes |
 
### Level 3: Integration Tests
| Aspect | Detail |
|---|---|
| What | Pipeline stages connected together |
| Examples | `test_parse_chunk_retrieve_produces_results()`, `test_confidence_routes_to_agent()` |
| Tooling | pytest + real model calls (on 2-3 cases) |
| When | After pipeline assembled |
| Pass/fail | End-to-end produces valid results |
| Blocks release | Yes |
 
### Level 4: API Contract Tests
| Aspect | Detail |
|---|---|
| What | FastAPI endpoints match Pydantic schemas |
| Examples | `test_review_endpoint_returns_200()`, `test_invalid_input_returns_422()`, `test_review_response_matches_schema()` |
| Tooling | pytest + httpx (TestClient) |
| When | After API built |
| Pass/fail | All endpoints return correct schemas |
| Blocks release | Yes |
 
### Level 5: End-to-End Tests
| Aspect | Detail |
|---|---|
| What | Full request through API to result |
| Examples | `test_full_nda_review_17_requirements()`, `test_upload_and_review()` |
| Tooling | pytest + httpx + real model calls |
| When | After frontend connected |
| Pass/fail | Complete NDA review produces 17 valid results |
| Blocks release | Yes |
 
### Level 6: Regression Tests (Golden Dataset)
| Aspect | Detail |
|---|---|
| What | 12 hand-picked cases covering all difficulty levels |
| Examples | See golden dataset below |
| Tooling | pytest + real model calls |
| When | Before every release, after any pipeline change |
| Pass/fail | ≥ 10/12 correct |
| Blocks release | Yes |
 
### Level 7: Load Tests
| Aspect | Detail |
|---|---|
| What | Concurrent request handling |
| Examples | `test_5_concurrent_reviews()`, `test_burst_of_17_requirements()` |
| Tooling | locust or httpx async |
| When | Day 8 |
| Pass/fail | No errors at 5 concurrent, p95 < 30s |
| Blocks release | No (nice-to-have for demo) |
 
### Level 8: Failure-Injection Tests
| Aspect | Detail |
|---|---|
| What | System behaviour when dependencies fail |
| Examples | J01-J05 (model timeout, 429, invalid JSON, empty response, parser failure) |
| Tooling | pytest + mocked failing responses |
| When | Day 9 |
| Pass/fail | System returns meaningful error, never crashes |
| Blocks release | Yes for critical paths |
 
### Level 9: Document Robustness Tests
| Aspect | Detail |
|---|---|
| What | System behaviour on unusual documents |
| Examples | K01-K06 (short NDA, long NDA, empty file, oversized, unsupported format) |
| Tooling | pytest + synthetic test files |
| When | Day 9 |
| Pass/fail | Appropriate error for each case |
| Blocks release | No (but fixes should be made if time permits) |
 
### Level 10: Technical Security Tests
| Aspect | Detail |
|---|---|
| What | Prompt injection, key exposure, content in logs |
| Examples | M01-M04 |
| Tooling | pytest + manual inspection |
| When | Day 9 |
| Pass/fail | Zero injection successes, zero key exposures |
| Blocks release | Yes for M02 (key exposure), No for others |
 
### Level 11: Usability Tests
| Aspect | Detail |
|---|---|
| What | Self-test of the complete user flow |
| Examples | O01-O03 |
| Tooling | Manual testing with screen recording |
| When | Day 10 (demo prep) |
| Pass/fail | Complete flow works, evidence is visible, abstention is clear |
| Blocks release | No (but critical bugs should be fixed) |
 
## Golden Regression Dataset (12 Cases)
 
Select from the dev set during Day 3-4 experimentation:
 
| Case | Type | What It Tests |
|---|---|---|
| G01 | Easy entailment | Obvious confidentiality obligation clearly stated |
| G02 | Hard entailment | Entailment through paraphrased language |
| G03 | Explicit contradiction | NDA explicitly contradicts the requirement |
| G04 | Contradiction through exception | NDA agrees but an exception clause reverses it |
| G05 | Clear Not Mentioned | Requirement topic is entirely absent from NDA |
| G06 | Misleading lexical overlap | Similar words but different meaning |
| G07 | Cross-reference case | Evidence depends on following a "see Section X" reference |
| G08 | Definition-dependent case | Correct classification requires understanding a defined term |
| G09 | Distributed evidence | Evidence is spread across 2+ separate clauses |
| G10 | Conflicting evidence | Some clauses support, others contradict |
| G11 | Agent-recovery case | Standard RAG gets wrong, agent should recover |
| G12 | Required-abstention case | Evidence is genuinely insufficient; correct answer is to abstain |
 
---
 
# SECTION 15 — WORK BREAKDOWN STRUCTURE
 
| Task ID | Phase | Task | Purpose | Exact Work | Input | Output | Dependency | Hours | Priority | Acceptance Criteria |
|---|---|---|---|---|---|---|---|---|---|---|
| **Phase 0: Repository and Scope** |
| T001 | 0 | Set up repository | Code organisation | Create git repo, folder structure per Section 18, .gitignore, .env.example | None | Initialised repo | None | 1 | P0 | `git log` shows initial commit; all folders exist |
| T002 | 0 | Verify API budget | Budget safety | Check OpenRouter balance, verify GPT-5 mini pricing, calculate projected total spend | API key | budget_plan.json | None | 1 | P0 | Remaining budget documented; projected spend < 80% of budget |
| T003 | 0 | Install dependencies | Environment | Create requirements.txt, install core packages (fastapi, sentence-transformers, faiss-cpu, openai, pydantic) | None | requirements.txt, working venv | T001 | 1 | P0 | `pip install -r requirements.txt` succeeds on clean environment |
| **Phase 1: Budget and Cost Planning** |
| T004 | 1 | Estimate experiment costs | Budget allocation | Calculate API calls × tokens × price for each P0 experiment | Token analysis, pricing | cost_estimates.json | T002 | 1 | P0 | Each P0 experiment has a cost estimate; total < budget |
| **Phase 2: Dataset and Harness** |
| T005 | 2 | Download ContractNLI | Data acquisition | Download dataset, extract, verify file integrity | URL | Raw dataset files | T001 | 0.5 | P0 | 607 NDAs present; all files readable |
| T006 | 2 | Validate dataset | Data quality | Run experiments A01-A07: schema validation, missing data, duplicates, leakage test, label distribution, evidence spans, token analysis | Raw dataset | validation_report.json | T005 | 1.5 | P0 | All validation passes; any issues documented |
| T007 | 2 | Build evaluation harness | Measurement infra | Implement all metric functions (Section 11), unit tests (A08), append-only JSONL storage (A10), config snapshots (A11), run resumption (A09) | Metric definitions | evaluation/ module, tests passing | T001 | 3 | P0 | All metric unit tests pass; harness can score a synthetic run |
| T008 | 2 | Build logging utility | Infrastructure | Implement JSON logger with request/trace IDs per Section 0B | None | pipeline/logging_config.py | T001 | 0.5 | P0 | Logger produces valid JSON lines; no NDA text in logs |
| **Phase 3: Smallest Vertical Slice** |
| T009 | 3 | Build model gateway | Core infra | Implement unified LLM call interface with retries, token counting, cost tracking, timeout handling | API key | pipeline/model_gateway.py | T003, T008 | 2 | P0 | Can call GPT-5 mini, returns response + token counts + cost |
| T010 | 3 | Build document parser | Core pipeline | Parse ContractNLI JSON into structured document objects | Dataset schema | pipeline/parser.py | T005 | 1 | P0 | Parses all 607 NDAs without error (K01) |
| T011 | 3 | Build classification prompt v1 | Core pipeline | Design initial zero-shot classification prompt with structured JSON output | None | prompts/classify_v1.txt | None | 1 | P0 | Prompt produces valid JSON with label + evidence + explanation |
| T012 | 3 | Run smallest slice | Proof of life | One NDA + one hypothesis → classify → compare with gold | One NDA, one hypothesis | Single prediction result | T009, T010, T011 | 1 | P0 | Correct label on at least one easy case |
| **Phase 4: Baselines** |
| T013 | 4 | Majority-class baseline | Floor | Compute majority class, score (B01) | Label distribution | majority_baseline.json | T006, T007 | 0.25 | P0 | Scores computed on dev set |
| T014 | 4 | Rule-based keyword baseline | Non-AI baseline | Implement keyword matching rules for all 17 hypotheses, run on dev set (B02) | Hypothesis texts | rule_baseline.json | T007, T010 | 2 | P0 | All 17 hypotheses have rules; scored on dev set |
| T015 | 4 | Full-context LLM baseline | LLM baseline | Send entire NDA + hypothesis to model, score (B03) | Model gateway, dev set | fullcontext_baseline.json | T007, T009 | 2 | P0 | Scored on dev set; cost recorded |
| **Phase 5: Oracle and Model Selection** |
| T016 | 5 | Oracle experiment | Ceiling measurement | Feed gold evidence to model, score (B04) | Model gateway, gold evidence | oracle_baseline.json | T007, T009 | 1.5 | P0 | Oracle accuracy computed; ceiling identified |
| T017 | 5 | Model comparison | Model decision | Run Oracle on 2-3 models, compare (C01) | Multiple model configs | model_comparison.json | T016 | 2 | P0 | Best model identified by Oracle accuracy × cost |
| T018 | 5 | Prompt tuning | Prompt optimisation | Test zero-shot vs few-shot (C03), prompt variants (C04), JSON output (C05), Not Mentioned handling (C07) | Selected model | prompt_comparison.json | T017 | 3 | P0 | Best prompt selected; valid JSON rate > 90% |
| T019 | 5 | Explanation cost analysis | Cost planning | Measure explanation tokens as % of cost (C10) | Dev set results | explanation_cost.json | T018 | 0.5 | P0 | Know explanation cost fraction |
| **Phase 6: Retrieval** |
| T020 | 6 | Build chunker (clause-aware + fixed) | Retrieval pipeline | Implement both chunking strategies | Parser output | pipeline/chunker.py | T010 | 2 | P0 | Both strategies produce valid chunks from any NDA |
| T021 | 6 | Build embedding + FAISS indexing | Retrieval pipeline | Implement embedding generation + FAISS index creation | Chunks | pipeline/embedder.py, pipeline/indexer.py | T020 | 1.5 | P0 | Can create index for any NDA and query it |
| T022 | 6 | Build retriever | Retrieval pipeline | Implement top-K retrieval with score tracking | FAISS index | pipeline/retriever.py | T021 | 1 | P0 | Returns K chunks with scores |
| T023 | 6 | Retrieval experiments | Strategy selection | Run D01 (chunking comparison), D02 (chunk size), D06 (dense baseline), D07 (top-K) | Retriever | retrieval_results.json | T022, T007 | 3 | P0 | Best chunking + K selected by Evidence Recall@K |
| **Phase 7: Standard RAG** |
| T024 | 7 | Build RAG pipeline | Core product | Connect retriever → classifier, run on dev set (E03) | All retrieval + model components | pipeline/rag.py, e2e_rag.json | T022, T018 | 2 | P0 | RAG E2E scored; joint correctness computed (E08) |
| T025 | 7 | Build evidence validator | Quality check | Check that cited evidence exists in retrieved chunks | Classifier output | pipeline/evidence_validator.py | T024 | 1 | P0 | Hallucinated citations flagged |
| **Phase 8: Confidence and Abstention** |
| T026 | 8 | Confidence analysis | Routing decisions | Run F01 (self-confidence), F02 (retrieval-score), F04 (threshold sweep), F05 (effectiveness), F06 (accuracy-coverage) | RAG results on dev set | confidence_results.json | T024 | 2 | P0 | Threshold selected; abstention rate and effectiveness known |
| T027 | 8 | Build confidence/abstention module | Product component | Implement routing logic based on selected threshold and signals | Analysis results | pipeline/confidence.py | T026 | 1 | P0 | Routes cases to: accept / agent / abstain |
| **Phase 9: Selective Agent** |
| T028 | 9 | Build agent tools | Agent infrastructure | Implement search_clauses, find_defined_term, search_exceptions, retrieve_more_evidence, inspect_neighbouring_clauses | Chunked documents, index | pipeline/agent_tools.py | T022 | 2 | P0 | Each tool returns valid results from NDA |
| T029 | 9 | Build agent router | Agent core | Implement agent loop with step/token/time limits, duplicate detection, trace recording | Agent tools, model gateway | pipeline/agent.py | T028, T027 | 2 | P0 | Agent terminates within limits; trace is complete |
| T030 | 9 | Agent experiments | Agent decision | Run G01 (vs no-agent), G02 (trigger rules), G04 (step limit), G07 (regression), G08 (cost) | Agent, dev set | agent_results.json | T029, T007 | 3 | P0 | Agent included/excluded decision documented |
| **Phase 10: Architecture Selection** |
| T031 | 10 | Architecture comparison | Final selection | Run architecture ablation (E07), complete scorecard (Section 12), document decision | All E2E results | architecture_decision.json | T024, T030 | 1 | P0 | One architecture selected; scorecard complete |
| **Phase 11: Backend API** |
| T032 | 11 | Build FastAPI app | Product backend | Implement endpoints: POST /review, POST /review/nda, GET /reviews, GET /experiments, GET /health | Selected architecture pipeline | backend/app.py | T031 | 3 | P1 | All endpoints return valid responses; Pydantic schemas enforce contracts |
| T033 | 11 | Build SQLite persistence | Data storage | Implement review and experiment storage | Schema from Section 19 | backend/database.py | T032 | 1.5 | P1 | Reviews persist across server restarts |
| **Phase 12: Frontend** |
| T034 | 12 | Scaffold Next.js app | Product frontend | Create Next.js + TypeScript app with pages: upload, review, results, experiments | None | frontend/ folder | T001 | 1 | P1 | `npm run dev` starts; pages load |
| T035 | 12 | Build review UI | Core UX | Upload/select NDA, select requirement, display results with evidence, confidence, cost | API endpoints | Working review page | T032, T034 | 3 | P1 | Can review one requirement and see results |
| T036 | 12 | Build NDA review UI | Full review | Review all 17 requirements, summary table, per-requirement detail | API endpoints | Working NDA review page | T035 | 2 | P1 | Can review entire NDA; 17 results displayed |
| T037 | 12 | Build experiment browser | Transparency | Display experiment results, architecture comparison, cost analysis | API endpoints | Working experiments page | T034, T033 | 1.5 | P1 | Can browse past experiment results |
| **Phase 13: Persistence & Background (if justified)** |
| T038 | 13 | Add BackgroundTasks (if needed) | Async processing | Implement async NDA review with polling endpoint | Performance test results | Async review endpoint | T032, H03 result | 1.5 | P1 | Full NDA review runs in background; status endpoint works |
| **Phase 14: Performance and Reliability** |
| T039 | 14 | Performance testing | Measurement | Run H01-H03 (latency), H05 (memory), H06 (rate limits) | Running backend | performance_results.json | T032 | 2 | P1 | Latency numbers documented; background job decision made |
| T040 | 14 | Reliability testing | Robustness | Run J01-J05, K02-K06, M01-M04 | Running backend | reliability_results.json | T032 | 2 | P1 | All critical failures handled gracefully |
| **Phase 15: Final Evaluation** |
| T041 | 15 | Final locked test-set evaluation | Academic requirement | Run selected architecture on held-out test set ONCE; compute all metrics | Frozen pipeline, test set | final_evaluation.json | T031 | 1.5 | P0 | Final numbers reported; no re-tuning |
| **Phase 16: Documentation** |
| T042 | 16 | Write README | Reproducibility | Setup instructions, usage guide, architecture description | Working system | README.md | T041 | 1.5 | P0 | Another machine can set up and run using README |
| T043 | 16 | Environment files | Reproducibility | .env.example (no secrets), requirements.txt (pinned), docker-compose.yml | Working system | Config files | T042 | 0.5 | P0 | `docker-compose up` or manual setup works |
| T044 | 16 | Experiment documentation | Academic credit | Document each experiment: question, method, result, decision | All experiment results | docs/experiments.md | T041 | 1 | P1 | Each experiment has question + result + decision |
| **Phase 17: Demo and Submission** |
| T045 | 17 | Reproducibility test | Verification | Clone repo on clean machine, follow README, run golden test suite | README, clean environment | Reproducibility confirmed | T042, T043 | 1 | P0 | Golden tests pass on clean machine |
| T046 | 17 | Demo preparation | Submission | Prepare demo flow, test complete NDA review, prepare talking points | Working system | Demo script, working demo | T041 | 1.5 | P0 | Can demonstrate full flow without errors |
| T047 | 17 | Submission packaging | Delivery | Final git tag, verify all files present, zip if needed | Complete repository | Submission package | T046 | 1 | P0 | All required files present; repo is clean |
 
---
 
# SECTION 16 — DAY-BY-DAY PLAN
 
| Date | Main Objective | Tasks | Hours | End-of-Day Artifact | Decision Gate | Recovery if Delayed |
|---|---|---|---|---|---|---|
| **Sun 20 Sep (TODAY)** | Pre-Phase 0: eval cases + API check | Verify OpenRouter API key + balance (15 min). Curate 50 golden battery cases from ContractNLI (30 ordinary + 20 negative families). Define 10 injection test cases. Define 10 system behaviour cases (abstention, agent, LLM output). Freeze all 100 cases as expected_outcomes.json. | 3–4h | expected_outcomes.json with 100 cases; API balance confirmed | API key works? Balance ≥ $15? If no → fix before Monday. | Cases can be refined on Day 1 if needed, but the structure must exist |
| **Mon 21 Sep** | Foundations: repo, data, harness, budget | T001 (1h), T002 (0.5h — already verified Sun), T003 (1h), T004 (1h), T005 (0.5h), T006 (1.5h), T007 (2.5h — includes golden battery loader) | 8 | Repo initialised; dataset validated; budget verified; harness skeleton with metric functions, unit tests, and golden battery loader | Budget gate: Can I afford all P0 experiments? If no → reduce dev set size. | If harness incomplete → finish first thing Day 2 |
| **Tue 22 Sep** | Baselines + Oracle = ceiling | T007 finish (1h), T008 (0.5h), T009 (2h), T010 (1h), T011 (1h), T012 (0.5h), T013 (0.25h), T014 (2h) | 8.25 → trim T014 to 1.5h = 7.75 | Model gateway working; parser working; smallest slice proved; majority + rule baselines scored | Smallest slice works? If not → debug parser or model gateway before proceeding | Cut rule baseline scope (do 5 hypotheses instead of 17) |
| **Wed 23 Sep** | Oracle + full-context + model selection | T015 (2h), T016 (1.5h), T017 (2h), T018 (2.5h) | 8 | Oracle results; full-context results; model selected; prompt tuned | **MODEL DECISION GATE**: Oracle accuracy ≥ 75%? If not → try alternative model before proceeding | If Oracle < 75% on all models → document limitation, increase abstention, proceed |
| **Thu 24 Sep** | Retrieval experiments | T019 (0.5h), T020 (2h), T021 (1.5h), T022 (1h), T023 (3h) | 8 | Chunker, embedder, indexer, retriever working; best retrieval config selected | **RETRIEVAL DECISION GATE**: Evidence Recall@5 ≥ 50%? If not → try hybrid retrieval or different embeddings | If retrieval weak → try BM25, try different embedding model; worst case: accept lower evidence quality |
| **Fri 25 Sep** | RAG E2E + confidence/abstention | T024 (2h), T025 (1h), T026 (2h), T027 (1h), E07 analysis (1h), E08-E10 analysis (1h) | 8 | Standard RAG scored; joint correctness computed; confidence threshold set; architecture ablation table | **RAG DECISION GATE**: RAG outperforms full-context? Abstention threshold effective? | If RAG ≤ full-context → revisit retrieval; if no time, use full-context as architecture |
| **Mon 28 Sep** | Agent experiments + architecture freeze | T028 (2h), T029 (2h), T030 (3h), T031 (1h) | 8 | Agent tested; include/exclude decision; ARCHITECTURE FROZEN | **AGENT DECISION GATE**: Recovery > regression? Cost justified? **ARCHITECTURE FREEZE**: Must happen today. | If agent experiments incomplete → freeze without agent (simpler is safer); can add later only if architecture allows |
| **Tue 29 Sep** | Backend API + persistence | T032 (3h), T033 (1.5h), T039 (2h), T038 if needed (1.5h) | 8 (7 if no background jobs needed) | FastAPI backend working with persistence; performance numbers known | Background job decision (based on H03) | If backend incomplete → simplify endpoints; minimal viable API with /review and /health only |
| **Wed 30 Sep** | Frontend (Next.js target, Streamlit fallback) | T034 (1h), T035 (3h), T036 (2h), T037 (1.5h) | 7.5 | Frontend working: upload, review, results, experiments | Frontend usable by end of day? If not → switch to Streamlit fallback (2h max) | If Next.js takes > 6h without a working review page → stop, switch to Streamlit. Professor said "Streamlit last and thin; keep it for video" |
| **Thu 1 Oct** | Final evaluation + testing + docs | T041 (1.5h), T040 (2h), T042 (1.5h), T043 (0.5h), T044 (1h), L03 (0.25h), L04 (0.25h) | 7 | Final test-set numbers; reliability verified; README written; golden tests pass | Final numbers acceptable? (No re-tuning allowed!) | If final numbers are poor → document honestly; focus on analysis and explanation of why |
| **Fri 2 Oct** | Demo prep + submission packaging + reproducibility | T045 (1h), T046 (1.5h), T047 (1h), bug fixes (2h), polish (1h) | 6.5 | Submission-ready package; demo rehearsed; reproducibility confirmed | Can demo without errors? | Fix critical bugs only; skip polish; ensure core flow works |
 
## Latest Safe Completion Dates
 
| Milestone | Latest Safe Date | Consequence of Missing |
|---|---|---|
| Evaluation harness | Mon 21 Sep | Cannot measure any experiment |
| Oracle experiment | Wed 23 Sep | Cannot make model decision |
| Model choice | Wed 23 Sep | All downstream experiments use wrong model |
| Retrieval choice | Thu 24 Sep | RAG pipeline uses suboptimal retrieval |
| Standard RAG | Fri 25 Sep | No core pipeline to build on |
| Abstention | Fri 25 Sep | No confidence routing |
| Agent decision | Mon 28 Sep | Architecture cannot be frozen |
| Architecture freeze | Mon 28 Sep | Cannot start building product |
| Backend API | Tue 29 Sep | No API for frontend |
| Frontend | Wed 30 Sep | Product incomplete |
| Final locked evaluation | Thu 1 Oct | No final numbers |
| Reproducibility test | Fri 2 Oct | Repository may not run elsewhere |
| Demo readiness | Fri 2 Oct | Demo may fail |
 
---
 
# SECTION 17 — CRITICAL PATH AND CUT ORDER
 
## Critical Path
 
```
Dataset validation (Day 1)
→ Evaluation harness (Day 1)
→ Model gateway (Day 2)
→ Oracle experiment (Day 2-3)  ← KEY DECISION POINT
→ Model selection (Day 3)
→ Retrieval pipeline (Day 4)  ← KEY DECISION POINT
→ Standard RAG E2E (Day 5)
→ Confidence/abstention (Day 5)
→ Agent experiments (Day 6)   ← KEY DECISION POINT
→ Architecture freeze (Day 6)
→ Backend API (Day 7)
→ Frontend (Day 8)
→ Final evaluation (Day 9)
→ Demo + submission (Day 10)
```
 
## Blocking Dependencies
 
- Oracle experiment blocks model selection
- Model selection blocks all experiments using the model
- Retrieval experiments block RAG E2E
- RAG E2E blocks confidence/abstention
- Confidence/abstention blocks agent routing
- Architecture freeze blocks backend API
- Backend API blocks frontend
## Tasks That Can Proceed in Parallel
 
- Rule-based baseline (T014) can run alongside model gateway development
- Evaluation harness (T007) is partially parallel with data validation (T006)
- Frontend scaffolding (T034) can start any time (but content depends on API)
- Documentation (T042-T044) can be drafted alongside other work
## Decisions That Cannot Be Postponed
 
- Budget check: Day 1 (before running any paid experiments)
- Model selection: Day 3 (everything depends on this)
- Architecture freeze: Day 6 (4 days of product work depend on this)
## Tasks That Should Not Begin Early
 
- Frontend (don't start before Day 7 — architecture must be frozen)
- Final test-set evaluation (don't start before Day 9 — no re-tuning allowed)
- Docker packaging (don't start before Day 9 — add bugs to containers)
## Recovery Strategies
 
### If One Day Is Lost
 
Drop the lowest-priority items from that day. Specific:
- Day 1 lost → Move harness to Day 2 morning; combine with baselines in afternoon
- Day 2 lost → Skip rule baseline for now; jump straight to Oracle + full-context
- Day 3 lost → Use GPT-5 mini without model comparison; skip prompt variant testing
- Day 4 lost → Use fixed-size chunking; skip retrieval optimisation
- Day 5 lost → Move RAG E2E to Day 6 morning; compress agent to Day 6 afternoon
- Day 6 lost → Skip agent entirely; freeze with RAG + abstention
- Day 7 lost → Simplify API to 2 endpoints; move to Day 8 morning
- Day 8 lost → Use minimal HTML frontend (or even Streamlit as fallback)
- Day 9 lost → Skip reliability testing; run final eval + write README only
- Day 10 lost → Submit without demo rehearsal (weekend buffer)
### If Two Days Are Lost
 
Cut agent experiments entirely. Freeze architecture as RAG + abstention. Compress frontend to minimal HTML. Skip reliability and load testing.
 
### If API Cost Is Higher Than Expected
 
1. Reduce dev set size (use 30% subsample for experiments)
2. Drop model comparison (use GPT-5 mini without alternatives)
3. Reduce agent experiments (test on 50 cases instead of full dev set)
4. Drop explanation generation (return evidence only, no explanation text)
### If Agent Does Not Improve Results
 
This is a valid finding. Discard agent from architecture. Document: "Selective investigation was tested but did not improve quality enough to justify its cost. The final architecture uses RAG with confidence-based abstention."
 
### If Retrieval Is Weak
 
1. Try different chunking strategy (clause-aware if using fixed, or vice versa)
2. Try different embedding model
3. Try hybrid retrieval (BM25 + dense)
4. If still weak: fall back to full-context LLM (if documents fit context window)
5. If full-context also fails: increase abstention rate, document limitation
### If Selected Model Is Weak
 
1. Try an alternative model within budget
2. If no model works: increase abstention to 30-40%, focus only on clear cases
3. Document: "Current models cannot reliably reason about complex legal NDA clauses without substantial improvement in [specific weakness]"
## Feature Cut Order (first to cut → last to cut)
 
1. Docker packaging
2. Hosted vs local model comparison
3. Reranking
4. Hybrid retrieval
5. Content-hash caching
6. Experiment browser in frontend
7. Background job processing
8. Full 17-requirement NDA review UI (keep single-requirement)
9. PDF upload support
10. Result export (CSV/JSON)
11. Next.js frontend (fall back to minimal HTML)
12. Selective agent (keep RAG + abstention)
13. FastAPI backend (fall back to CLI + JSONL)
— NEVER CUT BELOW THIS LINE —
14. Evaluation harness and metrics
15. Oracle experiment
16. Standard RAG pipeline
17. Confidence and abstention
18. Final locked test-set evaluation
19. Reproducibility
---
 
# SECTION 18 — REPOSITORY STRUCTURE
 
```
ndatrace/
├── README.md
├── .gitignore
├── .env.example                     # Template without secrets
├── requirements.txt                 # Pinned Python dependencies
├── docker-compose.yml               # If time permits
├── Dockerfile                       # If time permits
│
├── data/
│   ├── contractnli/                 # Raw ContractNLI files (gitignored if large)
│   │   ├── train.json
│   │   ├── dev.json
│   │   └── test.json
│   ├── golden/                      # 12-case golden regression dataset
│   │   └── golden_cases.json
│   └── README.md                    # Dataset source, licence, download instructions
│
├── pipeline/                        # AI pipeline modules (PRODUCTION CODE)
│   ├── __init__.py
│   ├── logging_config.py            # JSON logger with request/trace IDs
│   ├── config.py                    # Configuration management
│   ├── parser.py                    # Document parsing
│   ├── chunker.py                   # Clause-aware + fixed-size chunking
│   ├── embedder.py                  # Embedding generation
│   ├── indexer.py                   # FAISS index build/load
│   ├── retriever.py                 # Top-K retrieval
│   ├── model_gateway.py             # LLM calls, retries, cost tracking
│   ├── classifier.py               # Classification prompt + output parsing
│   ├── evidence_validator.py        # Citation verification
│   ├── confidence.py                # Confidence scoring + routing
│   ├── agent.py                     # Selective agent loop + bounds
│   ├── agent_tools.py               # Agent tool implementations
│   └── orchestrator.py              # Full pipeline coordination
│
├── prompts/                         # Versioned prompt templates
│   ├── classify_v1.txt
│   ├── classify_v2.txt              # etc.
│   ├── agent_system.txt
│   └── README.md                    # Prompt version history
│
├── evaluation/                      # Evaluation harness (REUSABLE)
│   ├── __init__.py
│   ├── metrics.py                   # All metric implementations
│   ├── harness.py                   # Run evaluation, produce comparison tables
│   ├── scorer.py                    # Score predictions against gold labels
│   ├── schemas.py                   # Pydantic schemas for experiment records
│   └── report.py                    # Generate summary reports
│
├── experiments/                     # Experiment configurations
│   ├── configs/                     # JSON config files for each experiment
│   │   ├── oracle_gpt5mini.json
│   │   ├── rag_dense_k5.json
│   │   └── ...
│   └── README.md                    # How to run experiments
│
├── notebooks/                       # Jupyter notebooks (EXPLORATION)
│   ├── 01_data_validation.ipynb
│   ├── 02_oracle_experiment.ipynb
│   ├── 03_model_comparison.ipynb
│   ├── 04_retrieval_experiments.ipynb
│   ├── 05_rag_e2e.ipynb
│   ├── 06_confidence_abstention.ipynb
│   ├── 07_agent_experiments.ipynb
│   ├── 08_architecture_selection.ipynb
│   └── README.md                    # Notebook index with one-line summaries
│
├── backend/                         # FastAPI application
│   ├── __init__.py
│   ├── app.py                       # FastAPI app + routes
│   ├── routes/
│   │   ├── review.py                # POST /review, POST /review/nda
│   │   ├── results.py               # GET /reviews
│   │   └── experiments.py           # GET /experiments
│   ├── models.py                    # Pydantic request/response schemas
│   └── database.py                  # SQLite persistence
│
├── frontend/                        # Next.js application
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx             # Upload/review page
│   │   │   ├── review/[id]/page.tsx # Review results
│   │   │   └── experiments/page.tsx # Experiment browser
│   │   ├── components/
│   │   │   ├── EvidenceViewer.tsx
│   │   │   ├── ClassificationResult.tsx
│   │   │   ├── CostLatencyDisplay.tsx
│   │   │   └── AgentTraceViewer.tsx
│   │   └── lib/
│   │       └── api.ts               # Backend API client
│   └── ...
│
├── results/                         # Experiment results (APPEND-ONLY)
│   ├── runs/                        # One JSONL per run
│   │   ├── run_20260921_001.jsonl
│   │   └── ...
│   ├── comparisons/                 # Generated comparison tables
│   └── final/                       # Final locked test-set results
│       └── final_evaluation.json
│
├── cache/                           # Cached artifacts (gitignored)
│   ├── embeddings/
│   ├── indexes/
│   └── parsed/
│
├── logs/                            # Structured JSON logs (gitignored)
│   └── ndatrace.jsonl
│
├── tests/
│   ├── test_metrics.py
│   ├── test_parser.py
│   ├── test_chunker.py
│   ├── test_retriever.py
│   ├── test_classifier.py
│   ├── test_confidence.py
│   ├── test_agent.py
│   ├── test_api.py
│   └── test_golden.py               # Golden regression tests
│
├── scripts/
│   ├── run_experiment.py            # CLI for running experiments
│   ├── run_evaluation.py            # CLI for scoring results
│   ├── download_data.sh             # Dataset download
│   └── verify_environment.py        # Environment check
│
└── docs/
    ├── architecture.md              # Architecture description
    ├── experiments.md               # Experiment log with decisions
    └── api.md                       # API documentation
```
 
### Key Design Decisions
 
**Why separate `pipeline/` from `notebooks/`?**  
Notebooks IMPORT from `pipeline/`. The notebook explores and decides; `pipeline/` contains the proven, clean code. The API also imports from `pipeline/`. Same code runs experiments and serves users.
 
**Why `results/runs/` with unique filenames?**  
Append-only: no run ever overwrites another. Each file is self-contained with its config snapshot. You can always go back.
 
**Why `prompts/` as separate files?**  
Version control on prompts. Each prompt file is referenced by name in experiment configs. You can see exactly which prompt produced which results.
 
**Why `cache/` is gitignored?**  
Embeddings and indexes are large and derived. They can be regenerated from data + config. Don't commit 500MB of FAISS indexes.
 
**Why SQLite instead of PostgreSQL?**  
For a single-user academic prototype, SQLite is sufficient. It's zero-setup, file-based, and works everywhere. The persistence schema (Section 19) is designed so that migrating to PostgreSQL later requires only a connection-string change, not a schema redesign.
 
---
 
# SECTION 19 — RESULT AND EXPERIMENT SCHEMAS
 
## 1. Experiment Configuration
 
```json
{
  "run_id": "run_20260922_003",
  "experiment_id": "B04_oracle",
  "architecture": "oracle_evidence_llm",
  "model": "openrouter/openai/gpt-5-mini",
  "model_version": "2026-08",
  "prompt_version": "classify_v2",
  "prompt_file": "prompts/classify_v2.txt",
  "retrieval_config": {
    "method": "oracle",
    "chunking": "none",
    "embedding_model": "none",
    "top_k": "n/a"
  },
  "confidence_config": {
    "threshold": 0.7,
    "signals": ["self_reported"]
  },
  "agent_config": {
    "enabled": false,
    "max_steps": null,
    "max_tokens": null,
    "max_seconds": null
  },
  "temperature": 0.0,
  "split": "dev",
  "sample_size": 500,
  "seed": 42,
  "timestamp": "2026-09-22T14:30:00+08:00",
  "code_revision": "abc123f",
  "estimated_cost_usd": 0.50
}
```
 
## 2. Prediction Record
 
```json
{
  "run_id": "run_20260922_003",
  "case_id": "dev_0042",
  "document_id": "nda_123",
  "hypothesis_id": "hypothesis_3",
  "split": "dev",
  "architecture": "oracle_evidence_llm",
  "model": "openrouter/openai/gpt-5-mini",
  "prompt_version": "classify_v2",
  "predicted_label": "Entailment",
  "confidence": 0.92,
  "retrieved_evidence_ids": ["span_45", "span_46"],
  "explanation": "The NDA requires the receiving party to destroy confidential information...",
  "explanation_tokens": 87,
  "abstained": false,
  "agent_routed": false,
  "valid_structured_output": true,
  "unsupported_citations": [],
  "input_tokens": 644,
  "output_tokens": 149,
  "total_tokens": 793,
  "latency_ms": {
    "total": 9210,
    "parse": 12,
    "chunk": 0,
    "embed": 0,
    "retrieve": 0,
    "classify": 9180,
    "validate": 18
  },
  "estimated_cost_usd": 0.000459,
  "error_state": null,
  "timestamp": "2026-09-22T14:30:15+08:00"
}
```
 
**Note:** `gold_label` and `gold_evidence_ids` are NEVER stored in the prediction record. They exist only in the scoring output, produced by the evaluation harness AFTER prediction is complete. This prevents leakage.
 
## 3. Retrieval Result
 
```json
{
  "case_id": "dev_0042",
  "document_id": "nda_123",
  "hypothesis_id": "hypothesis_3",
  "retrieval_method": "dense",
  "embedding_model": "all-mpnet-base-v2",
  "top_k": 5,
  "chunks_retrieved": [
    {
      "chunk_id": "nda_123_chunk_12",
      "text_preview": "The Receiving Party shall destroy...",
      "score": 0.847,
      "clause_number": "5.3",
      "section_heading": "Return of Confidential Information",
      "char_start": 2340,
      "char_end": 2580
    }
  ],
  "retrieval_latency_ms": 45,
  "index_size_vectors": 87
}
```
 
## 4. Agent Trace
 
```json
{
  "case_id": "dev_0042",
  "agent_trigger": "low_confidence",
  "initial_confidence": 0.43,
  "steps": [
    {
      "step": 1,
      "tool": "search_clauses",
      "query": "destruction of confidential information",
      "result_count": 3,
      "result_preview": "Found 3 matching clauses in Sections 5, 7, 12",
      "tokens_used": 450,
      "latency_ms": 2100,
      "duplicate": false
    },
    {
      "step": 2,
      "tool": "find_defined_term",
      "query": "Confidential Information",
      "result_count": 1,
      "result_preview": "Defined in Section 1.1 as...",
      "tokens_used": 380,
      "latency_ms": 1800,
      "duplicate": false
    }
  ],
  "total_steps": 2,
  "total_tokens": 830,
  "total_latency_ms": 3900,
  "total_cost_usd": 0.000415,
  "stop_reason": "confident_classification",
  "final_label": "Entailment",
  "final_confidence": 0.88,
  "duplicate_queries_prevented": 0,
  "loops_detected": 0
}
```
 
## 5. Cost/Latency Record
 
```json
{
  "run_id": "run_20260922_003",
  "case_id": "dev_0042",
  "total_input_tokens": 1474,
  "total_output_tokens": 529,
  "explanation_tokens": 87,
  "explanation_token_pct": 16.4,
  "total_cost_usd": 0.000874,
  "classification_cost_usd": 0.000459,
  "agent_cost_usd": 0.000415,
  "total_latency_ms": 13110,
  "classification_latency_ms": 9210,
  "agent_latency_ms": 3900,
  "api_calls": 3,
  "retries": 0
}
```
 
## 6. Final Review Result (Product Layer)
 
```json
{
  "review_id": "rev_20261001_001",
  "document_id": "nda_123",
  "document_name": "Vendor_ABC_NDA.txt",
  "hypothesis_id": "hypothesis_3",
  "hypothesis_text": "Receiving Party shall destroy or return...",
  "architecture_used": "rag_with_abstention",
  "predicted_label": "Entailment",
  "confidence": 0.92,
  "evidence": [
    {
      "chunk_id": "nda_123_chunk_12",
      "text": "The Receiving Party shall destroy or return all copies...",
      "clause_number": "5.3",
      "section": "Return of Confidential Information",
      "relevance_score": 0.847
    }
  ],
  "explanation": "The NDA explicitly requires the receiving party to destroy confidential information upon termination.",
  "abstained": false,
  "agent_used": false,
  "agent_trace": null,
  "latency_ms": 9210,
  "cost_usd": 0.000459,
  "status": "completed",
  "timestamp": "2026-10-01T10:30:00+08:00"
}
```
 
---
 
# SECTION 20 — DEFINITION OF DONE
 
## 1. Dataset Pipeline
- [ ] All 607 NDAs parse without error
- [ ] Split validation confirms zero document overlap between dev and test
- [ ] Label distribution matches expected proportions (documented)
- [ ] Gold evidence spans are valid text ranges for ≥99% of cases
- [ ] Token analysis report generated
## 2. Evaluation Harness
- [ ] All metric functions implemented (Section 11)
- [ ] All metric unit tests pass on synthetic data
- [ ] Harness accepts prediction JSONL and produces comparison table
- [ ] Append-only storage: verified no overwrites across 3 sequential runs
- [ ] Config snapshot saved with every run
- [ ] Run resumption works after simulated crash
## 3. Baselines
- [ ] Majority-class accuracy computed on dev set
- [ ] Rule-based baseline scored on dev set for all 17 hypotheses
- [ ] Full-context LLM baseline scored on dev set with cost recorded
- [ ] All three baselines in comparison table
## 4. Oracle Experiment
- [ ] Oracle accuracy and macro-F1 computed on dev set
- [ ] Ceiling identified (retrieval vs reasoning bottleneck documented)
- [ ] At least 2 models compared on Oracle task
- [ ] Model selection decision documented with rationale
## 5. Standard RAG
- [ ] Evidence Recall@5 ≥ 50% on dev set
- [ ] RAG E2E scored on all metrics including joint correctness
- [ ] RAG outperforms at least one baseline OR deviation documented
- [ ] Cost and latency per requirement recorded
## 6. Confidence and Abstention
- [ ] Confidence threshold selected using dev set
- [ ] Abstention rate between 5% and 40%
- [ ] Abstention effectiveness ≥ 50% (abstained cases are disproportionately wrong)
- [ ] Unsafe non-abstention rate documented
## 7. Selective Agent
- [ ] Agent recovery rate measured on dev set
- [ ] Agent regression rate measured on dev set
- [ ] Agent terminates within step/token/time limits 100% of the time
- [ ] Include/exclude decision documented with rationale
- [ ] If excluded: experiment results still reported
## 8. Final Architecture Decision
- [ ] Scorecard (Section 12) completed for all tested architectures
- [ ] All hard gates checked
- [ ] One architecture selected with documented rationale
- [ ] Decision documented: which experiments led to this choice
## 9. FastAPI Backend
- [ ] POST /review returns valid Pydantic response
- [ ] POST /review/nda processes all 17 requirements
- [ ] GET /reviews returns persisted results
- [ ] GET /health returns 200
- [ ] Invalid input returns 422 with meaningful message
- [ ] Model timeout returns error within 35 seconds
- [ ] All responses include latency and cost metadata
## 10. Next.js Frontend
- [ ] NDA upload or selection works
- [ ] Requirement selection works
- [ ] Classification result displays: label, confidence, evidence, explanation
- [ ] Evidence text is highlighted or clearly shown
- [ ] Abstention cases show "Human Review Required" with reason
- [ ] Cost and latency displayed
- [ ] No JavaScript console errors on main flow
## 11. Performance Testing
- [ ] Single-requirement p95 latency measured and documented
- [ ] Full-NDA (17-requirement) total time measured
- [ ] Memory usage measured
- [ ] Rate-limit compatibility verified (no 429s during normal operation)
- [ ] Background-job decision made based on measurements
## 12. Reliability Testing
- [ ] Model timeout handled gracefully (no crash, meaningful error)
- [ ] Invalid JSON from model handled (retry + error)
- [ ] Empty file upload handled (422 error)
- [ ] Oversized file handled (413/422 error)
- [ ] Unsupported format handled (422 error)
- [ ] No API keys in logs or error responses
## 13. Reproducible Repository
- [ ] README has complete setup instructions
- [ ] requirements.txt has pinned versions
- [ ] .env.example has all required variables (no secrets)
- [ ] `pip install -r requirements.txt && python scripts/verify_environment.py` succeeds
- [ ] Golden test suite (12 cases) passes on fresh setup
## 14. Final Evaluation
- [ ] Run on held-out test set exactly once
- [ ] All metrics computed and reported
- [ ] No re-tuning after seeing test results
- [ ] Results saved in results/final/
## 15. Demonstration
- [ ] Can demo single-requirement review without errors
- [ ] Can demo full-NDA review (or at least 3 requirements in sequence)
- [ ] Can show evidence, confidence, cost, architecture used
- [ ] Can explain abstention case
- [ ] Can show experiment comparison
## 16. Submission Package
- [ ] Git repository with clean history
- [ ] All experiment results preserved
- [ ] Final evaluation results included
- [ ] No secrets committed
- [ ] No large data files committed (or documented in .gitignore with download instructions)
- [ ] README is accurate and complete
---
 
# SECTION 21 — FINAL RECOMMENDATION
 
## 1. Recommended Architecture to Start With
 
**Synchronous modular monolith:** FastAPI backend + modular Python pipeline + Next.js frontend + SQLite persistence + FAISS vector index. No agent unless experiments justify it. No background jobs unless 17-requirement NDA review exceeds 3 minutes.
 
## 2. Experiments That Could Change It
 
| Experiment | If Result Is | Architecture Changes To |
|---|---|---|
| Oracle experiment (B04) | Accuracy < 75% | Switch model before proceeding |
| 17-req NDA time (H03) | > 3 minutes | Add FastAPI BackgroundTasks |
| Agent experiments (G01) | Recovery < 15% OR regression > 10% | Remove agent from architecture |
| Retrieval experiments (D01-D07) | Evidence Recall@5 < 40% on all configs | Consider full-context approach instead of RAG |
| Rate-limit test (H06) | Frequent 429s during normal operation | Add request queuing or switch provider |
 
## 3. First Five Tasks
 
**Pre-Phase 0 (Sunday 20 Sep — TODAY):**
0. **Verify API** — Check OpenRouter API key works and balance ≥ $15 (15 min)
0. **Curate eval cases** — Select 50 golden battery cases from ContractNLI + define 50 system/injection/behaviour cases → freeze as expected_outcomes.json (3–4h)
 
**Phase 0 (Monday 21 Sep):**
1. **T001** — Set up repository with folder structure from Section 18
2. **T003** — Install Python dependencies and verify environment
3. **T005 + T006** — Download ContractNLI and run dataset validation (A01-A07)
4. **T007** — Build evaluation harness with metric unit tests + golden battery loader (loads expected_outcomes.json)
5. **T004** — Estimate experiment costs with verified pricing
## 4. What to Complete Before Day 1 (Sunday 20 September)
 
- OpenRouter API key verified and balance confirmed ≥ $15
- 100 eval cases frozen in expected_outcomes.json (see NDATrace_100_Eval_Cases.md):
  - 30 ordinary golden cases (curated from ContractNLI)
  - 20 negative cases (misleading wording, wrong section, conflicts, keyword absence, long docs)
  - 10 injection cases (prompt override, JSON spoofing, evidence flooding, agent hijack)
  - 10 LLM behaviour cases (valid JSON, hallucination, explanation quality)
  - 10 agent behaviour cases (trigger rules, step caps, improvement tracking)
  - 5 confidence/abstention cases
  - 5 evidence quality cases
  - 5 data leakage prevention checks
  - 5 API/error handling cases
## 5. What to Complete on Day 1 (Monday 21 September)
 
- Repository initialised with folder structure
- Cost projections documented (API budget already verified Sunday)
- Python environment working with all core dependencies
- ContractNLI downloaded and validated (all 607 NDAs parse, no split leakage)
- Evaluation harness with all metric functions + passing unit tests
- Golden battery loader: can load expected_outcomes.json and run cases through harness
- Structured JSON logging utility built
## 5. What Must Not Start Yet
 
- Frontend development (wait until architecture freeze on Day 6)
- Docker packaging (wait until Day 9 at earliest)
- Final test-set evaluation (wait until Day 9, after all decisions frozen)
- Any caching or performance optimisation (wait until Day 8 measurements)
- SQLite persistence (wait until Day 7 with the backend)
## 6. Largest Schedule Risk
 
**The Oracle experiment revealing a weak model on Day 2-3.** If the model can't reason about legal text even with perfect evidence, you'll need to test alternative models, which costs time and money. Mitigation: have 2-3 model candidates pre-identified; run Oracle on a small subset (50 cases) of each to decide quickly.
 
## 7. Highest-Value Experiment
 
**B04 — Oracle experiment.** One hour of work, ~$0.50 in API cost, and it tells you whether your ceiling is set by retrieval or reasoning. This single experiment decides where you spend the next 8 days. Your professor called this out as the number-one thing to do first.
 
## 8. Minimum Acceptable Submission if Time Is Constrained
 
If only 5 days are available instead of 10:
- Dataset validation + evaluation harness ✓
- Oracle experiment + model selection ✓
- Standard RAG pipeline (one chunk strategy, one embedding, one K value) ✓
- Confidence threshold + abstention ✓
- Final locked evaluation on test set ✓
- CLI interface (no web frontend)
- Results in JSONL (no SQLite, no API)
- README with setup instructions ✓
- Architecture comparison table: rule vs full-context vs Oracle vs RAG ✓
This meets all academic requirements: progressive architecture comparison, professor's key metrics (joint label+evidence correctness), abstention, cost analysis, reproducibility. It just won't be a "near-production prototype" — it'll be a solid, evaluated, well-documented experimental system.
 
---
 
"Planning is complete. No implementation or repository modification has been performed. Wait for explicit approval before beginning Phase 0."

---

# SECTION 22 — INSTRUCTOR FEEDBACK (Week 3 Problem Statement) & PLAN REVISIONS

Feedback received 2026-09-23 from Ajay Vikram Singh on the Week 3 Problem Statement
(`PE6201_Project_Problem_Statement_Asmitha.pdf`), ahead of the 4 October final submission. This
section records what the feedback confirmed was already working, what it flagged as gaps, and the
concrete plan revisions each gap drove - kept here (not silently edited into earlier sections) so
the audit trail of *why* the plan changed is preserved, matching CLAUDE.md's Decisions Log style.

## 22.1 Confirmed already working (no plan change)

- The four-architecture technique ladder (rule-based → full-context → RAG → selective agentic
  investigation), each layer earning its keep, is exactly what Sections 1/5 already specified and
  what was actually built (T013-T015, T020-T024, T028-T030).
- The explicit "I will not assume the agentic version is better" commitment (Section 7 of the
  problem statement) was honored - the agent was tested for real (T030), not assumed, and even
  re-tested when a tool-usage ablation was questioned.
- Abstention effectiveness is measured, not just present (T026's F05 - "whether abstained cases
  are disproportionately cases the system would otherwise get wrong").
- The Oracle-retrieval arm ("feed gold evidence straight to the model, no retrieval, to find out
  whether the ceiling is retrieval or reasoning") was already built and run (B04, T016) - this is
  the plan's own Section 10 Oracle Decision Tree, executed exactly as designed.
- Joint label-AND-evidence correctness (`evaluation/metrics.py`'s `joint_label_evidence_correctness`)
  already exists and has been reported (T024: 0.813 for RAG) - it was not missing, it needs to be
  **headlined** in the final report/README, not built.

## 22.2 Real gaps found and their plan revisions

**Gap 1 — No local model path existed, despite the problem statement (Section 5, "Compute: Rent +
local") committing to Llama 3.2 3B for a hosted-vs-local comparison (C02).**
`pipeline/model_gateway.py` only ever talked to OpenRouter. Fixed 2026-09-23: installed Ollama,
pulled `llama3.2:3b`, added `ModelGateway.local()` (same complete()/retry/cost-tracking logic,
pointed at Ollama's OpenAI-compatible `/v1` endpoint, $0 pricing registered). Verified end-to-end
through the real classifier (correct label, valid JSON, $0 cost, 5.37s latency vs Gemini's ~1s).

**Revised final-evaluation strategy:** the held-out test split is 123 documents × 17 hypotheses =
**2,091 examples exactly** (verified against the real parsed data, matching the instructor's math).
Two independent cost estimates exist for running the full 4-architecture ladder on this split:
- The instructor's estimate (based on the Week 3 submission's GPT-5-mini example, $0.001059/9.21s
  per case): standard RAG ~$2.21, full-context ~$4, one clean agentic pass ~$7.50 - against a
  $10 lifetime key already partly drawn on for A1/A2. This does not fit.
- This project's own real, measured cost using Gemini 2.5 Flash Lite (the model actually in use
  since the C01 bake-off, 2026-09-22): RAG ≈$0.30, full-context ≈$0.71, RAG+agent ≈$0.54 for the
  *entire* 2,091-example test set - about $1.55 total for all three paid architectures, against a
  real remaining balance of ~$6.59 (of the original $6.99, ~$0.40 spent on experiments so far).
  This fits comfortably.

The switch to Gemini (already made for unrelated cost/latency reasons, C01) means the budget
emergency the instructor's math predicts does not materialize the way it would have under GPT-5
mini. **The local-model requirement is adopted anyway**, not because survival demands it, but
because (a) it was explicitly promised in the approved problem statement and (b) it is the
intended Class 5 (cost-to-serve, hosted-vs-local) result the course rubric maps to. Final-evaluation
plan: run all four architectures on local Llama 3.2 3B across the full 2,091-example test set
(free), then run Gemini on a stratified subsample of ~300 examples for the hosted-vs-local
comparison section - converting what would have been a budget failure into the intended course
result, per the instructor's own suggested fix.

**Gap 2 — The primary metric (risk-sensitive recall) hides Contradiction-class performance.**
`evaluation/metrics.py`'s `risk_sensitive_recall()` is `(recall_Contradiction + recall_NotMentioned)
/ 2` - a plain average. Since NotMentioned is 40.2% of the label distribution and Contradiction only
11.2%, a system can improve the combined number purely by getting better at the easier, more
common class while making no progress on catching actual conflicts - the class that matters most in
this workload. **Plan revision:** report Contradiction recall as its own separate headline metric,
with a count-based interval given the small class size (~234 test examples, per the instructor's
note) - not folded into a single averaged number. `risk_sensitive_recall()` itself is not removed
(still a useful combined view) but is no longer the sole headline figure.

**Gap 3 — Citation precision (applies to the Week 3 PDF; actionable for the final report, not code):**
(a) the workload/staff-hours figure is vendor research (LegalOn Technologies' 2025 State of
Contracting Survey, n=286) and must be labeled as such, not cited as neutral data; (b) the
ContractNLI-follow-up citation link (`2024.nllp-1.pdf`) points at the whole EMNLP proceedings
volume, not the specific paper - the correct reference is `2024.nllp-1.11` (Narendra, Shetty &
Ratnaparkhi); (c) the 0.389 Span NLI BERT figure cited is the NDA-fine-tuned ablation, not the
paper's actual headline result (0.357 ± 0.039; best-in-paper is 0.405, DeBERTa) - the final report
must cite the headline number, not the ablation; (d) GPT-5 mini pricing should not be presented as
current in the final report - this project already moved off it (C01) specifically because of a
cost/latency comparison, and Gemini's verified pricing is what was actually used throughout.

## 22.3 Augmentation already anticipated, one new finding

**Output tokens as the real cost driver** (instructor's Augmentation 2: the Week 3 example's
output ran 4.5x over the predicted 100 tokens, at $2/M vs $0.25/M input - explanation text, not
retrieved context, was the actual cost driver for GPT-5 mini). Checked against this project's own
real Gemini data (T018 v2, 150 real cases): average input 978 tokens, average output only 116
tokens - **input cost dominates** (~2x output cost per case), the opposite pattern. This is not a
contradiction of the instructor's finding; it is a consequence of a decision already made and
tested earlier in this project (T009): GPT-5 mini is a reasoning model whose `completion_tokens`
silently includes hidden reasoning tokens even for trivial JSON replies, inflating its real output
cost far past what a visible response would suggest. Gemini does not exhibit this to the same
degree. **The model bake-off (C01) already avoided the exact cost-blowup problem being flagged
here** - worth stating plainly in the final report as a positive, evidenced finding, not just
noting agreement with the instructor's observation.

## 22.4 Scope alignment

The instructor's suggested cut (four systems on the local model, one hosted comparison = five
configurations, not eight) is adopted directly: Rule-based, Full-context, RAG, RAG+agent all run
locally on the full test set; Gemini runs once, on a ~300-example stratified subsample, for the
hosted-vs-local section. Streamlit interface remains last-and-thin (video demonstration only,
per both this plan's original cut order and the instructor's explicit confirmation). Rule-based
baseline is kept (cheap, and the Class 1 point per the instructor).