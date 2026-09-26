#!/usr/bin/env python3
"""E12B Stage B analysis (evaluator-side). Scoring reuses scripts/analyze_e08b_stronger_model.py helpers (same span-overlap and
joint definitions used for E08B/E12A). Applies the FROZEN selection rule programmatically.
'Macro-F1 materially worse' is interpreted as a drop of more than 0.03 vs P0 (fixed before any result was seen)."""
from __future__ import annotations
import json, random, statistics, sys
from collections import Counter
from pathlib import Path
from scipy import stats
from sklearn.metrics import confusion_matrix, f1_score, recall_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
from evaluation.metrics import wilson_score_interval  # noqa: E402
import analyze_e08b_stronger_model as A  # noqa: E402

D = REPO / "experiments/E12B_gpt_prompt_optimization"; R = D / "results"
LABELS, ORDER = A.LABELS, ["gpt_p0", "gpt_p1", "gpt_p2", "gpt_p3"]
SHORT = {"Entailment": "E", "Contradiction": "C", "NotMentioned": "NM", None: "X"}
GUARD_CASES, ADOPT_NET, F1_TOL, HARM_NET = 3, 9, 0.03, -5
N_BOOT, SEED = 10_000, 900
CTX = {c["case_id"]: c for c in json.load(open(D / "TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
GOLD = {c["case_id"]: c["gold_span_indices"] for c in json.load(open(D / "TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1_GOLD.json"))["cases"]}
DOCSP = A.load_doc_spans()
PTOK = json.load(open(R / "pre_run_forecast.json"))["prompt_stats"]


def score(raw):
    out = []
    for c in raw:
        gi, ds, off = GOLD[c["case_id"]], DOCSP[c["document_id"]], c["retrieved_chunk_offsets"]
        pi = A.evidence_to_span_indices(c.get("evidence") or [], CTX[c["case_id"]]["ranked_chunk_text"], off, ds)
        d = dict(c); d.update(pred_span_idx=pi, gold_span_idx=gi, correct=c["gold_label"] == c["predicted_label"],
                              gold_overlap=(bool(set(gi) & set(pi)) if gi else None),
                              joint=A.joint_success(c["gold_label"], c["predicted_label"], gi, pi))
        out.append(d)
    return out


def dist(v):
    v = sorted(x for x in v if x is not None)
    return {"mean": statistics.mean(v), "median": statistics.median(v), "p90": v[min(int(len(v) * .9), len(v) - 1)], "max": max(v)}


def macro(g, p): return f1_score(g, p, labels=LABELS, average="macro", zero_division=0)


def summarize(rows):
    n = len(rows); g = [r["gold_label"] for r in rows]; p = [r["predicted_label"] or "PARSE_FAILED" for r in rows]
    rec = dict(zip(LABELS, recall_score(g, p, labels=LABELS, average=None, zero_division=0)))
    cn = sum(x == "Contradiction" for x in g); ch = sum(a == b == "Contradiction" for a, b in zip(g, p))
    eb = [r for r in rows if r["gold_span_idx"]]; claims = [bool(set(r["gold_span_idx"]) & set(r["pred_span_idx"])) for r in rows if r.get("evidence")]
    ev = [r for r in rows if r.get("evidence")]
    jb = {l: sum(r["joint"] for r in rows if r["gold_label"] == l) / 50 for l in LABELS}
    costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    ins = [r["input_tokens"] for r in rows]; outs = [r["output_tokens"] for r in rows]
    return {"n": n, "accuracy": sum(r["correct"] for r in rows) / n, "macro_f1": macro(g, p), "recall": rec,
            "contradiction_correct": ch, "contradiction_n": cn, "contradiction_ci95": list(wilson_score_interval(ch, cn)),
            "confusion_matrix": confusion_matrix(g, p, labels=LABELS).tolist(),
            "parse": {s: sum(r["parse_status"] == s for r in rows) for s in ("strict", "recovered", "invalid")},
            "errors": sum(bool(r.get("error_type")) for r in rows), "retries": sum(r.get("retry_count") or 0 for r in rows),
            "source_valid_evidence_rate": statistics.mean(bool(r["evidence_valid"]) for r in ev) if ev else None,
            "evidence_recall": sum(bool(r["gold_overlap"]) for r in eb) / len(eb),
            "gold_overlap_rate_of_evidence_bearing": sum(bool(r["gold_overlap"]) for r in eb) / len(eb),
            "evidence_precision": sum(claims) / len(claims) if claims else None,
            "joint": sum(r["joint"] for r in rows) / n, "joint_n": sum(r["joint"] for r in rows), "joint_by_class": jb,
            "input_tokens": dist(ins), "output_tokens": dist(outs), "total_tokens_mean": statistics.mean(ins) + statistics.mean(outs),
            "latency_ms": dist([r["generation_latency_ms"] for r in rows]),
            "cost": {"total": sum(costs), "mean": statistics.mean(costs), "median": statistics.median(costs), "p90": sorted(costs)[int(.9 * len(costs))], "max": max(costs)}}


def mcnemar(a, b):
    x = sum(u and not v for u, v in zip(a, b)); y = sum(v and not u for u, v in zip(a, b)); nd = x + y
    return {"p0_only": x, "candidate_only": y, "n_discordant": nd, "p": 1.0 if nd == 0 else float(stats.binomtest(min(x, y), nd, .5).pvalue)}


def trans(a, b):
    return {"wrong_to_right": sum((not u) and v for u, v in zip(a, b)), "right_to_wrong": sum(u and not v for u, v in zip(a, b)),
            "both_right": sum(u and v for u, v in zip(a, b)), "both_wrong": sum((not u) and (not v) for u, v in zip(a, b))}


def boot(c0, c1):
    rng = random.Random(SEED); n = len(c0); res = {k: [] for k in ("accuracy", "macro_f1", "contradiction_recall", "joint")}
    for _ in range(N_BOOT):
        ix = [rng.randrange(n) for _ in range(n)]
        res["accuracy"].append(statistics.mean(c1[i]["correct"] for i in ix) - statistics.mean(c0[i]["correct"] for i in ix))
        g = [c0[i]["gold_label"] for i in ix]
        res["macro_f1"].append(macro(g, [c1[i]["predicted_label"] or "X" for i in ix]) - macro(g, [c0[i]["predicted_label"] or "X" for i in ix]))
        res["joint"].append(statistics.mean(c1[i]["joint"] for i in ix) - statistics.mean(c0[i]["joint"] for i in ix))
        ci = [i for i in ix if c0[i]["gold_label"] == "Contradiction"]
        res["contradiction_recall"].append(statistics.mean(c1[i]["correct"] for i in ci) - statistics.mean(c0[i]["correct"] for i in ci))
    cc = [i for i in range(n) if c0[i]["gold_label"] == "Contradiction"]
    pt = {"accuracy": statistics.mean(r["correct"] for r in c1) - statistics.mean(r["correct"] for r in c0),
          "macro_f1": macro([r["gold_label"] for r in c0], [r["predicted_label"] or "X" for r in c1]) - macro([r["gold_label"] for r in c0], [r["predicted_label"] or "X" for r in c0]),
          "contradiction_recall": statistics.mean(c1[i]["correct"] for i in cc) - statistics.mean(c0[i]["correct"] for i in cc),
          "joint": statistics.mean(r["joint"] for r in c1) - statistics.mean(r["joint"] for r in c0)}
    return {k: {"point": pt[k], "ci95": [sorted(v)[int(.025 * N_BOOT)], sorted(v)[int(.975 * N_BOOT)]]} for k, v in res.items()}


def main():
    FILES = {"gpt_p0": "run_E12B_gpt_p0_cases.jsonl", "gpt_p1": "run_E12B_gpt_p1_resume_cases.jsonl",  # P1 = resumed benchmark artifact; outage file EXCLUDED
             "gpt_p2": "run_E12B_gpt_p2_cases.jsonl", "gpt_p3": "run_E12B_gpt_p3_cases.jsonl"}
    ids = [c["case_id"] for c in json.load(open(D / "TRAIN_GPT_PROMPT_v1.json"))["cases"]]; pos = {c: i for i, c in enumerate(ids)}
    raw = {k: sorted((json.loads(l) for l in open(R / FILES[k])), key=lambda r: pos[r["case_id"]]) for k in ORDER}  # concurrent arms wrote in completion order
    assert all([r["case_id"] for r in raw[k]] == ids and len(raw[k]) == 150 and not any(r.get("error_type") for r in raw[k]) for k in ORDER), "arms are not matched 150/150 all-successful"
    S = {k: score(raw[k]) for k in ORDER}; SUM = {k: summarize(S[k]) for k in ORDER}
    cor = {k: [r["correct"] for r in S[k]] for k in ORDER}; jt = {k: [r["joint"] for r in S[k]] for k in ORDER}
    n = 150; cidx = [i for i in range(n) if S["gpt_p0"][i]["gold_label"] == "Contradiction"]
    paired = {}
    for k in ORDER[1:]:
        def disc(a, b, want): return [ids[i] for i in range(n) if (a[i], b[i]) == want]
        paired[k] = {"cls": trans(cor["gpt_p0"], cor[k]), "joint": trans(jt["gpt_p0"], jt[k]),
                     "cls_wrong_to_right_ids": disc(cor["gpt_p0"], cor[k], (False, True)), "cls_right_to_wrong_ids": disc(cor["gpt_p0"], cor[k], (True, False)),
                     "joint_fail_to_success_ids": disc(jt["gpt_p0"], jt[k], (False, True)), "joint_success_to_fail_ids": disc(jt["gpt_p0"], jt[k], (True, False)),
                     "mcnemar_cls": mcnemar(cor["gpt_p0"], cor[k]), "mcnemar_joint": mcnemar(jt["gpt_p0"], jt[k]), "bootstrap": boot(S["gpt_p0"], S[k])}
    # Contradiction analysis
    contra = {}
    for k in ORDER:
        cm = SUM[k]["confusion_matrix"][1]
        contra[k] = {"correct": cm[1], "of": 50, "recall": cm[1] / 50, "to_Entailment": cm[0], "to_NotMentioned": cm[2],
                     "joint": SUM[k]["joint_by_class"]["Contradiction"]}
    contra_sens = [{"case_id": ids[i], "labels": {k: S[k][i]["predicted_label"] for k in ORDER}} for i in cidx
                   if len({S[k][i]["predicted_label"] for k in ORDER}) > 1]
    # sensitivity
    pattern, fam = {}, Counter(); allc = allw = 0; sens = []
    for i in range(n):
        labs = {k: S[k][i]["predicted_label"] for k in ORDER}
        if all(cor[k][i] for k in ORDER): allc += 1; continue
        if not any(cor[k][i] for k in ORDER) and len(set(labs.values())) >= 1 and all(not cor[k][i] for k in ORDER): allw += 1
        if len(set(labs.values())) > 1:
            sens.append(i)
            for a in set(labs.values()):
                for b in set(labs.values()):
                    if SHORT[a] < SHORT[b]: fam[f"{SHORT[a]}<->{SHORT[b]}"] += 1
    sens_rows = []
    for i in sens:
        row = {"case_id": ids[i], "gold": S["gpt_p0"][i]["gold_label"], "pattern": "  ".join(f"{k[-2:].upper()}={SHORT[S[k][i]['predicted_label']]}" for k in ORDER), "evidence": {}}
        for k in ORDER:
            r = S[k][i]; ev = bool(r.get("evidence"))
            cat = ("correct_label_gold_valid_evidence" if r["correct"] and r["joint"] else "correct_label_bad_evidence" if r["correct"] else
                   ("wrong_label_gold_overlap_evidence" if r["gold_overlap"] else "wrong_label_source_valid_evidence" if (ev and r["evidence_valid"]) else "wrong_label_other"))
            omitted = r["predicted_label"] in ("Entailment", "Contradiction") and not ev
            row["evidence"][k] = {"category": cat, "evidence_omitted": omitted, "n_quotes": len(r.get("evidence") or [])}
        spans = {k: tuple(S[k][i]["pred_span_idx"]) for k in ORDER}
        row["evidence_drift_across_prompts"] = len(set(spans.values())) > 1
        sens_rows.append(row)
    ev_counts = {k: Counter(r["evidence"][k]["category"] for r in sens_rows) for k in ORDER}
    ev_counts = {k: dict(v) | {"evidence_omitted": sum(r["evidence"][k]["evidence_omitted"] for r in sens_rows)} for k, v in ev_counts.items()}
    # selection rule
    base = SUM["gpt_p0"]; sel = {}
    for k in ORDER[1:]:
        s = SUM[k]; dC = contra[k]["correct"] - contra["gpt_p0"]["correct"]; net = s["joint_n"] - base["joint_n"]; dF = s["macro_f1"] - base["macro_f1"]
        guard = dC > -GUARD_CASES; f1_ok = dF >= -F1_TOL
        ev_drop = {"recall": s["evidence_recall"] - base["evidence_recall"], "precision": (s["evidence_precision"] or 0) - (base["evidence_precision"] or 0)}
        status = ("DISQUALIFIED (Contradiction guard)" if not guard else "ADOPTION-ELIGIBLE" if (net >= ADOPT_NET and f1_ok) else
                  "NEAR-TIE" if 1 <= net <= ADOPT_NET - 1 else "NO BENEFIT" if net <= 0 and net > HARM_NET else "HARMFUL")
        if guard and net >= ADOPT_NET and not f1_ok: status = "NEAR-TIE (joint >= +9 but Macro-F1 materially worse)"
        sel[k] = {"contradiction_delta_cases": dC, "guard_pass": guard, "net_joint_cases": net, "macro_f1_delta": dF, "macro_f1_ok": f1_ok,
                  "evidence_delta_vs_p0": ev_drop, "status": status}
    elig = [k for k in sel if sel[k]["status"] == "ADOPTION-ELIGIBLE"]
    if elig:
        best = sorted(elig, key=lambda k: (-sel[k]["net_joint_cases"], PTOK[k]["chars"]))[0]; outcome = f"A - {best} EARNS ADOPTION"
    elif any(v["status"].startswith("NEAR-TIE") for v in sel.values()):
        outcome = "B - EFFECTIVELY TIED (near-tie) - KEEP P0"
    elif all(v["status"] in ("HARMFUL", "DISQUALIFIED (Contradiction guard)") for v in sel.values()):
        outcome = "C - GPT-SPECIFIC PROMPTS HURT - KEEP P0"
    else:
        outcome = "B - NO BENEFIT - KEEP P0"
    wall = json.load(open(R / "run_E12B_resume_wall_seconds.json")) | {"p0_sequential_wall_minutes_from_log": 19.0, "note": "P0 ran sequentially before the outage; P1-P3 ran with bounded concurrency=5 -> total wall-clock is NOT comparable across arms; use per-call latency"}
    cost_vs = {k: {"prompt_tokens": PTOK[k]["tokens_cl100k"], "mean_input": SUM[k]["input_tokens"]["mean"], "mean_output": SUM[k]["output_tokens"]["mean"],
                   "total_cost": SUM[k]["cost"]["total"], "cost_delta_vs_p0": SUM[k]["cost"]["total"] - base["cost"]["total"],
                   "cost_delta_pct": (SUM[k]["cost"]["total"] / base["cost"]["total"] - 1) * 100,
                   "latency_mean_ms": SUM[k]["latency_ms"]["mean"], "latency_delta_pct": (SUM[k]["latency_ms"]["mean"] / base["latency_ms"]["mean"] - 1) * 100,
                   "output_delta_pct": (SUM[k]["output_tokens"]["mean"] / base["output_tokens"]["mean"] - 1) * 100} for k in ORDER}
    out = {"summary": SUM, "paired_vs_p0": paired, "contradiction": contra, "contradiction_prompt_sensitive": contra_sens,
           "sensitivity": {"all_correct": allc, "all_wrong": allw, "prompt_sensitive": len(sens), "families": dict(fam), "rows": sens_rows, "evidence_counts": ev_counts,
                           "evidence_drift_cases": sum(r["evidence_drift_across_prompts"] for r in sens_rows)},
           "selection_rule": sel, "outcome": outcome, "cost_token_latency": cost_vs, "run": wall}
    json.dump(out, open(R / "e12b_analysis.json", "w"), indent=1, default=str)
    for k in ORDER: json.dump(SUM[k], open(R / f"run_E12B_{k}.json", "w"), indent=1, default=str)
    for k in ORDER: print(k, "acc %.3f f1 %.3f C %d/50 joint %d (%.3f) cost %.4f" % (SUM[k]["accuracy"], SUM[k]["macro_f1"], contra[k]["correct"], SUM[k]["joint_n"], SUM[k]["joint"], SUM[k]["cost"]["total"]))
    print(json.dumps(sel, indent=1)); print(outcome)


if __name__ == "__main__":
    main()
