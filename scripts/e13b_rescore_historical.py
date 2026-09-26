#!/usr/bin/env python3
"""E13B: offline v1-vs-v2 evidence-evaluator re-scoring of STORED outputs (TRAIN and DEV only; zero model calls; no TEST; raw outputs never modified).
v1 = historical exact-substring mapping; v2 = evaluation.evidence_matching (exact-first + formatting-normalized fallback). Reproduces each experiment's reported v1 numbers first."""
from __future__ import annotations
import json, re, sys, unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation import evidence_matching as EM  # noqa: E402

OUT = REPO / "experiments/E13B_evidence_evaluator_hardening/results"
JOIN = "\n\n---\n\n"
TRAIN = {d["id"]: d for d in json.load(open(REPO / "data/contractnli/train.json"))["documents"]}
DEV = {d["id"]: d for d in json.load(open(REPO / "data/contractnli/dev.json"))["documents"]}
E07 = REPO / "experiments/E07_standard_rag"
E07_CTX = {c["case_id"]: c for c in json.load(open(E07 / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
E07_GOLD = {c["case_id"]: c["gold_span_indices"] for c in json.load(open(E07 / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json"))["cases"]}
DOCID_ARCH = {c["case_id"]: c["document_id"] for c in json.load(open(REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"))["cases"]}
jl = lambda p: [json.loads(l) for l in open(p)]
WS = re.compile(r"[\s​‌‍⁠﻿]+")
FANCY = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-"})


def unit(exp, arm, rows, docs, get_ctx, gold, reported=None, label_key="predicted_label", ev_key="evidence", stored_valid_key="evidence_all_verbatim"):
    """rows: dicts with case_id, gold_label, <label_key>, <ev_key>, document_id. get_ctx(row)->(texts, offsets)."""
    recs = []
    for r in rows:
        texts, offs = get_ctx(r); ds = docs[r["document_id"]]["spans"]; gi = gold[r["case_id"]]; ev = r.get(ev_key) or []
        v1 = EM.evidence_to_span_indices_v1(ev, texts, offs, ds); v2 = EM.evidence_to_span_indices(ev, texts, offs, ds)
        ctxt = JOIN.join(texts) if len(texts) > 1 or arm.startswith("rag") else texts[0]
        j1 = EM.joint_success(r["gold_label"], r[label_key], gi, v1); j2 = EM.joint_success(r["gold_label"], r[label_key], gi, v2)
        sv1 = all(EM.is_source_valid(q, ctxt, EM.EVIDENCE_EVALUATOR_V1) for q in ev) if ev else None
        sv2 = all(EM.is_source_valid(q, ctxt, EM.EVIDENCE_EVALUATOR_V2) for q in ev) if ev else None
        details = []
        for q in ev:
            ms1 = EM.find_evidence_matches(q, texts, offs, EM.EVIDENCE_EVALUATOR_V1); ms2 = EM.find_evidence_matches(q, texts, offs, EM.EVIDENCE_EVALUATOR_V2)
            if not ms1 and ms2:
                for m in ms2:
                    sl = texts[m.text_index][m.start:m.end]; core = lambda s: unicodedata.normalize("NFC", re.sub(r"[\s​‌‍⁠﻿]+", "", s))
                    causes = [n for n, c in (("zero_width", any(ch in EM.ZERO_WIDTH for ch in sl + q)), ("nbsp_or_unicode_space", any(ch.isspace() and ch not in " \t\r\n" for ch in sl + q)),
                                             ("line_break_or_tab", any(ch in "\t\r\n" for ch in sl + q)), ("whitespace_run_or_join", bool(re.search(r"\s{2,}", sl)) or (sl != q and WS.sub(" ", sl).strip() == WS.sub(" ", q).strip())),
                                             ("nfc", unicodedata.normalize("NFC", sl) != sl or unicodedata.normalize("NFC", q) != q)) if c]
                    details.append({"quote": q, "recovered_original_text": sl, "n_occurrences": m.n_occurrences, "formatting_only_verified": core(sl) == core(q), "causes": causes or ["whitespace_run_or_join"]})
            elif not ms2 and q:
                pass
        unmatched_v2 = [q for q in ev if q and not EM.find_evidence_matches(q, texts, offs, EM.EVIDENCE_EVALUATOR_V2)]
        recs.append({"case_id": r["case_id"], "gold_label": r["gold_label"], "predicted_label": r[label_key], "gold_span_idx": gi, "v1_spans": v1, "v2_spans": v2, "joint_v1": j1, "joint_v2": j2,
                     "n_quotes": len(ev), "source_valid_v1": sv1, "source_valid_v2": sv2, "stored_all_verbatim": r.get(stored_valid_key), "rescued_quotes": details, "unmatched_v2": unmatched_v2,
                     "has_evidence": bool(ev), "gold_overlap_v1": bool(set(gi) & set(v1)) if gi else None, "gold_overlap_v2": bool(set(gi) & set(v2)) if gi else None})
    eb = [x for x in recs if x["gold_span_idx"]]; cl = [x for x in recs if x["has_evidence"]]
    agg = {"exp": exp, "arm": arm, "n": len(recs), "reported_joint_from_stored_summary": reported,
           "joint_v1": sum(x["joint_v1"] for x in recs), "joint_v2": sum(x["joint_v2"] for x in recs),
           "evidence_recall_v1": sum(bool(x["gold_overlap_v1"]) for x in eb) / len(eb), "evidence_recall_v2": sum(bool(x["gold_overlap_v2"]) for x in eb) / len(eb),
           "evidence_precision_v1": (sum(bool(set(x["gold_span_idx"]) & set(x["v1_spans"])) for x in cl) / len(cl)) if cl else None,
           "evidence_precision_v2": (sum(bool(set(x["gold_span_idx"]) & set(x["v2_spans"])) for x in cl) / len(cl)) if cl else None,
           "source_valid_records_v1": sum(bool(x["source_valid_v1"]) for x in recs), "source_valid_records_v2": sum(bool(x["source_valid_v2"]) for x in recs),
           "mappings_changed": [x["case_id"] for x in recs if x["v1_spans"] != x["v2_spans"]],
           "rescued_quote_cases": [x["case_id"] for x in recs if x["rescued_quotes"]],
           "joint_fail_to_success": [x["case_id"] for x in recs if not x["joint_v1"] and x["joint_v2"]], "joint_success_to_fail": [x["case_id"] for x in recs if x["joint_v1"] and not x["joint_v2"]],
           "regress_span_not_superset": [x["case_id"] for x in recs if not set(x["v1_spans"]) <= set(x["v2_spans"])],
           "regress_source_valid_true_to_false": [x["case_id"] for x in recs if x["source_valid_v1"] and not x["source_valid_v2"]],
           "v1_exact_stored_verbatim_mismatch": [x["case_id"] for x in recs if x["stored_all_verbatim"] is not None and x["has_evidence"] and bool(x["stored_all_verbatim"]) != bool(x["source_valid_v1"])],
           "n_rescued_quotes": sum(len(x["rescued_quotes"]) for x in recs), "n_rescued_quotes_multi_occurrence": sum(1 for x in recs for d in x["rescued_quotes"] if d["n_occurrences"] > 1),
           "residual_unmatched_quotes_v2": sum(len(x["unmatched_v2"]) for x in recs),
           "residual_by_cause": {"ellipsis": sum(1 for x in recs for q in x["unmatched_v2"] if "..." in q or "…" in q),
                                 "typographic_quotes_only": sum(1 for x in recs for q in x["unmatched_v2"] if "..." not in q and "…" not in q and any(EM.find_evidence_matches(q.translate(FANCY), [t.translate(FANCY)], [o], EM.EVIDENCE_EVALUATOR_V2) for t, o in zip(*get_ctx(next(r for r in rows if r["case_id"] == x["case_id"]))))),
                                 "other_nonverbatim": None}}
    agg["residual_by_cause"]["other_nonverbatim"] = agg["residual_unmatched_quotes_v2"] - agg["residual_by_cause"]["ellipsis"] - agg["residual_by_cause"]["typographic_quotes_only"]
    agg["v1_matches_reported"] = (reported is None) or abs(agg["joint_v1"] / agg["n"] - reported) < 1e-9
    return agg, recs


def main():
    units, allrecs = [], {}
    def add(u): units.append(u[0]); allrecs[f"{u[0]['exp']}::{u[0]['arm']}"] = u[1]
    rep = lambda p, key="joint": (lambda d: d[key]["overall"] if isinstance(d[key], dict) else d[key])(json.load(open(REPO / p)))
    # E05 (Qwen full context, TRAIN)
    r = jl(REPO / "experiments/E05_full_context/results/run_E05_A1_train_cases.jsonl")
    add(unit("E05", "qwen_full_context", r, TRAIN, lambda x: ([TRAIN[x["document_id"]]["text"]], [[0, len(TRAIN[x["document_id"]]["text"])]]), E07_GOLD, rep("experiments/E05_full_context/results/run_E05_A1_train.json")))
    ctx7 = lambda x: (E07_CTX[x["case_id"]]["ranked_chunk_text"], E07_CTX[x["case_id"]]["ranked_chunk_offsets"])
    add(unit("E07", "qwen_rag_top5", jl(REPO / "experiments/E07_standard_rag/results/run_E07_A2_train_cases.jsonl"), TRAIN, ctx7, E07_GOLD, rep("experiments/E07_standard_rag/results/run_E07_A2_train.json")))
    add(unit("E08B", "gpt5mini_rag_top5", jl(REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"), TRAIN, ctx7, E07_GOLD, rep("experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train.json")))
    # E11: A2 and A3 (scored, per its analyzer, against the E07 top-5 chunks)
    e11 = jl(REPO / "experiments/E11_selective_agent_evaluation/results/a3_scored_cases.jsonl")
    for r_ in e11: r_["document_id"] = DOCID_ARCH[r_["case_id"]]
    add(unit("E11", "A2_control", e11, TRAIN, ctx7, E07_GOLD, None, label_key="a2_label", ev_key="a2_evidence", stored_valid_key="__none__"))
    add(unit("E11", "A3_selective_agent", e11, TRAIN, ctx7, E07_GOLD, rep("experiments/E11_selective_agent_evaluation/results/run_E11_A3_train.json"), label_key="a3_label", ev_key="a3_evidence", stored_valid_key="__none__"))
    # E12A (top-11)
    c12a = {c["case_id"]: c for c in json.load(open(REPO / "experiments/E12A_static_context_expansion/TRAIN_ARCH_v1_RETRIEVED_static_context_candidate_v1.json"))["cases"]}
    add(unit("E12A", "gpt5mini_top11", jl(REPO / "experiments/E12A_static_context_expansion/results/run_E12A_top11_gpt5mini_train_cases.jsonl"), TRAIN,
             lambda x: (c12a[x["case_id"]]["ranked_chunk_text"], c12a[x["case_id"]]["ranked_chunk_offsets"]), E07_GOLD, json.load(open(REPO / "experiments/E12A_static_context_expansion/results/run_E12A_top11_gpt5mini_train.json"))["joint"]))
    def suite(exp, d, man, files, docs, split_note):
        ctx = {c["case_id"]: c for c in json.load(open(d / f"{man}_RETRIEVED_retrieval_v1.json"))["cases"]}
        gold = {c["case_id"]: c["gold_span_indices"] for c in json.load(open(d / f"{man}_RETRIEVED_retrieval_v1_GOLD.json"))["cases"]}
        for arm, fn, sfn in files:
            rows = jl(d / "results" / fn); rep_ = json.load(open(d / "results" / sfn))["joint"]
            add(unit(exp, arm, rows, docs, lambda x: (ctx[x["case_id"]]["ranked_chunk_text"], ctx[x["case_id"]]["ranked_chunk_offsets"]), gold, rep_))
    e12b = REPO / "experiments/E12B_gpt_prompt_optimization"
    suite("E12B", e12b, "TRAIN_GPT_PROMPT_v1", [("gpt_p0", "run_E12B_gpt_p0_cases.jsonl", "run_E12B_gpt_p0.json"), ("gpt_p1", "run_E12B_gpt_p1_resume_cases.jsonl", "run_E12B_gpt_p1.json"),
                                                 ("gpt_p2", "run_E12B_gpt_p2_cases.jsonl", "run_E12B_gpt_p2.json"), ("gpt_p3", "run_E12B_gpt_p3_cases.jsonl", "run_E12B_gpt_p3.json")], TRAIN, "")
    suite("E12C", REPO / "experiments/E12C_gpt_prompt_confirmation", "TRAIN_GPT_PROMPT_CONFIRM_v1", [("gpt_p0", "run_E12C_gpt_p0_cases.jsonl", "run_E12C_gpt_p0.json"), ("gpt_p3", "run_E12C_gpt_p3_cases.jsonl", "run_E12C_gpt_p3.json")], TRAIN, "")
    # E13 (DEV)
    e13 = REPO / "experiments/E13_gpt_context_architecture"
    full = {c["case_id"]: c for c in json.load(open(e13 / "DEV_ARCH_v1_FULL_CONTEXT.json"))["cases"]}; rag = {c["case_id"]: c for c in json.load(open(e13 / "DEV_ARCH_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
    g13 = {c["case_id"]: c["gold_span_indices"] for c in json.load(open(e13 / "DEV_ARCH_v1_GOLD.json"))["cases"]}
    add(unit("E13", "full_context", jl(e13 / "results/run_E13_gpt_full_cases.jsonl"), DEV, lambda x: ([full[x["case_id"]]["context_text"]], [[0, len(full[x["case_id"]]["context_text"])]]), g13, json.load(open(e13 / "results/run_E13_gpt_full.json"))["joint"]))
    add(unit("E13", "rag_top5", jl(e13 / "results/run_E13_gpt_rag_cases.jsonl"), DEV, lambda x: (rag[x["case_id"]]["ranked_chunk_text"], rag[x["case_id"]]["ranked_chunk_offsets"]), g13, json.load(open(e13 / "results/run_E13_gpt_rag.json"))["joint"]))
    json.dump({"units": units}, open(OUT / "rescoring_summary.json", "w"), indent=1, default=str)
    json.dump(allrecs, open(OUT / "rescoring_case_records.json", "w"), default=str)
    for u in units:
        print(f"{u['exp']:5} {u['arm']:20} n={u['n']} v1==reported:{u['v1_matches_reported']} joint {u['joint_v1']}->{u['joint_v2']} recall {u['evidence_recall_v1']:.3f}->{u['evidence_recall_v2']:.3f} prec {u['evidence_precision_v1']:.3f}->{u['evidence_precision_v2']:.3f} "
              f"mappings_changed={len(u['mappings_changed'])} rescued_cases={len(u['rescued_quote_cases'])} sv {u['source_valid_records_v1']}->{u['source_valid_records_v2']} regress: span={len(u['regress_span_not_superset'])} sv={len(u['regress_source_valid_true_to_false'])} joint_s2f={len(u['joint_success_to_fail'])} verbatim_mismatch={len(u['v1_exact_stored_verbatim_mismatch'])}")


if __name__ == "__main__":
    main()
