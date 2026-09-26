#!/usr/bin/env python3
"""
E05 Stage B full benchmark (reconstruction-v2) -- ALL 150 TRAIN_ARCH_v1 cases, A1 architecture.

Frozen configuration (do not change without a new Stage A/calibration pass):
  - Manifest: experiments/E05_full_context/TRAIN_ARCH_v1.json (150 cases, 50/50/50, seed=700,
    zero overlap with TRAIN_PROMPT_v1) -- this exact file is shared with the future E07.
  - Model: qwen2.5:7b-instruct-ctx16k (num_ctx=16384 baked into its Modelfile -- see
    configs/ollama/qwen2.5-7b-instruct-ctx16k.Modelfile; NOT via ModelGateway's num_ctx kwarg,
    which was empirically found ineffective for Ollama's OpenAI-compatible endpoint).
  - Temperature 0.0, request timeout 60s, retry policy = ModelGateway's existing default
    (unchanged from E01/E03).
  - Prompt: classification_prompt_v1 (=P0)'s system_prompt, byte-for-byte unchanged, plus one
    additive evidence-output instruction line (the same wrapper used in calibration -- not a
    new prompt variant, classification_prompt_v1.yaml itself is never touched).
  - Architecture wrapper: user-message context header is "Full NDA text:" (not the frozen
    prompt's own "Retrieved NDA excerpts:") -- documented, not a prompt change.
  - Parser: evaluation.structured_output.parse_structured_output() (deterministic strict/
    recovery, calibrated and approved).
  - Evidence validator: pipeline.evidence_validator.validate_evidence(), unchanged.

No DEV/TEST access, no hosted model call, no retrieval. Retries follow ModelGateway's existing
exponential-backoff policy only -- no case-specific retry logic for bad parses (a bad parse is a
recorded outcome, not a retry trigger).
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.prompt_selection import load_prompt_config  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
RESULTS_DIR = REPO / "experiments/E05_full_context/results"
OUT_CASES_PATH = RESULTS_DIR / "run_E05_A1_train_cases.jsonl"

EXPERIMENT_ID = "E05_full_context"
ARCHITECTURE = "A1_full_context"
MODEL = "qwen2.5:7b-instruct-ctx16k"
REQUEST_TIMEOUT_SECONDS = 60
PROMPT_VERSION = "classification_prompt_v1"  # = p00, unchanged

EVIDENCE_INSTRUCTION = (
    ' Also return the exact sentence(s) from the text that support your label, verbatim, as a '
    'list under "evidence". Return an empty list for NotMentioned.'
)
USER_TEMPLATE_A1 = "Requirement: {hypothesis_text}\n\nFull NDA text: {context_text}"

EXPECTED_N_CASES = 150
EXPECTED_DISTRIBUTION = {"Entailment": 50, "Contradiction": 50, "NotMentioned": 50}
EXPECTED_SEED = 700
EXPECTED_UNIQUE_DOCS = 78


def main() -> int:
    manifest = json.load(open(MANIFEST_PATH))
    cases = manifest["cases"]

    # Verify the frozen manifest directly before running -- do not trust a stale comment.
    from collections import Counter
    dist = Counter(c["gold_label"] for c in cases)
    assert len(cases) == EXPECTED_N_CASES, f"expected {EXPECTED_N_CASES} cases, found {len(cases)}"
    assert dict(dist) == EXPECTED_DISTRIBUTION, f"expected {EXPECTED_DISTRIBUTION}, found {dict(dist)}"
    assert manifest["seed"] == EXPECTED_SEED
    assert manifest["total_unique_documents"] == EXPECTED_UNIQUE_DOCS
    assert manifest["verified_zero_overlap_with_TRAIN_PROMPT_v1"] is True
    print(f"Verified: {len(cases)} cases, distribution {dict(dist)}, seed={manifest['seed']}, "
          f"{manifest['total_unique_documents']} unique documents, zero overlap with "
          f"TRAIN_PROMPT_v1.")

    cfg = load_prompt_config("p00")  # = classification_prompt_v1's source variant
    assert cfg["model"] == "qwen2.5:7b-instruct"  # the base model this Ollama tag derives from
    system_prompt = cfg["system_prompt"].rstrip() + "\n" + EVIDENCE_INSTRUCTION
    prompt_hash_material = system_prompt + USER_TEMPLATE_A1
    import hashlib
    prompt_config_hash = hashlib.sha1(prompt_hash_material.encode()).hexdigest()[:12]

    gateway = ModelGateway.local(model=MODEL, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    print(f"Model: {MODEL}, timeout={gateway.timeout_seconds}s, temperature=0.0")
    print(f"prompt_config_hash: {prompt_config_hash}")

    run_id = uuid.uuid4().hex[:12]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    run_start = time.perf_counter()
    with open(OUT_CASES_PATH, "w") as out_f:
        for i, case in enumerate(cases, 1):
            user_msg = USER_TEMPLATE_A1.format(
                hypothesis_text=case["hypothesis_text"], context_text=case["context_text"])

            record = {
                "run_id": run_id, "experiment_id": EXPERIMENT_ID, "architecture": ARCHITECTURE,
                "case_id": case["case_id"], "document_id": case["document_id"],
                "hypothesis_id": case["hypothesis_id"],
                # gold_label kept evaluator-side only -- not read by the model, recorded here
                # purely for later scoring, exactly as every other reconstruction-v2 runner does.
                "gold_label": case["gold_label"],
                "model": MODEL, "prompt_version": PROMPT_VERSION,
                "prompt_config_hash": prompt_config_hash,
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
                    "predicted_label": parsed.predicted_label,
                    "evidence": parsed.evidence,
                    "evidence_valid": ev_result.is_valid,
                    "evidence_all_verbatim": ev_result.all_verbatim,
                    "evidence_label_consistent": ev_result.label_evidence_consistent,
                    "evidence_hallucinated_count": len(ev_result.hallucinated_quotes),
                    "error_type": parsed.error_type, "error_message": parsed.error_message,
                })
                status = parsed.parse_status.upper()
            except ModelError as e:
                wall_latency_s = time.perf_counter() - t0
                is_timeout = "timeout" in str(e).lower() or "timed out" in str(e).lower()
                record.update({
                    "input_tokens": None, "output_tokens": None, "latency_ms": None,
                    "wall_latency_s": round(wall_latency_s, 2),
                    "retry_count": getattr(e, "num_retries", None),
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
                  f"({record.get('wall_latency_s')}s, {elapsed/60:.1f}min elapsed)")

    total_seconds = time.perf_counter() - run_start
    with open(RESULTS_DIR / "run_E05_A1_train_wall_seconds.json", "w") as f:
        json.dump({"total_wall_seconds": total_seconds, "n_cases": len(cases),
                    "run_id": run_id}, f, indent=2)
    print(f"\nwrote {OUT_CASES_PATH} ({len(cases)} cases, {total_seconds/60:.1f} min total)")
    print("No LLM/API cost -- local Ollama only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
