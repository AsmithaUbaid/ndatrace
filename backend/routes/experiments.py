"""
NDATrace API Routes - reconstruction-v2 final TEST comparison, plus the
restored legacy cost-estimate endpoint.

GET /experiments reads results/final/reconstruction_v2/full_test_comparison.csv
- the canonical, already-computed Rule/Qwen/GPT comparison on the identical
n=2,091 official TEST population (E17/E17B). Never recomputes a metric.

GET /experiments/e20 reads the frozen E20 report and returns the matched
FULL-versus-RAG comparison used for the final product architecture decision.

GET /cost-estimate reads historical RAG+agent results/runs/*.jsonl records.
The current product UI does not display this rejected architecture's estimate.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.models import CostEstimate, FinalTestResult
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


def _runs_dir() -> Path:
    return settings.results_path / "runs"


def _iter_run_records():
    # Legacy results/runs/*.jsonl records (Section 19 schema) - excludes
    # checkpoint_*.jsonl (in-progress harness state). Yields only the LAST
    # line per file (append-only convention).
    if not _runs_dir().exists():
        return
    for path in sorted(_runs_dir().glob("*.jsonl")):
        if path.name.startswith("checkpoint_"):
            continue
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            continue
        try:
            yield json.loads(lines[-1])
        except json.JSONDecodeError:
            continue


@router.get("/cost-estimate", response_model=CostEstimate)
def get_cost_estimate() -> CostEstimate:
    """
    Historical measured average cost per requirement for the rejected
    RAG+agent architecture. Prefers the largest available sample.
    """
    candidates = [
        rec for rec in _iter_run_records()
        if "rag_agent" in rec.get("config", {}).get("experiment_id", "").lower()
        and rec.get("config", {}).get("sample_size")
    ]
    if not candidates:
        raise HTTPException(status_code=404, detail="No rag_agent experiment record found to estimate cost from")

    best = max(candidates, key=lambda rec: rec["config"]["sample_size"])
    sample_size = best["config"]["sample_size"]
    total_cost = sum(
        (p.get("cost_latency", {}) or {}).get("cost_usd", 0.0) or 0.0
        for p in best.get("predictions", [])
    )
    return CostEstimate(
        avg_cost_per_requirement_usd=total_cost / sample_size,
        source_experiment_id=best["config"]["experiment_id"],
        source_sample_size=sample_size,
        model=best["config"].get("model", ""),
    )
