#!/usr/bin/env python3
"""
E08B calibration run (reconstruction-v2) -- 8 cases only, NOT the full 150-case diagnostic.

Purpose only: verify the 30s hosted timeout is adequate for A2's actual task shape (retrieved
context, not Oracle's single-sentence shape), get real GPT-5-mini output-token/cost data for
this task, and validate structured-output parsing end-to-end against a real hosted GPT-5-mini
call. These 8 predictions are NOT scored against gold and NOT used to tune the prompt, retrieval,
evidence schema, or experiment design -- purely operational diagnostics, mirroring E05's own
calibration precedent (scripts/run_e05_calibration.py).

Deterministically selects 8 cases from the frozen TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json
artifact spanning the real A2 input-token distribution (2 near Q1, 2 near median, 2 near p90,
2 near max), preferring distinct documents/classes where possible. Frozen BEFORE any call.

Frozen configuration (identical to the planned E08B full run, see
experiments/E08B_stronger_model_diagnostic/{config.yaml,summary.md}):
  - Manifest + retrieved context: the frozen TRAIN_ARCH_v1 / ..._RETRIEVED_retrieval_v1.json
    artifacts E07 used. Retrieval NOT re-run.
  - Model: openai/gpt-5-mini via OpenRouter.
  - Prompt: classification_prompt_v1 (=P0), byte-for-byte unchanged, same evidence instruction
    and "Retrieved NDA excerpts:" wrapper E07 used. No GPT-specific prompt.
  - Parser: evaluation.structured_output.parse_structured_output (unchanged).
  - Evidence validator: pipeline.evidence_validator.validate_evidence (unchanged).
  - No response_format / provider-side JSON schema enforcement (matches E07's Qwen run).

Budget gate: checked before any hosted call via evaluation.budget.check_budget_against_ledger.
Real spend recorded via evaluation.budget.record_spend after every successful call.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import tiktoken

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.budget import check_budget_against_ledger, record_spend  # noqa: E402
from evaluation.prompt_selection import load_prompt_config  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
RETRIEVED_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
OUT_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/calibration_8case.json"

EXPERIMENT_ID = "E08B_stronger_model_diagnostic"
MODEL = "openai/gpt-5-mini"
PROVIDER = "openrouter"
REQUEST_TIMEOUT_SECONDS = 30  # current frozen default -- being verified this pass, not changed
PLANNING_BUDGET_USD = 5.00
PROTECTED_RESERVE_FRACTION = 0.25

EVIDENCE_INSTRUCTION = (
    ' Also return the exact sentence(s) from the text that support your label, verbatim, as a '
    'list under "evidence". Return an empty list for NotMentioned.'
)
USER_TEMPLATE_A2 = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"


def select_calibration_cases(manifest_cases: list[dict], retrieved_by_id: dict) -> list[dict]:
    enc = tiktoken.get_encoding("cl100k_base")
    cases = []
    for c in manifest_cases:
        rc = retrieved_by_id[c["case_id"]]
        context_text = "\n\n---\n\n".join(rc["ranked_chunk_text"])
        cases.append(dict(c, context_text=context_text))
    for c in cases:
        c["doc_tokens"] = len(enc.encode(c["context_text"]))
    sorted_cases = sorted(cases, key=lambda c: c["doc_tokens"])
    n = len(sorted_cases)

    def nearest_idx(pct: float) -> int:
        return min(int(n * pct), n - 1)

    def pick_near(idx: int, exclude_ids: set, exclude_docs: set, k: int = 2) -> list[dict]:
        window = sorted(range(n), key=lambda i: abs(i - idx))
        picked, used_docs = [], set()
        for i in window:
            c = sorted_cases[i]
            if c["case_id"] in exclude_ids or c["document_id"] in exclude_docs or c["document_id"] in used_docs:
                continue
            picked.append(c)
            used_docs.add(c["document_id"])
            if len(picked) >= k:
                break
        return picked

    exclude_ids: set = set()
    exclude_docs: set = set()
    q1_picks = pick_near(nearest_idx(0.25), exclude_ids, exclude_docs)
    exclude_ids |= {c["case_id"] for c in q1_picks}
    exclude_docs |= {c["document_id"] for c in q1_picks}

    med_picks = pick_near(nearest_idx(0.50), exclude_ids, exclude_docs)
    exclude_ids |= {c["case_id"] for c in med_picks}
    exclude_docs |= {c["document_id"] for c in med_picks}

    p90_picks = pick_near(nearest_idx(0.90), exclude_ids, exclude_docs)
    exclude_ids |= {c["case_id"] for c in p90_picks}
    exclude_docs |= {c["document_id"] for c in p90_picks}

    max_picks, used_docs = [], set()
    for c in reversed(sorted_cases):
        if c["document_id"] in exclude_docs or c["document_id"] in used_docs:
            continue
        max_picks.append(c)
        used_docs.add(c["document_id"])
        if len(max_picks) >= 2:
            break

    return [dict(c, length_bucket="q1") for c in q1_picks] + \
           [dict(c, length_bucket="median") for c in med_picks] + \
           [dict(c, length_bucket="p90") for c in p90_picks] + \
           [dict(c, length_bucket="max") for c in max_picks]


def main() -> int:
    manifest = json.load(open(MANIFEST_PATH))
    retrieved = json.load(open(RETRIEVED_PATH))
    retrieved_by_id = {c["case_id"]: c for c in retrieved["cases"]}
    assert retrieved["total_cases"] == 150
    assert [c["case_id"] for c in retrieved["cases"]] == [c["case_id"] for c in manifest["cases"]]

    calibration_cases = select_calibration_cases(manifest["cases"], retrieved_by_id)

    print("Selection rule: deterministic, 2 nearest each of Q1/median/p90/max of the real "
          "cl100k_base-approximated A2 input-token distribution over the frozen retrieved-"
          "context artifact, preferring distinct documents/classes. Frozen case_ids:")
    for c in calibration_cases:
        print(f"  {c['length_bucket']:8} {c['case_id']:22} gold={c['gold_label']:14} "
              f"context_tokens={c['doc_tokens']}")

    # Budget gate -- BEFORE any hosted call.
    projected = 0.379  # Stage A's worst-plausible 150-case estimate (summary.md section 5)
    gate = check_budget_against_ledger(
        projected_experiment_cost_usd=projected,
        planning_budget_usd=PLANNING_BUDGET_USD,
        protected_reserve_fraction=PROTECTED_RESERVE_FRACTION,
    )
    print(f"\nBudget gate (pre-calibration, using Stage A's worst-plausible 150-case estimate): "
          f"{gate.reason}")
    if not gate.allowed:
        print("BUDGET GATE BLOCKED. Aborting before any hosted call.")
        return 1

    cfg = load_prompt_config("p00")
    system_prompt = cfg["system_prompt"].rstrip() + "\n" + EVIDENCE_INSTRUCTION

    gateway = ModelGateway(model=MODEL, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    print(f"\nModel: {MODEL} via {PROVIDER}, timeout={gateway.timeout_seconds}s, "
          f"response_format=NOT USED (matches E07's Qwen run)")

    results = []
    for i, case in enumerate(calibration_cases, 1):
        user_msg = USER_TEMPLATE_A2.format(
            hypothesis_text=case["hypothesis_text"], context_text=case["context_text"])

        record = {
            "case_id": case["case_id"], "gold_label": case["gold_label"],
            "length_bucket": case["length_bucket"], "context_tokens_approx": case["doc_tokens"],
        }
        t0 = time.perf_counter()
        try:
            response = gateway.complete(system_prompt=system_prompt, user_prompt=user_msg,
                                          temperature=0.0)
            wall_latency_s = time.perf_counter() - t0
            parsed = parse_structured_output(response.content)
            ev_result = validate_evidence(case["context_text"], parsed.evidence,
                                           parsed.predicted_label or "")

            record.update({
                "input_tokens": response.tokens_in, "output_tokens": response.tokens_out,
                "latency_ms": response.latency_ms, "wall_latency_s": round(wall_latency_s, 2),
                "retry_count": response.num_retries, "cost_usd": response.cost_usd,
                "raw_response": parsed.raw_response,
                "strict_parse_valid": parsed.strict_parse_valid,
                "recovered_parse_valid": parsed.recovered_parse_valid,
                "parse_status": parsed.parse_status,
                "prediction": parsed.predicted_label,
                "evidence": parsed.evidence,
                "evidence_valid": ev_result.is_valid,
                "evidence_all_verbatim": ev_result.all_verbatim,
                "evidence_label_consistent": ev_result.label_evidence_consistent,
                "evidence_hallucinated_count": len(ev_result.hallucinated_quotes),
                "error_type": parsed.error_type, "error_message": parsed.error_message,
                "timeout": False,
            })
            record_spend(experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL,
                          input_tokens=response.tokens_in, output_tokens=response.tokens_out,
                          cost_usd=response.cost_usd, run_id="e08b_calibration_8case")
            status = parsed.parse_status.upper()
        except ModelError as e:
            wall_latency_s = time.perf_counter() - t0
            is_timeout = "timeout" in str(e).lower() or "timed out" in str(e).lower()
            record.update({
                "input_tokens": None, "output_tokens": None, "latency_ms": None,
                "wall_latency_s": round(wall_latency_s, 2), "retry_count": None, "cost_usd": None,
                "raw_response": "", "strict_parse_valid": False, "recovered_parse_valid": False,
                "parse_status": "invalid", "prediction": None, "evidence": [],
                "evidence_valid": None, "evidence_all_verbatim": None,
                "evidence_label_consistent": None, "evidence_hallucinated_count": None,
                "error_type": "TIMEOUT" if is_timeout else "MODEL_ERROR",
                "error_message": str(e), "timeout": is_timeout,
            })
            status = "ERROR"

        results.append(record)
        print(f"[{i}/{len(calibration_cases)}] {status} {case['case_id']} "
              f"({case['length_bucket']}, {case['doc_tokens']} ctx tokens) -- "
              f"{record.get('wall_latency_s')}s wall, gold={case['gold_label']} "
              f"pred={record.get('prediction')} cost=${record.get('cost_usd')}")

    strict_count = sum(1 for r in results if r["parse_status"] == "strict")
    recovered_count = sum(1 for r in results if r["parse_status"] == "recovered")
    invalid_count = sum(1 for r in results if r["parse_status"] == "invalid")
    evidence_valid_count = sum(1 for r in results if r.get("evidence_valid"))
    timeout_count = sum(1 for r in results if r.get("timeout"))
    costs = [r["cost_usd"] for r in results if r.get("cost_usd") is not None]
    out_tokens = [r["output_tokens"] for r in results if r.get("output_tokens") is not None]

    print(f"\nstrict={strict_count} recovered={recovered_count} invalid={invalid_count} "
          f"evidence_valid={evidence_valid_count} timeouts={timeout_count}")
    print(f"strict parse validity = {strict_count/len(results):.1%}  "
          f"usable structured-output validity (strict+recovered) = "
          f"{(strict_count+recovered_count)/len(results):.1%}")

    revised_projection = None
    if costs:
        mean_cost = sum(costs) / len(costs)
        max_cost = max(costs)
        revised_projection = {
            "mean_cost_per_case_usd": mean_cost, "max_cost_per_case_usd": max_cost,
            "mean_output_tokens": sum(out_tokens) / len(out_tokens) if out_tokens else None,
            "max_output_tokens": max(out_tokens) if out_tokens else None,
            "projected_150_case_central_usd": mean_cost * 150,
            "projected_150_case_conservative_usd": max_cost * 150,
        }
        revised_gate = check_budget_against_ledger(
            projected_experiment_cost_usd=revised_projection["projected_150_case_conservative_usd"],
            planning_budget_usd=PLANNING_BUDGET_USD,
            protected_reserve_fraction=PROTECTED_RESERVE_FRACTION,
        )
        revised_projection["gate_result"] = revised_gate.reason
        revised_projection["gate_allowed"] = revised_gate.allowed
        print(f"\nRevised 150-case projection from real calibration data: "
              f"central=${revised_projection['projected_150_case_central_usd']:.4f} "
              f"conservative=${revised_projection['projected_150_case_conservative_usd']:.4f}")
        print(f"Revised budget gate: {revised_gate.reason}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({
            "model": MODEL, "provider": PROVIDER,
            "request_timeout_seconds": gateway.timeout_seconds,
            "strict_parse_count": strict_count, "recovered_parse_count": recovered_count,
            "invalid_parse_count": invalid_count, "evidence_valid_count": evidence_valid_count,
            "timeout_count": timeout_count,
            "revised_150_case_projection": revised_projection,
            "cases": results,
        }, f, indent=2)
    print(f"\nwrote {OUT_PATH}")
    print("Not scored against gold, not used for any prompt/model/retrieval decision -- "
          "operational diagnostics only. STOP for review -- do NOT run the remaining 142 cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
