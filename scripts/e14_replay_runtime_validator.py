#!/usr/bin/env python3
"""E14: offline replay of STORED TRAIN/DEV outputs through runtime validator v1 vs v2 vs evaluator_v2 source-validity. Zero model calls, no TEST."""
from __future__ import annotations
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
import e13b_rescore_historical as H  # noqa: E402  (context loaders/constants only; its main() is not run)
from evaluation import evidence_matching as EM  # noqa: E402
from pipeline.evidence_validator import RUNTIME_EVIDENCE_VALIDATOR_V1 as V1, RUNTIME_EVIDENCE_VALIDATOR_V2 as V2, validate_evidence  # noqa: E402

OUT = REPO / "experiments/E14_runtime_evidence_validator/results"
jl, J = H.jl, H.JOIN
E = REPO / "experiments"


def arms():
    e07 = lambda x: J.join(H.E07_CTX[x["case_id"]]["ranked_chunk_text"])
    yield "E05", "qwen_full", jl(E / "E05_full_context/results/run_E05_A1_train_cases.jsonl"), lambda x: H.TRAIN[x["document_id"]]["text"], "predicted_label", "evidence"
    yield "E07", "qwen_rag", jl(E / "E07_standard_rag/results/run_E07_A2_train_cases.jsonl"), e07, "predicted_label", "evidence"
    yield "E08B", "gpt_rag", jl(E / "E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"), e07, "predicted_label", "evidence"
    e11 = jl(E / "E11_selective_agent_evaluation/results/a3_scored_cases.jsonl")
    yield "E11", "A2", e11, e07, "a2_label", "a2_evidence"
    yield "E11", "A3", e11, e07, "a3_label", "a3_evidence"
    c = {x["case_id"]: x for x in json.load(open(E / "E12A_static_context_expansion/TRAIN_ARCH_v1_RETRIEVED_static_context_candidate_v1.json"))["cases"]}
    yield "E12A", "top11", jl(E / "E12A_static_context_expansion/results/run_E12A_top11_gpt5mini_train_cases.jsonl"), lambda x: J.join(c[x["case_id"]]["ranked_chunk_text"]), "predicted_label", "evidence"
    for exp, d, man, files in (("E12B", "E12B_gpt_prompt_optimization", "TRAIN_GPT_PROMPT_v1", ["gpt_p0", "gpt_p1_resume", "gpt_p2", "gpt_p3"]),
                               ("E12C", "E12C_gpt_prompt_confirmation", "TRAIN_GPT_PROMPT_CONFIRM_v1", ["gpt_p0", "gpt_p3"])):
        ctx = {x["case_id"]: x for x in json.load(open(E / d / f"{man}_RETRIEVED_retrieval_v1.json"))["cases"]}
        for a in files:
            yield exp, a, jl(E / d / "results" / f"run_{exp}_{a}_cases.jsonl"), (lambda ctx: lambda x: J.join(ctx[x["case_id"]]["ranked_chunk_text"]))(ctx), "predicted_label", "evidence"
    e13 = E / "E13_gpt_context_architecture"
    full = {x["case_id"]: x for x in json.load(open(e13 / "DEV_ARCH_v1_FULL_CONTEXT.json"))["cases"]}
    rag = {x["case_id"]: x for x in json.load(open(e13 / "DEV_ARCH_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
    yield "E13", "full", jl(e13 / "results/run_E13_gpt_full_cases.jsonl"), lambda x: full[x["case_id"]]["context_text"], "predicted_label", "evidence"
    yield "E13", "rag", jl(e13 / "results/run_E13_gpt_rag_cases.jsonl"), lambda x: J.join(rag[x["case_id"]]["ranked_chunk_text"]), "predicted_label", "evidence"


def main():
    rows, per_arm, bad = [], [], []
    for exp, arm, recs, ctxf, lk, ek in arms():
        n = {"exp": exp, "arm": arm, "cases": 0, "quotes": 0, "inv2val": 0, "val2inv": 0, "v2_ne_evaluator": 0, "label_or_consistency_changed": 0}
        for r in recs:
            ev = r.get(ek) or []
            ctx = ctxf(r); label = r.get(lk) or ""
            n["cases"] += 1
            a = validate_evidence(ctx, ev, label, V1); b = validate_evidence(ctx, ev, label, V2)
            if a.label_evidence_consistent != b.label_evidence_consistent: n["label_or_consistency_changed"] += 1
            for q in ev:
                o, nw, evl = q in ctx and bool(q), q in b.verbatim_quotes, EM.is_source_valid(q, ctx)
                assert o == (q in a.verbatim_quotes)
                n["quotes"] += 1
                if not o and nw:
                    n["inv2val"] += 1
                    s, e = b.spans[q]
                    rows.append({"exp": exp, "arm": arm, "case_id": r["case_id"], "quote": q, "recovered_source": ctx[s:e], "span": [s, e], "changed": "invalid->valid"})
                if o and not nw: n["val2inv"] += 1; bad.append({"exp": exp, "case_id": r["case_id"], "quote": q})
                if nw != evl: n["v2_ne_evaluator"] += 1
        per_arm.append(n)
    tot = {k: sum(x[k] for x in per_arm) for k in ("cases", "quotes", "inv2val", "val2inv", "v2_ne_evaluator", "label_or_consistency_changed")}
    json.dump({"per_arm": per_arm, "total": tot, "valid_to_invalid": bad}, open(OUT / "replay_summary.json", "w"), indent=1)
    json.dump(rows, open(OUT / "changed_quotes.json", "w"), indent=1)
    for x in per_arm: print(x)
    print("TOTAL", tot, "changed quote rows", len(rows), "unique", len({(r["exp"], r["case_id"], r["quote"]) for r in rows}))


if __name__ == "__main__":
    main()
