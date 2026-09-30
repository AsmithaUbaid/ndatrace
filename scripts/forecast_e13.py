#!/usr/bin/env python3
"""E13 Stage A: artifact verification, exact message construction, token/context-window/cost/budget/runtime forecast, length groups. Zero model calls."""
import hashlib, json, statistics, sys
from pathlib import Path
import tiktoken

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation.budget import check_budget_against_ledger, final_spend_so_far  # noqa: E402

D = REPO / "experiments/E13_gpt_context_architecture"; B = REPO / "experiments/E12B_gpt_prompt_optimization/results"; C = REPO / "experiments/E12C_gpt_prompt_confirmation/results"
SYSTEM = open(REPO / "prompts/final/gpt_p0.txt", newline="").read()          # GPT-P0 effective system prompt (includes the evidence line), byte-identical for BOTH arms
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"          # shared neutral wrapper, identical for BOTH arms
JOIN = "\n\n---\n\n"
LEAK = {"gold_label", "gold_span_indices", "choice", "relevance_flag", "expected_prediction", "failure_bucket", "failure_family"}
enc = tiktoken.get_encoding("cl100k_base"); tok = lambda s: len(enc.encode(s))
q = lambda v, p: sorted(v)[min(int(len(v) * p), len(v) - 1)]
st = lambda v: {"mean": statistics.mean(v), "median": statistics.median(v), "p90": q(v, .9), "p95": q(v, .95), "max": max(v)}
PI, PO = 0.25 / 1e6, 2.0 / 1e6


