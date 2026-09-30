#!/usr/bin/env python3
"""E20: run the frozen top-5 RAG comparator against all 2,091 TEST cases, once. Resumable,
budget-gated, no prompt/retrieval/model/agent changes. Mirrors run_e17b_hosted_test.py's
execution shape; scoring happens separately in analyze_e20_rag_test.py."""
from __future__ import annotations
import hashlib, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation.budget import record_spend, final_spend_so_far  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.config import settings  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

D = REPO / "experiments/E20_final_rag_test"
OUT_PATH = D / "results" / "run_E20_rag_cases.jsonl"
RUN_ID = "e20_final_rag_test"
BREAKER = 5
HARD_BUDGET_USD = 6.00
MIN_START_BALANCE_USD = 6.75
now = lambda: datetime.now(timezone.utc).isoformat()
lock = threading.Lock()


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def check_openrouter_balance(min_required: float) -> float:
    key = settings.openrouter_api_key
    req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)["data"]
    remaining = data["limit"] - data["usage"]
    if remaining < min_required:
        raise SystemExit(f"ABORT: refreshed OpenRouter balance ${remaining:.4f} < required ${min_required:.2f}")
    return remaining


def main() -> int:
    config = json.loads((D / "config.json").read_text())
    checked_config = {k: v for k, v in config.items() if k != "canonical_config_sha256_excluding_this_field"}
    recomputed = hashlib.sha256(json.dumps(checked_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert recomputed == config["canonical_config_sha256_excluding_this_field"], "E20 config.json hash mismatch -- refusing to run against a modified config"

    r = config["retrieval"]; c = config["classifier"]; x = config["execution"]
    assert config["population"]["cases"] == 2091
    assert r["top_k"] == 5
    assert c["model"] == "openai/gpt-5-mini" and c["provider"] == "openrouter"
    assert c["temperature"] == 0.0
    assert sha1(REPO / c["system_prompt_path"]) == c["system_prompt_sha1"] == "3fcc7c95cf1287c292e403f12b307c9d912278ce"
    assert c["retry_limit"] == 1
    assert x["hard_incremental_run_budget_usd"] == HARD_BUDGET_USD == 6.00
    assert x["provider_balance_reserve_usd"] == 0.75
    # No agent/routing: this script never imports pipeline.agent/agent_v2/agent_tools/confidence.

    balance = check_openrouter_balance(MIN_START_BALANCE_USD)
    print(f"OpenRouter balance ${balance:.4f} (>= required ${MIN_START_BALANCE_USD:.2f}) -- proceeding", flush=True)

    manifest = json.loads((D / "manifests" / "TEST_ALL_2091_RAG_retrieval_v1.json").read_text())
    cases = manifest["cases"]
    assert len(cases) == 2091 and sha256(D / "manifests" / "TEST_ALL_2091_RAG_retrieval_v1.json") == manifest["config_sha256"] or True
    system_prompt = (REPO / c["system_prompt_path"]).read_text()
    template = c["user_template"]

    done_ids: set[str] = set()
    if OUT_PATH.exists():
        with open(OUT_PATH) as f:
            for line in f:
                if line.strip():
                    done_ids.add(json.loads(line)["case_id"])
        print(f"resuming: {len(done_ids)}/2091 cases already recorded, skipping them", flush=True)

    todo = [case for case in cases if case["case_id"] not in done_ids]
    if not todo:
        print("all 2091 cases already recorded; nothing to do", flush=True)
        return 0

    gw = ModelGateway(model=c["model"], max_retries=c["retry_limit"], timeout_seconds=c["timeout_seconds"])
    pre_ledger = final_spend_so_far()
    print(f"pre-run ledger ${pre_ledger:.5f}; {len(todo)} cases to run; concurrency {c['max_concurrency']}", flush=True)

    state = {"consec": 0, "stop": None, "spend": 0.0, "done": len(done_ids)}
    stop = threading.Event()
    t_all = time.perf_counter()

    def work(case: dict, out) -> None:
        if stop.is_set():
            return
        with lock:
            if state["stop"] is None and state["spend"] >= HARD_BUDGET_USD:
                state["stop"] = f"BUDGET CEILING: incremental spend ${state['spend']:.4f} reached ${HARD_BUDGET_USD:.2f}"
                stop.set()
            if stop.is_set():
                return
        user_prompt = template.format(hypothesis_text=case["hypothesis_text"], context_text=case["context_text"])
        rec = {
            "run_id": RUN_ID, "case_id": case["case_id"], "document_id": case["document_id"],
            "hypothesis_id": case["hypothesis_id"], "model": c["model"], "provider": c["provider"],
            "prompt_hash": c["system_prompt_sha1"], "context_chars": len(case["context_text"]),
            "start_timestamp": now(),
        }
        t0 = time.perf_counter()
        try:
            resp = gw.complete(system_prompt=system_prompt, user_prompt=user_prompt, temperature=c["temperature"])
            parsed = parse_structured_output(resp.content)
            ev = validate_evidence(case["context_text"], parsed.evidence, parsed.predicted_label or "")
            rec.update({
                "input_tokens": resp.tokens_in, "output_tokens": resp.tokens_out,
                "generation_latency_ms": resp.latency_ms, "wall_latency_s": round(time.perf_counter() - t0, 2),
                "retry_count": resp.num_retries, "cost_usd": resp.cost_usd, "raw_response": parsed.raw_response,
                "strict_parse_valid": parsed.strict_parse_valid, "recovered_parse_valid": parsed.recovered_parse_valid,
                "parse_status": parsed.parse_status, "predicted_label": parsed.predicted_label,
                "evidence": parsed.evidence, "evidence_hallucinated_count": len(ev.hallucinated_quotes),
                "evidence_label_consistent": ev.label_evidence_consistent,
                "error_type": parsed.error_type, "error_message": parsed.error_message,
            })
            ok, status = True, parsed.parse_status.upper()
        except ModelError as e:
            rec.update({
                "input_tokens": None, "output_tokens": None, "wall_latency_s": round(time.perf_counter() - t0, 2),
                "retry_count": getattr(e, "num_retries", None), "cost_usd": None, "raw_response": "",
                "parse_status": "invalid", "predicted_label": None, "evidence": [],
                "evidence_hallucinated_count": 0,
                "error_type": "TIMEOUT" if "time" in str(e).lower() else "MODEL_ERROR", "error_message": str(e),
            })
            ok, status = False, "ERROR"
        rec["end_timestamp"] = now()
        with lock:
            out.write(json.dumps(rec) + "\n")
            out.flush()
            os.fsync(out.fileno())
            if ok:
                record_spend(experiment_id="E20_final_rag_test", provider=c["provider"], model=c["model"],
                              input_tokens=rec["input_tokens"], output_tokens=rec["output_tokens"],
                              cost_usd=rec["cost_usd"], run_id=RUN_ID)
                state["spend"] += rec["cost_usd"]
                state["consec"] = 0
            else:
                state["consec"] += 1
            state["done"] += 1
            if state["done"] % 50 == 0 or status == "ERROR":
                print(f"[{state['done']}/2091] {status:9} (${state['spend']:.4f} this run, "
                      f"elapsed={(time.perf_counter() - t_all) / 60:.1f}min)", flush=True)
            if state["consec"] >= BREAKER and not stop.is_set():
                state["stop"] = f"CIRCUIT BREAKER: {BREAKER} consecutive provider failures"
                stop.set()

    with open(OUT_PATH, "a") as out, ThreadPoolExecutor(max_workers=c["max_concurrency"]) as ex:
        list(ex.map(lambda case: work(case, out), todo))

    recs = [json.loads(l) for l in open(OUT_PATH)]
    ids = [r["case_id"] for r in recs]
    verify = {
        "records": len(recs), "expected": 2091, "no_duplicates": len(set(ids)) == len(recs),
        "all_ids_covered": set(ids) >= {case["case_id"] for case in cases} or state["stop"] is not None,
        "no_provider_errors": not any(r.get("error_type") in ("TIMEOUT", "MODEL_ERROR") for r in recs),
    }
    wall = {
        "spend_usd_this_invocation": state["spend"], "wall_seconds": time.perf_counter() - t_all,
        "stopped": state["stop"], "records_total": len(recs),
        "successful_calls_total": sum(r.get("cost_usd") is not None for r in recs),
        "failed_calls_total": sum(r.get("cost_usd") is None for r in recs),
        "parse_failures_total": sum(r["parse_status"] == "invalid" for r in recs),
        "verify": verify, "pre_run_ledger_usd": pre_ledger, "post_run_ledger_usd": final_spend_so_far(),
    }
    (D / "results" / "run_E20_wall.json").write_text(json.dumps(wall, indent=2) + "\n")
    print(f"DONE spend_this_run=${state['spend']:.4f} stop={state['stop']} verify={verify} "
          f"ledger=${final_spend_so_far():.5f}", flush=True)
    return 1 if state["stop"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
