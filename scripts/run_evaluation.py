#!/usr/bin/env python3
"""
Independent reproducibility check for a saved experiment result (WBS T032
support; fixes a dead stub flagged in the 2026-09-24 code audit - this
used to just print "TODO: Implement evaluation scoring").

Every results/runs/*.jsonl file already bundles predictions + the metrics
computed from them (evaluation/harness.py's _finalize saves both
together) - that pairing is exactly what lets this script prove
reproducibility: reload the raw ContractNLI split independently, rebuild
GoldCase records from scratch (never reading the stored metrics), rerun
evaluation/metrics.py's compute_all_metrics() on the stored predictions,
and diff the result against what was saved. A clean diff means the
reported numbers are mechanically reproducible from the repo's own data
files, not just asserted.

Usage:
    python scripts/run_evaluation.py --results results/runs/run_T041_final_test_rag_llama3.2_3b.jsonl
    python scripts/run_evaluation.py --results <path> --data-dir data/contractnli
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.metrics import compute_all_metrics
from evaluation.schemas import ExperimentResult, GoldCase, Label
from pipeline.parser import parse_contractnli_file

# Fields not worth diffing: agent recovery/regression need the OTHER
# architecture's predictions as a baseline (compute_all_metrics(...,
# baseline_predictions=None) always returns 0.0 for these without it),
# so a mismatch here would just mean "no baseline was supplied", not a
# reproducibility failure.
SKIP_FIELDS = {"agent_recovery_rate", "agent_regression_rate"}
TOLERANCE = 1e-6


def load_experiment_result(results_path: Path) -> ExperimentResult:
    """Read the LAST record in the file - results/runs/ is append-only,
    so a re-run of the same experiment_id adds a new line rather than
    overwriting; the last one is the current result."""
    lines = [line for line in results_path.read_text().splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"No records found in {results_path}")
    return ExperimentResult.model_validate(json.loads(lines[-1]))


def rebuild_golds(result: ExperimentResult, data_dir: Path) -> list[GoldCase]:
    """Rebuild gold labels from the raw ContractNLI split file for
    exactly the (doc_id, hypothesis_id) pairs present in this result's
    predictions - never from the stored metrics themselves."""
    split = result.config.split or "test"
    dataset = parse_contractnli_file(data_dir / f"{split}.json")

    golds: list[GoldCase] = []
    missing: list[tuple[str, str]] = []
    for pred in result.predictions:
        doc = dataset.get_document(pred.doc_id)
        ann = doc.annotations.get(pred.hypothesis_id) if doc else None
        if doc is None or ann is None:
            missing.append((pred.doc_id, pred.hypothesis_id))
            continue
        golds.append(GoldCase(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            gold_label=Label(ann.label),
            gold_span_indices=[s.span_index for s in ann.evidence_spans],
        ))

    if missing:
        raise ValueError(
            f"{len(missing)} prediction(s) have no matching gold case in {split}.json "
            f"(e.g. {missing[0]}) - wrong --data-dir, or config.split doesn't match "
            f"the split these predictions actually came from."
        )
    return golds


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently re-score an NDATrace experiment result")
    parser.add_argument("--results", required=True, type=Path, help="Path to a results/runs/*.jsonl file")
    parser.add_argument("--data-dir", type=Path, default=Path("data/contractnli"),
                         help="ContractNLI data directory (default: data/contractnli)")
    parser.add_argument("--tau-evidence", type=float, default=0.5,
                         help="Evidence-overlap threshold for the joint metric (default: 0.5, matches "
                              "the harness's own default)")
    args = parser.parse_args()

    result = load_experiment_result(args.results)
    print(f"Experiment: {result.config.experiment_id} ({result.config.experiment_name})")
    print(f"Model: {result.config.model}  Split: {result.config.split}  "
          f"Predictions: {len(result.predictions)}")

    golds = rebuild_golds(result, args.data_dir)
    recomputed = compute_all_metrics(result.predictions, golds, tau_evidence=args.tau_evidence)

    stored = result.metrics.model_dump()
    fresh = recomputed.model_dump()

    mismatches = []
    for field, stored_value in stored.items():
        if field in SKIP_FIELDS or field == "per_class":
            continue
        fresh_value = fresh.get(field)
        if isinstance(stored_value, (int, float)) and isinstance(fresh_value, (int, float)):
            if abs(stored_value - fresh_value) > TOLERANCE:
                mismatches.append((field, stored_value, fresh_value))
        elif stored_value != fresh_value:
            mismatches.append((field, stored_value, fresh_value))

    print(f"\n{'Metric':<32}{'Stored':>14}{'Recomputed':>14}")
    for field in ("accuracy", "macro_f1", "risk_sensitive_recall", "contradiction_recall",
                   "joint_label_evidence_correctness", "total_cost_usd"):
        print(f"{field:<32}{stored.get(field, 0.0):>14.4f}{fresh.get(field, 0.0):>14.4f}")

    if mismatches:
        print(f"\nMISMATCH on {len(mismatches)} field(s) - stored metrics are NOT reproducible "
              f"from the saved predictions + {result.config.split}.json:")
        for field, s, f in mismatches:
            print(f"  {field}: stored={s!r} vs recomputed={f!r}")
        return 1

    print(f"\nOK - all metrics reproduced exactly from {result.config.split}.json "
          f"(tolerance {TOLERANCE:g}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
