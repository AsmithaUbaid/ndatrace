#!/usr/bin/env python3
"""E17B: run the frozen E17 system on the 1,941-case complement, once. Two credential pools split load only (NOT experimental arms; never recorded per-case).
Credentials are read ONLY from env vars E17B_KEY_1 / E17B_KEY_2 at runtime and are never written to any file, log, or result. Same failure semantics as E17."""
import json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e17_common as C
from evaluation.budget import record_spend, reconstruction_spend_so_far
from evaluation.structured_output import parse_structured_output
from pipeline.evidence_validator import validate_evidence
from pipeline.model_gateway import ModelError, ModelGateway

MODEL, PROVIDER, TIMEOUT, BREAKER, RUN_ID = "openai/gpt-5-mini", "openrouter", 60, 5, "e17b_gpt_hosted_completion"
lock = threading.Lock(); now = lambda: datetime.now(timezone.utc).isoformat()
D = C.REPO / "experiments/E17B_full_test_completion"

def main() -> int:
    man = json.load(open(D / "manifests/E17B_REMAINING_v1.json")); cases = man["cases"]
    out_path = D / "results/run_E17B_gpt_cases.jsonl"; assert man["status"].startswith("FROZEN") and len(cases) == 1941 and not out_path.exists()
    F = C.load_frozen()  # asserts every E17 frozen value unchanged; complement built from the same load_frozen()
    k1, k2 = os.environ.get("E17B_KEY_1"), os.environ.get("E17B_KEY_2"); assert k1 and k2, "set E17B_KEY_1 / E17B_KEY_2 env vars (not persisted anywhere)"
    gws = [ModelGateway(model=MODEL, api_key=k1, timeout_seconds=TIMEOUT), ModelGateway(model=MODEL, api_key=k2, timeout_seconds=TIMEOUT)]
    pre = reconstruction_spend_so_far(); assert "e17b_" not in open(C.REPO / "results/budget/reconstruction_spend_ledger.csv").read()
    print(f"pre-run ledger ${pre:.5f}; {len(cases)} cases; frozen checks OK; 2 credential pools, concurrency 3 each", flush=True)
    state = {"consec": 0, "stop": None, "spend": 0.0, "done": 0}; stop = threading.Event(); t_all = time.perf_counter()

    def work(i, c, out):
        if stop.is_set(): return
        gw = gws[i % 2]  # alternate keys; pure execution split, never recorded per-case
        ctx = F["ctx"](c); user = F["user"](c)
        rec = {"run_id": RUN_ID, "case_id": c["case_id"], "document_id": c["document_id"], "hypothesis_id": c["hypothesis_id"], "gold_label": c["gold_label"], "model": MODEL, "provider": PROVIDER, "prompt_hash": C.FROZEN["prompt_sha1"], "timeout_seconds": TIMEOUT, "context_chars": len(ctx), "start_timestamp": now()}
        t0 = time.perf_counter()
        try:
            r = gw.complete(system_prompt=C.SYSTEM, user_prompt=user, temperature=0.0); p = parse_structured_output(r.content); ev = validate_evidence(ctx, p.evidence, p.predicted_label or "")
            rec.update({"input_tokens": r.tokens_in, "output_tokens": r.tokens_out, "generation_latency_ms": r.latency_ms, "wall_latency_s": round(time.perf_counter() - t0, 2), "retry_count": r.num_retries, "cost_usd": r.cost_usd, "raw_response": p.raw_response,
                        "strict_parse_valid": p.strict_parse_valid, "recovered_parse_valid": p.recovered_parse_valid, "parse_status": p.parse_status, "predicted_label": p.predicted_label, "evidence": p.evidence, "evidence_hallucinated_count": len(ev.hallucinated_quotes),
                        "evidence_label_consistent": ev.label_evidence_consistent, "error_type": p.error_type, "error_message": p.error_message}); ok, status = True, p.parse_status.upper()
        except ModelError as e:
            rec.update({"input_tokens": None, "output_tokens": None, "wall_latency_s": round(time.perf_counter() - t0, 2), "retry_count": getattr(e, "num_retries", None), "cost_usd": None, "raw_response": "", "parse_status": "invalid", "predicted_label": None, "evidence": [],
                        "evidence_hallucinated_count": 0, "error_type": "TIMEOUT" if "time" in str(e).lower() else "MODEL_ERROR", "error_message": str(e)}); ok, status = False, "ERROR"
        rec["end_timestamp"] = now()
        with lock:
            out.write(json.dumps(rec) + "\n"); out.flush(); os.fsync(out.fileno())
            if ok: record_spend(experiment_id="E17B_full_test_completion", provider=PROVIDER, model=MODEL, input_tokens=r.tokens_in, output_tokens=r.tokens_out, cost_usd=r.cost_usd, run_id=RUN_ID); state["spend"] += r.cost_usd; state["consec"] = 0
            else: state["consec"] += 1
            state["done"] += 1
            if state["done"] % 25 == 0 or status == "ERROR": print(f"[{state['done']}/1941] {status:9} ({rec['wall_latency_s']}s, ${state['spend']:.4f}) elapsed={(time.perf_counter()-t_all)/60:.1f}min", flush=True)
            if state["consec"] >= BREAKER and not stop.is_set(): state["stop"] = f"CIRCUIT BREAKER: {BREAKER} consecutive provider failures"; stop.set()

    with open(out_path, "x") as out, ThreadPoolExecutor(max_workers=6) as ex: list(ex.map(lambda ic: work(ic[0], ic[1], out), enumerate(cases)))
    recs = [json.loads(l) for l in open(out_path)]; ids = [r["case_id"] for r in recs]
    verify = {"records_1941": len(recs) == 1941, "no_duplicates": len(set(ids)) == 1941, "all_ids": set(ids) == {c["case_id"] for c in cases}, "no_provider_errors": not any(r.get("error_type") in ("TIMEOUT", "MODEL_ERROR") for r in recs)}
    json.dump({"spend_usd": state["spend"], "wall_seconds": time.perf_counter() - t_all, "stopped": state["stop"], "successful_calls": sum(r.get("cost_usd") is not None for r in recs), "failed_calls": sum(r.get("cost_usd") is None for r in recs),
               "parse_failures": sum(r["parse_status"] == "invalid" for r in recs), "verify": verify, "pre_run_ledger_usd": pre, "post_run_ledger_usd": reconstruction_spend_so_far()}, open(D / "results/run_E17B_wall.json", "w"), indent=2)
    print(f"DONE spend ${state['spend']:.4f} stop={state['stop']} verify={verify} ledger ${reconstruction_spend_so_far():.5f}", flush=True)

if __name__ == "__main__":
    main()
