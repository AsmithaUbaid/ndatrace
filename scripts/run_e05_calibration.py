#!/usr/bin/env python3
"""
E05 Stage B calibration run (reconstruction-v2) -- 8 cases only, NOT the full benchmark.

Purpose only: verify the fixed context configuration end-to-end, detect truncation/runtime
failures, estimate real per-case latency at the corrected 60s timeout, and validate structured-
output parsing (including deterministic recovery, evaluation.structured_output). These 8
predictions are NOT scored against gold and NOT used to change the prompt or select anything --
purely operational diagnostics. This is a re-run of the IDENTICAL 8 cases from the prior
calibration pass (same manifest, same deterministic selection algorithm) -- not a new sample.

Deterministically selects 8 cases from TRAIN_ARCH_v1 spanning the document-length distribution
(2 near Q1, 2 near median, 2 near p90, 2 longest), preferring distinct documents/classes where
possible.

A1 architecture wrapper (documented, not a new prompt variant, not touched this pass): reuses
classification_prompt_v1 (=P0)'s system_prompt byte-for-byte, plus one additive evidence-output
instruction line; the user-side context header changes from the frozen prompt's "Retrieved NDA
excerpts:" to "Full NDA text:" for this architecture. classification_prompt_v1.yaml itself is
never modified. The 3/8 parse failures found in the prior calibration pass (well-formed JSON
followed by trailing free-text commentary) are handled by a parsing/protocol fix
(evaluation.structured_output.parse_structured_output), NOT a prompt change -- see that
module's docstring.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import tiktoken

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.prompt_selection import load_prompt_config  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
OUT_PATH = REPO / "experiments/E05_full_context/results/calibration_8case.json"
# CONTEXT CONFIGURATION (authoritative -- do not rely on ModelGateway's num_ctx kwarg for this):
# Ollama's OpenAI-compatible /v1/chat/completions endpoint was empirically observed (direct
# curl, independent of this script's code, installed Ollama version 0.34.3) to IGNORE a
# per-request options.num_ctx field -- `ollama ps` stayed at the model's already-loaded
# CONTEXT=4096 regardless, and even reverted an already-16384-loaded instance back down to 4096
# on the next OpenAI-compat call. ModelGateway's num_ctx parameter did NOT fix this and is not
# claimed to. The actual, verified fix is this Modelfile-based custom model tag, which bakes
# num_ctx=16384 into the model's own default (configs/ollama/qwen2.5-7b-instruct-ctx16k.Modelfile):
MODEL = "qwen2.5:7b-instruct-ctx16k"
EFFECTIVE_CONTEXT = 16384  # verified via `ollama ps` (CONTEXT column) and via token-usage checks
REQUEST_TIMEOUT_SECONDS = 60  # ~2x the 28.8s max observed in calibration; current 30s default left almost no margin

# Architecture wrapper -- additive only, classification_prompt_v1.yaml itself untouched.
EVIDENCE_INSTRUCTION = (
    ' Also return the exact sentence(s) from the text that support your label, verbatim, as a '
    'list under "evidence". Return an empty list for NotMentioned.'
)
USER_TEMPLATE_A1 = "Requirement: {hypothesis_text}\n\nFull NDA text: {context_text}"


def select_calibration_cases(manifest_cases: list[dict]) -> list[dict]:
    enc = tiktoken.get_encoding("cl100k_base")
    cases = [dict(c) for c in manifest_cases]
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

    longest_picks, used_docs = [], set()
    for c in reversed(sorted_cases):
        if c["document_id"] in exclude_docs or c["document_id"] in used_docs:
            continue
        longest_picks.append(c)
        used_docs.add(c["document_id"])
        if len(longest_picks) >= 2:
            break

    return [dict(c, length_bucket="q1") for c in q1_picks] + \
           [dict(c, length_bucket="median") for c in med_picks] + \
           [dict(c, length_bucket="p90") for c in p90_picks] + \
           [dict(c, length_bucket="longest") for c in longest_picks]


def main() -> int:
    manifest = json.load(open(MANIFEST_PATH))
    calibration_cases = select_calibration_cases(manifest["cases"])

    print(f"Selected {len(calibration_cases)} calibration cases:")
    for c in calibration_cases:
        print(f"  {c['length_bucket']:8} {c['case_id']:20} gold={c['gold_label']:14} "
              f"doc_tokens={c['doc_tokens']}")

    cfg = load_prompt_config("p00")  # = classification_prompt_v1's source variant
    system_prompt = cfg["system_prompt"].rstrip() + "\n" + EVIDENCE_INSTRUCTION

    gateway = ModelGateway.local(model=MODEL, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    print(f"\nModel: {MODEL} (num_ctx={EFFECTIVE_CONTEXT} baked into this model tag's "
          f"Modelfile -- NOT via ModelGateway's num_ctx kwarg, see module docstring), "
          f"timeout={gateway.timeout_seconds}s")

    results = []
    for i, case in enumerate(calibration_cases, 1):
        user_msg = USER_TEMPLATE_A1.format(
            hypothesis_text=case["hypothesis_text"], context_text=case["context_text"])

        record = {
            "case_id": case["case_id"], "gold_label": case["gold_label"],
            "length_bucket": case["length_bucket"], "doc_tokens_approx": case["doc_tokens"],
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
                "retry_count": response.num_retries,
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
            status = parsed.parse_status.upper()
        except ModelError as e:
            wall_latency_s = time.perf_counter() - t0
            is_timeout = "timeout" in str(e).lower() or "timed out" in str(e).lower()
            record.update({
                "input_tokens": None, "output_tokens": None, "latency_ms": None,
                "wall_latency_s": round(wall_latency_s, 2), "retry_count": None,
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
              f"({case['length_bucket']}, {case['doc_tokens']} doc tokens) -- "
              f"{record.get('wall_latency_s')}s wall, gold={case['gold_label']} "
              f"pred={record.get('prediction')}")

    strict_count = sum(1 for r in results if r["parse_status"] == "strict")
    recovered_count = sum(1 for r in results if r["parse_status"] == "recovered")
    invalid_count = sum(1 for r in results if r["parse_status"] == "invalid")
    evidence_valid_count = sum(1 for r in results if r.get("evidence_valid"))
    timeout_count = sum(1 for r in results if r.get("timeout"))
    print(f"\nstrict={strict_count} recovered={recovered_count} invalid={invalid_count} "
          f"evidence_valid={evidence_valid_count} timeouts={timeout_count}")
    print(f"strict parse validity = {strict_count/len(results):.1%}  "
          f"usable structured-output validity (strict+recovered) = "
          f"{(strict_count+recovered_count)/len(results):.1%}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({
            "model": MODEL, "effective_context": EFFECTIVE_CONTEXT,
            "context_configuration_note": (
                "num_ctx=16384 is baked into the qwen2.5:7b-instruct-ctx16k Modelfile tag, "
                "NOT set via ModelGateway's num_ctx kwarg -- that kwarg is plumbing/API "
                "compatibility only and was empirically observed to be ignored by Ollama's "
                "OpenAI-compatible endpoint. Verified via `ollama ps` (CONTEXT column) and "
                "input-token-usage checks."
            ),
            "request_timeout_seconds": gateway.timeout_seconds,
            "strict_parse_count": strict_count, "recovered_parse_count": recovered_count,
            "invalid_parse_count": invalid_count, "evidence_valid_count": evidence_valid_count,
            "timeout_count": timeout_count,
            "cases": results,
        }, f, indent=2)
    print(f"\nwrote {OUT_PATH}")
    print("No LLM/API cost -- local Ollama only. Not scored against gold, not used for any "
          "prompt/model decision -- diagnostics only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
