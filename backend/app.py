"""
NDATrace FastAPI Application.

Serves the frozen E20 top-5 RAG product pipeline at POST /api/review and
through the batch/history adapter at POST /review. Both use BM25 top-20,
cross-encoder reranking, top-5 GPT-5-mini + P0 classification, parsing,
and evidence validation; neither uses an agent or routing. The historical
FULL benchmark result remains available through GET /experiments.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import database
from backend.routes import experiments, results, review


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="NDATrace API",
    description="Evidence-grounded NDA requirement review (ContractNLI).",
    version="0.1.0",
    lifespan=lifespan,
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
app.include_router(results.router)
app.include_router(experiments.router)
