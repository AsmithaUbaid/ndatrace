"""
NDATrace FastAPI Application.

Serves the final frozen product pipeline (pipeline/final_review.py, E19:
GPT-5-mini + P0 + FULL NDA context) at POST /api/review - the architecture
that completed the one-shot TEST evaluation (E17/E17B). Also serves the
earlier RAG + selective agent pipeline (pipeline/orchestrator.py, T031) at
POST /review for backward compatibility with /history's saved records -
that architecture is superseded, not the selected final one - plus read
access to past reviews (SQLite) and offline experiment records
(results/runs/*.jsonl).
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

# Permissive for local dev (Next.js frontend on a different port, T034-T037
# not built yet); tighten to an explicit origin list once the frontend exists.
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
