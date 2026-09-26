#!/usr/bin/env python3
"""E15 Stage A: offline routing-policy evaluation on stored E13 FULL (GPT-5-mini + GPT-P0) DEV outputs + fresh-DEV validation planning + cost forecast.
ZERO model calls, NO TEST. Routing FEATURES use inference-time signals only; gold is used ONLY to evaluate. Evaluator = frozen evidence_evaluator_v2."""
from __future__ import annotations
import csv, glob, json, random, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation import evidence_matching as EM  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.rule_baseline import classify_by_keywords  # noqa: E402
from pipeline.parser import parse_contractnli_file  # noqa: E402
from scripts.run_oracle_experiment import stratified_sample  # noqa: E402

E13 = REPO / "experiments/E13_gpt_context_architecture"
OUT = REPO / "experiments/E15_review_routing/results"
DEV = json.load(open(REPO / "data/contractnli/dev.json")); DOCS = {d["id"]: d for d in DEV["documents"]}
GOLD = {c["case_id"]: c for c in json.load(open(E13 / "DEV_ARCH_v1_GOLD.json"))["cases"]}
FULLCTX = {c["case_id"]: c["context_text"] for c in json.load(open(E13 / "DEV_ARCH_v1_FULL_CONTEXT.json"))["cases"]}
RUN = [json.loads(l) for l in open(E13 / "results/run_E13_gpt_full_cases.jsonl")]
ASSERT_NO_GOLD_FEATURES = ("gold_label", "gold_span_indices", "joint", "correct")

# ------------------------------------------------------------------ inference-time signals (NO gold)
def signals(r):
    """Only fields observable when the request completes (no evaluation-side truth is read here)."""
    ctx = FULLCTX[r["case_id"]]; ev = r["evidence"] or []; label = r["predicted_label"]
    v = validate_evidence(ctx, ev, label or "")            # runtime validator v2 (E14), source-grounding only
    return {"label": label, "parse_status": r["parse_status"], "error": r["error_type"], "retries": r["retry_count"],
            "n_quotes": len(ev), "n_hallucinated_v2": len(v.hallucinated_quotes), "n_duplicate_quotes": len(ev) - len(set(ev)),
            "evidence_chars": sum(len(q) for q in ev), "context_chars": r["context_chars"], "output_tokens": r["output_tokens"],
            "latency_ms": r["generation_latency_ms"], "label_evidence_consistent": v.label_evidence_consistent,
            "unusable": r["parse_status"] not in ("strict", "recovered") or r["predicted_label"] is None or r["error_type"] is not None,
            "rule_label": classify_by_keywords(r["hypothesis_id"], ctx)}      # deterministic keyword rule (pipeline/rule_baseline.py), input-only

R1_REASONS = lambda s: [n for n, c in (
    ("unusable_parse_or_error", s["unusable"]),
    ("EC_without_source_valid_evidence", s["label"] in ("Entailment", "Contradiction") and (s["n_quotes"] == 0 or s["n_quotes"] == s["n_hallucinated_v2"])),
    ("hallucinated_evidence", s["n_hallucinated_v2"] > 0),
    ("NotMentioned_with_evidence", s["label"] == "NotMentioned" and s["n_quotes"] > 0)) if c]
POLICIES = {
    "R0": lambda s: False,
    "R1": lambda s: bool(R1_REASONS(s)),
    "R2": lambda s: bool(R1_REASONS(s)) or s["label"] == "Contradiction",
    "R3": lambda s: bool(R1_REASONS(s)) or s["rule_label"] != s["label"],
}

# ------------------------------------------------------------------ evaluation-side truth (gold), evaluator v2
def outcome(r):
    d = DOCS[r["document_id"]]; ctx = FULLCTX[r["case_id"]]; g = GOLD[r["case_id"]]; ev = r["evidence"] or []
    gi = json.loads(g["gold_span_indices"]) if isinstance(g["gold_span_indices"], str) else g["gold_span_indices"]
    pi = EM.evidence_to_span_indices(ev, [ctx], [[0, len(ctx)]], d["spans"])
    lab_ok = r["predicted_label"] == r["gold_label"]
    return {"gold": r["gold_label"], "label_ok": lab_ok, "joint_ok": EM.joint_success(r["gold_label"], r["predicted_label"], gi, pi), "gold_spans": gi, "pred_spans": pi}

