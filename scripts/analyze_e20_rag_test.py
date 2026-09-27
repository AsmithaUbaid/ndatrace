#!/usr/bin/env python3
"""E20: score the completed frozen top-5 RAG TEST run (2,091 cases) and compare against the
historical FULL comparator (E17B). Read-only analysis -- no hosted calls, no prompt/retrieval/
model changes. Mirrors scripts/e17b_merge_and_analyze.py's scoring conventions so the two
architectures are measured identically."""
from __future__ import annotations
import hashlib, json, sys
from collections import Counter
from math import comb
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation import evidence_matching as EM  # noqa: E402

D = REPO / "experiments/E20_final_rag_test"
E17B = REPO / "experiments/E17B_full_test_completion"
E17 = REPO / "experiments/E17_final_test"
LABELS = ("Entailment", "Contradiction", "NotMentioned")
W = {"Entailment": 968, "Contradiction": 220, "NotMentioned": 903}

wilson = lambda k, n, z=1.96: None if not n else [round(max(0.0, (k / n + z * z / (2 * n) - z * np.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n))) / (1 + z * z / n)), 4),
                                                   round(min(1.0, (k / n + z * z / (2 * n) + z * np.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n))) / (1 + z * z / n)), 4)]


def macro_f1(S):
    f = []
    for c in LABELS:
        tp = sum(s["pred"] == c and s["gold"] == c for s in S)
        fp = sum(s["pred"] == c and s["gold"] != c for s in S)
        fn = sum(s["gold"] == c and s["pred"] != c for s in S)
        f.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
    return float(np.mean(f))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) * 2 / (2 ** n)
    return min(1.0, p)


def load_gold():
    gold = json.loads((D / "manifests" / "TEST_ALL_2091_GOLD_SCORER_ONLY.json").read_text())
    return {c["case_id"]: c for c in gold["cases"]}


def load_model_cases():
    model = json.loads((D / "manifests" / "TEST_ALL_2091_RAG_retrieval_v1.json").read_text())
    return {c["case_id"]: c for c in model["cases"]}


