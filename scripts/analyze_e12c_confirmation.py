#!/usr/bin/env python3
"""E12C Stage B analysis: standalone P0 vs P3 on the confirmation manifest, E12B recap, pooled + stratified analysis, frozen decision.
Scoring/bootstrap/McNemar code is reused from scripts/analyze_e12b_gpt_prompts.py (same definitions); its module-level context/gold globals are
re-pointed per manifest. Decision rule applied mechanically exactly as frozen in config.yaml (+ user's Stage B wording)."""
from __future__ import annotations
import json, random, shutil, statistics, sys
from collections import Counter
from pathlib import Path
from sklearn.metrics import f1_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
import analyze_e12b_gpt_prompts as B  # noqa: E402

E12B = REPO / "experiments/E12B_gpt_prompt_optimization"; E12C = REPO / "experiments/E12C_gpt_prompt_confirmation"; R = E12C / "results"
N_BOOT, SEED = 10_000, 900
CONTRA_GUARD, F1_TOL, EV_TOL, STRONG = 3, 0.03, 0.03, 5


def load_scored(exp_dir, man_name, files):
    ctx = {c["case_id"]: c for c in json.load(open(exp_dir / f"{man_name}_RETRIEVED_retrieval_v1.json"))["cases"]}
    gold = {c["case_id"]: c["gold_span_indices"] for c in json.load(open(exp_dir / f"{man_name}_RETRIEVED_retrieval_v1_GOLD.json"))["cases"]}
    ids = [c["case_id"] for c in json.load(open(exp_dir / f"{man_name}.json"))["cases"]]; pos = {c: i for i, c in enumerate(ids)}
    B.CTX, B.GOLD = ctx, gold  # score() reads these module globals
    out = {}
    for arm, fn in files.items():
        raw = sorted((json.loads(l) for l in open(exp_dir / "results" / fn)), key=lambda r: pos[r["case_id"]])
        assert [r["case_id"] for r in raw] == ids and not any(r.get("error_type") for r in raw), f"{fn}: not 150 matched successful rows"
        out[arm] = B.score(raw)
    return ids, out


def macro(rows): return f1_score([r["gold_label"] for r in rows], [r["predicted_label"] or "X" for r in rows], labels=B.LABELS, average="macro", zero_division=0)
def evid(rows):
    eb = [r for r in rows if r["gold_span_idx"]]; cl = [bool(set(r["gold_span_idx"]) & set(r["pred_span_idx"])) for r in rows if r.get("evidence")]
    return sum(bool(r["gold_overlap"]) for r in eb) / len(eb), (sum(cl) / len(cl) if cl else None)
def crecall(rows):
    c = [r for r in rows if r["gold_label"] == "Contradiction"]; return sum(r["correct"] for r in c), len(c)


def pooled_stats(p0, p3):
    o = {}
    for k, rows in (("p0", p0), ("p3", p3)):
        er, ep = evid(rows); cc, cn = crecall(rows)
        o[k] = {"n": len(rows), "joint": sum(r["joint"] for r in rows), "accuracy": sum(r["correct"] for r in rows) / len(rows), "macro_f1": macro(rows),
                "contradiction_correct": cc, "contradiction_n": cn, "contradiction_recall": cc / cn, "evidence_recall": er, "evidence_precision": ep}
    return o


def strat_boot(strata):  # strata: list of (p0_rows, p3_rows), one per manifest; resample cases WITHIN each manifest, pair preserved
    rng = random.Random(SEED); res = {k: [] for k in ("joint", "accuracy", "macro_f1", "contradiction_recall")}
    for _ in range(N_BOOT):
        a0, a3 = [], []
        for p0, p3 in strata:
            ix = [rng.randrange(len(p0)) for _ in range(len(p0))]; a0 += [p0[i] for i in ix]; a3 += [p3[i] for i in ix]
        res["joint"].append(statistics.mean(r["joint"] for r in a3) - statistics.mean(r["joint"] for r in a0))
        res["accuracy"].append(statistics.mean(r["correct"] for r in a3) - statistics.mean(r["correct"] for r in a0))
        res["macro_f1"].append(macro(a3) - macro(a0))
        c0, n0 = crecall(a0); c3, n3 = crecall(a3); res["contradiction_recall"].append(c3 / n3 - c0 / n0)
    f0 = [r for p0, _ in strata for r in p0]; f3 = [r for _, p3 in strata for r in p3]
    pt = {"joint": statistics.mean(r["joint"] for r in f3) - statistics.mean(r["joint"] for r in f0), "accuracy": statistics.mean(r["correct"] for r in f3) - statistics.mean(r["correct"] for r in f0),
          "macro_f1": macro(f3) - macro(f0), "contradiction_recall": crecall(f3)[0] / crecall(f3)[1] - crecall(f0)[0] / crecall(f0)[1]}
    return {k: {"point": pt[k], "ci95": [sorted(v)[int(.025 * N_BOOT)], sorted(v)[int(.975 * N_BOOT)]]} for k, v in res.items()}


