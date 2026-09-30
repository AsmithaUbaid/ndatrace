#!/usr/bin/env python3
"""E12C Stage B: GPT-P0 -> GPT-P3 confirmation on TRAIN_GPT_PROMPT_CONFIRM_v1, sequential ARMS, bounded concurrency (MAX_CONCURRENCY=5) WITHIN each arm.

Same execution pattern as the completed E12B resume (scripts/run_e12b_resume.py): identical model, schema, parser, evaluator, temperature, 60s timeout.
Circuit breaker: 5 consecutive failed calls -> stop scheduling new work, let in-flight calls finish, preserve everything, stop.
Logs print operational health only (status/latency/cost) -- never labels or metrics (no interim quality analysis).
"""
from __future__ import annotations
import hashlib, json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation.budget import check_budget_against_ledger, record_spend, final_spend_so_far  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

D = REPO / "experiments/E12C_gpt_prompt_confirmation"; R = D / "results"
EXPERIMENT_ID = "E12C_gpt_prompt_confirmation"
ARMS = [("gpt_p0", "e12c_gpt_p0", "run_E12C_gpt_p0_cases.jsonl"),
        ("gpt_p3", "e12c_gpt_p3", "run_E12C_gpt_p3_cases.jsonl")]
FULL_HASH = {"gpt_p0": "3fcc7c95cf1287c292e403f12b307c9d912278ce", "gpt_p3": "d2bca31164c2db9ea9995fb769977e3e2c0a6496"}
MODEL, PROVIDER, TIMEOUT, MAX_CONCURRENCY = "openai/gpt-5-mini", "openrouter", 60, 5
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"
PLANNING, RESERVE_FRAC = 5.00, 0.25
CONSERVATIVE_REMAINING = 0.7851  # results/pre_run_forecast.json conservative_total
SAFETY_FRAC, BREAKER = 0.90, 5
LEAK = {"gold_label", "gold_span_indices", "choice", "relevance_flag", "expected_prediction", "failure_bucket"}
lock = threading.Lock()


