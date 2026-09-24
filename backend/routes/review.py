"""
NDATrace API Routes - live requirement review (WBS T032).

POST /review runs the frozen production pipeline (pipeline/orchestrator.py,
T031: RAG + selective agent) against a submitted NDA document and persists
the result; GET /review/{review_id} fetches it back.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend import database
from backend.models import RequirementResult, ReviewRequest, ReviewResponse
from pipeline.logging_config import get_logger
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.orchestrator import review_document
from pipeline.parser import load_hypotheses
from pipeline.pdf_extractor import PdfExtractionError, extract_text_from_pdf

logger = get_logger("api.review")
router = APIRouter(tags=["review"])


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
        gateway = ModelGateway()
    except ModelError as e:
        raise HTTPException(status_code=503, detail=f"Model gateway unavailable: {e}") from e

    review_id = str(uuid.uuid4())
    doc_id = review_id[:8]
    start = time.time()
    try:
        results = review_document(request.nda_text, selected, gateway, doc_id=doc_id)
    except ModelError as e:
        # review_document() isolates per-hypothesis ModelErrors internally
        # (eval case 095) - reaching here means every attempt failed before
        # any hypothesis could even be processed (e.g. the provider is down
        # entirely), not a partial failure.
        raise HTTPException(status_code=503, detail=f"Model provider unavailable after retries: {e}") from e
    duration_ms = (time.time() - start) * 1000

    total_cost = sum(r.cost_usd for r in results)
    total_latency = sum(r.latency_ms for r in results)
    created_at = datetime.now(timezone.utc).isoformat()

    items = [
        {
            "hypothesis_id": r.hypothesis_id, "hypothesis_text": r.hypothesis_text, "label": r.label,
            "confidence": r.confidence, "explanation": r.explanation, "evidence": r.evidence,
            "agent_used": r.agent_used, "agent_steps": r.agent_steps, "cost_usd": r.cost_usd,
            "latency_ms": r.latency_ms, "error": r.error,
        }
        for r in results
    ]
    database.save_review(review_id, doc_id, created_at, gateway.model, total_cost, total_latency, items)

    logger.info("API: review created", extra={
        "stage": "api_review", "doc_id": doc_id, "num_requirements": len(results),
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