def main():
    idsC, C = load_scored(E12C, "TRAIN_GPT_PROMPT_CONFIRM_v1", {"p0": "run_E12C_gpt_p0_cases.jsonl", "p3": "run_E12C_gpt_p3_cases.jsonl"})
    idsB, Bb = load_scored(E12B, "TRAIN_GPT_PROMPT_v1", {"p0": "run_E12B_gpt_p0_cases.jsonl", "p3": "run_E12B_gpt_p3_cases.jsonl"})
    B.CTX, B.GOLD = None, None
    # need C's CTX/GOLD again for summarize? summarize() does not use them -> fine
    SC = {k: B.summarize(C[k]) for k in C}; SB = {k: B.summarize(Bb[k]) for k in Bb}
    cor = {k: [r["correct"] for r in C[k]] for k in C}; jt = {k: [r["joint"] for r in C[k]] for k in C}; n = 150
    disc = lambda a, b, w: [idsC[i] for i in range(n) if (a[i], b[i]) == w]
    paired = {"cls": B.trans(cor["p0"], cor["p3"]), "joint": B.trans(jt["p0"], jt["p3"]),
              "cls_wrong_to_right_ids": disc(cor["p0"], cor["p3"], (False, True)), "cls_right_to_wrong_ids": disc(cor["p0"], cor["p3"], (True, False)),
              "joint_fail_to_success_ids": disc(jt["p0"], jt["p3"], (False, True)), "joint_success_to_fail_ids": disc(jt["p0"], jt["p3"], (True, False)),
              "mcnemar_cls": B.mcnemar(cor["p0"], cor["p3"]), "mcnemar_joint": B.mcnemar(jt["p0"], jt["p3"]), "bootstrap": B.boot(C["p0"], C["p3"])}
    cidx = [i for i in range(n) if C["p0"][i]["gold_label"] == "Contradiction"]
    contra = {k: {"correct": SC[k]["confusion_matrix"][1][1], "of": 50, "recall": SC[k]["confusion_matrix"][1][1] / 50, "to_Entailment": SC[k]["confusion_matrix"][1][0], "to_NotMentioned": SC[k]["confusion_matrix"][1][2]} for k in C}
    contra["recoveries"] = [idsC[i] for i in cidx if not cor["p0"][i] and cor["p3"][i]]; contra["regressions"] = [idsC[i] for i in cidx if cor["p0"][i] and not cor["p3"][i]]
    def evcats(rows):
        c = Counter()
        for r in rows:
            ev = bool(r.get("evidence"))
            if r["correct"]: c["correct_label_gold_valid_evidence" if r["joint"] else "correct_label_bad_evidence"] += 1
            else:
                c["wrong_label_gold_overlap_evidence" if r["gold_overlap"] else "wrong_label_source_valid_evidence" if (ev and r["evidence_valid"]) else "wrong_label_other"] += 1
                if r["gold_overlap"] and ev and r["evidence_valid"]: c["(wrong_label_source_valid_evidence_incl_overlap)"] += 1
        return dict(c)
    evc = {k: evcats(C[k]) for k in C}
    # frozen guards / band
    s0, s3 = SC["p0"], SC["p3"]; net = s3["joint_n"] - s0["joint_n"]; dC = contra["p3"]["correct"] - contra["p0"]["correct"]
    dF = s3["macro_f1"] - s0["macro_f1"]; dER = s3["evidence_recall"] - s0["evidence_recall"]; dEP = (s3["evidence_precision"] or 0) - (s0["evidence_precision"] or 0)
    guards = {"1_contradiction_not_3_or_more_cases_below_P0": {"delta_cases": dC, "pass": dC > -CONTRA_GUARD}, "2_net_joint_positive": {"net_joint_cases": net, "pass": net > 0},
              "3_macro_f1_drop_not_over_0.03": {"delta": dF, "pass": dF >= -F1_TOL}, "4_evidence_recall_drop_not_over_3pp": {"delta": dER, "pass": dER >= -EV_TOL},
              "5_evidence_precision_drop_not_over_3pp": {"delta": dEP, "pass": dEP >= -EV_TOL}}
    all_pass = all(g["pass"] for g in guards.values())
    band = "STRONG CONFIRMATION" if all_pass and net >= STRONG else "WEAK CONFIRMATION" if all_pass and 1 <= net <= STRONG - 1 else "NO CONFIRMATION"
    # E12B recap + pooled
    recapB = {"p0_joint": SB["p0"]["joint_n"], "p3_joint": SB["p3"]["joint_n"], "delta": SB["p3"]["joint_n"] - SB["p0"]["joint_n"], "of": 150}
    recapC = {"p0_joint": s0["joint_n"], "p3_joint": s3["joint_n"], "delta": net, "of": 150}
    pool = pooled_stats(Bb["p0"] + C["p0"], Bb["p3"] + C["p3"])
    pooled = {"stats": pool, "joint_p0_of_300": pool["p0"]["joint"], "joint_p3_of_300": pool["p3"]["joint"], "net": pool["p3"]["joint"] - pool["p0"]["joint"],
              "stratified_bootstrap": strat_boot([(Bb["p0"], Bb["p3"]), (C["p0"], C["p3"])]),
              "per_manifest_bootstrap_joint": {"E12B": B.boot(Bb["p0"], Bb["p3"])["joint"], "E12C": paired["bootstrap"]["joint"]}}
    reversal = (recapB["delta"] > 0) != (recapC["delta"] > 0) or recapC["delta"] <= 0 < recapB["delta"]
    ci = pooled["stratified_bootstrap"]["joint"]["ci95"]; ci_excludes_zero = ci[0] > 0 or ci[1] < 0
    if band == "STRONG CONFIRMATION": outcome = "A - P3 CONFIRMED (strong confirmation) -> freeze classification_prompt_gpt_v1 = P3"
    elif band == "WEAK CONFIRMATION" and ci_excludes_zero and not reversal: outcome = "A - P3 CONFIRMED (weak confirmation + pooled CI excludes zero + no reversal) -> freeze classification_prompt_gpt_v1 = P3"
    elif band == "WEAK CONFIRMATION": outcome = "C - P3 WEAKLY CONFIRMED - PREFER P0 (pooled CI includes zero)"
    else: outcome = "B - P3 NOT CONFIRMED - KEEP P0"
    direction = {"E12B_delta": recapB["delta"], "E12C_delta": recapC["delta"], "same_direction": not reversal, "reversal": reversal,
                 "note": "If E12C reverses vs E12B this is stated explicitly regardless of the pooled aggregate."}
    def lat(k): return {x: v for x, v in B.dist([r["generation_latency_ms"] for r in C[k]]).items()}
    cost = {k: {"total": SC[k]["cost"]["total"], "per_case": SC[k]["cost"]["mean"], "latency_ms": lat(k), "input_tokens_mean": SC[k]["input_tokens"]["mean"], "output_tokens_mean": SC[k]["output_tokens"]["mean"]} for k in C}
    cost["delta"] = {"cost_pct": (cost["p3"]["total"] / cost["p0"]["total"] - 1) * 100, "latency_mean_pct": (cost["p3"]["latency_ms"]["mean"] / cost["p0"]["latency_ms"]["mean"] - 1) * 100,
                     "input_tokens": cost["p3"]["input_tokens_mean"] - cost["p0"]["input_tokens_mean"], "output_tokens": cost["p3"]["output_tokens_mean"] - cost["p0"]["output_tokens_mean"]}
    wall = json.load(open(R / "run_E12C_wall_seconds.json"))
    out = {"E12C_standalone": SC, "E12B_recap_summary": {k: {x: SB[k][x] for x in ("accuracy", "macro_f1", "joint_n", "evidence_recall", "evidence_precision")} for k in SB},
           "paired_E12C": paired, "contradiction": contra, "evidence_categories": evc, "guards": guards, "all_guards_pass": all_pass, "net_joint": net, "confirmation_band": band,
           "E12B_recap": recapB, "E12C": recapC, "pooled": pooled, "direction_consistency": direction, "pooled_ci_excludes_zero": ci_excludes_zero,
           "outcome": outcome, "cost_latency": cost, "run": wall}
    json.dump(out, open(R / "e12c_analysis.json", "w"), indent=1, default=str)
    for k in SC: json.dump(SC[k], open(R / f"run_E12C_gpt_{k}.json", "w"), indent=1, default=str)
    if outcome.startswith("A"):
        src = REPO / "prompts/reconstruction_v2/gpt_p3.txt"; dst = REPO / "prompts/reconstruction_v2/classification_prompt_gpt_v1.txt"
        shutil.copyfile(src, dst); import hashlib
        json.dump({"name": "classification_prompt_gpt_v1", "byte_identical_copy_of": "prompts/reconstruction_v2/gpt_p3.txt", "sha1": hashlib.sha1(open(dst, "rb").read()).hexdigest(),
                   "confirmation_manifests": ["TRAIN_GPT_PROMPT_v1 (E12B)", "TRAIN_GPT_PROMPT_CONFIRM_v1 (E12C)"], "E12B": recapB, "E12C": recapC,
                   "pooled_joint": [pooled["joint_p0_of_300"], pooled["joint_p3_of_300"]], "rationale": outcome,
                   "status": "frozen prompt artifact; NOT a final architecture; classification_prompt_v1 (Qwen-selected P0) remains unchanged"},
                  open(REPO / "prompts/reconstruction_v2/classification_prompt_gpt_v1.meta.json", "w"), indent=2)
    print(json.dumps({"band": band, "guards": guards, "net": net, "E12B": recapB, "E12C": recapC, "pooled": {k: pooled[k] for k in ("joint_p0_of_300", "joint_p3_of_300", "net")},
                      "pooled_boot": pooled["stratified_bootstrap"], "direction": direction}, indent=1, default=str)); print(outcome)


if __name__ == "__main__":
    main()
