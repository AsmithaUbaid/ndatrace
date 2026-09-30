#!/usr/bin/env python3
"""Build the frozen E20 TEST manifest/retrieval artifact and forecast. No hosted calls."""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path

import tiktoken

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.reranker import rerank as cross_encoder_rerank  # noqa: E402
from pipeline.retriever import RetrievalResult  # noqa: E402
from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

OUT = REPO / "experiments/E20_final_rag_test"
MAN = OUT / "manifests"
RES = OUT / "results"
TEST = REPO / "data/contractnli/test.json"
SOURCE_MANIFEST = REPO / "experiments/E17_final_test/manifests/TEST_ALL_2091_cases.json"
SYSTEM_PROMPT = REPO / "prompts/final/gpt_p0.txt"

TEST_SHA256 = "460267b56052a2dc5aead98eb35eadef9e6734d5723d37b4a9790e410f812387"
SOURCE_MANIFEST_SHA256 = "8a2f13af814951a5af682ab5acfb79ecd8a2a644f14e1bc7944a364bd5dd6be4"
P0_SHA1 = "3fcc7c95cf1287c292e403f12b307c9d912278ce"
MODEL = "openai/gpt-5-mini"
PROVIDER = "openrouter"
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"
JOIN = "\n\n---\n\n"
RETRIEVAL = {
    "method": "bm25",
    "chunk_method": "clause",
    "chunk_size": 256,
    "chunk_overlap": 50,
    "embedding_model": None,
    "candidate_pool_size": 20,
    "top_k": 5,
    "reranking": True,
    "reranker_model": "cross-encoder/ms-marco-MiniLM-L-12-v2",
}


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def quantile(values: list[float], p: float) -> float:
    return sorted(values)[min(int(len(values) * p), len(values) - 1)]


def describe(values: list[float]) -> dict:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "p90": quantile(values, 0.90),
        "p95": quantile(values, 0.95),
        "max": max(values),
    }


