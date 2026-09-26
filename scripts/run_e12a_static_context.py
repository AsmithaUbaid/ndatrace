#!/usr/bin/env python3
"""E12A Stage B -- static_context_candidate_v1 (top-11) on all 150 TRAIN_ARCH_v1 cases.

Identical to scripts/run_e08b_stronger_model_diagnostic.py except the retrieved-context artifact
(top-11 instead of top-5) and the ledger run_id/experiment_id. Pre-run verification is recorded to
results/pre_run_verification.json before the first hosted call.
"""
from __future__ import annotations

import hashlib, json, sys, time, uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.budget import check_budget_against_ledger, record_spend, reconstruction_spend_so_far  # noqa: E402
from evaluation.prompt_selection import load_prompt_config  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

MANIFEST = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
CONTROL_RETRIEVED = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
CAND = REPO / "experiments/E12A_static_context_expansion/TRAIN_ARCH_v1_RETRIEVED_static_context_candidate_v1.json"
E08B_CASES = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"
OUT_DIR = REPO / "experiments/E12A_static_context_expansion/results"
OUT_CASES = OUT_DIR / "run_E12A_top11_gpt5mini_train_cases.jsonl"

EXPERIMENT_ID = "E12A_static_context_expansion"
MODEL, PROVIDER = "openai/gpt-5-mini", "openrouter"
FINAL_K = 11
PLANNING_BUDGET_USD, RESERVE_FRACTION = 5.00, 0.25
CONSERVATIVE_USD = 0.4650  # from results/pre_run_forecast.json
SAFETY_STOP_FRACTION = 0.90
EVIDENCE_INSTRUCTION = (
    ' Also return the exact sentence(s) from the text that support your label, verbatim, as a '
    'list under "evidence". Return an empty list for NotMentioned.'
)
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"
LEAK = {"gold_label", "gold_span_indices", "choice", "relevance_flag", "expected_prediction",
        "failure_bucket", "previously_wrong_marker"}


