#!/usr/bin/env python3
"""E13 Stage B analysis: FULL-context vs retrieval_v1 RAG (GPT-P0, GPT-5-mini) on DEV_ARCH_v1. Evaluator-side. Scoring/bootstrap/McNemar reuse
scripts/analyze_e12b_gpt_prompts.py + analyze_e08b_stronger_model.py (same span-overlap and joint definitions). Applies the FROZEN decision rule mechanically.
Deltas are RAG minus FULL."""
from __future__ import annotations
import json, statistics, sys
from pathlib import Path
import tiktoken

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
import analyze_e12b_gpt_prompts as B  # noqa: E402
import analyze_e08b_stronger_model as A  # noqa: E402

D = REPO / "experiments/E13_gpt_context_architecture"; R = D / "results"
enc = tiktoken.get_encoding("cl100k_base"); tok = lambda s: len(enc.encode(s))
NET_PRACTICAL, CONTRA_GUARD, F1_TOL, EV_TOL = 5, 3, 0.03, 0.03
CUT_SHORT, CUT_MED = 1352, 2683  # predeclared FULL-NDA token tertile cutoffs
q = lambda v, p: sorted(v)[min(int(len(v) * p), len(v) - 1)]
dist = lambda v: {"mean": statistics.mean(v), "median": statistics.median(v), "p90": q(v, .9), "p95": q(v, .95), "max": max(v)}


