#!/usr/bin/env python3
"""
E03 prompt-selection analysis (reconstruction-v2) — Stage B, evaluator-side only.

Computes, per prompt variant (p00/p01/p02): accuracy, macro-F1, per-class recall
(Entailment/Contradiction/NotMentioned), Contradiction Recall with a 95% Wilson CI
(reused from evaluation.metrics.wilson_score_interval), parse-valid rate, retry count,
latency (mean/median/p90), and mean input/output tokens. Also builds the case-level
retrieval-aware failure artifact (results/prompt_failure_analysis.csv) distinguishing
retrieval-limited errors (gold evidence not in the frozen retrieval_v1 top-5 context) from
reasoning/prompt-limited errors (evidence was present, model still wrong).

Evaluator-side only: never feeds gold_label, gold spans, or this analysis back into any
prompt or model call.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from sklearn.metrics import confusion_matrix, f1_score, recall_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.metrics import wilson_score_interval  # noqa: E402

LABELS = ["Entailment", "Contradiction", "NotMentioned"]
E03_DIR = REPO / "experiments/E03_prompt_selection"
RESULTS_DIR = E03_DIR / "results"

# Keyword heuristics used only to flag CANDIDATE failure families for representative-case
# review -- not a confirmed manual finding. See report caveat.
EXCEPTION_KEYWORDS = ("except", "provided that", "unless", "notwithstanding", "other than",
                      "carve-out", "carve out")
NEGATION_KEYWORDS = (" not ", "no obligation", "shall not", "does not", "will not")


def load_manifest_by_case_id() -> dict[str, dict]:
    manifest = json.load(open(E03_DIR / "TRAIN_PROMPT_v1.json"))
    return {c["case_id"]: c for c in manifest["cases"]}


def load_gold_spans_by_case_id() -> dict[str, list[int]]:
    gold = json.load(open(E03_DIR / "TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1_GOLD.json"))
    return {c["case_id"]: c["gold_span_indices"] for c in gold["cases"]}


def load_retrieved_by_case_id() -> dict[str, dict]:
    retrieved = json.load(open(E03_DIR / "TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json"))
    return {c["case_id"]: c for c in retrieved["cases"]}


def load_doc_spans() -> dict[int, list[list[int]]]:
    train = json.load(open(REPO / "data/contractnli/train.json"))
    return {doc["id"]: doc["spans"] for doc in train["documents"]}


def load_predictions(prompt_version: str) -> dict[str, dict]:
    path = RESULTS_DIR / f"run_E03_prompt_selection_{prompt_version}.jsonl"
    records = [json.loads(line) for line in open(path)]
    return {r["case_id"]: r for r in records}


def retrieval_contains_gold(gold_span_idx: list[int], doc_spans: list[list[int]],
                             ranked_offsets: list[list[int]]) -> bool | None:
    """True/False for evidence-bearing cases (Entailment/Contradiction); None for
    NotMentioned, which has no annotated evidence by construction (E00 semantics)."""
    if not gold_span_idx:
        return None
    gold_char_spans = [doc_spans[i] for i in gold_span_idx]
    for g_start, g_end in gold_char_spans:
        for c_start, c_end in ranked_offsets:
            if g_start < c_end and g_end > c_start:
                return True
    return False


def classify_failure_family(gold_label: str, prediction: str, context_text: str) -> str:
    """Observed-category tagging from the actual confusion direction plus a keyword
    heuristic -- a candidate signal for manual review, not a confirmed diagnosis."""
    if prediction is None:
        return "parse_or_model_error"
    direction = f"{gold_label}->{prediction}"
    ctx_lower = context_text.lower()
    has_exception_kw = any(k in ctx_lower for k in EXCEPTION_KEYWORDS)
    has_negation_kw = any(k in ctx_lower for k in NEGATION_KEYWORDS)

    if gold_label == "Contradiction" and has_exception_kw:
        return f"{direction} (candidate: exception/carve-out clause present)"
    if {gold_label, prediction} == {"NotMentioned", "Contradiction"}:
        return f"{direction} (NotMentioned/Contradiction confusion)"
    if gold_label != prediction and has_negation_kw:
        return f"{direction} (candidate: negation present in context)"
    return direction


def latency_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "p90": None}
    s = sorted(values)
    p90_idx = min(int(len(s) * 0.9), len(s) - 1)
    return {"mean": statistics.mean(s), "median": statistics.median(s), "p90": s[p90_idx]}


def compute_prompt_metrics(preds_by_case: dict[str, dict], manifest_by_case: dict[str, dict]) -> dict:
    case_ids = list(preds_by_case.keys())
    golds = [manifest_by_case[cid]["gold_label"] for cid in case_ids]
    # sklearn needs a concrete label for unparseable predictions -- use a sentinel outside
    # LABELS so it always counts as wrong, never accidentally matches a real class.
    preds = [preds_by_case[cid]["predicted_label"] or "PARSE_FAILED" for cid in case_ids]

    parse_valid = [preds_by_case[cid]["parse_valid"] for cid in case_ids]
    retries = [preds_by_case[cid]["retry_count"] for cid in case_ids]
    latencies = [preds_by_case[cid]["latency_ms"] for cid in case_ids
                 if preds_by_case[cid]["latency_ms"] is not None]
    in_tokens = [preds_by_case[cid]["input_tokens"] for cid in case_ids
                 if preds_by_case[cid]["input_tokens"] is not None]
    out_tokens = [preds_by_case[cid]["output_tokens"] for cid in case_ids
                  if preds_by_case[cid]["output_tokens"] is not None]

    accuracy = sum(1 for g, p in zip(golds, preds) if g == p) / len(case_ids)
    macro_f1 = f1_score(golds, preds, labels=LABELS, average="macro", zero_division=0)
    per_class_recall = dict(zip(LABELS, recall_score(golds, preds, labels=LABELS,
                                                       average=None, zero_division=0)))
    cm = confusion_matrix(golds, preds, labels=LABELS).tolist()

    c_successes = sum(1 for g, p in zip(golds, preds) if g == "Contradiction" and p == "Contradiction")
    c_n = sum(1 for g in golds if g == "Contradiction")
    c_recall = c_successes / c_n if c_n else 0.0
    c_ci = wilson_score_interval(c_successes, c_n) if c_n else (0.0, 0.0)

    return {
        "n": len(case_ids),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class_recall": per_class_recall,
        "contradiction_recall": c_recall,
        "contradiction_recall_ci95": list(c_ci),
        "contradiction_n": c_n,
        "confusion_matrix": {"labels": LABELS, "matrix": cm},
        "parse_valid_rate": sum(parse_valid) / len(parse_valid),
        "total_retries": sum(retries),
        "latency_ms": latency_stats(latencies),
        "mean_input_tokens": statistics.mean(in_tokens) if in_tokens else None,
        "mean_output_tokens": statistics.mean(out_tokens) if out_tokens else None,
    }


def main() -> int:
    manifest_by_case = load_manifest_by_case_id()
    gold_spans_by_case = load_gold_spans_by_case_id()
    retrieved_by_case = load_retrieved_by_case_id()
    doc_spans_by_doc = load_doc_spans()

    preds = {v: load_predictions(v) for v in ("p00", "p01", "p02")}
    case_ids = list(manifest_by_case.keys())
    for v, p in preds.items():
        missing = set(case_ids) - set(p.keys())
        if missing:
            raise ValueError(f"{v} is missing {len(missing)} of {len(case_ids)} cases -- "
                              f"refusing to analyze an incomplete run.")

    metrics = {v: compute_prompt_metrics(preds[v], manifest_by_case) for v in preds}

    rows = []
    prompt_sensitive_count = 0
    all_wrong_count = 0
    all_correct_count = 0
    retrieval_limited_count = 0
    reasoning_limited_count = 0
    ambiguous_count = 0

    for cid in case_ids:
        m = manifest_by_case[cid]
        gold_label = m["gold_label"]
        doc_spans = doc_spans_by_doc[m["document_id"]]
        gold_span_idx = gold_spans_by_case[cid]
        ranked_offsets = retrieved_by_case[cid]["ranked_chunk_offsets"]
        context_text = "\n".join(retrieved_by_case[cid]["ranked_chunk_text"])

        contains_gold = retrieval_contains_gold(gold_span_idx, doc_spans, ranked_offsets)

        p0 = preds["p00"][cid]["predicted_label"]
        p1 = preds["p01"][cid]["predicted_label"]
        p2 = preds["p02"][cid]["predicted_label"]
        p0_correct = p0 == gold_label
        p1_correct = p1 == gold_label
        p2_correct = p2 == gold_label
        correctness = (p0_correct, p1_correct, p2_correct)

        is_prompt_sensitive = len({p0, p1, p2}) > 1 or len(set(correctness)) > 1
        if is_prompt_sensitive:
            prompt_sensitive_count += 1
        if not any(correctness):
            all_wrong_count += 1
        if all(correctness):
            all_correct_count += 1

        if all(correctness):
            failure_source = "n/a (all correct)"
            failure_family = "n/a"
        elif contains_gold is None:
            # NotMentioned: no annotated evidence exists to be "missing" -- any error here
            # is necessarily a reasoning/prompt-limited error, not a retrieval failure.
            failure_source = "reasoning_prompt_limited (no gold evidence exists)"
            reasoning_limited_count += 1
            wrong_variant = "p00" if not p0_correct else ("p01" if not p1_correct else "p02")
            failure_family = classify_failure_family(
                gold_label, {"p00": p0, "p01": p1, "p02": p2}[wrong_variant], context_text)
        elif contains_gold is False:
            failure_source = "retrieval_limited"
            retrieval_limited_count += 1
            failure_family = "gold evidence absent from retrieval_v1 top-5 context"
        else:
            # Evidence WAS retrieved but at least one prompt still got it wrong.
            failure_source = "reasoning_prompt_limited"
            reasoning_limited_count += 1
            wrong_variant = "p00" if not p0_correct else ("p01" if not p1_correct else "p02")
            failure_family = classify_failure_family(
                gold_label, {"p00": p0, "p01": p1, "p02": p2}[wrong_variant], context_text)

        rows.append({
            "case_id": cid, "gold_label": gold_label,
            "retrieval_contains_gold": contains_gold,
            "p0_prediction": p0, "p1_prediction": p1, "p2_prediction": p2,
            "p0_correct": p0_correct, "p1_correct": p1_correct, "p2_correct": p2_correct,
            "prompt_sensitive": is_prompt_sensitive,
            "failure_source": failure_source, "failure_family": failure_family,
            "notes": "",
        })

    csv_path = RESULTS_DIR / "prompt_failure_analysis.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "n_cases": len(case_ids),
        "metrics": metrics,
        "prompt_sensitive_count": prompt_sensitive_count,
        "all_wrong_count": all_wrong_count,
        "all_correct_count": all_correct_count,
        "retrieval_limited_count": retrieval_limited_count,
        "reasoning_prompt_limited_count": reasoning_limited_count,
        "ambiguous_count": ambiguous_count,
        "contradiction_failure_families": dict(Counter(
            r["failure_family"] for r in rows
            if r["gold_label"] == "Contradiction" and r["failure_source"] != "n/a (all correct)")),
    }
    with open(RESULTS_DIR / "prompt_failure_analysis_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"wrote {csv_path}")
    print(f"wrote {RESULTS_DIR / 'prompt_failure_analysis_summary.json'}")
    for v in ("p00", "p01", "p02"):
        m = metrics[v]
        print(f"{v}: acc={m['accuracy']:.3f} macroF1={m['macro_f1']:.3f} "
              f"contradiction_recall={m['contradiction_recall']:.3f} "
              f"parse_valid={m['parse_valid_rate']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
