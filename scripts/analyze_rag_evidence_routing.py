#!/usr/bin/env python3
"""Stage C2: offline RAG evidence/retrieval-risk routing on frozen stored outputs.

This script makes no model calls. Router features are constructed separately from evaluator-side
gold data; gold labels/evidence and the historical failure taxonomy are joined only for scoring.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.rule_baseline import classify_by_keywords  # noqa: E402
from scripts.analyze_e07_standard_rag import (  # noqa: E402
    evidence_to_span_indices,
    joint_success,
    retrieval_contains_gold,
)

ADDENDUM = REPO / "experiments/E15_review_routing/addendum_rag_evidence_routing"
PROTOCOL_PATH = ADDENDUM / "frozen_protocol.json"
RESULTS = ADDENDUM / "results"
PREDICTIONS_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"
RETRIEVAL_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
GOLD_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json"
TRAIN_PATH = REPO / "data/contractnli/train.json"
TAXONOMY_PATH = REPO / "experiments/E09_agent_justification/results/gpt_residual_failure_analysis.csv"

LABELS = ("Entailment", "Contradiction", "NotMentioned")
QUANTILES = ("q10", "q20", "q30")
FORBIDDEN_ROUTER_KEYS = {
    "gold_label", "gold_span_indices", "correct", "label_ok", "joint", "joint_ok",
    "failure", "failure_bucket", "primary_bucket", "oracle_action_needed",
}
EXCEPTION_CUES = ("except", "provided that", "unless", "notwithstanding", "other than")
CROSS_REFERENCE_CUES = (
    "of the definition of", "as defined in", "pursuant to section", "pursuant to clause",
    "under clause", "under section", "as set forth in section", "as provided in section",
    "in accordance with section", "paragraph (a)", "paragraphs (a)",
)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_runtime_signals(prediction: dict, retrieved: dict, document_text: str) -> dict:
    """Use inference-time information only. Never pass a gold-bearing object here."""
    assert not (FORBIDDEN_ROUTER_KEYS & set(prediction))
    assert not (FORBIDDEN_ROUTER_KEYS & set(retrieved))
    context = "\n\n---\n\n".join(retrieved["ranked_chunk_text"])
    evidence = prediction.get("evidence") or []
    label = prediction.get("predicted_label")
    validation = validate_evidence(context, evidence, label or "")
    rerank = retrieved["ranked_chunk_rerank_scores"]
    bm25 = retrieved["ranked_chunk_bm25_candidate_scores"]
    context_lower = context.lower()
    offsets = retrieved["ranked_chunk_offsets"]
    return {
        "case_id": prediction["case_id"],
        "predicted_label": label,
        "parse_status": prediction.get("parse_status"),
        "unusable": prediction.get("parse_status") not in ("strict", "recovered")
        or label is None or prediction.get("error_type") is not None,
        "n_evidence_quotes": len(evidence),
        "n_source_invalid_quotes": len(validation.hallucinated_quotes),
        "n_duplicate_evidence_quotes": len(evidence) - len(set(evidence)),
        "label_evidence_consistent": validation.label_evidence_consistent,
        "evidence_chars": sum(len(q) for q in evidence),
        "retrieved_count": len(retrieved["ranked_chunk_text"]),
        "duplicate_chunk_ids": len(retrieved["ranked_chunk_ids"]) - len(set(retrieved["ranked_chunk_ids"])),
        "duplicate_chunk_texts": len(retrieved["ranked_chunk_text"]) - len(set(retrieved["ranked_chunk_text"])),
        "top1_reranker_score": rerank[0] if rerank else None,
        "top2_reranker_score": rerank[1] if len(rerank) > 1 else None,
        "top1_top2_margin": rerank[0] - rerank[1] if len(rerank) > 1 else None,
        "reranker_mean": statistics.mean(rerank) if rerank else None,
        "reranker_stdev": statistics.pstdev(rerank) if len(rerank) > 1 else 0.0,
        "bm25_top1_in_final_order": bm25[0] if bm25 else None,
        "bm25_mean_final5": statistics.mean(bm25) if bm25 else None,
        "retrieved_offset_spread": max(e for _, e in offsets) - min(s for s, _ in offsets) if offsets else 0,
        "document_chars": len(document_text),
        "document_span_count": None,
        "cross_reference_cue": any(cue in context_lower for cue in CROSS_REFERENCE_CUES),
        "exception_qualification_cue": any(cue in context_lower for cue in EXCEPTION_CUES),
        "rule_label": classify_by_keywords(prediction["hypothesis_id"], document_text),
    }


def r1_reasons(signal: dict) -> list[str]:
    return [name for name, active in (
        ("unusable_parse_or_error", signal["unusable"]),
        ("EC_without_evidence", signal["predicted_label"] in ("Entailment", "Contradiction")
         and signal["n_evidence_quotes"] == 0),
        ("source_invalid_evidence", signal["n_source_invalid_quotes"] > 0),
        ("NotMentioned_with_evidence", signal["predicted_label"] == "NotMentioned"
         and signal["n_evidence_quotes"] > 0),
    ) if active]


def build_routes(signals: dict[str, dict], protocol: dict) -> tuple[dict[str, dict[str, bool]], dict[str, dict[str, list[str]]]]:
    routes: dict[str, dict[str, bool]] = defaultdict(dict)
    reasons: dict[str, dict[str, list[str]]] = defaultdict(dict)
    weak = protocol["threshold_derivation"]["weak_top1_reranker_score_lte"]
    ambiguous = protocol["threshold_derivation"]["ambiguous_top1_top2_margin_lte"]
    for cid, s in signals.items():
        base_reasons = r1_reasons(s)
        routes["R0"][cid], reasons["R0"][cid] = False, []
        routes["R1"][cid], reasons["R1"][cid] = bool(base_reasons), base_reasons
        for q in QUANTILES:
            is_weak = s["top1_reranker_score"] is None or s["top1_reranker_score"] <= weak[q]
            is_ambiguous = s["top1_top2_margin"] is None or s["top1_top2_margin"] <= ambiguous[q]
            definitions = {
                f"R2_{q}": (is_weak, "weak_top1_reranker_score"),
                f"R3_{q}": (is_ambiguous, "ambiguous_top1_top2_margin"),
                f"R4_{q}": (is_weak or is_ambiguous, "weak_or_ambiguous_retrieval"),
                f"R5_{q}": (is_weak or is_ambiguous or s["cross_reference_cue"],
                              "weak_or_ambiguous_or_cross_reference"),
            }
            for name, (extra, reason) in definitions.items():
                rs = base_reasons + ([reason] if extra else [])
                routes[name][cid], reasons[name][cid] = bool(rs), rs
        disagree = s["rule_label"] != s["predicted_label"]
        h_reasons = base_reasons + (["rule_disagreement"] if disagree else [])
        routes["H_rule_disagreement"][cid] = bool(h_reasons)
        reasons["H_rule_disagreement"][cid] = h_reasons
    return dict(routes), dict(reasons)


def score_outcomes(predictions: dict[str, dict], retrieval: dict[str, dict], gold: dict[str, dict], docs: dict[int, dict]) -> dict[str, dict]:
    outcomes = {}
    for cid, p in predictions.items():
        r, g, d = retrieval[cid], gold[cid], docs[p["document_id"]]
        gold_spans = g["gold_span_indices"]
        predicted_spans = evidence_to_span_indices(
            p.get("evidence") or [], r["ranked_chunk_text"], r["ranked_chunk_offsets"], d["spans"]
        )
        label_ok = p.get("predicted_label") == g["gold_label"]
        outcomes[cid] = {
            "gold_label": g["gold_label"],
            "label_ok": label_ok,
            "joint_ok": joint_success(g["gold_label"], p.get("predicted_label"), gold_spans, predicted_spans),
            "retrieval_contains_gold": retrieval_contains_gold(gold_spans, d["spans"], r["ranked_chunk_offsets"]),
            "gold_span_count": len(gold_spans),
            "predicted_span_count": len(predicted_spans),
        }
    return outcomes


def division(a: int | float, b: int | float) -> float | None:
    return a / b if b else None


def routing_metrics(route: dict[str, bool], outcomes: dict[str, dict], failure_key: str) -> dict:
    ids = list(outcomes)
    tp = sum(route[cid] and not outcomes[cid][failure_key] for cid in ids)
    fp = sum(route[cid] and outcomes[cid][failure_key] for cid in ids)
    fn = sum(not route[cid] and not outcomes[cid][failure_key] for cid in ids)
    tn = sum(not route[cid] and outcomes[cid][failure_key] for cid in ids)
    accepted = fn + tn
    return {
        "routed": tp + fp,
        "review_rate": (tp + fp) / len(ids),
        "total_failures": tp + fn,
        "failures_captured": tp,
        "failure_capture_rate": division(tp, tp + fn),
        "routing_precision": division(tp, tp + fp),
        "routing_recall": division(tp, tp + fn),
        "false_review_rate": division(fp, fp + tn),
        "residual_error_among_accepted": division(fn, accepted),
        "joint_or_label_success_among_accepted": division(tn, accepted),
        "confusion": {"failure_routed": tp, "success_routed": fp, "failure_accepted": fn, "success_accepted": tn},
    }


def contradiction_metrics(route: dict[str, bool], outcomes: dict[str, dict]) -> dict:
    cids = [cid for cid, o in outcomes.items() if o["gold_label"] == "Contradiction"]
    result = {"n_contradiction": len(cids)}
    for key, label in (("label_ok", "classification"), ("joint_ok", "joint")):
        failures = [cid for cid in cids if not outcomes[cid][key]]
        correct = [cid for cid in cids if outcomes[cid][key]]
        caught = sum(route[cid] for cid in failures)
        result[label] = {
            "failures": len(failures),
            "failures_routed": caught,
            "failure_capture_rate": division(caught, len(failures)),
            "residual_automated_failures": len(failures) - caught,
            "correct_cases_routed": sum(route[cid] for cid in correct),
        }
    return result


def taxonomy_metrics(route: dict[str, bool], outcomes: dict[str, dict], taxonomy: dict[str, dict]) -> dict:
    counts = defaultdict(lambda: {"total": 0, "routed": 0})
    routed_failures = 0
    eligible_routed = 0
    eligible_buckets = {"RETRIEVAL_FILTERING_LIMITED", "DYNAMIC_INFORMATION_ACQUISITION"}
    for cid, o in outcomes.items():
        if o["joint_ok"]:
            continue
        bucket = taxonomy.get(cid, {}).get("primary_bucket", "UNCLASSIFIED")
        counts[bucket]["total"] += 1
        if route[cid]:
            counts[bucket]["routed"] += 1
            routed_failures += 1
            eligible_routed += bucket in eligible_buckets
    return {
        "by_bucket": dict(counts),
        "routed_joint_failures": routed_failures,
        "agent_eligible_routed_joint_failures": eligible_routed,
        "agent_eligible_share_of_routed_failures": division(eligible_routed, routed_failures),
    }


def signal_inventory(signals: dict[str, dict]) -> dict:
    vals = list(signals.values())
    numeric = (
        "top1_reranker_score", "top2_reranker_score", "top1_top2_margin", "reranker_mean",
        "reranker_stdev", "bm25_top1_in_final_order", "bm25_mean_final5", "retrieved_count",
        "retrieved_offset_spread", "document_chars", "n_evidence_quotes", "evidence_chars",
    )
    distributions = {}
    for key in numeric:
        xs = sorted(v[key] for v in vals if v[key] is not None)
        distributions[key] = {
            "min": min(xs), "median": statistics.median(xs), "mean": statistics.mean(xs), "max": max(xs)
        }
    return {
        "available_runtime_signals": sorted(k for k in vals[0] if k != "case_id"),
        "unavailable": [
            "provider logprobs/probabilities (not requested or stored)",
            "self-reported confidence (not in GPT-P0 schema)",
            "full top-20 reranked distribution (artifact preserves final top-5 only)",
        ],
        "forbidden_scorer_only": sorted(FORBIDDEN_ROUTER_KEYS),
        "counts": {
            "unusable": sum(v["unusable"] for v in vals),
            "source_invalid_evidence": sum(v["n_source_invalid_quotes"] > 0 for v in vals),
            "EC_without_evidence": sum(v["predicted_label"] in ("Entailment", "Contradiction") and v["n_evidence_quotes"] == 0 for v in vals),
            "NotMentioned_with_evidence": sum(v["predicted_label"] == "NotMentioned" and v["n_evidence_quotes"] > 0 for v in vals),
            "duplicate_chunks": sum(v["duplicate_chunk_ids"] > 0 or v["duplicate_chunk_texts"] > 0 for v in vals),
            "cross_reference_cue": sum(v["cross_reference_cue"] for v in vals),
            "exception_qualification_cue": sum(v["exception_qualification_cue"] for v in vals),
            "predicted_labels": dict(Counter(v["predicted_label"] for v in vals)),
            "retrieved_chunk_counts": dict(Counter(str(v["retrieved_count"]) for v in vals)),
        },
        "numeric_distributions": distributions,
    }


def auroc_diagnostics(signals: dict[str, dict], outcomes: dict[str, dict]) -> dict:
    ids = list(outcomes)
    y = [not outcomes[cid]["joint_ok"] for cid in ids]
    diagnostics = {}
    for name, score in {
        "negative_top1_reranker_score": [-signals[cid]["top1_reranker_score"] for cid in ids],
        "negative_top1_top2_margin": [-signals[cid]["top1_top2_margin"] for cid in ids],
    }.items():
        diagnostics[name] = roc_auc_score(y, score)
    return diagnostics


def choose_router(results: dict[str, dict]) -> dict:
    candidates = []
    for name, result in results.items():
        if name == "R0" or name.startswith("H_"):
            continue
        joint = result["joint"]
        if joint["review_rate"] <= 0.40 and joint["residual_error_among_accepted"] < 0.10:
            candidates.append(name)
    family_rank = {"R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}
    quantile_rank = {"q10": 1, "q20": 2, "q30": 3}

    def key(name: str) -> tuple:
        r = results[name]
        prefix = name.split("_")[0]
        suffix = name.split("_")[1] if "_" in name else "q10"
        return (
            -r["contradiction"]["joint"]["failure_capture_rate"],
            -r["joint"]["failure_capture_rate"],
            r["joint"]["review_rate"],
            family_rank[prefix],
            quantile_rank[suffix],
        )

    selected = sorted(candidates, key=key)[0] if candidates else None
    return {
        "selected": selected,
        "passing_candidates": sorted(candidates),
        "decision": "router selected for agent-eligibility consideration" if selected else
        "no router meets both predeclared targets; stop before agent pilot",
    }


def pareto_frontier(results: dict[str, dict]) -> list[str]:
    eligible = [name for name in results if not name.startswith("H_")]
    frontier = []
    for name in eligible:
        a = results[name]["joint"]
        dominated = False
        for other in eligible:
            if other == name:
                continue
            b = results[other]["joint"]
            no_worse = b["review_rate"] <= a["review_rate"] and b["failure_capture_rate"] >= a["failure_capture_rate"]
            strict = b["review_rate"] < a["review_rate"] or b["failure_capture_rate"] > a["failure_capture_rate"]
            if no_worse and strict:
                dominated = True
                break
        if not dominated:
            frontier.append(name)
    return sorted(frontier, key=lambda n: results[n]["joint"]["review_rate"])


def markdown_summary(analysis: dict) -> str:
    within_ceiling = [
        (name, result) for name, result in analysis["routers"].items()
        if not name.startswith("H_") and result["joint"]["review_rate"] <= 0.40
    ]
    best_within_ceiling, best_result = min(
        within_ceiling, key=lambda item: item[1]["joint"]["residual_error_among_accepted"]
    )
    lines = [
        "# Stage C2 — RAG evidence/retrieval-risk routing", "",
        "No hosted calls were made. All routers use runtime-only features; gold and the E09 failure taxonomy are scorer-only.", "",
        "## Decision", "", f"**{analysis['selection']['decision']}**", "",
        "The inherited target is review rate ≤40% **and** residual joint error among accepted cases <10%.", "",
        f"The lowest residual error achievable within the workload ceiling is `{best_within_ceiling}` at "
        f"{100*best_result['joint']['review_rate']:.1f}% review and "
        f"{100*best_result['joint']['residual_error_among_accepted']:.1f}% residual Joint error—more than twice the target.", "",
        "## Router results", "",
        "| Router | Routed | Review | Joint failures caught | Residual joint error | C label failures caught | C joint failures caught | Precision | False-review | Agent-eligible routed failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    order = ["R0", "R1"] + [f"R{x}_{q}" for x in range(2, 6) for q in QUANTILES] + ["H_rule_disagreement"]
    for name in order:
        r = analysis["routers"][name]
        j, c, t = r["joint"], r["contradiction"], r["taxonomy"]
        pct = lambda x: "—" if x is None else f"{100*x:.1f}%"
        lines.append(
            f"| {name} | {j['routed']}/150 | {pct(j['review_rate'])} | "
            f"{j['failures_captured']}/{j['total_failures']} ({pct(j['failure_capture_rate'])}) | "
            f"{pct(j['residual_error_among_accepted'])} | "
            f"{c['classification']['failures_routed']}/{c['classification']['failures']} | "
            f"{c['joint']['failures_routed']}/{c['joint']['failures']} | "
            f"{pct(j['routing_precision'])} | {pct(j['false_review_rate'])} | "
            f"{t['agent_eligible_routed_joint_failures']}/{t['routed_joint_failures']} |"
        )
    base = analysis["base_rag"]
    lines += [
        "", "## Base RAG", "",
        f"- Accuracy: {base['classification_correct']}/150 ({100*base['accuracy']:.1f}%)",
        f"- Joint: {base['joint_correct']}/150 ({100*base['joint_success']:.1f}%)",
        f"- Contradiction Recall: {base['contradiction_correct']}/50 ({100*base['contradiction_recall']:.1f}%)",
        f"- Contradiction joint success: {base['contradiction_joint_correct']}/50 ({100*base['contradiction_joint_success']:.1f}%)",
        "", "## Agent-eligibility conclusion", "",
    ]
    selected = analysis["selection"]["selected"]
    if selected:
        t = analysis["routers"][selected]["taxonomy"]
        lines.append(
            f"Selected router `{selected}` captures {t['agent_eligible_routed_joint_failures']} scorer-side information-acquisition failures "
            f"among {t['routed_joint_failures']} routed joint failures ({100*t['agent_eligible_share_of_routed_failures']:.1f}%)."
        )
    else:
        lines.append("No router passed the workload+safety target, so Stage C3 is not authorized regardless of diagnostic agent eligibility.")
    lines += [
        "", "## Secondary diagnostics", "",
        f"- Pareto frontier: {', '.join(analysis['pareto_frontier'])}",
        f"- Weak-score AUROC: {analysis['auroc']['negative_top1_reranker_score']:.3f}",
        f"- Ambiguity-margin AUROC: {analysis['auroc']['negative_top1_top2_margin']:.3f}",
        "- AUROC is diagnostic only and was not used to choose a router.",
        "", "## Governance", "",
        "The approved pilot cost-per-net-C-recovery threshold is descriptive during a 20–30 case pilot and blocking only at confirmation. Final retention also requires the frozen Group F direct-human economic/workload comparison in `frozen_protocol.json`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    predictions_list = load_jsonl(PREDICTIONS_PATH)
    predictions = {row["case_id"]: row for row in predictions_list}
    retrieval_raw = json.loads(RETRIEVAL_PATH.read_text())["cases"]
    retrieval = {row["case_id"]: row for row in retrieval_raw}
    gold_raw = json.loads(GOLD_PATH.read_text())["cases"]
    gold = {row["case_id"]: row for row in gold_raw}
    train = json.loads(TRAIN_PATH.read_text())
    docs = {row["id"]: row for row in train["documents"]}
    with TAXONOMY_PATH.open(newline="") as handle:
        taxonomy = {row["case_id"]: row for row in csv.DictReader(handle)}

    assert len(predictions) == len(retrieval) == len(gold) == 150
    assert set(predictions) == set(retrieval) == set(gold)
    assert Counter(row["gold_label"] for row in gold.values()) == Counter({label: 50 for label in LABELS})
    for cid, p in predictions.items():
        assert p["gold_label"] == gold[cid]["gold_label"]

    signals = {}
    for cid, p in predictions.items():
        runtime_prediction = {
            key: p.get(key) for key in (
                "case_id", "document_id", "hypothesis_id", "predicted_label", "parse_status",
                "error_type", "evidence",
            )
        }
        signal = build_runtime_signals(
            runtime_prediction, retrieval[cid], docs[p["document_id"]]["text"]
        )
        signal["document_span_count"] = len(docs[p["document_id"]]["spans"])
        assert not (FORBIDDEN_ROUTER_KEYS & set(signal))
        signals[cid] = signal

    routes, reasons = build_routes(signals, protocol)
    outcomes = score_outcomes(predictions, retrieval, gold, docs)
    router_results = {}
    for name, route in routes.items():
        router_results[name] = {
            "joint": routing_metrics(route, outcomes, "joint_ok"),
            "classification": routing_metrics(route, outcomes, "label_ok"),
            "contradiction": contradiction_metrics(route, outcomes),
            "taxonomy": taxonomy_metrics(route, outcomes, taxonomy),
        }

    cids = list(outcomes)
    c_cases = [cid for cid in cids if outcomes[cid]["gold_label"] == "Contradiction"]
    analysis = {
        "stage": "C2_ROUTING_ONLY",
        "hosted_calls": 0,
        "population": {"n": 150, "class_distribution": dict(Counter(outcomes[cid]["gold_label"] for cid in cids))},
        "base_rag": {
            "classification_correct": sum(outcomes[cid]["label_ok"] for cid in cids),
            "accuracy": sum(outcomes[cid]["label_ok"] for cid in cids) / 150,
            "joint_correct": sum(outcomes[cid]["joint_ok"] for cid in cids),
            "joint_success": sum(outcomes[cid]["joint_ok"] for cid in cids) / 150,
            "contradiction_correct": sum(outcomes[cid]["label_ok"] for cid in c_cases),
            "contradiction_recall": sum(outcomes[cid]["label_ok"] for cid in c_cases) / len(c_cases),
            "contradiction_joint_correct": sum(outcomes[cid]["joint_ok"] for cid in c_cases),
            "contradiction_joint_success": sum(outcomes[cid]["joint_ok"] for cid in c_cases) / len(c_cases),
        },
        "signal_inventory": signal_inventory(signals),
        "auroc": auroc_diagnostics(signals, outcomes),
        "routers": router_results,
        "selection": choose_router(router_results),
        "pareto_frontier": pareto_frontier(router_results),
        "leakage_check": {
            "router_feature_keys": sorted(k for k in next(iter(signals.values())) if k != "case_id"),
            "forbidden_key_intersection": sorted(FORBIDDEN_ROUTER_KEYS & set(next(iter(signals.values())))),
            "gold_joined_after_routes_constructed": True,
            "status": "PASS",
        },
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "routing_results.json").write_text(json.dumps(analysis, indent=2) + "\n")
    with (RESULTS / "scored_cases.jsonl").open("w") as handle:
        for cid in sorted(cids):
            row = {
                "case_id": cid,
                "predicted_label": signals[cid]["predicted_label"],
                **outcomes[cid],
                "failure_bucket_scorer_only": taxonomy.get(cid, {}).get("primary_bucket"),
                "oracle_action_scorer_only": taxonomy.get(cid, {}).get("oracle_action_needed"),
                "routes": {name: route[cid] for name, route in routes.items()},
                "route_reasons": {name: reasons[name][cid] for name in routes},
            }
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (ADDENDUM / "summary.md").write_text(markdown_summary(analysis))

    print(json.dumps({
        "selection": analysis["selection"],
        "pareto_frontier": analysis["pareto_frontier"],
        "base_rag": analysis["base_rag"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
