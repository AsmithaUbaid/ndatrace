#!/usr/bin/env python3
"""
E07 Stage B full benchmark (reconstruction-v2) -- ALL 150 TRAIN_ARCH_v1 cases, A2 architecture.

Frozen configuration (matched to E05 as closely as possible -- do not change without a new
Stage A/calibration pass):
  - Manifest: experiments/E05_full_context/TRAIN_ARCH_v1.json (150 cases, 50/50/50, seed=700) --
    the IDENTICAL file E05 used, read directly, not copied.
  - Retrieved context: experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json --
    frozen retrieval_v1 (BM25/clause_256/top-20/rerank/top-5), verified before running (150/150
    present, ordering matches TRAIN_ARCH_v1, zero gold leakage).
  - Model: qwen2.5:7b-instruct-ctx16k (same tag as E05).
  - Temperature 0.0, request timeout 60s (same as E05), retry policy = ModelGateway's existing
    default (unchanged).
  - Prompt: classification_prompt_v1 (=P0)'s system_prompt, byte-for-byte unchanged, plus the
    same additive evidence-output instruction line used in E05.
  - Architecture wrapper: user-message context header is "Retrieved NDA excerpts:" (NOT E05's
    "Full NDA text:") -- the only architecture-level difference from E05's runner.
  - Parser: evaluation.structured_output.parse_structured_output() (unchanged from E05).
  - Evidence validator: pipeline.evidence_validator.validate_evidence() (unchanged from E05) --
    checked against the RETRIEVED context actually shown to the model, not the full document.

No DEV/TEST access, no hosted model call, retrieval_v1/classification_prompt_v1 unmodified.
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

from evaluation.prompt_selection import load_prompt_config  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402
from pipeline.reranker import rerank as cross_encoder_rerank  # noqa: E402
from pipeline.retriever import RetrievalResult  # noqa: E402
from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

RETRIEVAL_V1_CONFIG = dict(method="bm25", chunk_method="clause", chunk_size=256, chunk_overlap=50,
                            embedding_model=None)
CANDIDATE_POOL_SIZE = 20
TOP_K = 5

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
RETRIEVED_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
RESULTS_DIR = REPO / "experiments/E07_standard_rag/results"
OUT_CASES_PATH = RESULTS_DIR / "run_E07_A2_train_cases.jsonl"

EXPERIMENT_ID = "E07_standard_rag"
ARCHITECTURE = "A2_standard_rag"
MODEL = "qwen2.5:7b-instruct-ctx16k"
REQUEST_TIMEOUT_SECONDS = 60  # same as E05
PROMPT_VERSION = "classification_prompt_v1"
RETRIEVAL_VERSION = "retrieval_v1"

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
    train = json.load(open(REPO / "data/contractnli/train.json"))
    doc_text_by_id = {d["id"]: d["text"] for d in train["documents"]}

    # Verify the frozen manifest AND the frozen retrieved-context artifact before running.
    from collections import Counter
    dist = Counter(c["gold_label"] for c in cases)
    assert len(cases) == EXPECTED_N_CASES
    assert dict(dist) == EXPECTED_DISTRIBUTION
    assert manifest["seed"] == EXPECTED_SEED
    assert manifest["total_unique_documents"] == EXPECTED_UNIQUE_DOCS
    assert manifest["verified_zero_overlap_with_TRAIN_PROMPT_v1"] is True

    assert retrieved["total_cases"] == EXPECTED_N_CASES
    assert [c["case_id"] for c in retrieved["cases"]] == [c["case_id"] for c in cases], \
        "retrieved-context ordering does not match TRAIN_ARCH_v1"
    rc = retrieved["retrieval_config"]
    assert rc["method"] == "bm25" and rc["chunk_method"] == "clause" and rc["chunk_size"] == 256 \
        and rc["top_k"] == 5, f"unexpected retrieval config: {rc!r}"
    for c in retrieved["cases"]:
        assert not ({"gold_label", "gold_span_indices", "choice"} & set(c.keys())), \
            f"gold leakage detected in retrieved-context artifact for {c['case_id']}"
        assert len(c["ranked_chunk_text"]) <= 5

    print(f"Verified: {len(cases)} cases, distribution {dict(dist)}, seed={manifest['seed']}, "
          f"{manifest['total_unique_documents']} unique documents. Retrieved-context artifact: "
          f"150/150 present, ordering matches, retrieval_config={rc}, zero gold leakage, "
          f"top-5 chunks confirmed.")

    cfg = load_prompt_config("p00")
    assert cfg["model"] == "qwen2.5:7b-instruct"
    system_prompt = cfg["system_prompt"].rstrip() + "\n" + EVIDENCE_INSTRUCTION
    prompt_hash_material = system_prompt + USER_TEMPLATE_A2
    prompt_config_hash = hashlib.sha1(prompt_hash_material.encode()).hexdigest()[:12]

    gateway = ModelGateway.local(model=MODEL, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    print(f"Model: {MODEL}, timeout={gateway.timeout_seconds}s, temperature=0.0")
    print(f"prompt_config_hash: {prompt_config_hash}")

    run_id = uuid.uuid4().hex[:12]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    run_start = time.perf_counter()
    with open(OUT_CASES_PATH, "w") as out_f:
        for i, case in enumerate(cases, 1):
            rc_case = retrieved_by_id[case["case_id"]]

            # Real, timed retrieval -- NOT a hardcoded stub. Uses the cached index built during
            # Stage A's context generation (scripts/generate_e07_retrieved_context.py), so the
            # result is guaranteed identical to the frozen artifact (verified below) while still
            # measuring genuine candidate-generation + reranking latency, per section 15's
            # explicit instruction not to hide retrieval overhead.
            t_r0 = time.perf_counter()
            chunks, index = build_or_load_index(case["document_id"],
                                                 doc_text_by_id[case["document_id"]],
                                                 **RETRIEVAL_V1_CONFIG)
            t_cand0 = time.perf_counter()
            hits = index.search(case["hypothesis_text"], top_k=CANDIDATE_POOL_SIZE)
            t_cand1 = time.perf_counter()
            candidates = [RetrievalResult(chunk=c, score=s) for c, s in hits]
            reranked = cross_encoder_rerank(case["hypothesis_text"], candidates, top_k=TOP_K)
            t_rerank1 = time.perf_counter()

            retrieved_chunk_ids = [r.chunk.chunk_index for r in reranked]
            assert retrieved_chunk_ids == rc_case["ranked_chunk_ids"], (
                f"retrieval divergence for {case['case_id']}: live retrieval produced "
                f"{retrieved_chunk_ids} but the frozen artifact has "
                f"{rc_case['ranked_chunk_ids']} -- refusing to proceed with a case where the "
                f"context shown to the model would not match the verified frozen artifact.")
            context_text = "\n\n---\n\n".join(r.chunk.text for r in reranked)

            candidate_generation_latency_ms = (t_cand1 - t_cand0) * 1000
            reranking_latency_ms = (t_rerank1 - t_cand1) * 1000
            total_retrieval_latency_ms = (t_rerank1 - t_r0) * 1000

            user_msg = USER_TEMPLATE_A2.format(
                hypothesis_text=case["hypothesis_text"], context_text=context_text)

            record = {
                "run_id": run_id, "experiment_id": EXPERIMENT_ID, "architecture": ARCHITECTURE,
                "case_id": case["case_id"], "document_id": case["document_id"],
                "hypothesis_id": case["hypothesis_id"],
                "gold_label": case["gold_label"],  # evaluator-side only, never sent to the model
                "model": MODEL, "prompt_version": PROMPT_VERSION,
                "retrieval_version": RETRIEVAL_VERSION,
                "prompt_config_hash": prompt_config_hash,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "retrieved_chunk_bm25_candidate_scores": rc_case["ranked_chunk_bm25_candidate_scores"],
                "retrieved_chunk_rerank_scores": rc_case["ranked_chunk_rerank_scores"],
                "retrieved_chunk_offsets": rc_case["ranked_chunk_offsets"],
                "candidate_generation_latency_ms": candidate_generation_latency_ms,
                "reranking_latency_ms": reranking_latency_ms,
                "total_retrieval_latency_ms": total_retrieval_latency_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            t_retrieval = total_retrieval_latency_ms
            t0 = time.perf_counter()
            try:
                response = gateway.complete(system_prompt=system_prompt, user_prompt=user_msg,
                                              temperature=0.0)
                generation_latency_s = time.perf_counter() - t0
                parsed = parse_structured_output(response.content)
                ev_result = validate_evidence(context_text, parsed.evidence,
                                               parsed.predicted_label or "")

                record.update({
                    "input_tokens": response.tokens_in, "output_tokens": response.tokens_out,
                    "generation_latency_ms": response.latency_ms,
                    "retrieval_latency_ms": t_retrieval,
                    "end_to_end_latency_ms": response.latency_ms + t_retrieval,
                    "wall_latency_s": round(generation_latency_s, 2),
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
                generation_latency_s = time.perf_counter() - t0
                is_timeout = "timeout" in str(e).lower() or "timed out" in str(e).lower()
                record.update({
                    "input_tokens": None, "output_tokens": None,
                    "generation_latency_ms": None, "retrieval_latency_ms": t_retrieval,
                    "end_to_end_latency_ms": None,
                    "wall_latency_s": round(generation_latency_s, 2),
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
    with open(RESULTS_DIR / "run_E07_A2_train_wall_seconds.json", "w") as f:
        json.dump({"total_wall_seconds": total_seconds, "n_cases": len(cases),
                    "run_id": run_id}, f, indent=2)
    print(f"\nwrote {OUT_CASES_PATH} ({len(cases)} cases, {total_seconds/60:.1f} min total)")
    print("No LLM/API cost -- local Ollama only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
