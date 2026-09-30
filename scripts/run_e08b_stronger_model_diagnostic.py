#!/usr/bin/env python3
"""
E08B Stage B full benchmark (reconstruction-v2) -- ALL 150 TRAIN_ARCH_v1 cases, A2-GPT5mini.

Frozen configuration (matched to E07 exactly, only the model differs -- calibration-approved,
see experiments/E08B_stronger_model_diagnostic/results/calibration_8case.json):
  - Manifest: experiments/E05_full_context/TRAIN_ARCH_v1.json (identical to E07).
  - Retrieved context: experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json --
    frozen retrieval_v1 artifact, read directly, NOT re-run (verified before running: 150/150
    present, ordering matches, zero gold leakage, retrieval config confirmed).
  - Model: openai/gpt-5-mini via OpenRouter (the ONLY variable that differs from E07).
  - Timeout 30s (calibration-verified comfortable: max observed 16.03s of 8 real calls).
  - Prompt: classification_prompt_v1 (=P0)'s system_prompt, byte-for-byte unchanged, plus the
    same additive evidence-output instruction line used in E05/E07. No GPT-specific prompt.
  - Wrapper: "Retrieved NDA excerpts:" (identical to E07).
  - Output schema, parser, evidence validator: unchanged from E07. No response_format used.

This is a fresh, coherent 150-case run -- the 8 calibration predictions are NOT reused here, even
though their case_ids are among these 150 (explicit instruction: calibration traces stay separate
for audit/cost forecasting, never merged into the benchmark output).

Budget gate checked before this run starts (evaluation.budget.check_budget_against_ledger); real
spend recorded per call via evaluation.budget.record_spend, appended to the same running ledger
calibration used, never overwritten.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.budget import check_budget_against_ledger, record_spend, reconstruction_spend_so_far  # noqa: E402
from evaluation.prompt_selection import load_prompt_config  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
RETRIEVED_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
RESULTS_DIR = REPO / "experiments/E08B_stronger_model_diagnostic/results"
OUT_CASES_PATH = RESULTS_DIR / "run_E08B_A2_gpt5mini_train_cases.jsonl"

EXPERIMENT_ID = "E08B_stronger_model_diagnostic"
ARCHITECTURE = "A2-GPT5mini"
MODEL = "openai/gpt-5-mini"
PROVIDER = "openrouter"
REQUEST_TIMEOUT_SECONDS = 30  # calibration-verified: max observed 16.03s of 8 real calls
PROMPT_VERSION = "classification_prompt_v1"
RETRIEVAL_VERSION = "retrieval_v1"

PLANNING_BUDGET_USD = 5.00
PROTECTED_RESERVE_FRACTION = 0.25
# Calibration-revised conservative 150-case projection (max observed cost/case x 150):
CONSERVATIVE_PROJECTED_150_CASE_USD = 0.4659
SAFETY_STOP_FRACTION = 0.90  # abort mid-run if projected total approaches 90% of allowed budget

EVIDENCE_INSTRUCTION = (
    ' Also return the exact sentence(s) from the text that support your label, verbatim, as a '
    'list under "evidence". Return an empty list for NotMentioned.'
)
USER_TEMPLATE_A2 = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"

EXPECTED_N_CASES = 150
EXPECTED_DISTRIBUTION = {"Entailment": 50, "Contradiction": 50, "NotMentioned": 50}
EXPECTED_SEED = 700
EXPECTED_UNIQUE_DOCS = 78


def main() -> int:
    manifest = json.load(open(MANIFEST_PATH))
    cases = manifest["cases"]
    retrieved = json.load(open(RETRIEVED_PATH))
    retrieved_by_id = {c["case_id"]: c for c in retrieved["cases"]}

    from collections import Counter
    dist = Counter(c["gold_label"] for c in cases)
    assert len(cases) == EXPECTED_N_CASES
    assert dict(dist) == EXPECTED_DISTRIBUTION
    assert manifest["seed"] == EXPECTED_SEED
    assert manifest["total_unique_documents"] == EXPECTED_UNIQUE_DOCS
    assert retrieved["total_cases"] == EXPECTED_N_CASES
    assert [c["case_id"] for c in retrieved["cases"]] == [c["case_id"] for c in cases]
    rc = retrieved["retrieval_config"]
    assert rc["method"] == "bm25" and rc["chunk_method"] == "clause" and rc["chunk_size"] == 256 \
        and rc["top_k"] == 5
    for c in retrieved["cases"]:
        assert not ({"gold_label", "gold_span_indices", "choice"} & set(c.keys()))
        assert len(c["ranked_chunk_text"]) <= 5

    print(f"Verified: {len(cases)} cases, distribution {dict(dist)}, seed={manifest['seed']}, "
          f"{manifest['total_unique_documents']} unique documents. Retrieved-context artifact: "
          f"150/150 present, ordering matches, retrieval_config={rc}, zero gold leakage. "
          f"Retrieval NOT re-run -- reading the frozen artifact only.")

    pre_run_spend = reconstruction_spend_so_far()
    print(f"\nPre-run reconstruction-v2 ledger spend: ${pre_run_spend:.4f}")
    gate = check_budget_against_ledger(
        projected_experiment_cost_usd=CONSERVATIVE_PROJECTED_150_CASE_USD,
        planning_budget_usd=PLANNING_BUDGET_USD,
        protected_reserve_fraction=PROTECTED_RESERVE_FRACTION,
    )
    print(f"Budget gate (conservative projection ${CONSERVATIVE_PROJECTED_150_CASE_USD}): {gate.reason}")
    if not gate.allowed:
        print("BUDGET GATE BLOCKED THIS RUN. Aborting before any hosted call.")
        return 1

    allowed_budget = PLANNING_BUDGET_USD * (1 - PROTECTED_RESERVE_FRACTION)
    safety_stop_usd = allowed_budget * SAFETY_STOP_FRACTION

    cfg = load_prompt_config("p00")
    assert cfg["model"] == "qwen2.5:7b-instruct"  # source variant name only -- model overridden below
    system_prompt = cfg["system_prompt"].rstrip() + "\n" + EVIDENCE_INSTRUCTION
    prompt_hash_material = system_prompt + USER_TEMPLATE_A2
    prompt_config_hash = hashlib.sha1(prompt_hash_material.encode()).hexdigest()[:12]

    gateway = ModelGateway(model=MODEL, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    print(f"\nModel: {MODEL} via {PROVIDER}, timeout={gateway.timeout_seconds}s, temperature=0.0, "
          f"response_format=NOT USED")
    print(f"prompt_config_hash: {prompt_config_hash}")

    run_id = uuid.uuid4().hex[:12]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    run_spend_this_run = 0.0
    run_start = time.perf_counter()
    with open(OUT_CASES_PATH, "w") as out_f:
        for i, case in enumerate(cases, 1):
            rc_case = retrieved_by_id[case["case_id"]]
            context_text = "\n\n---\n\n".join(rc_case["ranked_chunk_text"])
            user_msg = USER_TEMPLATE_A2.format(
                hypothesis_text=case["hypothesis_text"], context_text=context_text)

            record = {
                "run_id": run_id, "experiment_id": EXPERIMENT_ID, "architecture": ARCHITECTURE,
                "case_id": case["case_id"], "document_id": case["document_id"],
                "hypothesis_id": case["hypothesis_id"],
                "gold_label": case["gold_label"],  # evaluator-side only, never sent to the model
                "model": MODEL, "provider": PROVIDER, "prompt_version": PROMPT_VERSION,
                "retrieval_version": RETRIEVAL_VERSION,
                "prompt_config_hash": prompt_config_hash,
                "retrieved_chunk_ids": rc_case["ranked_chunk_ids"],
                "retrieved_chunk_bm25_candidate_scores": rc_case["ranked_chunk_bm25_candidate_scores"],
                "retrieved_chunk_rerank_scores": rc_case["ranked_chunk_rerank_scores"],
                "retrieved_chunk_offsets": rc_case["ranked_chunk_offsets"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            t0 = time.perf_counter()
            try:
                response = gateway.complete(system_prompt=system_prompt, user_prompt=user_msg,
                                              temperature=0.0)
                wall_latency_s = time.perf_counter() - t0
                parsed = parse_structured_output(response.content)
                ev_result = validate_evidence(context_text, parsed.evidence,
                                               parsed.predicted_label or "")

                record.update({
                    "input_tokens": response.tokens_in, "output_tokens": response.tokens_out,
                    "generation_latency_ms": response.latency_ms,
                    "wall_latency_s": round(wall_latency_s, 2),
                    "retry_count": response.num_retries,
                    "cost_usd": response.cost_usd,
                    "raw_response": parsed.raw_response,
                    "strict_parse_valid": parsed.strict_parse_valid,
                    "recovered_parse_valid": parsed.recovered_parse_valid,
                    "parse_status": parsed.parse_status,
                    "predicted_label": parsed.predicted_label,
                    "evidence": parsed.evidence,
                    "evidence_valid": ev_result.is_valid,
                    "evidence_all_verbatim": ev_result.all_verbatim,
                    "evidence_label_consistent": ev_result.label_evidence_consistent,
                    "evidence_hallucinated_count": len(ev_result.hallucinated_quotes),
                    "error_type": parsed.error_type, "error_message": parsed.error_message,
                })
                record_spend(experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL,
                              input_tokens=response.tokens_in, output_tokens=response.tokens_out,
                              cost_usd=response.cost_usd, run_id=run_id)
                run_spend_this_run += response.cost_usd
                status = parsed.parse_status.upper()
            except ModelError as e:
                wall_latency_s = time.perf_counter() - t0
                is_timeout = "timeout" in str(e).lower() or "timed out" in str(e).lower()
                record.update({
                    "input_tokens": None, "output_tokens": None,
                    "generation_latency_ms": None, "wall_latency_s": round(wall_latency_s, 2),
                    "retry_count": getattr(e, "num_retries", None), "cost_usd": None,
                    "raw_response": "", "strict_parse_valid": False,
                    "recovered_parse_valid": False, "parse_status": "invalid",
                    "predicted_label": None, "evidence": [], "evidence_valid": None,
                    "evidence_all_verbatim": None, "evidence_label_consistent": None,
                    "evidence_hallucinated_count": None,
                    "error_type": "TIMEOUT" if is_timeout else "MODEL_ERROR",
                    "error_message": str(e),
                })
                status = "ERROR"

            out_f.write(json.dumps(record) + "\n")
            out_f.flush()

            elapsed = time.perf_counter() - run_start
            print(f"[{i}/{len(cases)}] {status:9} {case['case_id']:22} gold={case['gold_label']:14} "
                  f"pred={record.get('predicted_label')} "
                  f"({record.get('wall_latency_s')}s, {elapsed/60:.1f}min elapsed, "
                  f"run_spend=${run_spend_this_run:.4f})")

            projected_total_so_far = pre_run_spend + run_spend_this_run
            if projected_total_so_far >= safety_stop_usd:
                print(f"\nSAFETY STOP: cumulative spend ${projected_total_so_far:.4f} has reached "
                      f"{SAFETY_STOP_FRACTION:.0%} of the allowed budget (${allowed_budget:.2f}). "
                      f"Stopping mid-run after case {i}/{len(cases)}.")
                break

    total_seconds = time.perf_counter() - run_start
    with open(RESULTS_DIR / "run_E08B_A2_gpt5mini_train_wall_seconds.json", "w") as f:
        json.dump({"total_wall_seconds": total_seconds, "n_cases": len(cases),
                    "run_id": run_id, "run_spend_usd": run_spend_this_run,
                    "pre_run_ledger_spend_usd": pre_run_spend,
                    "post_run_ledger_spend_usd": reconstruction_spend_so_far()}, f, indent=2)
    print(f"\nwrote {OUT_CASES_PATH} ({len(cases)} cases, {total_seconds/60:.1f} min total)")
    print(f"Real spend this run: ${run_spend_this_run:.4f}. "
          f"Ledger total now: ${reconstruction_spend_so_far():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
