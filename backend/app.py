"""
NDATrace FastAPI Application (WBS T032).

Serves the frozen production pipeline (pipeline/orchestrator.py,
T031: RAG + selective agent) over HTTP, plus read access to past live
reviews (SQLite) and offline experiment records (results/runs/*.jsonl).
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
