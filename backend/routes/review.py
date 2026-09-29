"""
NDATrace API Routes - live requirement review.

POST /api/review is the single-requirement frozen E20 top-5 RAG product
path: BM25 top-20, L-12 cross-encoder reranking, GPT-5-mini + GPT-P0 over
the top five clauses, structured parsing, and source validation.

POST /review is the batch/history adapter used by the interactive UI. It
uses the same frozen RAG path and reuses one document index across selected
requirements. Neither endpoint invokes an agent or routing policy.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend import database
from backend.models import FinalReviewRequest, FinalReviewResponse, RequirementResult, ReviewRequest, ReviewResponse
from backend.rate_limit import ConcurrencyLimitExceeded, RateLimitExceeded, check_rate_limit, concurrency_guard
from pipeline.cost_guard import CostCeilingExceeded, check_batch_budget, check_budget
from pipeline.final_review import MODEL as FINAL_REVIEW_MODEL
from pipeline.final_review import MODEL_MAX_RETRIES, MODEL_TIMEOUT_SECONDS, review_final, review_final_document
from pipeline.logging_config import get_logger
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import load_hypotheses
from pipeline.pdf_extractor import PdfExtractionError, extract_text_from_pdf

logger = get_logger("api.review")
router = APIRouter(tags=["review"])


def _enforce_traffic_guards(requirement_text_for_cost_estimate: str) -> None:
    """E22 LLM10 remediation: rate limit -> concurrency -> budget, in that order, all
    BEFORE any retrieval/model work. Raises HTTPException(429/402) if any guard trips."""
    try:
        check_rate_limit()
    except RateLimitExceeded as e:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {e}") from e
    try:
        check_budget(requirement_text_for_cost_estimate)
    except CostCeilingExceeded as e:
        raise HTTPException(status_code=402, detail=str(e)) from e


@router.post("/api/review", response_model=FinalReviewResponse)
def create_final_review(request: FinalReviewRequest) -> FinalReviewResponse:
    """Single-requirement frozen RAG endpoint. Never logs NDA text - only metadata."""
    # Constructed here (not left to review_final()'s own default) so a
    # missing-configuration error is caught before the request proceeds,
    # distinct from a runtime provider failure mid-request - which
    # review_final() already handles itself by returning needs_human_review.
    _enforce_traffic_guards(request.requirement)

    try:
        gateway = ModelGateway(
            model=FINAL_REVIEW_MODEL,
            max_retries=MODEL_MAX_RETRIES,
            timeout_seconds=MODEL_TIMEOUT_SECONDS,
        )
    except ModelError as e:
        raise HTTPException(status_code=503, detail="Review service is not configured.") from e

    trace_id = str(uuid.uuid4())
    try:
        with concurrency_guard():
            result = review_final(request.nda_text, request.requirement, gateway=gateway)
    except ConcurrencyLimitExceeded as e:
        raise HTTPException(status_code=429, detail=f"Too many concurrent requests: {e}") from e

    logger.info("API: final review", extra={
        "stage": "api_final_review", "trace_id": trace_id, "model": result.model,
        "label": result.label, "parse_status": result.parse_status, "source_valid": result.source_valid,
        "needs_human_review": result.needs_human_review, "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd, "error": result.error,
        "security_review_required": result.security_review_required, "security_flags": result.security_flags,
    })

    return FinalReviewResponse(
        label=result.label, evidence=result.evidence, explanation=result.explanation,
        source_valid=result.source_valid, needs_human_review=result.needs_human_review,
        review_reason=result.review_reason, model=result.model, latency_ms=result.latency_ms,
        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        estimated_cost_usd=result.cost_usd, trace_id=trace_id,
        sources=[asdict(source) for source in result.sources],
        retrieved_chunks=[asdict(chunk) for chunk in result.retrieved_chunks],
        security_review_required=result.security_review_required, security_flags=result.security_flags,
    )


@router.post("/review", response_model=ReviewResponse)
def create_review(request: ReviewRequest) -> ReviewResponse:
    all_hypotheses = load_hypotheses()
    if request.hypothesis_ids:
        unknown = set(request.hypothesis_ids) - set(all_hypotheses)
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown hypothesis_id(s): {sorted(unknown)}")
        selected = {hid: all_hypotheses[hid]["hypothesis"] for hid in request.hypothesis_ids}
    else:
        selected = {hid: entry["hypothesis"] for hid, entry in all_hypotheses.items()}

    try:
        check_rate_limit()
    except RateLimitExceeded as e:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {e}") from e
    try:
        check_batch_budget(list(selected.values()))
    except CostCeilingExceeded as e:
        raise HTTPException(status_code=402, detail=str(e)) from e

    try:
        gateway = ModelGateway(
            model=FINAL_REVIEW_MODEL,
            max_retries=MODEL_MAX_RETRIES,
            timeout_seconds=MODEL_TIMEOUT_SECONDS,
        )
    except ModelError as e:
        raise HTTPException(status_code=503, detail=f"Model gateway unavailable: {e}") from e

    review_id = str(uuid.uuid4())
    doc_id = review_id[:8]
    start = time.time()
    try:
        with concurrency_guard():
            results_by_id = review_final_document(request.nda_text, selected, gateway)
    except ConcurrencyLimitExceeded as e:
        raise HTTPException(status_code=429, detail=f"Too many concurrent requests: {e}") from e
    duration_ms = (time.time() - start) * 1000

    total_cost = sum(r.cost_usd or 0.0 for r in results_by_id.values())
    total_latency = sum(r.latency_ms or 0.0 for r in results_by_id.values())
    created_at = datetime.now(timezone.utc).isoformat()

    items = [
        {
            "hypothesis_id": hypothesis_id,
            "hypothesis_text": selected[hypothesis_id],
            "label": result.label,
            "confidence": None,
            "confidence_available": False,
            "explanation": result.explanation,
            "evidence": result.evidence,
            "source_valid": result.source_valid,
            "needs_human_review": result.needs_human_review,
            "review_reason": result.review_reason,
            "sources": [asdict(source) for source in result.sources],
            "retrieved_chunks": [asdict(chunk) for chunk in result.retrieved_chunks],
            "agent_used": False,
            "agent_steps": 0,
            "cost_usd": result.cost_usd or 0.0,
            "latency_ms": result.latency_ms or 0.0,
            "error": result.error,
            "security_review_required": result.security_review_required,
            "security_flags": result.security_flags,
        }
        for hypothesis_id, result in results_by_id.items()
    ]
    database.save_review(review_id, doc_id, created_at, gateway.model, total_cost, total_latency, items)

    logger.info("API: review created", extra={
        "stage": "api_review", "doc_id": doc_id, "num_requirements": len(items),
        "cost_usd": total_cost, "latency_ms": round(duration_ms, 1), "model": gateway.model,
    })

    return ReviewResponse(
        review_id=review_id, doc_id=doc_id, created_at=created_at,
        results=[RequirementResult(**it) for it in items],
        total_cost_usd=total_cost, total_latency_ms=total_latency, model=gateway.model,
    )


@router.get("/review/{review_id}", response_model=ReviewResponse)
def get_review(review_id: str) -> ReviewResponse:
    review = database.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Review not found: {review_id}")

    return ReviewResponse(
        review_id=review["review_id"], doc_id=review["doc_id"], created_at=review["created_at"],
        results=[RequirementResult(**it) for it in review["items"]],
        total_cost_usd=review["total_cost_usd"], total_latency_ms=review["total_latency_ms"],
        model=review["model"],
    )


MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024  # 10MB - real NDAs are a few pages; this is a generous cap


@router.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)) -> dict:
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail=f"Expected a PDF file, got: {file.content_type}")

    # WBS K05 (found missing entirely, 2026-09-24 audit): no size limit meant
    # an arbitrarily large upload would be read entirely into memory with no
    # cap. Read one byte over the limit to detect oversized files without
    # necessarily buffering the whole thing if the client streams it.
    file_bytes = await file.read(MAX_PDF_SIZE_BYTES + 1)
    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF too large (max {MAX_PDF_SIZE_BYTES // (1024*1024)}MB)",
        )
    try:
        text = extract_text_from_pdf(file_bytes)
    except PdfExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    logger.info("API: extracted text from PDF", extra={
        "stage": "api_extract_pdf", "num_chars": len(text),
    })
    return {"text": text}


@router.get("/hypotheses")
def list_hypotheses() -> list[dict]:
    all_hypotheses = load_hypotheses()
    return [
        {"hypothesis_id": hid, "short_description": entry["short_description"], "hypothesis_text": entry["hypothesis"]}
        for hid, entry in sorted(all_hypotheses.items())
    ]
