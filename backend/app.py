"""
NDATrace FastAPI Application.

Serves the final frozen product pipeline (pipeline/final_review.py, E19:
GPT-5-mini + P0 + FULL NDA context) at POST /api/review - the architecture
that completed the one-shot TEST evaluation (E17/E17B) - plus the
reconstruction-v2 final TEST comparison (GET /experiments, read from
results/final/reconstruction_v2/). The earlier RAG + selective-agent
pipeline and its legacy endpoints (POST /review, GET /review/{id},
GET /results, GET /cost-estimate) were removed from the active product
surface; that architecture is preserved in
`archive/pre_reconstruction/pipeline/` for historical reproduction.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import experiments, review

app = FastAPI(
    title="NDATrace API",
    description="Evidence-grounded NDA requirement review (ContractNLI).",
    version="0.1.0",
)

# Permissive for local dev (Next.js frontend on a different port); tighten
# to an explicit origin list once there's a non-local deployment target.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(review.router)
app.include_router(experiments.router)
