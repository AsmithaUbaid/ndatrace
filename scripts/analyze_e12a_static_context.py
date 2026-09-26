#!/usr/bin/env python3
"""E12A Stage B analysis: top-5 control (E08B A2, frozen) vs top-11 candidate, paired, 150 cases.

Scoring reuses scripts/analyze_e08b_stronger_model.py's helpers (same overlap/joint definitions) for
BOTH arms; the control's recomputed joint is asserted equal to E08B's stored joint column.
"""
from __future__ import annotations

import csv, json, random, statistics, sys
from collections import Counter
from pathlib import Path

from scipy import stats
from sklearn.metrics import confusion_matrix, f1_score, recall_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
from evaluation.metrics import wilson_score_interval  # noqa: E402
import analyze_e08b_stronger_model as A  # noqa: E402

LABELS = A.LABELS
E12 = REPO / "experiments/E12A_static_context_expansion"
R = E12 / "results"
CAND = json.load(open(E12 / "TRAIN_ARCH_v1_RETRIEVED_static_context_candidate_v1.json"))
CAND_TEXT = {c["case_id"]: c["ranked_chunk_text"] for c in CAND["cases"]}
CTRL_TEXT = A.load_retrieved_chunk_text()
GOLD = A.load_gold_span_indices()
DOCSP = A.load_doc_spans()
BUCKET = {r["case_id"]: r["primary_bucket"] for r in csv.DictReader(
    open(REPO / "experiments/E09_agent_justification/results/gpt_residual_failure_analysis.csv"))}
E08B_CSV = {r["case_id"]: r for r in csv.DictReader(
    open(REPO / "experiments/E08B_stronger_model_diagnostic/results/gpt5mini_failure_analysis.csv"))}
SIX = ["train::160::nda-10", "train::247::nda-10", "train::353::nda-10", "train::379::nda-10",
       "train::438::nda-2", "train::518::nda-10"]
GOLD_RANK = dict(zip(SIX, [11, 9, 9, 8, 8, 9]))
N_BOOT, SEED = 10_000, 900


def score(rows, texts):
    out = []
    for c in rows:
        gi = GOLD[c["case_id"]]
        ds = DOCSP[c["document_id"]]
        off = c["retrieved_chunk_offsets"]
        pred_idx = A.evidence_to_span_indices(c.get("evidence") or [], texts[c["case_id"]], off, ds)
        d = dict(c)
        d.update(pred_span_idx=pred_idx, gold_span_idx=gi,
                 gold_in_context=A.retrieval_contains_gold(gi, ds, off),
                 gold_overlap=(bool(set(gi) & set(pred_idx)) if gi else None),
                 correct=c["gold_label"] == c["predicted_label"],
                 joint=A.joint_success(c["gold_label"], c["predicted_label"], gi, pred_idx))
        out.append(d)
    return out


def dist(v):
    v = sorted(x for x in v if x is not None)
    return {"mean": statistics.mean(v), "median": statistics.median(v),
            "p90": v[min(int(len(v) * .9), len(v) - 1)], "max": max(v)}


def summarize(rows):
    n = len(rows); g = [r["gold_label"] for r in rows]; p = [r["predicted_label"] or "PARSE_FAILED" for r in rows]
    rec = dict(zip(LABELS, recall_score(g, p, labels=LABELS, average=None, zero_division=0)))
    cn = sum(x == "Contradiction" for x in g); ch = sum(a == b == "Contradiction" for a, b in zip(g, p))
    eb = [r for r in rows if r["gold_span_idx"]]
    claims = [bool(set(r["gold_span_idx"]) & set(r["pred_span_idx"])) for r in rows if r.get("evidence")]
    jb = {l: sum(r["joint"] for r in rows if r["gold_label"] == l) / sum(r["gold_label"] == l for r in rows) for l in LABELS}
    costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    return {
        "n": n, "accuracy": sum(r["correct"] for r in rows) / n,
        "macro_f1": f1_score(g, p, labels=LABELS, average="macro", zero_division=0),
        "recall": rec, "contradiction_recall_ci95": list(wilson_score_interval(ch, cn)),
        "confusion_matrix": confusion_matrix(g, p, labels=LABELS).tolist(),
        "parse": {s: sum(r["parse_status"] == s for r in rows) for s in ("strict", "recovered", "invalid")},
        "source_valid_evidence_rate": statistics.mean(bool(r["evidence_valid"]) for r in rows if r.get("evidence")),
        "gold_overlap_rate_of_evidence_bearing": sum(bool(r["gold_overlap"]) for r in eb) / len(eb),
        "evidence_recall": sum(bool(r["gold_overlap"]) for r in eb) / len(eb),
        "evidence_precision": sum(claims) / len(claims),
        "joint": sum(r["joint"] for r in rows) / n, "joint_by_class": jb,
        "input_tokens": dist([r["input_tokens"] for r in rows]),
        "output_tokens": dist([r["output_tokens"] for r in rows]),
        "latency_ms": dist([r["generation_latency_ms"] for r in rows]),
        "cost": {"total": sum(costs), "mean": statistics.mean(costs), "median": statistics.median(costs),
                 "p90": sorted(costs)[int(.9 * len(costs))], "max": max(costs)},
    }