def metrics(rows, pol, key):
    """key: 'joint_ok' | 'label_ok'; failure = not key."""
    rev = [POLICIES[pol](s) for s, o in rows]; fail = [not o[key] for s, o in rows]
    n = len(rows); TP = sum(r and f for r, f in zip(rev, fail)); FP = sum(r and not f for r, f in zip(rev, fail))
    FN = sum((not r) and f for r, f in zip(rev, fail)); TN = sum((not r) and not f for r, f in zip(rev, fail))
    auto = FN + TN; div = lambda a, b: (a / b) if b else None
    return {"policy": pol, "failure_def": key, "n": n, "review": TP + FP, "review_rate": (TP + FP) / n, "auto": auto, "automation_coverage": auto / n,
            "confusion": {"failure_review": TP, "failure_auto": FN, "success_review": FP, "success_auto": TN},
            "error_capture": div(TP, TP + FN), "routing_precision": div(TP, TP + FP), "false_review_rate": div(FP, FP + TN),
            "residual_error_rate": div(FN, auto), "selective_success": div(TN, auto), "total_failures": TP + FN}

def main():
    rows = []
    for r in RUN:
        assert r["case_id"] in GOLD and r["gold_label"] == GOLD[r["case_id"]]["gold_label"]
        rows.append((signals(r), outcome(r), r))
    R = [(s, o) for s, o, _ in rows]
    res = {"n": len(rows), "joint_success": sum(o["joint_ok"] for _, o in R), "label_correct": sum(o["label_ok"] for _, o in R), "policies": {}}

    # signal availability inventory
    sig = {"available": sorted(signals(RUN[0]).keys()) + ["input_tokens", "retry_count", "cost_usd"],
           "not_available": ["confidence/probability (GPT-P0 schema is {label,evidence} only)", "logprobs (not requested/recorded)", "retrieval scores (FULL context has no retrieval)", "timeouts/provider errors: fields exist (error_type, retry_count) but are all None/0 in E13 FULL (150/150 strict parse, 0 errors, 0 retries)"],
           "forbidden_gold_only": ["gold_label", "gold_span_indices / gold evidence", "joint_success / label correctness", "gold-derived retrieval rank", "E13 manual error categories", "TEST behaviour"],
           "signal_value_counts": {"parse_status": dict(Counter(s["parse_status"] for s, _ in R)), "unusable": sum(s["unusable"] for s, _ in R), "hallucinated_v2>0": sum(s["n_hallucinated_v2"] > 0 for s, _ in R),
                                    "NM_with_evidence": sum(s["label"] == "NotMentioned" and s["n_quotes"] > 0 for s, _ in R), "EC_without_evidence": sum(s["label"] in ("Entailment", "Contradiction") and s["n_quotes"] == 0 for s, _ in R),
                                    "duplicate_quotes>0": sum(s["n_duplicate_quotes"] > 0 for s, _ in R), "pred_label_counts": dict(Counter(s["label"] for s, _ in R))}}
    res["signals"] = sig

    for pol in POLICIES:
        res["policies"][pol] = {"joint": metrics(R, pol, "joint_ok"), "classification": metrics(R, pol, "label_ok")}
        rev = [POLICIES[pol](s) for s, _ in R]
        # label-conditional routing behaviour
        res["policies"][pol]["review_rate_by_predicted_label"] = {l: sum(r for r, (s, _) in zip(rev, R) if s["label"] == l) / max(1, sum(s["label"] == l for s, _ in R)) for l in ("Entailment", "Contradiction", "NotMentioned")}
        rbg = {g: sum(r for r, (_, o) in zip(rev, R) if o["gold"] == g) / 50 for g in ("Entailment", "Contradiction", "NotMentioned")}
        res["policies"][pol]["review_rate_by_gold_class"] = rbg
        # descriptive natural-prevalence estimate: post-stratify sample gold-class review rates by official DEV gold distribution (assumes within-class case mix = sample; DEV != production)
        W = {"Entailment": 519, "Contradiction": 95, "NotMentioned": 423}
        res["policies"][pol]["descriptive_dev_prevalence_review_rate"] = sum(rbg[g] * W[g] for g in W) / sum(W.values())
        for per in (100, 1000, 8000):
            res["policies"][pol][f"reviews_per_{per}_balanced"] = round(res["policies"][pol]["joint"]["review_rate"] * per, 1)
            res["policies"][pol][f"reviews_per_{per}_dev_prevalence"] = round(res["policies"][pol]["descriptive_dev_prevalence_review_rate"] * per, 1)
        # contradiction-specific
        cf = [(r, o) for r, (s, o) in zip(rev, R) if o["gold"] == "Contradiction" and not o["joint_ok"]]
        cs = [(r, o) for r, (s, o) in zip(rev, R) if o["gold"] == "Contradiction" and o["joint_ok"]]
        predC = [(r, o) for r, (s, o) in zip(rev, R) if s["label"] == "Contradiction"]
        res["policies"][pol]["contradiction"] = {"true_C_joint_failures": len(cf), "routed": sum(r for r, _ in cf), "capture_rate": (sum(r for r, _ in cf) / len(cf)) if cf else None,
                                                 "correct_C_unnecessarily_reviewed": sum(r for r, _ in cs), "n_correct_C": len(cs), "residual_automated_C_failures": sum(not r for r, _ in cf),
                                                 "predicted_C_cases": len(predC), "predicted_C_wrong_joint_(any gold)_routed": sum(r for r, o in predC if not o["joint_ok"]), "predicted_C_wrong_joint_(any gold)": sum(not o["joint_ok"] for r, o in predC)}

    # Pareto (review_rate vs joint capture): dominated if another policy reviews <= and captures >= with one strict
    pts = {p: (res["policies"][p]["joint"]["review"], res["policies"][p]["joint"]["confusion"]["failure_review"]) for p in POLICIES}
    res["pareto"] = {"points_(reviews,failures_captured)": pts,
                     "dominated_by": {p: [q for q in pts if q != p and pts[q][0] <= pts[p][0] and pts[q][1] >= pts[p][1] and (pts[q][0] < pts[p][0] or pts[q][1] > pts[p][1])] for p in pts}}

    # error buckets (analysis-only; NOT routing features)
    def bucket(s, o):
        if o["joint_ok"]: return None
        if not o["label_ok"]:
            if o["gold"] == "Contradiction": return "contradiction_missed_or_misread (C->E/NM)"
            if o["gold"] == "NotMentioned": return "over_inference (gold NotMentioned, predicted E/C)"
            return "entailment_predicted_NotMentioned" if s["label"] == "NotMentioned" else "entailment_predicted_Contradiction"
        return "label_correct_evidence_invalid_or_nonoverlapping"
    buckets = defaultdict(lambda: {"n": 0, **{p: 0 for p in POLICIES}, "examples": []})
    for s, o, r in rows:
        b = bucket(s, o)
        if b is None: continue
        x = buckets[b]; x["n"] += 1
        for p in POLICIES: x[p] += POLICIES[p](s)
        if len(x["examples"]) < 3: x["examples"].append(r["case_id"] + f" (gold {o['gold']} pred {s['label']})")
    res["failure_buckets"] = buckets
    res["failure_detail"] = [{"case_id": r["case_id"], "gold": o["gold"], "pred": s["label"], "label_ok": o["label_ok"], "n_quotes": s["n_quotes"], "hallucinated": s["n_hallucinated_v2"], "rule_label": s["rule_label"],
                              **{p: POLICIES[p](s) for p in POLICIES}} for s, o, r in rows if not o["joint_ok"]]
    res["rule_baseline_agreement_note"] = {"rule_agrees_rate": sum(s["rule_label"] == s["label"] for s, _ in R) / len(R),
                                           "joint_success_when_agree": (lambda a: sum(o["joint_ok"] for _, o in a) / len(a))([(s, o) for s, o in R if s["rule_label"] == s["label"]]),
                                           "joint_success_when_disagree": (lambda a: sum(o["joint_ok"] for _, o in a) / len(a))([(s, o) for s, o in R if s["rule_label"] != s["label"]])}
    json.dump(res, open(OUT / "routing_policy_eval_e13_full.json", "w"), indent=1, default=str)

    # ------------------------------------------------------------------ fresh DEV pool + proposed manifest (design only)
    ann = {(d["id"], h): a["choice"] for d in DEV["documents"] for h, a in d["annotation_sets"][0]["annotations"].items()}
    hyp = {k: v["hypothesis"] for k, v in DEV["labels"].items()}
    ds = parse_contractnli_file(REPO / "data/contractnli/dev.json")
    s150 = {(int(d.id if hasattr(d, "id") else d.doc_id), a.hypothesis_id) for d, a in stratified_sample(ds, 150, 42)}
    golden = set()
    for f in sorted(glob.glob(str(REPO / "data/golden/*.json"))):
        for c in json.load(open(f)):
            if str(c.get("doc_id", "")).isdigit() and "hypothesis_id" in c: golden.add((int(c["doc_id"]), c["hypothesis_id"]))
    e13 = {(c["document_id"], c["hypothesis_id"]) for c in json.load(open(E13 / "DEV_ARCH_v1.json"))["cases"]}
    pool = [k for k in ann if k not in s150 and k not in golden and k not in e13]
    pc = Counter(ann[k] for k in pool)
    # per-class joint failure rate in E13 FULL (planning input)
    fr = {g: sum(not o["joint_ok"] for _, o in R if o["gold"] == g) / 50 for g in ("Entailment", "Contradiction", "NotMentioned")}
    SEED, N = 1500, {"Contradiction": 18, "Entailment": 60, "NotMentioned": 60}; CAP = 3
    rng, chosen = random.Random(SEED), []
    bydoc = defaultdict(lambda: defaultdict(list))
    for d, h in pool: bydoc[ann[(d, h)]][d].append(h)
    for cls in ("Entailment", "NotMentioned"):
        ids = sorted(bydoc[cls]); rng.shuffle(ids); n = 0
        for d in ids:
            for h in sorted(bydoc[cls][d])[:CAP]:
                if n < N[cls]: chosen.append((d, h, cls)); n += 1
    chosen += [(d, h, "Contradiction") for (d, h) in sorted(pool) if ann[(d, h)] == "Contradiction"]
    chosen.sort(key=lambda c: (c[2], c[0], c[1]))
    assert len(chosen) == sum(N.values()) and not ({(d, h) for d, h, _ in chosen} & (s150 | golden | e13))
    man = {"manifest_id": "DEV_ROUTING_v1_DRAFT", "status": "PROPOSED - not frozen, not run; performance-agnostic (no model output read)", "seed": SEED, "per_class": N, "cap_per_doc_per_class": CAP,
           "contradiction_policy": "ALL remaining fresh Contradictions", "disjoint_from": ["historical 150-case seed-42 sample", "golden battery DEV cases", "DEV_ARCH_v1 (E13)"],
           "n_docs": len({d for d, _, _ in chosen}), "cases": [{"case_id": f"dev::{d}::{h}", "document_id": d, "hypothesis_id": h, "hypothesis_text": hyp[h], "gold_label": c} for d, h, c in chosen]}
    json.dump(man, open(OUT / "proposed_manifest_DEV_ROUTING_v1_DRAFT.json", "w"), indent=1)

    # ------------------------------------------------------------------ cost forecast from actual E13 FULL costs
    costs = sorted(r["cost_usd"] for r in RUN); p90 = costs[int(0.9 * len(costs))]; mean = sum(costs) / len(costs)
    led = sum(float(x["cost_usd"] or 0) for x in csv.DictReader(open(REPO / "results/budget/reconstruction_spend_ledger.csv")))
    n = len(chosen); exp_, cons = n * mean, n * p90
    exp_class = sum(N[g] * fr[g] for g in N)
    res2 = {"ledger_now": round(led, 8), "pool_after_exclusions": {"total": len(pool), **dict(pc)}, "manifest_size": n, "expected_calls": n, "expected_cost": round(exp_, 4), "conservative_cost_p90_every_call": round(cons, 4),
            "per_call_mean": mean, "per_call_p90": p90, "expected_joint_failures_in_manifest_(from_E13_class_rates)": round(exp_class, 1), "E13_FULL_joint_failure_rate_by_gold_class": fr,
            "budget_plan": 5.00, "reserve": 1.25, "gate_expected": round(led + exp_ + 1.25, 4), "gate_conservative": round(led + cons + 1.25, 4),
            "gate_pass": led + cons + 1.25 <= 5.00, "remaining_after_conservative": round(5.00 - (led + cons), 4), "reserve_intact": led + cons <= 3.75,
            "pool_left_after_manifest": {"Entailment": pc["Entailment"] - N["Entailment"], "NotMentioned": pc["NotMentioned"] - N["NotMentioned"], "Contradiction": 0}}
    json.dump(res2, open(OUT / "fresh_dev_plan_and_cost_forecast.json", "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("n", "joint_success", "label_correct")}))
    for p in POLICIES:
        j = res["policies"][p]["joint"]; c = res["policies"][p]["classification"]
        print(p, "review", j["review"], f"{j['review_rate']:.3f}", "cap_joint", j["error_capture"], "cap_cls", c["error_capture"], "resid", j["residual_error_rate"], "falserev", j["false_review_rate"], j["confusion"])
    print(json.dumps(res["pareto"], default=str)); print(json.dumps(res2, indent=1))

if __name__ == "__main__":
    main()