def main() -> int:
    checks = {
        "test_sha256": hash_file(TEST) == TEST_SHA256,
        "source_manifest_sha256": hash_file(SOURCE_MANIFEST) == SOURCE_MANIFEST_SHA256,
        "gpt_p0_sha1": hash_file(SYSTEM_PROMPT, "sha1") == P0_SHA1,
    }
    if not all(checks.values()):
        raise SystemExit(f"Frozen-input check failed before retrieval: {checks}")

    test = json.loads(TEST.read_text())
    source = json.loads(SOURCE_MANIFEST.read_text())
    docs = {doc["id"]: doc for doc in test["documents"]}
    labels = test["labels"]
    source_cases = source["cases"]
    checks.update({
        "test_documents_123": len(docs) == 123,
        "test_hypotheses_17": len(labels) == 17,
        "source_cases_2091": len(source_cases) == 2091,
        "source_unique_case_ids_2091": len({c["case_id"] for c in source_cases}) == 2091,
        "full_cartesian_population": len(docs) * len(labels) == len(source_cases),
    })
    if not all(checks.values()):
        raise SystemExit(f"Population check failed: {checks}")

    model_cases = []
    gold_cases = []
    label_counts = {label: 0 for label in ("Entailment", "Contradiction", "NotMentioned")}
    full_nda_tokens = []
    enc = tiktoken.get_encoding("cl100k_base")
    system = SYSTEM_PROMPT.read_text()

    current_doc_id = None
    current_index = None
    for position, case in enumerate(source_cases):
        doc = docs[case["document_id"]]
        hyp_text = labels[case["hypothesis_id"]]["hypothesis"]
        ann = doc["annotation_sets"][0]["annotations"][case["hypothesis_id"]]
        expected_id = f"test::{case['document_id']}::{case['hypothesis_id']}"
        if case["case_id"] != expected_id or case["gold_label"] != ann["choice"]:
            raise SystemExit(f"Manifest/data mismatch at {case['case_id']}")
        if current_doc_id != case["document_id"]:
            _, current_index = build_or_load_index(
                case["document_id"], doc["text"],
                method=RETRIEVAL["method"], chunk_method=RETRIEVAL["chunk_method"],
                chunk_size=RETRIEVAL["chunk_size"], chunk_overlap=RETRIEVAL["chunk_overlap"],
                embedding_model=RETRIEVAL["embedding_model"],
            )
            current_doc_id = case["document_id"]

        hits = current_index.search(hyp_text, top_k=RETRIEVAL["candidate_pool_size"])
        candidates = [RetrievalResult(chunk=chunk, score=score) for chunk, score in hits]
        reranked = cross_encoder_rerank(
            hyp_text, candidates, top_k=RETRIEVAL["top_k"],
            model_name=RETRIEVAL["reranker_model"],
        )
        bm25_by_chunk = {chunk.chunk_index: float(score) for chunk, score in hits}
        top5 = [{
            "chunk_id": hit.chunk.chunk_index,
            "text": hit.chunk.text,
            "offset": [hit.chunk.start_char, hit.chunk.end_char],
            "bm25_candidate_score": bm25_by_chunk[hit.chunk.chunk_index],
            "rerank_score": float(hit.score),
        } for hit in reranked]
        top20 = [{
            "chunk_id": chunk.chunk_index,
            "offset": [chunk.start_char, chunk.end_char],
            "bm25_score": float(score),
        } for chunk, score in hits]
        context = JOIN.join(hit["text"] for hit in top5)
        nda_tokens = len(enc.encode(doc["text"]))
        full_nda_tokens.append(nda_tokens)
        model_cases.append({
            "position": position,
            "case_id": case["case_id"],
            "document_id": case["document_id"],
            "hypothesis_id": case["hypothesis_id"],
            "hypothesis_text": hyp_text,
            "candidate_pool_top20": top20,
            "final_top5": top5,
            "context_text": context,
            "full_nda_tokens_cl100k": nda_tokens,
        })
        gold_cases.append({
            "case_id": case["case_id"],
            "gold_label": ann["choice"],
            "gold_span_indices": ann["spans"],
        })
        label_counts[ann["choice"]] += 1
        if (position + 1) % 100 == 0:
            print(f"local retrieval {position + 1}/2091", flush=True)

    c1, c2 = quantile(full_nda_tokens, 1 / 3), quantile(full_nda_tokens, 2 / 3)
    for case in model_cases:
        t = case["full_nda_tokens_cl100k"]
        case["predeclared_length_band"] = "short" if t <= c1 else "medium" if t <= c2 else "long"

    config = {
        "experiment_id": "E20_final_rag_test",
        "population": {"split": "test", "documents": 123, "hypotheses": 17, "cases": 2091},
        "retrieval": RETRIEVAL,
        "classifier": {
            "model": MODEL,
            "provider": PROVIDER,
            "temperature": 0.0,
            "system_prompt_path": str(SYSTEM_PROMPT.relative_to(REPO)),
            "system_prompt_sha1": P0_SHA1,
            "user_template": USER_TEMPLATE,
            "context_join": JOIN,
            "timeout_seconds": 60,
            "retry_limit": 1,
            "max_concurrency": 5,
        },
        "evaluation": {
            "parser": "evaluation.structured_output.parse_structured_output",
            "runtime_validator": "pipeline.evidence_validator.validate_evidence",
            "evidence_evaluator": "v2 character-overlap, tau=0.5",
            "length_bands": {
                "method": "E13-compatible case-weighted full-NDA cl100k tercile cutoffs, frozen before predictions",
                "short_le": c1,
                "medium_le": c2,
            },
        },
        "execution": {
            "expected_successful_hosted_calls": 2091,
            "maximum_request_attempts_if_every_case_retries": 4182,
            "hard_incremental_run_budget_usd": 6.00,
            "provider_balance_reserve_usd": 0.75,
            "minimum_starting_balance_usd": 6.75,
            "incremental_jsonl": True,
            "resume_without_rerunning_successes": True,
            "quality_metrics_hidden_until_population_complete": True,
        },
    }
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    config["canonical_config_sha256_excluding_this_field"] = config_hash

    model_artifact = {
        "manifest_id": "E20_TEST_ALL_2091_RAG_retrieval_v1",
        "note": "Model-facing retrieval artifact. Contains no gold labels or gold evidence.",
        "test_json_sha256": TEST_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "config_sha256": config_hash,
        "total_cases": len(model_cases),
        "cases": model_cases,
    }
    gold_artifact = {
        "manifest_id": "E20_TEST_ALL_2091_GOLD_SCORER_ONLY",
        "note": "Scorer-side only. Never pass any field from this artifact to the classifier.",
        "test_json_sha256": TEST_SHA256,
        "total_cases": len(gold_cases),
        "label_counts": label_counts,
        "cases": gold_cases,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    (MAN / "TEST_ALL_2091_RAG_retrieval_v1.json").write_text(json.dumps(model_artifact, indent=1) + "\n")
    (MAN / "TEST_ALL_2091_GOLD_SCORER_ONLY.json").write_text(json.dumps(gold_artifact, indent=1) + "\n")

    # Calibrate local cl100k request counts against actual E13 top-5 RAG input tokens.
    e13_art = json.loads((REPO / "experiments/E13_gpt_context_architecture/DEV_ARCH_v1_RETRIEVED_retrieval_v1.json").read_text())
    e13_raw = [json.loads(line) for line in (REPO / "experiments/E13_gpt_context_architecture/results/run_E13_gpt_rag_cases.jsonl").read_text().splitlines()]
    e13_by = {c["case_id"]: c for c in e13_art["cases"]}
    e13_local = []
    for row in e13_raw:
        c = e13_by[row["case_id"]]
        msg = USER_TEMPLATE.format(hypothesis_text=c["hypothesis_text"], context_text=JOIN.join(c["ranked_chunk_text"]))
        e13_local.append(len(enc.encode(system)) + len(enc.encode(msg)))
    calibration = sum(r["input_tokens"] for r in e13_raw) / sum(e13_local)
    local_inputs = []
    for case in model_cases:
        msg = USER_TEMPLATE.format(hypothesis_text=case["hypothesis_text"], context_text=case["context_text"])
        local_inputs.append(len(enc.encode(system)) + len(enc.encode(msg)))
    calibrated_inputs = [x * calibration for x in local_inputs]
    e13_outputs = [r["output_tokens"] for r in e13_raw]
    output_mean = statistics.mean(e13_outputs)
    output_p90 = quantile(e13_outputs, 0.90)
    expected_cost = sum(calibrated_inputs) * 0.25 / 1_000_000 + len(model_cases) * output_mean * 2.0 / 1_000_000
    conservative_cost = len(model_cases) * (
        quantile(calibrated_inputs, 0.90) * 0.25 / 1_000_000 + output_p90 * 2.0 / 1_000_000
    )
    e13_latencies = [r["generation_latency_ms"] for r in e13_raw]
    forecast = {
        "checks": checks,
        "label_counts_scorer_side_only": label_counts,
        "config_sha256": config_hash,
        "artifact_hashes": {
            "config_json_sha256": hash_file(OUT / "config.json"),
            "model_facing_manifest_sha256": hash_file(MAN / "TEST_ALL_2091_RAG_retrieval_v1.json"),
            "gold_scorer_manifest_sha256": hash_file(MAN / "TEST_ALL_2091_GOLD_SCORER_ONLY.json"),
        },
        "length_bands": {
            "short_le_full_nda_tokens": c1,
            "medium_le_full_nda_tokens": c2,
            "counts": {band: sum(c["predeclared_length_band"] == band for c in model_cases) for band in ("short", "medium", "long")},
        },
        "request_input_tokens": {
            "cl100k_uncalibrated": describe(local_inputs),
            "calibration_ratio_from_E13_actual_rag": calibration,
            "calibrated": describe(calibrated_inputs),
            "calibrated_total": sum(calibrated_inputs),
        },
        "output_token_basis_E13_actual_rag": {"n": len(e13_outputs), "mean": output_mean, "p90": output_p90, "max": max(e13_outputs)},
        "cost_forecast_usd": {
            "prices": {"input_per_million": 0.25, "output_per_million": 2.0},
            "expected": expected_cost,
            "conservative_all_cases_at_p90_input_and_output": conservative_cost,
            "hard_incremental_run_budget": 6.00,
            "reserve": 0.75,
        },
        "runtime_forecast": {
            "basis": "E13 actual top-5 RAG latency, same model/prompt/context architecture",
            "mean_call_seconds": statistics.mean(e13_latencies) / 1000,
            "p90_call_seconds": quantile(e13_latencies, 0.90) / 1000,
            "expected_wall_minutes_at_concurrency_5": len(model_cases) * statistics.mean(e13_latencies) / 1000 / 5 / 60,
            "p90_wall_minutes_at_concurrency_5": len(model_cases) * quantile(e13_latencies, 0.90) / 1000 / 5 / 60,
        },
    }
    (RES / "pre_run_forecast.json").write_text(json.dumps(forecast, indent=2) + "\n")
    print(json.dumps(forecast, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
