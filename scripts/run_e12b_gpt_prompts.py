#!/usr/bin/env python3
"""E12B Stage B -- 4-arm matched GPT prompt run on TRAIN_GPT_PROMPT_v1 (150 cases x P0,P1,P2,P3).

Fixed predeclared order P0,P1,P2,P3, one process, sequential. Identical frozen context, model, timeout (60s),
temperature 0.0, parser and evidence validator for every arm; only the system prompt file differs.
Stops ONLY for budget safety or systemic failure; never resumes silently and never overwrites raw outputs.
"""
from __future__ import annotations
import hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation.budget import check_budget_against_ledger, record_spend, reconstruction_spend_so_far  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

D = REPO / "experiments/E12B_gpt_prompt_optimization"
R = D / "results"
EXPERIMENT_ID = "E12B_gpt_prompt_optimization"
ORDER = ["gpt_p0", "gpt_p1", "gpt_p2", "gpt_p3"]  # predeclared, never reordered
MODEL, PROVIDER, TIMEOUT = "openai/gpt-5-mini", "openrouter", 60
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"
PLANNING, RESERVE_FRAC, CONSERVATIVE = 5.00, 0.25, 1.6759
SAFETY_FRAC, MAX_CONSEC_ERRORS = 0.90, 5
LEAK = {"gold_label", "gold_span_indices", "choice", "relevance_flag", "expected_prediction", "failure_bucket"}


def sha1(p): return hashlib.sha1(open(p, "rb").read()).hexdigest()


