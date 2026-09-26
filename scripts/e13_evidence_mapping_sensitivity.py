#!/usr/bin/env python3
"""E13 post-hoc SENSITIVITY (does NOT replace the frozen result): the frozen scorer maps a quoted evidence string to gold spans by EXACT substring search. Models often merge
lines / drop zero-width chars, so a correct quote can map to no span. Here the same scoring is repeated with a whitespace-tolerant, ellipsis-segmented mapping applied
IDENTICALLY to both arms. Reported alongside the frozen result; the frozen outcome stands."""
import json, re, sys, statistics
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
import analyze_e08b_stronger_model as A  # noqa: E402
import analyze_e12b_gpt_prompts as B  # noqa: E402

D = REPO / "experiments/E13_gpt_context_architecture"; R = D / "results"
WS = re.compile(r"[\s​   ]+")


def norm_with_map(text):
    out, mp, prev_ws = [], [], False
    for i, ch in enumerate(text):
        if WS.match(ch):
            if not prev_ws and out: out.append(" "); mp.append(i)
            prev_ws = True
        else: out.append(ch); mp.append(i); prev_ws = False
    return "".join(out), mp


def spans_tolerant(evidence, texts, offsets, doc_spans):
    idx = set()
    for quote in evidence or []:
        for seg in [s for s in re.split(r"\.\.\.|…", quote) if s.strip()]:
            nq = WS.sub(" ", seg).strip()
            if len(nq) < 12: continue
            for text, (c0, c1) in zip(texts, offsets):
                nt, mp = norm_with_map(text); p = nt.find(nq)
                if p == -1: continue
                a0 = c0 + mp[p]; a1 = c0 + mp[min(p + len(nq) - 1, len(mp) - 1)] + 1
                for k, (s0, s1) in enumerate(doc_spans):
                    if min(s1, a1) > max(s0, a0): idx.add(k)
    return sorted(idx)


def main():
    man = json.load(open(D / "DEV_ARCH_v1.json"))["cases"]; ids = [c["case_id"] for c in man]; pos = {c: i for i, c in enumerate(ids)}
    full = {c["case_id"]: c for c in json.load(open(D / "DEV_ARCH_v1_FULL_CONTEXT.json"))["cases"]}; rag = {c["case_id"]: c for c in json.load(open(D / "DEV_ARCH_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
    gold = {c["case_id"]: c["gold_span_indices"] for c in json.load(open(D / "DEV_ARCH_v1_GOLD.json"))["cases"]}
    docsp = {d["id"]: d["spans"] for d in json.load(open(REPO / "data/contractnli/dev.json"))["documents"]}
    res = {}
    for arm in ("full", "rag"):
        raw = sorted((json.loads(l) for l in open(R / f"run_E13_gpt_{arm}_cases.jsonl")), key=lambda r: pos[r["case_id"]]); rows = []; rescued = []
        for c in raw:
            cid = c["case_id"]; gi = gold[cid]; ds = docsp[c["document_id"]]
            texts, offs = ([full[cid]["context_text"]], [[0, len(full[cid]["context_text"])]]) if arm == "full" else (rag[cid]["ranked_chunk_text"], c["retrieved_chunk_offsets"])
            strict = A.evidence_to_span_indices(c.get("evidence") or [], texts, offs, ds); tol = spans_tolerant(c.get("evidence"), texts, offs, ds)
            js, jt = A.joint_success(c["gold_label"], c["predicted_label"], gi, strict), A.joint_success(c["gold_label"], c["predicted_label"], gi, tol)
            if jt and not js: rescued.append(cid)
            rows.append({"case_id": cid, "gold_label": c["gold_label"], "predicted_label": c["predicted_label"], "correct": c["gold_label"] == c["predicted_label"], "joint_strict": js, "joint": jt,
                         "gold_span_idx": gi, "pred_span_idx": tol, "evidence": c.get("evidence"), "empty_map_with_quote_strict": bool(c.get("evidence")) and not strict, "empty_map_with_quote_tol": bool(c.get("evidence")) and not tol})
        eb = [r for r in rows if r["gold_span_idx"]]; cl = [r for r in rows if r["evidence"]]
        res[arm] = {"rows": rows, "joint_strict": sum(r["joint_strict"] for r in rows), "joint_tolerant": sum(r["joint"] for r in rows), "rescued_by_tolerant_mapping": rescued,
                    "quotes_unmappable_strict": sum(r["empty_map_with_quote_strict"] for r in rows), "quotes_unmappable_tolerant": sum(r["empty_map_with_quote_tol"] for r in rows),
                    "evidence_recall_tolerant": sum(bool(set(r["gold_span_idx"]) & set(r["pred_span_idx"])) for r in eb) / len(eb),
                    "evidence_precision_tolerant": sum(bool(set(r["gold_span_idx"]) & set(r["pred_span_idx"])) for r in cl) / len(cl)}
    f, r = res["full"], res["rag"]; net = r["joint_tolerant"] - f["joint_tolerant"]
    cF = sum(x["correct"] for x in f["rows"] if x["gold_label"] == "Contradiction"); cR = sum(x["correct"] for x in r["rows"] if x["gold_label"] == "Contradiction")
    F1 = lambda rows: B.macro([x["gold_label"] for x in rows], [x["predicted_label"] or "X" for x in rows])
    g3 = r["evidence_recall_tolerant"] - f["evidence_recall_tolerant"] < -0.03; g4 = r["evidence_precision_tolerant"] - f["evidence_precision_tolerant"] < -0.03
    g1 = cR - cF <= -3; g2 = F1(r["rows"]) - F1(f["rows"]) < -0.03; fails = g1 or g2 or g3 or g4
    outcome = ("A" if net >= 5 and not fails else "B" if net <= -5 or (fails and net <= 0) else "C" if -4 <= net <= 4 and not fails else "D")
    out = {"note": "POST-HOC sensitivity, not the frozen result. Same tolerant mapping applied to both arms.", "full": {k: v for k, v in f.items() if k != "rows"}, "rag": {k: v for k, v in r.items() if k != "rows"},
           "net_joint_tolerant": net, "guards_tolerant": {"contradiction_delta": cR - cF, "macro_f1_delta": F1(r["rows"]) - F1(f["rows"]), "evidence_recall_delta": r["evidence_recall_tolerant"] - f["evidence_recall_tolerant"],
                                                        "evidence_precision_delta": r["evidence_precision_tolerant"] - f["evidence_precision_tolerant"], "fails": {"1": g1, "2": g2, "3": g3, "4": g4}}, "outcome_letter_if_this_mapping_had_been_frozen": outcome}
    json.dump(out, open(R / "e13_evidence_mapping_sensitivity.json", "w"), indent=1, default=str); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