def main():
    man = json.load(open(D / "DEV_ARCH_v1.json"))["cases"]; ids = [c["case_id"] for c in man]; pos = {c: i for i, c in enumerate(ids)}
    full_art = {c["case_id"]: c for c in json.load(open(D / "DEV_ARCH_v1_FULL_CONTEXT.json"))["cases"]}
    rag_art = {c["case_id"]: c for c in json.load(open(D / "DEV_ARCH_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
    gold = {c["case_id"]: c["gold_span_indices"] for c in json.load(open(D / "DEV_ARCH_v1_GOLD.json"))["cases"]}
    docsp = {d["id"]: d["spans"] for d in json.load(open(REPO / "data/contractnli/dev.json"))["documents"]}
    raw = {k: sorted((json.loads(l) for l in open(R / f"run_E13_gpt_{k}_cases.jsonl")), key=lambda r: pos[r["case_id"]]) for k in ("full", "rag")}
    assert all([r["case_id"] for r in raw[k]] == ids and len(raw[k]) == 150 and not any(r.get("error_type") for r in raw[k]) for k in raw), "arms not 150/150 all-successful"

    def score(arm):
        out = []
        for c in raw[arm]:
            cid = c["case_id"]; gi = gold[cid]; ds = docsp[c["document_id"]]
            if arm == "full": texts, offs = [full_art[cid]["context_text"]], [[0, len(full_art[cid]["context_text"])]]
            else: texts, offs = rag_art[cid]["ranked_chunk_text"], c["retrieved_chunk_offsets"]
            pi = A.evidence_to_span_indices(c.get("evidence") or [], texts, offs, ds)
            d = dict(c); d.update(pred_span_idx=pi, gold_span_idx=gi, correct=c["gold_label"] == c["predicted_label"], gold_overlap=(bool(set(gi) & set(pi)) if gi else None),
                                  joint=A.joint_success(c["gold_label"], c["predicted_label"], gi, pi)); out.append(d)
        return out
    S = {k: score(k) for k in raw}; SUM = {k: B.summarize(S[k]) for k in S}
    for k in SUM:
        SUM[k]["input_tokens"] = dist([r["input_tokens"] for r in S[k]]); SUM[k]["output_tokens"] = dist([r["output_tokens"] for r in S[k]]); SUM[k]["latency_ms"] = dist([r["generation_latency_ms"] for r in S[k]])
        SUM[k]["retries"] = sum(r.get("retry_count") or 0 for r in S[k]); SUM[k]["timeouts"] = sum(r.get("error_type") == "TIMEOUT" for r in S[k])
        c = SUM[k]["cost"]; SUM[k]["cost_projection"] = {"per_1000": c["mean"] * 1000, "per_8000": c["mean"] * 8000}
    cf, cr = [r["correct"] for r in S["full"]], [r["correct"] for r in S["rag"]]; jf, jr = [r["joint"] for r in S["full"]], [r["joint"] for r in S["rag"]]; n = 150
    disc = lambda a, b, w: [ids[i] for i in range(n) if (a[i], b[i]) == w]
    paired = {"cls": B.trans(cf, cr), "joint": B.trans(jf, jr), "cls_full_wrong_rag_right": disc(cf, cr, (False, True)), "cls_full_right_rag_wrong": disc(cf, cr, (True, False)),
              "joint_full_fail_rag_success": disc(jf, jr, (False, True)), "joint_full_success_rag_fail": disc(jf, jr, (True, False)),
              "mcnemar_cls_b_fullonly_c_raglonly": B.mcnemar(cf, cr), "mcnemar_joint": B.mcnemar(jf, jr), "bootstrap_rag_minus_full": B.boot(S["full"], S["rag"])}
    # Contradiction
    cidx = [i for i in range(n) if S["full"][i]["gold_label"] == "Contradiction"]
    contra = {k: {"correct": SUM[k]["confusion_matrix"][1][1], "of": 50, "recall": SUM[k]["confusion_matrix"][1][1] / 50, "to_Entailment": SUM[k]["confusion_matrix"][1][0], "to_NotMentioned": SUM[k]["confusion_matrix"][1][2],
                   "joint": sum(S[k][i]["joint"] for i in cidx), "joint_rate": sum(S[k][i]["joint"] for i in cidx) / 50} for k in S}
    def row(i):
        f, r = S["full"][i], S["rag"][i]; cid = ids[i]
        return {"case_id": cid, "gold": f["gold_label"], "hypothesis": next(m["hypothesis_text"] for m in man if m["case_id"] == cid), "n_chunks_rag": len(rag_art[cid]["ranked_chunk_ids"]),
                "full_label": f["predicted_label"], "rag_label": r["predicted_label"], "full_joint": f["joint"], "rag_joint": r["joint"], "full_evidence": f["evidence"], "rag_evidence": r["evidence"],
                "gold_spans": f["gold_span_idx"], "full_pred_spans": f["pred_span_idx"], "rag_pred_spans": r["pred_span_idx"],
                "gold_in_rag_context": A.retrieval_contains_gold(f["gold_span_idx"], docsp[f["document_id"]], r["retrieved_chunk_offsets"]),
                "gold_span_text": [(m := docsp[f["document_id"]][s], full_art[cid]["context_text"][m[0]:m[1]]) [1] for s in f["gold_span_idx"]],
                "full_nda_tokens": tok(full_art[cid]["context_text"])}
    contra_disc = [row(i) for i in cidx if cf[i] != cr[i] or jf[i] != jr[i]]
    ctx_loss = [row(i) for i in range(n) if (jf[i] and not jr[i]) or (cf[i] and not cr[i])]
    distractor = [row(i) for i in range(n) if (not jf[i] and jr[i]) or (not cf[i] and cr[i])]
    # length groups
    nt = [tok(full_art[c]["context_text"]) for c in ids]; g = lambda t: "short" if t <= CUT_SHORT else "medium" if t <= CUT_MED else "long"
    groups = {}
    for name in ("short", "medium", "long"):
        ix = [i for i in range(n) if g(nt[i]) == name]; m = lambda k, key: statistics.mean(S[k][i][key] for i in ix)
        groups[name] = {"n": len(ix), "nda_tokens_mean": statistics.mean(nt[i] for i in ix), "full_request_tokens_mean": statistics.mean(S["full"][i]["input_tokens"] for i in ix),
                        "rag_request_tokens_mean": statistics.mean(S["rag"][i]["input_tokens"] for i in ix), "full_accuracy": m("full", "correct"), "rag_accuracy": m("rag", "correct"),
                        "full_joint": m("full", "joint"), "rag_joint": m("rag", "joint"), "full_joint_n": sum(S["full"][i]["joint"] for i in ix), "rag_joint_n": sum(S["rag"][i]["joint"] for i in ix),
                        "joint_delta_cases": sum(S["rag"][i]["joint"] for i in ix) - sum(S["full"][i]["joint"] for i in ix), "accuracy_delta": m("rag", "correct") - m("full", "correct")}
    # operational
    op = {"input_token_ratio_full_over_rag_mean": SUM["full"]["input_tokens"]["mean"] / SUM["rag"]["input_tokens"]["mean"], "latency_ratio_full_over_rag_mean": SUM["full"]["latency_ms"]["mean"] / SUM["rag"]["latency_ms"]["mean"],
          "latency_ratio_full_over_rag_median": SUM["full"]["latency_ms"]["median"] / SUM["rag"]["latency_ms"]["median"], "latency_ratio_p95": SUM["full"]["latency_ms"]["p95"] / SUM["rag"]["latency_ms"]["p95"],
          "cost_ratio_full_over_rag": SUM["full"]["cost"]["total"] / SUM["rag"]["cost"]["total"], "output_token_ratio_full_over_rag_mean": SUM["full"]["output_tokens"]["mean"] / SUM["rag"]["output_tokens"]["mean"],
          "input_token_reduction_pct_rag_vs_full": (1 - SUM["rag"]["input_tokens"]["mean"] / SUM["full"]["input_tokens"]["mean"]) * 100,
          "timeouts": {k: SUM[k]["timeouts"] for k in SUM}, "errors": {k: SUM[k]["errors"] for k in SUM}, "retries": {k: SUM[k]["retries"] for k in SUM}}
    # frozen rule
    sf, sr = SUM["full"], SUM["rag"]; net = sr["joint_n"] - sf["joint_n"]
    guards = {"1_contradiction_correct_ge3_below_full": {"delta_cases": contra["rag"]["correct"] - contra["full"]["correct"], "fails": contra["rag"]["correct"] - contra["full"]["correct"] <= -CONTRA_GUARD},
              "2_macro_f1_more_than_0.03_below_full": {"delta": sr["macro_f1"] - sf["macro_f1"], "fails": sr["macro_f1"] - sf["macro_f1"] < -F1_TOL},
              "3_evidence_recall_more_than_3pp_below_full": {"delta": sr["evidence_recall"] - sf["evidence_recall"], "fails": sr["evidence_recall"] - sf["evidence_recall"] < -EV_TOL},
              "4_evidence_precision_more_than_3pp_below_full": {"delta": (sr["evidence_precision"] or 0) - (sf["evidence_precision"] or 0), "fails": (sr["evidence_precision"] or 0) - (sf["evidence_precision"] or 0) < -EV_TOL}}
    fails = any(v["fails"] for v in guards.values())
    if net >= NET_PRACTICAL and not fails: outcome = "A - RAG MATERIALLY BETTER"
    elif net <= -NET_PRACTICAL or (fails and net <= 0): outcome = "B - FULL MATERIALLY BETTER"
    elif -NET_PRACTICAL + 1 <= net <= NET_PRACTICAL - 1 and not fails: outcome = "C - EFFECTIVELY TIED - SELECT RAG FOR OPERATIONAL EFFICIENCY"
    else: outcome = "D - MIXED - NO ARCHITECTURE FREEZE YET"
    wall = json.load(open(R / "run_E13_wall_seconds.json"))
    out = {"summary": SUM, "paired": paired, "contradiction": contra, "contradiction_discordant_cases": contra_disc, "context_loss_cases": ctx_loss, "distractor_cases": distractor,
           "length_groups": groups, "operational": op, "guards": guards, "any_guard_fails": fails, "net_joint": net, "outcome": outcome, "run": wall}
    json.dump(out, open(R / "e13_analysis.json", "w"), indent=1, default=str)
    for k in SUM: json.dump(SUM[k], open(R / f"run_E13_gpt_{k}.json", "w"), indent=1, default=str)
    print("FULL joint", sf["joint_n"], "RAG joint", sr["joint_n"], "net", net); print(json.dumps(guards, indent=1)); print(outcome)


if __name__ == "__main__":
    main()
