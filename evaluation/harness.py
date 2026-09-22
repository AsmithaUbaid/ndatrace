"""
Evaluation harness — runs predictions through metrics and stores results.

Responsibilities:
- Load golden battery cases (expected_outcomes.json)
- Run a set of predictions through all metrics
- Store results as append-only JSONL
- Record config snapshots for reproducibility
- Support run resumption (A09 from planning doc)
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence

from evaluation.metrics import compute_all_metrics
from evaluation.schemas import (
    ExperimentConfig,
    ExperimentResult,
    GoldCase,
    Label,
    MetricResult,
    Prediction,
)
from pipeline.logging_config import get_logger

logger = get_logger("harness")


class EvaluationHarness:
    """
    Orchestrates evaluation runs: loads gold data, computes metrics,
    persists results.
    """

    def __init__(
        self,
        results_dir: str = "results",
        gold_cases: Optional[list[GoldCase]] = None,
    ):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.gold_cases: list[GoldCase] = gold_cases or []

    def load_gold_cases(self, filepath: str | Path) -> list[GoldCase]:
        """
        Load golden battery cases from a JSON file.

        Expected format: list of objects matching GoldCase schema.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Gold cases file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)

        cases = []
        for entry in raw:
            # Normalise label
            label_str = entry.get("gold_label", entry.get("label", ""))
            try:
                label = Label(label_str)
            except ValueError:
                logger.warning(f"Unknown label '{label_str}' in gold case, skipping")
                continue

            cases.append(GoldCase(
                doc_id=entry["doc_id"],
                hypothesis_id=entry["hypothesis_id"],
                gold_label=label,
                gold_span_indices=entry.get("gold_span_indices", []),
                category=entry.get("category", "golden_battery"),
                case_id=entry.get("case_id", ""),
                description=entry.get("description", ""),
            ))

        self.gold_cases = cases
        logger.info(f"Loaded {len(cases)} gold cases from {filepath.name}")
        return cases

    def load_gold_from_dataset(
        self,
        documents: list,  # list[NDADocument]
        doc_ids: Optional[set[str]] = None,
        hypothesis_ids: Optional[set[str]] = None,
    ) -> list[GoldCase]:
        """
        Build gold cases directly from parsed ContractNLI documents.

        Args:
            documents: Parsed NDADocument objects.
            doc_ids: If given, only include these document IDs.
            hypothesis_ids: If given, only include these hypotheses.
        """
        cases = []
        for doc in documents:
            if doc_ids and doc.doc_id not in doc_ids:
                continue
            for hyp_id, ann in doc.annotations.items():
                if hypothesis_ids and hyp_id not in hypothesis_ids:
                    continue
                cases.append(GoldCase(
                    doc_id=doc.doc_id,
                    hypothesis_id=hyp_id,
                    gold_label=Label(ann.label),
                    gold_span_indices=[s.span_index for s in ann.evidence_spans],
                    category="dataset",
                ))

        self.gold_cases = cases
        logger.info(f"Built {len(cases)} gold cases from dataset")
        return cases

    def evaluate(
        self,
        predictions: Sequence[Prediction],
        config: ExperimentConfig,
        tau_evidence: float = 0.5,
        baseline_predictions: Optional[Sequence[Prediction]] = None,
    ) -> ExperimentResult:
        """
        Run full evaluation: compute all metrics and build result.

        Args:
            predictions: Model predictions to evaluate.
            config: Experiment configuration snapshot.
            tau_evidence: Minimum evidence recall for joint correctness.
            baseline_predictions: For agent recovery rate comparison.

        Returns:
            ExperimentResult with all metrics computed.
        """
        if not self.gold_cases:
            raise ValueError("No gold cases loaded. Call load_gold_cases() first.")

        start = time.perf_counter()

        metrics = compute_all_metrics(
            predictions=predictions,
            golds=self.gold_cases,
            tau_evidence=tau_evidence,
            baseline_predictions=baseline_predictions,
        )

        elapsed = time.perf_counter() - start

        result = ExperimentResult(
            config=config,
            metrics=metrics,
            predictions=list(predictions),
            duration_seconds=round(elapsed, 3),
        )

        logger.info(
            f"Evaluation complete: accuracy={metrics.accuracy:.3f}, "
            f"macro_f1={metrics.macro_f1:.3f}, "
            f"joint={metrics.joint_label_evidence_correctness:.3f}"
        )

        return result

    def save_result(
        self,
        result: ExperimentResult,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Append result to JSONL file (append-only, never overwrite).

        Returns path to the result file.
        """
        if filename is None:
            filename = f"run_{result.config.experiment_id}.jsonl"

        filepath = self.results_dir / filename
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(result.model_dump_json() + "\n")

        logger.info(f"Result saved to {filepath}")
        return filepath

    def load_results(self, filename: str) -> list[ExperimentResult]:
        """Load all results from a JSONL file."""
        filepath = self.results_dir / filename
        if not filepath.exists():
            return []

        results = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(ExperimentResult.model_validate_json(line))
        return results

    def checkpoint_path(self, experiment_id: str) -> Path:
        """Path to the incremental per-prediction checkpoint file for a run."""
        return self.results_dir / "runs" / f"checkpoint_{experiment_id}.jsonl"

    def save_prediction_checkpoint(self, experiment_id: str, prediction: Prediction) -> None:
        """
        Append one prediction to the run's checkpoint file immediately after
        it's computed (A09: run resumption). If the process crashes mid-run,
        load_checkpoint() lets the caller skip cases already done on restart.
        """
        path = self.checkpoint_path(experiment_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(prediction.model_dump_json() + "\n")

    def load_checkpoint(self, experiment_id: str) -> list[Prediction]:
        """Load whatever predictions were already checkpointed for this run."""
        path = self.checkpoint_path(experiment_id)
        if not path.exists():
            return []
        predictions = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    predictions.append(Prediction.model_validate_json(line))
        return predictions

    def completed_case_keys(self, experiment_id: str) -> set[tuple[str, str]]:
        """(doc_id, hypothesis_id) pairs already checkpointed for this run."""
        return {(p.doc_id, p.hypothesis_id) for p in self.load_checkpoint(experiment_id)}

    def clear_checkpoint(self, experiment_id: str) -> None:
        """Remove the checkpoint file once a run completes successfully."""
        path = self.checkpoint_path(experiment_id)
        if path.exists():
            path.unlink()

    def evaluate_by_category(
        self,
        predictions: Sequence[Prediction],
    ) -> dict[str, MetricResult]:
        """
        Compute metrics grouped by gold case category.

        Returns dict mapping category name to metrics.
        """
        # Group gold cases by category
        categories: dict[str, list[GoldCase]] = {}
        for gc in self.gold_cases:
            categories.setdefault(gc.category, []).append(gc)

        results = {}
        for cat_name, cat_golds in categories.items():
            metrics = compute_all_metrics(predictions, cat_golds)
            results[cat_name] = metrics

        return results