def mcnemar(a, b):
    x = sum(u and not v for u, v in zip(a, b)); y = sum(v and not u for u, v in zip(a, b))
    nd = x + y
    return {"top5_only": x, "top11_only": y, "n_discordant": nd,
            "p": 1.0 if nd == 0 else float(stats.binomtest(min(x, y), nd, .5).pvalue)}


def trans(a, b):
    return {"wrong_to_right": sum((not u) and v for u, v in zip(a, b)),
            "right_to_wrong": sum(u and not v for u, v in zip(a, b)),
            "both_right": sum(u and v for u, v in zip(a, b)),
            "both_wrong": sum((not u) and (not v) for u, v in zip(a, b))}


def boot(ctrl, cand):
    rng = random.Random(SEED); n = len(ctrl)
    acc, f1, cr, jt = [], [], [], []
    for _ in range(N_BOOT):
        ix = [rng.randrange(n) for _ in range(n)]
        acc.append(statistics.mean(cand[i]["correct"] for i in ix) - statistics.mean(ctrl[i]["correct"] for i in ix))
        g = [ctrl[i]["gold_label"] for i in ix]
        f1.append(f1_score(g, [cand[i]["predicted_label"] or "X" for i in ix], labels=LABELS, average="macro", zero_division=0)
                  - f1_score(g, [ctrl[i]["predicted_label"] or "X" for i in ix], labels=LABELS, average="macro", zero_division=0))
        jt.append(statistics.mean(cand[i]["joint"] for i in ix) - statistics.mean(ctrl[i]["joint"] for i in ix))
        ci = [i for i in ix if ctrl[i]["gold_label"] == "Contradiction"]
        cr.append(statistics.mean(cand[i]["correct"] for i in ci) - statistics.mean(ctrl[i]["correct"] for i in ci))
    def ci(v, point):
        v.sort(); return {"point": point, "ci95": [v[int(.025 * N_BOOT)], v[int(.975 * N_BOOT)]]}
    m = lambda rows: f1_score([r["gold_label"] for r in rows], [r["predicted_label"] or "X" for r in rows], labels=LABELS, average="macro", zero_division=0)
    cc = [i for i in range(n) if ctrl[i]["gold_label"] == "Contradiction"]
    return {"accuracy": ci(acc, statistics.mean(r["correct"] for r in cand) - statistics.mean(r["correct"] for r in ctrl)),
            "macro_f1": ci(f1, m(cand) - m(ctrl)),
            "contradiction_recall": ci(cr, statistics.mean(cand[i]["correct"] for i in cc) - statistics.mean(ctrl[i]["correct"] for i in cc)),
            "joint": ci(jt, statistics.mean(r["joint"] for r in cand) - statistics.mean(r["joint"] for r in ctrl))}


