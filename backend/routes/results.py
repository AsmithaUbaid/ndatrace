"""
NDATrace API Routes - past live review results (WBS T032).

Lists reviews previously created via POST /review (backend/routes/review.py),
persisted in SQLite. This is product usage history, distinct from
backend/routes/experiments.py's offline results/runs/*.jsonl records.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend import database
from backend.models import ReviewSummary

router = APIRouter(tags=["results"])


@router.get("/results", response_model=list[ReviewSummary])
def list_results(limit: int = Query(default=50, ge=1, le=500)) -> list[ReviewSummary]:
    rows = database.list_reviews(limit=limit)
    return [
        ReviewSummary(
            review_id=row["review_id"], doc_id=row["doc_id"], created_at=row["created_at"],
            num_requirements=row["num_requirements"], total_cost_usd=row["total_cost_usd"], model=row["model"],
        )
        for row in rows
    ]
