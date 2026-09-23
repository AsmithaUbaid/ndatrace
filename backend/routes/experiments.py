"""
NDATrace API Routes - offline experiment browser (WBS T032).

Reads the append-only results/runs/*.jsonl records (Section 19 schema)
written by scripts/run_*.py - this is read-only browsing of research
results, never a place that writes new experiment records (those are
appended by the harness/scripts directly, per Section 0A).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.models import CostEstimate, ExperimentSummary
from pipeline.config import settings

router = APIRouter(tags=["experiments"])


def _runs_dir() -> Path:
    return settings.results_path / "runs"


def _iter_records():
    # Exclude checkpoint_*.jsonl - those are in-progress, per-prediction
    # artifacts (evaluation/harness.py's resume mechanism), not finalized
    # config+metrics experiment records.
    #
    # Yield only the LAST line per file, not every line: results/runs/ is
    # append-only (Section 0A) - a file can carry more than one record for
    # the same experiment_id (e.g. an older run re-scored after a schema
    # gain, scripts/backfill_missing_metrics.py, 2026-09-24). The last line
    # is always the current one; matches the convention already used by
    # scripts/run_evaluation.py and this same module's get_experiment().
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


def _to_summary(rec: dict) -> ExperimentSummary:
    config = rec.get("config", {})
    metrics = rec.get("metrics", {})
    total_cost = sum(
        (p.get("cost_latency", {}) or {}).get("cost_usd", 0.0) or 0.0
        for p in rec.get("predictions", [])
    )
    return ExperimentSummary(
        experiment_id=config.get("experiment_id", "unknown"),
        experiment_name=config.get("experiment_name", ""),
        model=config.get("model", ""),
        split=config.get("split"),
        sample_size=config.get("sample_size"),
        accuracy=metrics.get("accuracy"),
        macro_f1=metrics.get("macro_f1"),
        contradiction_recall=metrics.get("contradiction_recall"),
        contradiction_recall_ci_low=metrics.get("contradiction_recall_ci_low"),
        contradiction_recall_ci_high=metrics.get("contradiction_recall_ci_high"),
        joint_label_evidence_correctness=metrics.get("joint_label_evidence_correctness"),
        total_cost_usd=round(total_cost, 4),
        timestamp=rec.get("timestamp"),
    )


@router.get("/experiments", response_model=list[ExperimentSummary])
def list_experiments() -> list[ExperimentSummary]:
    if not _runs_dir().exists():
        return []
    return [_to_summary(rec) for rec in _iter_records()]


@router.get("/cost-estimate", response_model=CostEstimate)
def get_cost_estimate() -> CostEstimate:
    """
    Real, measured average cost per requirement for the production
    architecture (RAG + selective agent, T031) - lets the review UI show
    "this will cost about $X" before the user spends real money, using
    actual observed cost, not a guess. Prefers the rag_agent record with
    the largest sample_size (most statistically representative), on the
    reasoning that a bigger sample averages out per-case cost variance
    (agent escalation only fires on ~40-45% of cases) better than a small one.
    """
    candidates = [
        rec for rec in _iter_records()
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


@router.get("/experiments/{experiment_id}", response_model=ExperimentSummary)
def get_experiment(experiment_id: str) -> ExperimentSummary:
    matches = [_to_summary(rec) for rec in _iter_records()
               if rec.get("config", {}).get("experiment_id") == experiment_id]
    if not matches:
        raise HTTPException(status_code=404, detail=f"Experiment not found: {experiment_id}")
    # Last match wins if an experiment_id was ever re-run (append-only log).
    return matches[-1]
