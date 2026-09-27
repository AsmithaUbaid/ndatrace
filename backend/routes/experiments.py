"""
NDATrace API Routes - reconstruction-v2 final TEST comparison.

Reads results/final/reconstruction_v2/full_test_comparison.csv - the
canonical, already-computed Rule/Qwen/GPT comparison on the identical
n=2,091 official TEST population (E17/E17B). This route never recomputes
a metric and never reads results/runs/*.jsonl (the pre-reconstruction
experiment log, which this route intentionally does not depend on).
"""

from __future__ import annotations

import csv
from pathlib import Path

from fastapi import APIRouter

from backend.models import FinalTestResult
from pipeline.config import settings

router = APIRouter(tags=["experiments"])


def _comparison_csv_path() -> Path:
    return settings.results_path / "final" / "reconstruction_v2" / "full_test_comparison.csv"


def _to_float(value: str) -> float | None:
    return float(value) if value else None


@router.get("/experiments", response_model=list[FinalTestResult])
def list_final_test_comparison() -> list[FinalTestResult]:
    path = _comparison_csv_path()
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [
        FinalTestResult(
            system=row["system"],
            n=int(row["n"]),
            accuracy=float(row["accuracy"]),
            macro_f1=float(row["macro_f1"]),
            joint=float(row["joint"]),
            entailment_recall=float(row["entailment_recall"]),
            contradiction_recall=float(row["contradiction_recall"]),
            notmentioned_recall=float(row["notmentioned_recall"]),
            evidence_recall=_to_float(row["evidence_recall"]),
            evidence_precision=_to_float(row["evidence_precision"]),
            source_valid_quote_rate=_to_float(row["source_valid_quote_rate"]),
            api_cost_usd=float(row["api_cost_usd"]),
        )
        for row in rows
    ]