def main():
    man = json.load(open(D / "DEV_ARCH_v1.json")); full = json.load(open(D / "DEV_ARCH_v1_FULL_CONTEXT.json")); rag = json.load(open(D / "DEV_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    F, R = full["cases"], rag["cases"]; ids = [c["case_id"] for c in man["cases"]]
    e12b_cfg = json.load(open(REPO / "experiments/E12B_gpt_prompt_optimization/TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1.json"))["retrieval_config"]
    docs = {d["id"]: d["text"] for d in json.load(open(REPO / "data/contractnli/dev.json"))["documents"]}
    checks = {"full_150": len(F) == 150, "rag_150": len(R) == 150, "same_ids_order_as_manifest": [c["case_id"] for c in F] == ids == [c["case_id"] for c in R],
              "same_document_ids": [c["document_id"] for c in F] == [c["document_id"] for c in R], "same_hypothesis_text": [c["hypothesis_text"] for c in F] == [c["hypothesis_text"] for c in R] == [c["hypothesis_text"] for c in man["cases"]],
              "no_evaluator_truth_in_model_facing": not any(LEAK & set(c) for c in F + R), "full_context_equals_complete_dev_document_text": all(c["context_text"] == docs[c["document_id"]] for c in F),
              "rag_top5_only": all(len(c["ranked_chunk_ids"]) <= 5 for c in R), "rag_retrieval_config_equals_E12B": rag["retrieval_config"] == e12b_cfg,
              "rag_rerank_order_non_increasing": all(all(a >= b for a, b in zip(c["ranked_chunk_rerank_scores"], c["ranked_chunk_rerank_scores"][1:])) for c in R)}
    sysp_sha = hashlib.sha1(SYSTEM.encode()).hexdigest()
    checks["system_prompt_is_frozen_gpt_p0"] = sysp_sha == "3fcc7c95cf1287c292e403f12b307c9d912278ce"
    msgs_f = [USER_TEMPLATE.format(hypothesis_text=c["hypothesis_text"], context_text=c["context_text"]) for c in F]
    msgs_r = [USER_TEMPLATE.format(hypothesis_text=c["hypothesis_text"], context_text=JOIN.join(c["ranked_chunk_text"])) for c in R]
    # template-only difference check: strip the context field and compare
    checks["messages_identical_except_context_field"] = all(a.replace(c["context_text"], "@@") == b.replace(JOIN.join(r["ranked_chunk_text"]), "@@") for a, b, c, r in zip(msgs_f, msgs_r, F, R))
    # calibration: cl100k -> real API tokens from E12B/E12C P0 (same system prompt, similar wrapper); measured on RAG-type contexts
    E12B_CTX = {c["case_id"]: c for c in json.load(open(REPO / "experiments/E12B_gpt_prompt_optimization/TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
    E12B_HYP = {c["case_id"]: c["hypothesis_text"] for c in json.load(open(REPO / "experiments/E12B_gpt_prompt_optimization/TRAIN_GPT_PROMPT_v1.json"))["cases"]}
    p0b = [json.loads(l) for l in open(B / "run_E12B_gpt_p0_cases.jsonl")]
    old_tpl = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"
    ratio = sum(r["input_tokens"] for r in p0b) / sum(tok(SYSTEM) + tok(old_tpl.format(hypothesis_text=E12B_HYP[r["case_id"]], context_text=JOIN.join(E12B_CTX[r["case_id"]]["ranked_chunk_text"]))) for r in p0b)
    tf = [(tok(SYSTEM) + tok(m)) for m in msgs_f]; tr = [(tok(SYSTEM) + tok(m)) for m in msgs_r]
    calf = [x * ratio for x in tf]; calr = [x * ratio for x in tr]
    nda_full = [tok(c["context_text"]) for c in F]; nda_rag = [tok(JOIN.join(c["ranked_chunk_text"])) for c in R]
    red = {"mean_abs": statistics.mean(calf) - statistics.mean(calr), "mean_pct": (1 - statistics.mean(calr) / statistics.mean(calf)) * 100,
           "median_pct": (1 - statistics.median(calr) / statistics.median(calf)) * 100, "nda_text_mean_pct": (1 - statistics.mean(nda_rag) / statistics.mean(nda_full)) * 100}
    # context-window safety
    max_req = max(max(calf), max(tf))
    safety = {"provider_listing_context_length": 400000, "provider_max_completion_tokens": 128000, "source": "OpenRouter public GET /api/v1/models (metadata only, no model call), 2026-09-27; also matches E12A's assumed 400K",
              "repo_config_records_context_window": False, "max_full_request_tokens_cl100k": max(tf), "max_full_request_tokens_calibrated": max_req,
              "headroom_pct_vs_400k": (1 - (max_req + 3000) / 400000) * 100, "would_truncate_or_reject_any_case": max_req + 3000 > 400000}
    # length groups from FULL NDA token tertiles (chosen before any result)
    c1, c2 = q(nda_full, 1 / 3), q(nda_full, 2 / 3)
    grp = lambda t: "short" if t <= c1 else "medium" if t <= c2 else "long"
    groups = {}
    for g in ("short", "medium", "long"):
        ix = [i for i, t in enumerate(nda_full) if grp(t) == g]
        groups[g] = {"n": len(ix), "nda_tokens_full_mean": statistics.mean(nda_full[i] for i in ix), "request_tokens_full_mean": statistics.mean(calf[i] for i in ix),
                     "request_tokens_rag_mean": statistics.mean(calr[i] for i in ix), "nda_tokens_range": [min(nda_full[i] for i in ix), max(nda_full[i] for i in ix)],
                     "labels": {l: sum(man["cases"][i]["gold_label"] == l for i in ix) for l in ("Entailment", "Contradiction", "NotMentioned")}}
    # cost: real E12B/E12C P0 output behaviour (RAG-type context)
    outs = [r["output_tokens"] for r in p0b] + [json.loads(l)["output_tokens"] for l in open(C / "run_E12C_gpt_p0_cases.jsonl")]
    o_mean, o_p90 = statistics.mean(outs), q(outs, .9)
    # For the FULL arm, calibrated (ratio<1) tokens are uncertain on long text: conservative uses ratio 1.0 (no calibration discount)
    def cost(intoks, om): return sum(x * PI + om * PO for x in intoks)
    exp = {"full": {"input": sum(calf) * PI, "output": len(F) * o_mean * PO}, "rag": {"input": sum(calr) * PI, "output": len(R) * o_mean * PO}}
    for k in exp: exp[k]["total"] = exp[k]["input"] + exp[k]["output"]
    cons = {"full": cost([x for x in tf], o_p90) if False else sum(q(tf, .9) for _ in F) * PI + len(F) * o_p90 * PO, "rag": sum(q(calr, .9) for _ in R) * PI + len(R) * o_p90 * PO}
    stress = {"full": sum(tf) * PI + len(F) * o_mean * 1.5 * PO, "rag": sum(calr) * PI + len(R) * o_mean * 1.5 * PO}
    ledger = final_spend_so_far(); ce = cons["full"] + cons["rag"]; gate = check_budget_against_ledger(ce, 5.0, 0.25)
    lat_rag = statistics.mean(statistics.mean(json.loads(l)["generation_latency_ms"] for l in open(f)) for f in [B / "run_E12B_gpt_p0_cases.jsonl", C / "run_E12C_gpt_p0_cases.jsonl"]) / 1000
    scale_full = 1 + 0.167 * (statistics.mean(calf) / statistics.mean(calr) - 1)  # E12A: +64% input -> +10.7% latency (0.167 per unit)
    runtime = {"rag_mean_call_s_assumed": lat_rag, "full_mean_call_s_assumed": lat_rag * scale_full, "note": "full-arm latency scaling extrapolated from E12A (+64% input -> +10.7% latency); a large extrapolation, uncertain",
               "sequential_minutes": (150 * lat_rag + 150 * lat_rag * scale_full) / 60, "concurrency5_minutes": (150 * lat_rag + 150 * lat_rag * scale_full) / 60 / 5}
    res = {"artifact_checks": checks, "system_prompt_sha1": sysp_sha, "user_template": USER_TEMPLATE, "context_join_rag": JOIN, "calibration_ratio": ratio,
           "nda_text_tokens": {"full": st(nda_full), "rag": st(nda_rag)}, "request_tokens_calibrated": {"full": st(calf), "rag": st(calr)}, "request_tokens_cl100k_uncalibrated": {"full": st(tf), "rag": st(tr)},
           "reduction_full_to_rag": red, "context_window_safety": safety, "length_group_cutoffs_nda_tokens": {"short_le": c1, "medium_le": c2}, "length_groups": groups,
           "output_tokens_real_p0_E12B_E12C": {"mean": o_mean, "p90": o_p90, "n": len(outs)}, "cost_usd": {"expected": exp, "expected_total": exp["full"]["total"] + exp["rag"]["total"], "conservative": cons, "conservative_total": ce,
           "stress_output_x1.5_info_only": stress, "stress_total": stress["full"] + stress["rag"]},
           "ledger_now": ledger, "ledger_after": {"expected": ledger + exp["full"]["total"] + exp["rag"]["total"], "conservative": ledger + ce},
           "budget_gate": {"allowed": bool(gate.allowed), "reason": gate.reason, "arithmetic": ledger + ce + 1.25, "stress_arithmetic": ledger + stress["full"] + stress["rag"] + 1.25}, "runtime": runtime}
    json.dump(res, open(D / "results/pre_run_forecast.json", "w"), indent=1, default=str)
    ex = {"system_prompt": SYSTEM, "user_message_FULL_example": msgs_f[0][:600] + " ...[NDA text continues]", "user_message_RAG_example": msgs_r[0][:600] + " ...[chunks continue]"}
    json.dump(ex, open(D / "results/message_template_examples.json", "w"), indent=1)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