def main() -> int:
    man = json.load(open(D / "TRAIN_GPT_PROMPT_v1.json")); cases = man["cases"]
    ctx = json.load(open(D / "TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1.json"))
    ctx_by = {c["case_id"]: c for c in ctx["cases"]}
    recorded = {l.split()[1]: l.split()[0] for l in open(R / "prompt_hashes_stageA_v1.txt")}
    prompts = {k: open(REPO / f"prompts/reconstruction_v2/{k}.txt", newline="").read() for k in ORDER}
    hashes = {k: sha1(REPO / f"prompts/reconstruction_v2/{k}.txt") for k in ORDER}
    pre = reconstruction_spend_so_far()
    gate = check_budget_against_ledger(CONSERVATIVE, PLANNING, RESERVE_FRAC)
    checks = {
        "manifest_150_50_50_50": len(cases) == 150 and man["per_class_case_counts"] == {"Entailment": 50, "Contradiction": 50, "NotMentioned": 50},
        "manifest_seed_1200_74_docs": man["seed"] == 1200 and man["total_unique_documents"] == 74,
        "manifest_disjoint_flags": all(man[k] for k in ("verified_document_disjoint_from_TRAIN_PROMPT_v1", "verified_document_disjoint_from_TRAIN_ARCH_v1", "verified_document_disjoint_from_TRAIN_ORACLE_v1")),
        "context_same_ids_order": [c["case_id"] for c in ctx["cases"]] == [c["case_id"] for c in cases],
        "context_top5_only": all(len(c["ranked_chunk_ids"]) <= 5 for c in ctx["cases"]),
        "context_no_gold_leakage": not any(LEAK & set(c) for c in ctx["cases"]),
        "prompt_hashes_match_stageA": all(hashes[k] == recorded[f"prompts/reconstruction_v2/{k}.txt"] for k in ORDER),
        "budget_gate_pass": bool(gate.allowed),
        "no_existing_raw_outputs": not any((R / f"run_E12B_{k}_cases.jsonl").exists() for k in ORDER),
    }
    json.dump({"checks": checks, "prompt_hashes": hashes, "run_order": ORDER, "model": MODEL, "provider": PROVIDER,
               "timeout_seconds": TIMEOUT, "temperature": 0.0, "pre_run_ledger_usd": pre, "gate_reason": gate.reason,
               "tests_before_run": "338 passed", "timestamp": datetime.now(timezone.utc).isoformat()},
              open(R / "pre_run_verification.json", "w"), indent=2)
    print(json.dumps(checks, indent=1), f"\npre-run ledger ${pre:.4f}", flush=True)
    if not all(checks.values()):
        print("PRE-RUN VERIFICATION FAILED; no hosted call made."); return 1

    allowed = PLANNING * (1 - RESERVE_FRAC)
    gw = ModelGateway(model=MODEL, timeout_seconds=TIMEOUT)
    grand, t_all, summary, consec = 0.0, time.perf_counter(), {}, 0
    for pid in ORDER:
        run_id, spend, t0a = f"e12b_{pid}", 0.0, time.perf_counter()
        with open(R / f"run_E12B_{pid}_cases.jsonl", "x") as out:
            for i, case in enumerate(cases, 1):
                rc = ctx_by[case["case_id"]]
                context_text = "\n\n---\n\n".join(rc["ranked_chunk_text"])
                user_msg = USER_TEMPLATE.format(hypothesis_text=case["hypothesis_text"], context_text=context_text)
                rec = {"experiment_id": EXPERIMENT_ID, "run_id": run_id, "prompt_id": pid, "prompt_hash": hashes[pid],
                       "case_id": case["case_id"], "document_id": case["document_id"], "hypothesis_id": case["hypothesis_id"],
                       "gold_label": case["gold_label"], "model": MODEL, "provider": PROVIDER, "retrieval_version": "retrieval_v1",
                       "final_k": 5, "timeout_seconds": TIMEOUT, "n_chunks_shown": len(rc["ranked_chunk_ids"]),
                       "retrieved_chunk_ids": rc["ranked_chunk_ids"], "retrieved_chunk_offsets": rc["ranked_chunk_offsets"],
                       "retrieved_chunk_rerank_scores": rc["ranked_chunk_rerank_scores"], "model_input_user": user_msg,
                       "timestamp": datetime.now(timezone.utc).isoformat()}
                t0 = time.perf_counter()
                try:
                    r = gw.complete(system_prompt=prompts[pid], user_prompt=user_msg, temperature=0.0)
                    wall = time.perf_counter() - t0
                    p = parse_structured_output(r.content)
                    ev = validate_evidence(context_text, p.evidence, p.predicted_label or "")
                    rec.update({"input_tokens": r.tokens_in, "output_tokens": r.tokens_out, "generation_latency_ms": r.latency_ms,
                                "wall_latency_s": round(wall, 2), "retry_count": r.num_retries, "cost_usd": r.cost_usd,
                                "raw_response": p.raw_response, "strict_parse_valid": p.strict_parse_valid,
                                "recovered_parse_valid": p.recovered_parse_valid, "parse_status": p.parse_status,
                                "predicted_label": p.predicted_label, "evidence": p.evidence, "evidence_valid": ev.is_valid,
                                "evidence_all_verbatim": ev.all_verbatim, "evidence_label_consistent": ev.label_evidence_consistent,
                                "evidence_hallucinated_count": len(ev.hallucinated_quotes),
                                "error_type": p.error_type, "error_message": p.error_message})
                    record_spend(experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL, input_tokens=r.tokens_in,
                                 output_tokens=r.tokens_out, cost_usd=r.cost_usd, run_id=run_id)
                    spend += r.cost_usd; grand += r.cost_usd; consec = 0; status = p.parse_status.upper()
                except ModelError as e:
                    wall = time.perf_counter() - t0; consec += 1
                    rec.update({"input_tokens": None, "output_tokens": None, "generation_latency_ms": None, "wall_latency_s": round(wall, 2),
                                "retry_count": getattr(e, "num_retries", None), "cost_usd": None, "raw_response": "",
                                "strict_parse_valid": False, "recovered_parse_valid": False, "parse_status": "invalid",
                                "predicted_label": None, "evidence": [], "evidence_valid": None, "evidence_all_verbatim": None,
                                "evidence_label_consistent": None, "evidence_hallucinated_count": None,
                                "error_type": "TIMEOUT" if "time" in str(e).lower() else "MODEL_ERROR", "error_message": str(e)})
                    status = "ERROR"
                out.write(json.dumps(rec) + "\n"); out.flush()
                print(f"[{pid} {i}/150] {status:9} {case['case_id']:22} gold={case['gold_label']:13} pred={rec.get('predicted_label')} "
                      f"({rec['wall_latency_s']}s, arm ${spend:.4f}, total ${grand:.4f})", flush=True)
                if pre + grand >= allowed * SAFETY_FRAC:
                    print("SAFETY STOP: budget threshold"); return 2
                if consec >= MAX_CONSEC_ERRORS:
                    print("SYSTEMIC STOP: consecutive model errors"); return 3
        summary[pid] = {"spend_usd": spend, "wall_seconds": time.perf_counter() - t0a}
        print(f"== {pid} done: ${spend:.4f}, {summary[pid]['wall_seconds']/60:.1f} min", flush=True)
    json.dump({"arms": summary, "total_wall_seconds": time.perf_counter() - t_all, "total_spend_usd": grand, "total_calls": 600,
               "pre_run_ledger_usd": pre, "post_run_ledger_usd": reconstruction_spend_so_far(), "order": ORDER},
              open(R / "run_E12B_wall_seconds.json", "w"), indent=2)
    print(f"ALL DONE spend ${grand:.4f}, ledger ${reconstruction_spend_so_far():.4f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