def sha1(p): return hashlib.sha1(open(p, "rb").read()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def main() -> int:
    man = json.load(open(D / "TRAIN_GPT_PROMPT_CONFIRM_v1.json")); cases = man["cases"]; order = [c["case_id"] for c in cases]
    ctx_by = {c["case_id"]: c for c in json.load(open(D / "TRAIN_GPT_PROMPT_CONFIRM_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
    pids = [a[0] for a in ARMS]
    prompts = {k: open(REPO / f"prompts/final/{k}.txt", newline="").read() for k in pids}
    hashes = {k: sha1(REPO / f"prompts/final/{k}.txt") for k in prompts}
    import csv
    led_rows = list(csv.DictReader(open(REPO / "results/budget/final_spend_ledger.csv")))
    pre = final_spend_so_far(); gate = check_budget_against_ledger(CONSERVATIVE_REMAINING, PLANNING, RESERVE_FRAC)
    checks = {"manifest_seed_1200_150": man["seed"] == 1300 and len(cases) == 150 and man["total_unique_documents"] == 67 and man["per_class_case_counts"] == {"Entailment": 50, "Contradiction": 50, "NotMentioned": 50},
              "context_same_ids_order": list(ctx_by) == order, "context_top5": all(len(c["ranked_chunk_ids"]) <= 5 for c in ctx_by.values()),
              "context_no_gold_leakage": not any(LEAK & set(c) for c in ctx_by.values()),
              "prompt_full_hashes_match_frozen": all(hashes[k] == FULL_HASH[k] for k in pids),
              "ledger_approx_1_7637": abs(pre - 1.7637) < 0.001, "no_existing_e12c_ledger_rows": not any("E12C" in x["experiment_id"] or x["run_id"].startswith("e12c") for x in led_rows),
              "e12b_ledger_rows_present_600": sum(x["run_id"].startswith("e12b_") for x in led_rows) == 600,
              "no_existing_e12c_outputs": not any((R / a[2]).exists() for a in ARMS),
              "budget_gate_pass": bool(gate.allowed)}
    json.dump({"checks": checks, "pre_run_ledger_usd": pre, "gate_reason": gate.reason,
               "gate_arithmetic": pre + CONSERVATIVE_REMAINING + 1.25, "max_concurrency": MAX_CONCURRENCY, "timeout_seconds": TIMEOUT,
               "arm_order": pids, "timestamp": now()}, open(R / "pre_run_verification.json", "w"), indent=2)
    print(json.dumps(checks, indent=1), f"\npre-run ledger ${pre:.4f}; gate {pre + CONSERVATIVE_REMAINING + 1.25:.3f} <= 5.00", flush=True)
    if not all(checks.values()): print("PRE-RUN VERIFICATION FAILED; no hosted call made."); return 1

    allowed = PLANNING * (1 - RESERVE_FRAC); gw = ModelGateway(model=MODEL, timeout_seconds=TIMEOUT)
    grand, summary, t_all = 0.0, {}, time.perf_counter()
    for pid, run_id, fname in ARMS:
        state = {"consec": 0, "stop": None, "spend": 0.0, "done": 0, "429": 0}; stop = threading.Event()

        def work(case, out):
            if stop.is_set(): return
            rc = ctx_by[case["case_id"]]; ctxt = "\n\n---\n\n".join(rc["ranked_chunk_text"])
            user_msg = USER_TEMPLATE.format(hypothesis_text=case["hypothesis_text"], context_text=ctxt)
            rec = {"experiment_id": EXPERIMENT_ID, "run_id": run_id, "prompt_id": pid, "prompt_hash": hashes[pid], "case_id": case["case_id"],
                   "document_id": case["document_id"], "hypothesis_id": case["hypothesis_id"], "gold_label": case["gold_label"],
                   "model": MODEL, "provider": PROVIDER, "retrieval_version": "retrieval_v1", "final_k": 5, "timeout_seconds": TIMEOUT,
                   "execution": {"mode": "bounded_concurrency", "max_concurrency": MAX_CONCURRENCY}, "n_chunks_shown": len(rc["ranked_chunk_ids"]),
                   "retrieved_chunk_ids": rc["ranked_chunk_ids"], "retrieved_chunk_offsets": rc["ranked_chunk_offsets"],
                   "retrieved_chunk_rerank_scores": rc["ranked_chunk_rerank_scores"], "model_input_user": user_msg, "start_timestamp": now()}
            t0 = time.perf_counter()
            try:
                r = gw.complete(system_prompt=prompts[pid], user_prompt=user_msg, temperature=0.0)
                wall = time.perf_counter() - t0; p = parse_structured_output(r.content)
                ev = validate_evidence(ctxt, p.evidence, p.predicted_label or "")
                rec.update({"input_tokens": r.tokens_in, "output_tokens": r.tokens_out, "generation_latency_ms": r.latency_ms, "wall_latency_s": round(wall, 2),
                            "retry_count": r.num_retries, "cost_usd": r.cost_usd, "raw_response": p.raw_response, "strict_parse_valid": p.strict_parse_valid,
                            "recovered_parse_valid": p.recovered_parse_valid, "parse_status": p.parse_status, "predicted_label": p.predicted_label,
                            "evidence": p.evidence, "evidence_valid": ev.is_valid, "evidence_all_verbatim": ev.all_verbatim,
                            "evidence_label_consistent": ev.label_evidence_consistent, "evidence_hallucinated_count": len(ev.hallucinated_quotes),
                            "error_type": p.error_type, "error_message": p.error_message}); ok, status = True, p.parse_status.upper()
            except ModelError as e:
                wall = time.perf_counter() - t0
                rec.update({"input_tokens": None, "output_tokens": None, "generation_latency_ms": None, "wall_latency_s": round(wall, 2),
                            "retry_count": getattr(e, "num_retries", None), "cost_usd": None, "raw_response": "", "strict_parse_valid": False,
                            "recovered_parse_valid": False, "parse_status": "invalid", "predicted_label": None, "evidence": [], "evidence_valid": None,
                            "evidence_all_verbatim": None, "evidence_label_consistent": None, "evidence_hallucinated_count": None,
                            "error_type": "TIMEOUT" if "time" in str(e).lower() else "MODEL_ERROR", "error_message": str(e)}); ok, status = False, "ERROR"
            rec["end_timestamp"] = now()
            with lock:
                out.write(json.dumps(rec) + "\n"); out.flush()
                if ok:
                    record_spend(experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL, input_tokens=r.tokens_in, output_tokens=r.tokens_out,
                                 cost_usd=r.cost_usd, run_id=run_id)
                    state["spend"] += r.cost_usd; state["consec"] = 0
                else:
                    state["consec"] += 1
                    if "429" in str(rec["error_message"]) or "rate" in str(rec["error_message"]).lower(): state["429"] += 1
                state["done"] += 1
                print(f"[{pid} {state['done']}/150] {status:9} {case['case_id']:22} ({rec['wall_latency_s']}s, arm ${state['spend']:.4f})", flush=True)
                if pre + grand + state["spend"] >= allowed * SAFETY_FRAC and not stop.is_set():
                    state["stop"] = "BUDGET SAFETY STOP"; stop.set()
                if state["consec"] >= BREAKER and not stop.is_set():
                    state["stop"] = f"CIRCUIT BREAKER: {BREAKER} consecutive failures"; stop.set()

        t0a = time.perf_counter()
        with open(R / fname, "x") as out, ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as ex:
            list(ex.map(lambda c: work(c, out), cases))
        wall_arm = time.perf_counter() - t0a; grand += state["spend"]
        recs = [json.loads(l) for l in open(R / fname)]
        ids = [r["case_id"] for r in recs]
        verify = {"records_150": len(recs) == 150, "no_duplicates": len(set(ids)) == len(ids), "all_case_ids_present": set(ids) == set(order),
                  "all_successful": not any(r.get("error_type") for r in recs), "prompt_hash_ok": {r["prompt_hash"] for r in recs} == {hashes[pid]},
                  "run_id_ok": {r["run_id"] for r in recs} == {run_id}}
        summary[pid] = {"spend_usd": state["spend"], "wall_seconds": wall_arm, "rate_limit_like_errors": state["429"], "stopped": state["stop"],
                        "failed_calls": sum(bool(r.get("error_type")) for r in recs), "verify": verify}
        print(f"== {pid}: {json.dumps(summary[pid])}", flush=True)
        if state["stop"] or not all(verify.values()):
            print(f"OPERATIONAL STOP in {pid}: {state['stop']}; verify={verify}", flush=True)
            json.dump({"arms": summary, "total_spend_usd": grand, "completed": False}, open(R / "run_E12C_wall_seconds.json", "w"), indent=2)
            return 2
    json.dump({"arms": summary, "total_wall_seconds": time.perf_counter() - t_all, "total_spend_usd": grand, "pre_run_ledger_usd": pre,
               "post_run_ledger_usd": final_spend_so_far(), "max_concurrency": MAX_CONCURRENCY, "completed": True}, open(R / "run_E12C_wall_seconds.json", "w"), indent=2)
    print(f"ALL DONE spend ${grand:.4f}, ledger ${final_spend_so_far():.4f}", flush=True); return 0


if __name__ == "__main__":
    sys.exit(main())
