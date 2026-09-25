#!/usr/bin/env python3
"""
Retroactively fixes the joint label+evidence correctness metric in
already-completed T041 result files - `scripts/run_final_test_evaluation.py`
never populated `Prediction.retrieved_span_indices` for ANY architecture
(a real bug found 2026-09-24, confirmed: every reported "joint" number for
T041 exactly equalled the NotMentioned-only-correct fraction, since the
joint metric requires retrieved_span_indices to check Entailment/
Contradiction evidence, and it was always empty).

No new LLM calls needed - retrieval is fully deterministic and free.
Re-derives retrieved_span_indices the same way the now-fixed
run_final_test_evaluation.py does per architecture, recomputes every
metric from the corrected predictions, and appends an updated record
(harness.save_result always appends - the original, under-specified
record stays in the file's history, per the append-only rule).

Usage:
    python scripts/backfill_joint_metric.py            # dry run
    python scripts/backfill_joint_metric.py --write     # actually append fixed records
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.metrics import compute_all_metrics
from evaluation.schemas import ExperimentResult, GoldCase, Label, Prediction
from evaluation.scorer import map_chunks_to_gold_span_indices
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_with_span

RUNS_DIR = settings.results_path / "runs"
FINAL_DIR = settings.results_path / "final"
ARCHIVE_DIR = settings.results_path / "archive" / "runs"

# 2026-09-25 results/ reorganization: the 3 hosted gemini T041 files now live
# in results/final/ (curated "final" set); the local-Llama + old 500-case
# rule files moved to results/archive/runs/. Resolved per-file below rather
# than a single shared directory, since this script's target list spans both.
TARGET_FILES = [
    "run_T041_final_test_full_context_google_gemini-2.5-flash-lite.jsonl",
    "run_T041_final_test_rag_google_gemini-2.5-flash-lite.jsonl",
    "run_T041_final_test_rag_agent_google_gemini-2.5-flash-lite.jsonl",
    "run_T041_final_test_full_context_llama3.2_3b.jsonl",
    "run_T041_final_test_rag_llama3.2_3b.jsonl",
    "run_T041_final_test_rag_agent_llama3.2_3b.jsonl",
    # rule has no retrieval/full-doc distinction issue in the same way, but
    # was also never populated - fix for completeness/consistency.
    "run_T041_final_test_rule.jsonl",
]


def architecture_of(filename: str) -> str:
    if "rag_agent" in filename:
        return "rag_agent"
    if "rag" in filename:
        return "rag"
    if "full_context" in filename:
        return "full_context"
    return "rule"


def rebuild_span_indices(arch: str, doc, ann_hypothesis_id: str, ann_hypothesis_text: str,
                          retrievers: dict[str, Retriever]) -> list[int]:
    if arch == "full_context":
        return list(range(len(doc.spans)))

    if arch == "rule":
        _, span = classify_with_span(ann_hypothesis_id, doc.text)
        if span is None:
            return []
        return [idx for idx, (s, e) in enumerate(doc.spans) if min(e, span[1]) > max(s, span[0])]

    # rag / rag_agent - both use the same rule-boosted retrieval as their
    # final-answer context (T023 round 7), free and deterministic to redo.
    if doc.doc_id not in retrievers:
        retrievers[doc.doc_id] = Retriever(doc.text, chunk_method="sentence")
    retriever = retrievers[doc.doc_id]
    retrieved = retriever.query_rerank_and_boost(ann_hypothesis_id, ann_hypothesis_text)
    return map_chunks_to_gold_span_indices(doc.spans, [r.chunk for r in retrieved])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    harness = EvaluationHarness()
    updated = 0

    for filename in TARGET_FILES:
        path = FINAL_DIR / filename
        if not path.exists():
            path = ARCHIVE_DIR / filename
        if not path.exists():
            path = RUNS_DIR / filename
        if not path.exists():
            print(f"{filename}: not found, skipping")
            continue

        lines = [l for l in path.read_text().splitlines() if l.strip()]
        result = ExperimentResult.model_validate(json.loads(lines[-1]))
        arch = architecture_of(filename)
        split = result.config.split or "test"
        dataset = parse_contractnli_file(settings.data_path / f"{split}.json")

        retrievers: dict[str, Retriever] = {}
        golds: list[GoldCase] = []
        fixed_predictions: list[Prediction] = []

        for pred in result.predictions:
            doc = dataset.get_document(pred.doc_id)
            ann = doc.annotations.get(pred.hypothesis_id)
            golds.append(GoldCase(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id, gold_label=Label(ann.label),
                gold_span_indices=[s.span_index for s in ann.evidence_spans],
            ))
            span_indices = rebuild_span_indices(arch, doc, pred.hypothesis_id, ann.hypothesis_text, retrievers)
            fixed_predictions.append(pred.model_copy(update={"retrieved_span_indices": span_indices}))

        fresh_metrics = compute_all_metrics(fixed_predictions, golds)
        old_joint = result.metrics.joint_label_evidence_correctness
        new_joint = fresh_metrics.joint_label_evidence_correctness
        print(f"{filename}: joint {old_joint:.3f} -> {new_joint:.3f}  "
              f"(accuracy unchanged: {fresh_metrics.accuracy:.3f})")

        if args.write:
            fixed_result = ExperimentResult(
                config=result.config, metrics=fresh_metrics, predictions=fixed_predictions,
                duration_seconds=result.duration_seconds, error=result.error,
            )
            # Append to wherever the file was actually resolved from (final/
            # archive/runs), not always results/runs/ - keeps results/final/
            # authoritative rather than silently drifting out of sync with it.
            relative = path.relative_to(settings.results_path)
            harness.save_result(fixed_result, filename=str(relative))
            updated += 1

    print(f"\n{'Wrote' if args.write else 'Would write'} {updated} corrected record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
