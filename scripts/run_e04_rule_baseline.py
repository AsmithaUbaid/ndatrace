#!/usr/bin/env python3
"""
E04 rule baseline runner (reconstruction-v2) — Stage B.

Runs the FROZEN, UNMODIFIED A0 rule baseline (pipeline/rule_baseline.py's classify_with_span)
against the full official TRAIN split only (423 docs x 17 hypotheses = 7,191 cases). No LLM/API
calls — pure deterministic keyword matching over full NDA text (not retrieval_v1's retrieved
excerpts — A0 is intentionally a separate, cheaper architecture, per the reconstruction brief).

Historical exposure disclosure: this exact rule_baseline.py code has previously been evaluated
on the full official DEV split (B02, docs/experiments.md) and the full official TEST split
(T041) in the T-series pre-reconstruction project. No rule modification happens here — this
run is a reconstruction-v2 CHARACTERIZATION of a pre-existing, unchanged baseline on TRAIN, not
a claim that A0 was developed blind to DEV/TEST.

Writes one fully-traceable JSONL record per case (results/run_E04_R0_train_cases.jsonl) for
scripts/analyze_e04_rule_baseline.py to consume.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.parser import parse_contractnli_file  # noqa: E402
from pipeline.rule_baseline import RULES, classify_with_span  # noqa: E402

TRAIN_PATH = REPO / "data/contractnli/train.json"
RESULTS_DIR = REPO / "experiments/E04_rule_baseline/results"
EXPECTED_N_DOCS = 423
EXPECTED_N_CASES = 7191
EXPECTED_DISTRIBUTION = {"Entailment": 3530, "NotMentioned": 2820, "Contradiction": 841}


def span_overlaps_gold(span: tuple[int, int], doc_spans: list[tuple[int, int]]) -> list[int]:
    """Same interval-overlap semantics as evaluation.scorer.map_chunks_to_gold_span_indices /
    scripts/run_full_rule_baseline_test.py -- which doc.spans indices does this char span
    (the rule's single matched-phrase location) overlap."""
    start, end = span
    return [idx for idx, (s_start, s_end) in enumerate(doc_spans)
            if min(s_end, end) > max(s_start, start)]


def rule_polarity(hypothesis_id: str, predicted_label: str) -> str:
    """Which list produced this label. All 17 TRAIN hypothesis IDs have a defined rule
    (verified below), so NotMentioned here always means genuine no-match fallback, never
    'no rule defined for this hypothesis'."""
    if predicted_label == "Contradiction":
        return "negative_fired"
    if predicted_label == "Entailment":
        return "positive_fired"
    return "none_fired"


def main() -> int:
    dataset = parse_contractnli_file(TRAIN_PATH)
    cases = dataset.all_cases()

    # Verify directly before evaluation -- do not trust a stale comment.
    assert dataset.num_documents == EXPECTED_N_DOCS, \
        f"expected {EXPECTED_N_DOCS} TRAIN documents, found {dataset.num_documents}"
    assert len(cases) == EXPECTED_N_CASES, \
        f"expected {EXPECTED_N_CASES} TRAIN cases, found {len(cases)}"
    actual_dist = Counter(ann.label for _, ann in cases)
    assert dict(actual_dist) == EXPECTED_DISTRIBUTION, \
        f"expected {EXPECTED_DISTRIBUTION}, found {dict(actual_dist)}"
    missing_rules = {ann.hypothesis_id for _, ann in cases} - set(RULES.keys())
    assert not missing_rules, f"hypothesis IDs with no defined rule: {missing_rules}"
    print(f"Verified: {dataset.num_documents} TRAIN documents, {len(cases)} cases, "
          f"distribution {dict(actual_dist)}, all hypothesis IDs have a defined rule.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "run_E04_R0_train_cases.jsonl"

    run_start = time.perf_counter()
    with open(out_path, "w") as out_f:
        for doc, ann in cases:
            t0 = time.perf_counter()
            predicted_label, span = classify_with_span(ann.hypothesis_id, doc.text)
            latency_ms = (time.perf_counter() - t0) * 1000

            matched_phrase = None
            span_start = span_end = None
            predicted_span_indices: list[int] = []
            if span is not None:
                span_start, span_end = span
                matched_phrase = doc.text.lower()[span_start:span_end]
                predicted_span_indices = span_overlaps_gold(span, doc.spans)

            gold_span_indices = [s.span_index for s in ann.evidence_spans]

            record = {
                "case_id": f"train::{doc.doc_id}::{ann.hypothesis_id}",
                "document_id": doc.doc_id,
                "hypothesis_id": ann.hypothesis_id,
                "gold_label": ann.label,
                "gold_span_indices": gold_span_indices,
                "predicted_label": predicted_label,
                "rule_polarity": rule_polarity(ann.hypothesis_id, predicted_label),
                "matched_phrase": matched_phrase,
                "matched_span_start": span_start,
                "matched_span_end": span_end,
                "predicted_span_indices": predicted_span_indices,
                "latency_ms": latency_ms,
                "experiment_id": "E04_rule_baseline",
                "run_variant": "R0",
                "architecture": "A0_rule_baseline_v1",
                "model": "none",
                "cost_usd": 0.0,
            }
            out_f.write(json.dumps(record) + "\n")

    total_seconds = time.perf_counter() - run_start
    with open(RESULTS_DIR / "run_E04_R0_train_wall_seconds.json", "w") as f:
        json.dump({"total_wall_seconds": total_seconds, "n_cases": len(cases)}, f)
    print(f"wrote {out_path} ({len(cases)} cases, {total_seconds:.2f}s total wall time)")
    print("No LLM/API calls were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
