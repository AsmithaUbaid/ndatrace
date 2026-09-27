#!/usr/bin/env python3
"""
Backfills newly-added metrics (e.g. contradiction_recall_with_ci,
joint_label_evidence_correctness) into OLDER results/runs/*.jsonl files
that predate those fields being added to MetricResult (2026-09-24 gap
found: every pre-T041 file - B01-B04, T018, T024 - has
contradiction_recall=None simply because that field didn't exist in the
schema yet when they were saved).

No re-run, no new LLM calls needed: every result file already stores its
full predictions list, and every metric is a pure function of
(predictions, golds). This recomputes the complete, current metric set
from the already-saved predictions and appends an updated record to the
same file (evaluation/harness.py's save_result() always appends, never
overwrites - the append-only rule (Section 0A) is respected: the
original under-specified record stays in the file's history, this just
adds a new, complete one after it, which is what
EvaluationHarness.load_results()[-1] / scripts/run_evaluation.py's
"take the last line" convention already expects).

Usage:
    python scripts/backfill_missing_metrics.py            # dry run, print only
    python scripts/backfill_missing_metrics.py --write     # actually append updated records
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.metrics import compute_all_metrics
from evaluation.schemas import ExperimentResult, GoldCase, Label
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file

RUNS_DIR = settings.results_path / "runs"


def rebuild_golds(result: ExperimentResult) -> list[GoldCase]:
    split = result.config.split or "dev"
    dataset = parse_contractnli_file(settings.data_path / f"{split}.json")

    golds = []
    for pred in result.predictions:
        doc = dataset.get_document(pred.doc_id)
        ann = doc.annotations.get(pred.hypothesis_id) if doc else None
        if doc is None or ann is None:
            raise ValueError(f"No gold case for {pred.doc_id}/{pred.hypothesis_id} in {split}.json")
        golds.append(GoldCase(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            gold_label=Label(ann.label),
            gold_span_indices=[s.span_index for s in ann.evidence_spans],
        ))
    return golds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Actually append updated records (default: dry run)")
    args = parser.parse_args()

    harness = EvaluationHarness()

    updated = 0
    for path in sorted(RUNS_DIR.glob("*.jsonl")):
        if path.name.startswith("checkpoint_"):
            continue

        lines = [line for line in path.read_text().splitlines() if line.strip()]
        if not lines:
            continue
        result = ExperimentResult.model_validate(json.loads(lines[-1]))

        if result.metrics.contradiction_n > 0 or not result.predictions:
            continue  # already has the field, or nothing to compute from

        golds = rebuild_golds(result)
        fresh_metrics = compute_all_metrics(result.predictions, golds)

        print(f"{path.name}: backfilling contradiction_recall="
              f"{fresh_metrics.contradiction_recall:.3f} (n={fresh_metrics.contradiction_n}), "
              f"joint={fresh_metrics.joint_label_evidence_correctness:.3f}")

        if args.write:
            updated_result = ExperimentResult(
                config=result.config, metrics=fresh_metrics, predictions=result.predictions,
                duration_seconds=result.duration_seconds, error=result.error,
            )
            harness.save_result(updated_result, filename=f"runs/{path.name}")
            updated += 1

    print(f"\n{'Wrote' if args.write else 'Would write'} {updated} updated record(s).")
    if not args.write and updated == 0:
        pass
    elif not args.write:
        print("Re-run with --write to actually append them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
