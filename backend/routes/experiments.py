"""
NDATrace API Routes - reconstruction-v2 final TEST comparison.

GET /experiments reads results/final/reconstruction_v2/full_test_comparison.csv
- the canonical, already-computed Rule/Qwen/GPT comparison on the identical
n=2,091 official TEST population (E17/E17B). Never recomputes a metric.

GET /experiments/e20 reads the frozen E20 report and returns the matched
FULL-versus-RAG comparison used for the final product architecture decision.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi import APIRouter

from backend.models import FinalTestResult
from pipeline.config import settings

router = APIRouter(tags=["experiments"])


def _comparison_csv_path() -> Path:
    return settings.results_path / "final" / "reconstruction_v2" / "full_test_comparison.csv"


def _e20_report_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "experiments" / "E20_final_rag_test" / "results" / "E20_final_report.json"


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


@router.get("/experiments/e20", response_model=list[FinalTestResult])
def list_e20_architecture_comparison() -> list[FinalTestResult]:
    """Return frozen E20 metrics without recomputing any experiment result."""
    path = _e20_report_path()
    if not path.exists():
        return []

    with open(path, encoding="utf-8") as f:
        report = json.load(f)

    n = int(report["population"]["n"])
    comparison = report["full_vs_rag_same_population"]
    rows: list[FinalTestResult] = []
    for key, system, status in (
        ("FULL", "gpt5mini_p0_full", "benchmark"),
        ("RAG", "gpt5mini_p0_rag_top5", "final"),
    ):
        metrics = comparison[key]
        recall = metrics["recall"]
        rows.append(FinalTestResult(
            system=system,
            n=n,
            accuracy=float(metrics["accuracy"]),
            macro_f1=float(metrics["macro_f1"]),
            joint=float(metrics["joint"]),
            entailment_recall=float(recall["Entailment"]),
            contradiction_recall=float(recall["Contradiction"]),
            notmentioned_recall=float(recall["NotMentioned"]),
            evidence_recall=float(metrics["evidence_recall"]),
            evidence_precision=float(metrics["evidence_precision"]),
            source_valid_quote_rate=float(metrics["source_valid_quote_rate"]),
            api_cost_usd=float(metrics["cost_per_case"]) * n,
            architecture_status=status,
        ))
    return rows