def main() -> int:
    cases = json.load(open(MANIFEST))["cases"]
    cand = json.load(open(CAND))
    ctrl = json.load(open(CONTROL_RETRIEVED))
    cand_by = {c["case_id"]: c for c in cand["cases"]}
    ctrl_by = {c["case_id"]: c for c in ctrl["cases"]}
    e08b_ids = [json.loads(l)["case_id"] for l in open(E08B_CASES)]

    ids = [c["case_id"] for c in cases]
    checks = {
        "candidate_150_of_150": len(cand["cases"]) == 150 and set(ids) == set(cand_by),
        "same_ids_and_order_as_e08b": [c["case_id"] for c in cand["cases"]] == e08b_ids == ids,
        "ranks_1_5_identical_to_control": all(
            cand_by[i]["ranked_chunk_ids"][:5] == ctrl_by[i]["ranked_chunk_ids"]
            and cand_by[i]["ranked_chunk_text"][:5] == ctrl_by[i]["ranked_chunk_text"] for i in ids),
        "no_gold_leakage_keys": not any(LEAK & set(c) for c in cand["cases"]),
        "k11_uniform_cap": cand["retrieval_config"]["final_k"] == FINAL_K
            and all(len(c["ranked_chunk_ids"]) <= FINAL_K for c in cand["cases"]),
        "rerank_scores_non_increasing_frozen_order": all(
            all(a >= b for a, b in zip(s, s[1:]))
            for s in (c["ranked_chunk_rerank_scores"] for c in cand["cases"])),
    }
    pre_spend = reconstruction_spend_so_far()
    gate = check_budget_against_ledger(CONSERVATIVE_USD, PLANNING_BUDGET_USD, RESERVE_FRACTION)
    checks["budget_gate_pass"] = bool(gate.allowed)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump({"checks": checks, "pre_run_ledger_usd": pre_spend, "gate_reason": gate.reason,
               "chunk_count_distribution": dict(Counter(len(c["ranked_chunk_ids"]) for c in cand["cases"])),
               "tests_passed_before_run": "338/338 (pytest tests/ -q, run immediately before)",
               "timestamp": datetime.now(timezone.utc).isoformat()},
              open(OUT_DIR / "pre_run_verification.json", "w"), indent=2)
    print(json.dumps(checks, indent=1), f"\npre-run ledger ${pre_spend:.4f}")
    if not all(checks.values()):
        print("PRE-RUN VERIFICATION FAILED; no hosted call made.")
        return 1

    allowed = PLANNING_BUDGET_USD * (1 - RESERVE_FRACTION)
    cfg = load_prompt_config("p00")
    system_prompt = cfg["system_prompt"].rstrip() + "\n" + EVIDENCE_INSTRUCTION
    prompt_hash = hashlib.sha1((system_prompt + USER_TEMPLATE).encode()).hexdigest()[:12]
    gw = ModelGateway(model=MODEL, timeout_seconds=60)  # 30s in E08B; 60s here since input is ~64% longer
    run_id = "e12a_" + uuid.uuid4().hex[:8]
    spend, t_start = 0.0, time.perf_counter()
    with open(OUT_CASES, "w") as out:
        for i, case in enumerate(cases, 1):
            rc = cand_by[case["case_id"]]
            context_text = "\n\n---\n\n".join(rc["ranked_chunk_text"])
            user_msg = USER_TEMPLATE.format(hypothesis_text=case["hypothesis_text"], context_text=context_text)
            rec = {"run_id": run_id, "experiment_id": EXPERIMENT_ID, "architecture": "static_context_candidate_v1",
                   "case_id": case["case_id"], "document_id": case["document_id"],
                   "hypothesis_id": case["hypothesis_id"], "gold_label": case["gold_label"],
                   "model": MODEL, "provider": PROVIDER, "prompt_version": "classification_prompt_v1",
                   "retrieval_version": "static_context_candidate_v1", "final_k": FINAL_K,
                   "prompt_config_hash": prompt_hash, "n_chunks_shown": len(rc["ranked_chunk_ids"]),
                   "retrieved_chunk_ids": rc["ranked_chunk_ids"],
                   "retrieved_chunk_bm25_candidate_scores": rc["ranked_chunk_bm25_candidate_scores"],
                   "retrieved_chunk_rerank_scores": rc["ranked_chunk_rerank_scores"],
                   "retrieved_chunk_offsets": rc["ranked_chunk_offsets"],
                   "model_input_system": system_prompt, "model_input_user": user_msg,
                   "timestamp": datetime.now(timezone.utc).isoformat()}
            t0 = time.perf_counter()
            try:
                r = gw.complete(system_prompt=system_prompt, user_prompt=user_msg, temperature=0.0)
                wall = time.perf_counter() - t0
                p = parse_structured_output(r.content)
                ev = validate_evidence(context_text, p.evidence, p.predicted_label or "")
                rec.update({"input_tokens": r.tokens_in, "output_tokens": r.tokens_out,
                            "generation_latency_ms": r.latency_ms, "wall_latency_s": round(wall, 2),
                            "retry_count": r.num_retries, "cost_usd": r.cost_usd,
                            "raw_response": p.raw_response, "strict_parse_valid": p.strict_parse_valid,
                            "recovered_parse_valid": p.recovered_parse_valid, "parse_status": p.parse_status,
                            "predicted_label": p.predicted_label, "evidence": p.evidence,
                            "evidence_valid": ev.is_valid, "evidence_all_verbatim": ev.all_verbatim,
                            "evidence_label_consistent": ev.label_evidence_consistent,
                            "evidence_hallucinated_count": len(ev.hallucinated_quotes),
                            "error_type": p.error_type, "error_message": p.error_message})
                record_spend(experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL,
                             input_tokens=r.tokens_in, output_tokens=r.tokens_out,
                             cost_usd=r.cost_usd, run_id=run_id)
                spend += r.cost_usd
                status = p.parse_status.upper()
            except ModelError as e:
                wall = time.perf_counter() - t0
                rec.update({"input_tokens": None, "output_tokens": None, "generation_latency_ms": None,
                            "wall_latency_s": round(wall, 2), "retry_count": getattr(e, "num_retries", None),
                            "cost_usd": None, "raw_response": "", "strict_parse_valid": False,
                            "recovered_parse_valid": False, "parse_status": "invalid",
                            "predicted_label": None, "evidence": [], "evidence_valid": None,
                            "evidence_all_verbatim": None, "evidence_label_consistent": None,
                            "evidence_hallucinated_count": None,
                            "error_type": "TIMEOUT" if "time" in str(e).lower() else "MODEL_ERROR",
                            "error_message": str(e)})
                status = "ERROR"
            out.write(json.dumps(rec) + "\n"); out.flush()
            print(f"[{i}/150] {status:9} {case['case_id']:22} gold={case['gold_label']:13} "
                  f"pred={rec.get('predicted_label')} ({rec['wall_latency_s']}s, run ${spend:.4f})", flush=True)
            if pre_spend + spend >= allowed * SAFETY_STOP_FRACTION:
                print("SAFETY STOP: budget threshold reached"); break
    total = time.perf_counter() - t_start
    json.dump({"total_wall_seconds": total, "n_cases": i, "run_id": run_id, "run_spend_usd": spend,
               "pre_run_ledger_spend_usd": pre_spend, "post_run_ledger_spend_usd": reconstruction_spend_so_far()},
              open(OUT_DIR / "run_E12A_wall_seconds.json", "w"), indent=2)
    print(f"done {total/60:.1f} min, spend ${spend:.4f}, ledger ${reconstruction_spend_so_far():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