def main():
    cand_raw = [json.loads(l) for l in open(R / "run_E12A_top11_gpt5mini_train_cases.jsonl")]
    ctrl_raw = [json.loads(l) for l in open(A.CASES_PATH)]
    assert [c["case_id"] for c in cand_raw] == [c["case_id"] for c in ctrl_raw]
    cand = score(cand_raw, CAND_TEXT); ctrl = score(ctrl_raw, CTRL_TEXT)
    assert all(r["joint"] == (E08B_CSV[r["case_id"]]["joint_success"] == "True") for r in ctrl), "control joint != E08B stored"
    n = len(cand); ids = [r["case_id"] for r in cand]
    S5, S11 = summarize(ctrl), summarize(cand)
    cc5, cc11 = [r["correct"] for r in ctrl], [r["correct"] for r in cand]
    j5, j11 = [r["joint"] for r in ctrl], [r["joint"] for r in cand]

    def lst(a, b, want):
        return [{"case_id": ids[i], "gold": cand[i]["gold_label"], "top5": ctrl[i]["predicted_label"],
                 "top11": cand[i]["predicted_label"]} for i in range(n) if (a[i], b[i]) == want]
    def rows_for(sel):
        out = []
        for c5, c11 in zip(ctrl, cand):
            if c5["case_id"] not in sel: continue
            out.append({"case_id": c5["case_id"], "gold": c5["gold_label"], "top5_label": c5["predicted_label"],
                        "top11_label": c11["predicted_label"], "top5_evidence": c5["evidence"], "top11_evidence": c11["evidence"],
                        "cls_transition": ("recovered" if (not c5["correct"] and c11["correct"]) else "regressed" if (c5["correct"] and not c11["correct"]) else "unchanged_correct" if c5["correct"] else "unchanged_wrong"),
                        "joint_transition": ("recovered" if (not c5["joint"] and c11["joint"]) else "regressed" if (c5["joint"] and not c11["joint"]) else "unchanged_success" if c5["joint"] else "unchanged_fail"),
                        "gold_in_top5": c5["gold_in_context"], "gold_in_top11": c11["gold_in_context"],
                        "top5_gold_overlap": c5["gold_overlap"], "top11_gold_overlap": c11["gold_overlap"],
                        "top11_source_valid": c11["evidence_valid"], "n_chunks_shown": c11["n_chunks_shown"]})
        return out
    def bucket_summary(name):
        sel = {c for c, b in BUCKET.items() if b == name}
        rr = rows_for(sel)
        return {"n": len(rr), "cls": Counter(r["cls_transition"] for r in rr), "joint": Counter(r["joint_transition"] for r in rr),
                "gold_overlap_top5_to_top11": Counter((r["top5_gold_overlap"], r["top11_gold_overlap"]) for r in rr).most_common(),
                "rows": rr}
    for b in ("RETRIEVAL_FILTERING_LIMITED", "EVIDENCE_SELECTION_LIMITED", "MODEL_REASONING_LIMITED", "DYNAMIC_INFORMATION_ACQUISITION"):
        pass
    bks = {b: bucket_summary(b) for b in ("RETRIEVAL_FILTERING_LIMITED", "EVIDENCE_SELECTION_LIMITED",
                                            "MODEL_REASONING_LIMITED", "DYNAMIC_INFORMATION_ACQUISITION")}
    for r in bks["RETRIEVAL_FILTERING_LIMITED"]["rows"]:
        r["gold_rank_expected"] = GOLD_RANK[r["case_id"]]
    for k in bks.values():
        k["cls"], k["joint"] = dict(k["cls"]), dict(k["joint"])
        k["gold_overlap_top5_to_top11"] = [[str(a), c] for a, c in k["gold_overlap_top5_to_top11"]]

    # regression dossier: added chunks are ranks 6..11 of the candidate
    dossier = []
    for i in range(n):
        if (cc5[i] and not cc11[i]) or (j5[i] and not j11[i]):
            added = CAND_TEXT[ids[i]][5:]
            gi, ds = GOLD[ids[i]], DOCSP[cand[i]["document_id"]]
            add_off = cand[i]["retrieved_chunk_offsets"][5:]
            dossier.append({"case_id": ids[i], "hypothesis": next(c["hypothesis_text"] for c in CAND["cases"] if c["case_id"] == ids[i]),
                            "gold": cand[i]["gold_label"], "top5_label": ctrl[i]["predicted_label"], "top11_label": cand[i]["predicted_label"],
                            "cls_regression": cc5[i] and not cc11[i], "joint_regression": j5[i] and not j11[i],
                            "top5_evidence": ctrl[i]["evidence"], "top11_evidence": cand[i]["evidence"],
                            "top11_evidence_gold_overlap": cand[i]["gold_overlap"], "n_added_chunks": len(added),
                            "gold_span_in_added_chunks": A.retrieval_contains_gold(gi, ds, add_off) if add_off else False,
                            "added_chunks_ranks_6_to_11": added})

    # saturation
    sat = {}
    for name, f in [("A_<=5_chunks", lambda k: k <= 5), ("B_6-10_chunks", lambda k: 6 <= k <= 10), ("C_>=11_chunks", lambda k: k >= 11)]:
        ix = [i for i in range(n) if f(cand[i]["n_chunks_shown"])]
        m = lambda rs, key: statistics.mean(r[key] for r in rs)
        sat[name] = {"n": len(ix), "mean_candidate_chunks_shown": statistics.mean(cand[i]["n_chunks_shown"] for i in ix),
                     "mean_control_chunks_shown": statistics.mean(len(ctrl[i]["retrieved_chunk_ids"]) for i in ix),
                     "top5_acc": m([ctrl[i] for i in ix], "correct"), "top11_acc": m([cand[i] for i in ix], "correct"),
                     "top5_joint": m([ctrl[i] for i in ix], "joint"), "top11_joint": m([cand[i] for i in ix], "joint"),
                     "cls_transitions": trans([cc5[i] for i in ix], [cc11[i] for i in ix]),
                     "joint_transitions": trans([j5[i] for i in ix], [j11[i] for i in ix])}
        sat[name]["acc_delta"] = sat[name]["top11_acc"] - sat[name]["top5_acc"]
        sat[name]["joint_delta"] = sat[name]["top11_joint"] - sat[name]["top5_joint"]

    ci_ = [i for i in range(n) if cand[i]["gold_label"] == "Contradiction"]
    contra = {"recall_top5": S5["recall"]["Contradiction"], "recall_top11": S11["recall"]["Contradiction"],
              "recoveries": [ids[i] for i in ci_ if not cc5[i] and cc11[i]],
              "regressions": [ids[i] for i in ci_ if cc5[i] and not cc11[i]],
              "joint_top5": S5["joint_by_class"]["Contradiction"], "joint_top11": S11["joint_by_class"]["Contradiction"],
              "joint_recoveries": [ids[i] for i in ci_ if not j5[i] and j11[i]],
              "joint_regressions": [ids[i] for i in ci_ if j5[i] and not j11[i]]}

    wall = json.load(open(R / "run_E12A_wall_seconds.json"))
    c5, c11 = S5["cost"]["mean"], S11["cost"]["mean"]
    out = {"top5": S5, "top11": S11,
           "cls_transitions": trans(cc5, cc11), "joint_transitions": trans(j5, j11),
           "cls_recoveries": lst(cc5, cc11, (False, True)), "cls_regressions": lst(cc5, cc11, (True, False)),
           "joint_recoveries": lst(j5, j11, (False, True)), "joint_regressions": lst(j5, j11, (True, False)),
           "buckets": bks, "contradiction": contra, "saturation": sat, "regression_dossier": dossier,
           "mcnemar_classification": mcnemar(cc5, cc11), "mcnemar_joint": mcnemar(j5, j11),
           "bootstrap": boot(ctrl, cand),
           "cost_projection": {"top5_per_1000": c5 * 1000, "top11_per_1000": c11 * 1000,
                                "top5_per_8000": c5 * 8000, "top11_per_8000": c11 * 8000,
                                "increase_pct": (c11 / c5 - 1) * 100},
           "input_token_increase": {"abs": S11["input_tokens"]["mean"] - S5["input_tokens"]["mean"],
                                     "pct": (S11["input_tokens"]["mean"] / S5["input_tokens"]["mean"] - 1) * 100,
                                     "forecast_mean": 1884.6},
           "latency_change": {"abs_ms": S11["latency_ms"]["mean"] - S5["latency_ms"]["mean"],
                               "pct": (S11["latency_ms"]["mean"] / S5["latency_ms"]["mean"] - 1) * 100},
           "run": wall}
    json.dump(out, open(R / "e12a_analysis.json", "w"), indent=1, default=str)
    json.dump(S11, open(R / "run_E12A_top11_gpt5mini_train.json", "w"), indent=1, default=str)
    print("acc", S5["accuracy"], "->", S11["accuracy"], "| joint", S5["joint"], "->", S11["joint"])
    print("cls", out["cls_transitions"], "joint", out["joint_transitions"])
    print("mcnemar", out["mcnemar_classification"], out["mcnemar_joint"])
    print("dossier n", len(dossier))


if __name__ == "__main__":
    main()