def main():
    results_path = D / "results" / "run_E20_rag_cases.jsonl"
    rows_raw = [json.loads(l) for l in open(results_path)]
    assert len(rows_raw) == 2091, f"expected 2091 result rows, found {len(rows_raw)}"
    ids = [r["case_id"] for r in rows_raw]
    assert len(set(ids)) == 2091, "duplicate case_id in E20 results"

    gold_by_id = load_gold()
    model_by_id = load_model_cases()
    test = json.loads((REPO / "data/contractnli/test.json").read_text())
    docs = {d["id"]: d for d in test["documents"]}

    scored = []
    for r in rows_raw:
        cid = r["case_id"]
        g = gold_by_id[cid]
        m = model_by_id[cid]
        doc = docs[m["document_id"]]
        gi = g["gold_span_indices"]
        chunk_texts = [c["text"] for c in m["final_top5"]]
        chunk_offsets = [c["offset"] for c in m["final_top5"]]
        ev = r["evidence"] or []
        pi = EM.evidence_to_span_indices(ev, chunk_texts, chunk_offsets, doc["spans"])
        joint = EM.joint_success(g["gold_label"], r["predicted_label"], gi, pi)

        # pure retrieval recall/precision/MRR @5 and @20-pool, independent of the model's quotes
        doc_spans = doc["spans"]
        gold_ranges = [doc_spans[i] for i in gi]

        def overlaps_any(c0, c1):
            return any(min(c1, s1) > max(c0, s0) for s0, s1 in gold_ranges)

        top5_hit_ranks = [rank for rank, c in enumerate(m["final_top5"], start=1) if overlaps_any(*c["offset"])]
        top20_hit = any(overlaps_any(*c["offset"]) for c in m["candidate_pool_top20"])
        retrieval_recall_5 = bool(top5_hit_ranks) if gold_ranges else None
        retrieval_recall_20 = top20_hit if gold_ranges else None
        retrieval_precision_5 = (len(top5_hit_ranks) / 5) if gold_ranges else None
        retrieval_rr_5 = (1.0 / top5_hit_ranks[0]) if top5_hit_ranks else (0.0 if gold_ranges else None)

        scored.append({
            "case_id": cid, "document_id": m["document_id"], "hypothesis_id": m["hypothesis_id"],
            "gold": g["gold_label"], "pred": r["predicted_label"], "ok": r["predicted_label"] == g["gold_label"],
            "joint": bool(joint), "gold_idx": gi, "pred_idx": pi, "has_ev": bool(ev), "n_quotes": len(ev),
            "n_nonsource": r.get("evidence_hallucinated_count", 0),
            "gold_overlap": bool(set(gi) & set(pi)) if gi else None,
            "parse": r.get("parse_status", "invalid"), "in_tok": r.get("input_tokens"), "out_tok": r.get("output_tokens"),
            "lat_ms": r.get("generation_latency_ms"), "cost": r.get("cost_usd"), "error": r.get("error_type"),
            "length_band": m["predeclared_length_band"],
            "retrieval_recall_5": retrieval_recall_5, "retrieval_recall_20": retrieval_recall_20,
            "retrieval_precision_5": retrieval_precision_5, "retrieval_rr_5": retrieval_rr_5,
        })

    def summarize(S):
        n = len(S)
        by = {c: [s for s in S if s["gold"] == c] for c in LABELS}
        eb = [s for s in S if s["gold_idx"]]
        pc = [s for s in S if s["has_ev"]]
        tq = sum(s["n_quotes"] for s in S)
        res = {
            "n": n, "accuracy": sum(s["ok"] for s in S) / n, "macro_f1": macro_f1(S),
            "joint": sum(s["joint"] for s in S) / n, "joint_n": sum(s["joint"] for s in S),
            "recall": {c: sum(s["ok"] for s in by[c]) / len(by[c]) for c in LABELS},
            "recall_counts": {c: [sum(s["ok"] for s in by[c]), len(by[c])] for c in LABELS},
            "recall_wilson95": {c: wilson(sum(s["ok"] for s in by[c]), len(by[c])) for c in LABELS},
            "joint_by_class": {c: sum(s["joint"] for s in by[c]) / len(by[c]) for c in LABELS},
            "joint_counts": {c: [sum(s["joint"] for s in by[c]), len(by[c])] for c in LABELS},
            "confusion_rows_gold_cols_pred": {g: {**{p: sum(s["pred"] == p for s in by[g]) for p in LABELS},
                                                   "invalid": sum(s["pred"] is None for s in by[g])} for g in LABELS},
            "evidence_recall": sum(bool(s["gold_overlap"]) for s in eb) / len(eb) if eb else None,
            "evidence_precision": (sum(bool(s["gold_overlap"]) for s in pc) / len(pc)) if pc else None,
            "source_valid_quote_rate": (1 - sum(s["n_nonsource"] for s in S) / tq) if tq else None,
            "parse_counts": dict(Counter(s["parse"] for s in S)),
        }
        ok = [s for s in S if s["in_tok"]]
        if ok:
            lat = [s["lat_ms"] for s in ok if s["lat_ms"]]
            res["ops"] = {
                "input_tokens_mean": float(np.mean([s["in_tok"] for s in ok])),
                "output_tokens_mean": float(np.mean([s["out_tok"] for s in ok])),
                "latency_ms_mean": float(np.mean(lat)), "latency_ms_median": float(np.median(lat)),
                "latency_ms_p95": float(np.percentile(lat, 95)),
                "total_cost_usd": sum(s["cost"] or 0 for s in S), "cost_per_case": sum(s["cost"] or 0 for s in S) / n,
            }
        return res

    RAG = summarize(scored)
    contra = RAG["confusion_rows_gold_cols_pred"]["Contradiction"]
    contra_summary = {
        "correct": RAG["recall_counts"]["Contradiction"], "recall": RAG["recall"]["Contradiction"],
        "joint": RAG["joint_counts"]["Contradiction"], "C_to_E": contra["Entailment"], "C_to_NM": contra["NotMentioned"],
        "invalid": contra["invalid"],
    }
    RAG["cost_per_joint_success"] = RAG["ops"]["total_cost_usd"] / RAG["joint_n"] if RAG["joint_n"] else None

    # retrieval-only diagnostics (16), averaged over the 1,188 Entailment+Contradiction cases
    retr = [s for s in scored if s["retrieval_recall_5"] is not None]
    retrieval_diag = {
        "n_with_gold_evidence": len(retr),
        "recall_at_5": sum(s["retrieval_recall_5"] for s in retr) / len(retr),
        "recall_at_20_pool": sum(s["retrieval_recall_20"] for s in retr) / len(retr),
        "precision_at_5": float(np.mean([s["retrieval_precision_5"] for s in retr])),
        "mrr_at_5": float(np.mean([s["retrieval_rr_5"] for s in retr])),
    }

    # failure taxonomy (item 16)
    def bucket(s):
        if s["joint"]:
            return None
        if not s["retrieval_recall_5"] and s["gold_idx"]:
            return "retrieval_limited"
        if s["n_nonsource"] > 0:
            return "runtime_parser_source_validity"
        if s["ok"]:
            return "evidence_selection"
        return "reasoning_classification"
    failures = [s for s in scored if not s["joint"]]
    taxonomy = dict(Counter(bucket(s) for s in failures))

    # length-band analysis (item 19), using the predeclared, outcome-independent tercile bands
    bands = {}
    for band in ("short", "medium", "long"):
        S = [s for s in scored if s["length_band"] == band]
        bands[band] = {"n": len(S), "accuracy": sum(s["ok"] for s in S) / len(S) if S else None,
                       "joint": sum(s["joint"] for s in S) / len(S) if S else None}

    # same-population FULL vs RAG comparison + paired significance (items 17-18)
    e17_150 = [json.loads(l) for l in open(E17 / "results/run_E17_gpt_hosted_test_cases.jsonl")]
    e17b_1941 = [json.loads(l) for l in open(E17B / "results/run_E17B_gpt_cases.jsonl")]
    full_merged = {r["case_id"]: r for r in e17_150}
    for r in e17b_1941:
        full_merged[r["case_id"]] = r
    full_scored = []
    for cid, r in full_merged.items():
        g = gold_by_id[cid]
        doc = docs[r["document_id"]]
        gi = g["gold_span_indices"]
        ev = r.get("evidence") or []
        pi = EM.evidence_to_span_indices(ev, [doc["text"]], [[0, len(doc["text"])]], doc["spans"])
        joint = EM.joint_success(g["gold_label"], r.get("predicted_label"), gi, pi)
        full_scored.append({"case_id": cid, "ok": r.get("predicted_label") == g["gold_label"], "joint": bool(joint)})
    full_by = {s["case_id"]: s for s in full_scored}
    rag_by = {s["case_id"]: s for s in scored}
    common_ids = sorted(set(full_by) & set(rag_by))
    assert len(common_ids) == 2091

    def paired(ids_subset, key):
        b = c = both_r = both_w = 0
        for cid in ids_subset:
            f, rg = full_by[cid][key], rag_by[cid][key]
            if f and rg:
                both_r += 1
            elif f and not rg:
                b += 1
            elif not f and rg:
                c += 1
            else:
                both_w += 1
        return {"full_correct_rag_wrong": b, "rag_correct_full_wrong": c, "both_correct": both_r,
                "both_wrong": both_w, "n": len(ids_subset), "mcnemar_p": mcnemar_exact(b, c)}

    paired_cls = paired(common_ids, "ok")
    paired_joint = paired(common_ids, "joint")
    FULL_accuracy = sum(s["ok"] for s in full_scored) / len(full_scored)
    FULL_joint = sum(s["joint"] for s in full_scored) / len(full_scored)

    full_metrics = json.loads((E17B / "results/final_full_test_metrics.json").read_text())["full_gpt_2091"]
    full_vs_rag = {
        "FULL": {"accuracy": full_metrics["accuracy"], "macro_f1": full_metrics["macro_f1"], "joint": full_metrics["joint"],
                 "recall": full_metrics["recall"], "evidence_recall": full_metrics["evidence_recall"],
                 "evidence_precision": full_metrics["evidence_precision"], "source_valid_quote_rate": full_metrics["source_valid_quote_rate"],
                 "cost_per_case": full_metrics["ops"]["cost_per_case"], "input_tokens_mean": full_metrics["ops"]["input_tokens_mean"],
                 "latency_ms_mean": full_metrics["ops"]["latency_ms_mean"]},
        "RAG": {"accuracy": RAG["accuracy"], "macro_f1": RAG["macro_f1"], "joint": RAG["joint"], "recall": RAG["recall"],
                "evidence_recall": RAG["evidence_recall"], "evidence_precision": RAG["evidence_precision"],
                "source_valid_quote_rate": RAG["source_valid_quote_rate"], "cost_per_case": RAG["ops"]["cost_per_case"],
                "input_tokens_mean": RAG["ops"]["input_tokens_mean"], "latency_ms_mean": RAG["ops"]["latency_ms_mean"]},
        "delta_accuracy_full_minus_rag": full_metrics["accuracy"] - RAG["accuracy"],
        "delta_joint_full_minus_rag": full_metrics["joint"] - RAG["joint"],
        "input_token_reduction_pct": 1 - RAG["ops"]["input_tokens_mean"] / full_metrics["ops"]["input_tokens_mean"],
        "cost_reduction_pct": 1 - RAG["ops"]["cost_per_case"] / full_metrics["ops"]["cost_per_case"],
    }

    # multi-requirement cost projection (item 20): one NDA review = 17 hypothesis calls
    projection = {
        "per_case_cost_usd": RAG["ops"]["cost_per_case"],
        "per_document_17_requirements_usd": RAG["ops"]["cost_per_case"] * 17,
        "per_1000_documents_usd": RAG["ops"]["cost_per_case"] * 17 * 1000,
        "full_context_per_document_17_requirements_usd": full_metrics["ops"]["cost_per_case"] * 17,
        "full_context_per_1000_documents_usd": full_metrics["ops"]["cost_per_case"] * 17 * 1000,
    }

    # E18 cost-to-serve comparison (item 21): allin_cost = C_AI + (1 - p_safe) * C_H, p_safe = joint success
    e18 = json.loads((REPO / "experiments/E18_business_course_synthesis/results/e18_analysis.json").read_text())
    C_H = e18["cost_to_serve"]["human_review_cost_scenarios_usd_per_case"]["5min_at_$40/hr"]
    rag_allin = RAG["ops"]["cost_per_case"] + (1 - RAG["joint"]) * C_H
    break_even = e18["cost_to_serve"]["break_even"]
    full_allin = break_even["AI_plus_human_vs_manual_only"]["gpt_allin_cost_per_case"]
    manual_only = break_even["AI_plus_human_vs_manual_only"]["manual_only_cost_per_case"]
    cost_to_serve = {
        "C_H_scenario_used": "5min_at_$40/hr", "C_H_usd_per_case": C_H,
        "RAG_C_AI": RAG["ops"]["cost_per_case"], "RAG_p_safe(joint)": RAG["joint"], "RAG_allin_cost_per_case": rag_allin,
        "FULL_C_AI": full_metrics["ops"]["cost_per_case"], "FULL_p_safe(joint)": full_metrics["joint"], "FULL_allin_cost_per_case": full_allin,
        "manual_only_cost_per_case": manual_only,
        "rag_cheaper_than_manual": rag_allin < manual_only,
        "rag_cheaper_than_full_allin": rag_allin < full_allin,
    }

    out = {
        "population": {"n": 2091, "gold_label_counts": dict(Counter(s["gold"] for s in scored))},
        "RAG_metrics": RAG, "RAG_contradiction_detail": contra_summary, "retrieval_diagnostics": retrieval_diag,
        "failure_taxonomy": taxonomy, "n_total_failures": len(failures), "length_band_analysis": bands,
        "full_vs_rag_same_population": full_vs_rag, "paired_classification": paired_cls, "paired_joint": paired_joint,
        "full_accuracy_recomputed_check": FULL_accuracy, "full_joint_recomputed_check": FULL_joint,
        "multi_requirement_cost_projection": projection, "cost_to_serve_comparison": cost_to_serve,
    }
    out_path = D / "results" / "E20_final_report.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    (D / "results" / "E20_final_report.sha256").write_text(hashlib.sha256(out_path.read_bytes()).hexdigest() + "\n")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
