"""
NDATrace API Routes - live requirement review.

POST /api/review is the sole review endpoint: the final, frozen
reconstruction-v2 candidate that completed the one-shot TEST evaluation
(E17/E17B) - openai/gpt-5-mini + GPT-P0 + FULL NDA context + structured
parsing + runtime evidence-source validation. One NDA, one requirement in,
one result out. No retrieval, no agent, no routing.

The earlier RAG + selective-agent pipeline (archive/pre_reconstruction/pipeline/orchestrator.py, T031)
and its POST /review, GET /review/{review_id}, and GET /results endpoints
were removed from the active product surface (final submission cleanup) -
that architecture is preserved in `archive/pre_reconstruction/pipeline/`
for historical reproduction, not served live.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.models import FinalReviewRequest, FinalReviewResponse
from pipeline.final_review import MODEL as FINAL_REVIEW_MODEL
from pipeline.final_review import review_final
from pipeline.logging_config import get_logger
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import load_hypotheses
from pipeline.pdf_extractor import PdfExtractionError, extract_text_from_pdf

logger = get_logger("api.review")
router = APIRouter(tags=["review"])


@router.post("/api/review", response_model=FinalReviewResponse)
def create_final_review(request: FinalReviewRequest) -> FinalReviewResponse:
    """The primary (and only) product endpoint (E19). Never logs NDA text - only metadata."""
    # Constructed here (not left to review_final()'s own default) so a
    # missing-configuration error is caught before the request proceeds,
    # distinct from a runtime provider failure mid-request - which
    # review_final() already handles itself by returning needs_human_review.
    try:
        gateway = ModelGateway(model=FINAL_REVIEW_MODEL)
    except ModelError as e:
        raise HTTPException(status_code=503, detail="Review service is not configured.") from e

    trace_id = str(uuid.uuid4())
    result = review_final(request.nda_text, request.requirement, gateway=gateway)

    logger.info("API: final review", extra={
        "stage": "api_final_review", "trace_id": trace_id, "model": result.model,
        "label": result.label, "parse_status": result.parse_status, "source_valid": result.source_valid,
        "needs_human_review": result.needs_human_review, "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd, "error": result.error,
    })

    return FinalReviewResponse(
        label=result.label, evidence=result.evidence, explanation=result.explanation,
        source_valid=result.source_valid, needs_human_review=result.needs_human_review,
        review_reason=result.review_reason, model=result.model, latency_ms=result.latency_ms,
        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        estimated_cost_usd=result.cost_usd, trace_id=trace_id,
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
    """Suggested requirement texts for the frontend's picker - POST /api/review
    itself accepts any free-text requirement, not just these 17."""
    all_hypotheses = load_hypotheses()
    return [
        {"hypothesis_id": hid, "short_description": entry["short_description"], "hypothesis_text": entry["hypothesis"]}
        for hid, entry in sorted(all_hypotheses.items())
    ]
