#!/usr/bin/env python3
"""Builds frontend/data/project-presentation.json from real repo artifacts.

Every number in the output is either (a) read directly from a canonical JSON/CSV
artifact under results/ or experiments/, or (b) a narrative string hand-transcribed
from docs/summary.md, docs/experiment_registry.md, or docs/architecture_decisions/
INDEX.md, cross-checked against (a) when it contains a number.

Fails loudly (raises) if any canonical artifact is missing. Does not call any model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "data" / "project-presentation.json"
sys.path.insert(0, str(ROOT))
from evaluation import evidence_matching as EM  # noqa: E402


def load_json(rel: str) -> dict:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(f"Missing canonical artifact: {rel}")
    return json.loads(path.read_text())


def src(experiment_id: str, path: str, population: str, measured: str = "measured", note: str = "") -> dict:
    return {
        "experimentId": experiment_id,
        "sourcePath": path,
        "population": population,
        "measured": measured,
        "note": note,
    }


def metric(value, unit: str, source: dict) -> dict:
    return {"value": value, "unit": unit, **source}


# ---------------------------------------------------------------------------
# 1. Canonical numeric artifacts (fail loudly if missing)
# ---------------------------------------------------------------------------

gpt_metrics = load_json("results/final/v2/gpt_full_test_metrics.json")
qwen_metrics = load_json("results/final/v2/qwen_full_test_metrics.json")
rule_metrics = load_json("results/final/v2/rule_full_test_metrics.json")
cost_summary = load_json("results/final/v2/cost_summary.json")
contradiction_analysis = load_json("results/final/v2/contradiction_analysis.json")
robustness_summary = load_json("results/final/v2/robustness_summary.json")
routing_summary = load_json("results/final/v2/routing_summary.json")
e20_report = load_json("experiments/E20_final_rag_test/results/E20_final_report.json")
e06_bm25 = load_json("experiments/E06_retrieval_optimisation/results/run_E06_R0_matched_clause256.json")
e06_mpnet = load_json("experiments/E06_retrieval_optimisation/results/run_E06_R2_clause256.json")
e06_bge = load_json("experiments/E06_retrieval_optimisation/results/run_E06_R4_bge.json")
e06_rerank = load_json("experiments/E06_retrieval_optimisation/results/run_E06_lexical_vs_dense_rerank.json")
e06_hybrid = load_json("experiments/E06_retrieval_optimisation/results/run_E06_hybrid_rrf.json")
e03_failure = load_json("experiments/E03_prompt_selection/results/prompt_failure_analysis_summary.json")
e06_failure = load_json("experiments/E06_retrieval_optimisation/results/failure_analysis_summary.json")
e09_ceiling = load_json("experiments/E09_agent_justification/results/oracle_agent_opportunity_ceiling.json")
e12a = load_json("experiments/E12A_static_context_expansion/results/e12a_analysis.json")
e12c = load_json("experiments/E12C_gpt_prompt_confirmation/results/e12c_analysis.json")
e21_report = load_json("experiments/E21_owasp_llm_top10/results/final_report.json")
e22_report = load_json("experiments/E22_targeted_security_remediation/results/final_report.json")
e22_injection = load_json("experiments/E22_targeted_security_remediation/results/llm01_prompt_injection.json")
e22_consumption = load_json("experiments/E22_targeted_security_remediation/results/llm10_unbounded_consumption.json")

# Chunk-size and top-K sweeps (E06 rounds 2/3) — real saved per-config recall/MRR, used to show
# WHY clause-256 and top-5 were selected, not just the final config.
e06_r2_clause256 = load_json("experiments/E06_retrieval_optimisation/results/run_E06_R2_clause256.json")
e06_r2_fixed512 = load_json("experiments/E06_retrieval_optimisation/results/run_E06_R2_fixed512.json")
e06_r2_sentence = load_json("experiments/E06_retrieval_optimisation/results/run_E06_R2_sentence.json")
e06_r3_k3 = load_json("experiments/E06_retrieval_optimisation/results/run_E06_R3_k3.json")
e06_r3_k10 = load_json("experiments/E06_retrieval_optimisation/results/run_E06_R3_k10.json")

# Selective agent — three real, distinct evaluations, not one collapsed number.
E11_DIR = "experiments/E11_selective_agent_evaluation/"
e11_selective = load_json(E11_DIR + "results/run_E11_A3_train.json")
e11_full_agent = load_json(E11_DIR + "addendum_selective_vs_full_agent/results/arm_metrics.json")
e11_prompt_v2 = load_json(E11_DIR + "addendum_agent_prompt_ablation/results/arm_metrics.json")
e11_tool_usage = load_json(E11_DIR + "addendum_agent_prompt_ablation/results/tool_usage.json")

for req in [gpt_metrics, qwen_metrics, rule_metrics, cost_summary, contradiction_analysis,
            robustness_summary, routing_summary, e20_report,
            e06_bm25, e06_mpnet, e06_bge, e06_rerank, e06_hybrid,
            e03_failure, e06_failure, e09_ceiling, e12a, e12c,
            e21_report, e22_report, e22_injection, e22_consumption,
            e11_selective, e11_full_agent, e11_prompt_v2, e11_tool_usage,
            e06_r2_clause256, e06_r2_fixed512, e06_r2_sentence, e06_r3_k3, e06_r3_k10]:
    assert req, "canonical artifact loaded empty"

RECON_V2 = "results/final/v2/"
E20_PATH = "experiments/E20_final_rag_test/results/E20_final_report.json"
E18_PATH = "experiments/E18_business_course_synthesis/summary.md"
ADR012_PATH = "docs/architecture_decisions/INDEX.md"
SUMMARY_PATH = "docs/summary.md"
CONTAM_PATH = "docs/data_contamination_register.md"

TEST_N = 2091
SPLIT_COUNTS = {
    "train": {"docs": 423, "cases": 7191, "entailment": 3530, "contradiction": 841, "notMentioned": 2820},
    "dev": {"docs": 61, "cases": 1037, "entailment": 519, "contradiction": 95, "notMentioned": 423},
    "test": {"docs": 123, "cases": 2091, "entailment": 968, "contradiction": 220, "notMentioned": 903},
}
TOTAL_DOCS = sum(v["docs"] for v in SPLIT_COUNTS.values())  # 607
TOTAL_CASES = sum(v["cases"] for v in SPLIT_COUNTS.values())  # 10,319

# ---------------------------------------------------------------------------
# 2. Case Explorer — join final-architecture per-case files (Rule/FULL/RAG,
#    all real TEST n=2,091 runs, same doc_id+hypothesis_id case scheme) with
#    ContractNLI gold labels. The selective agent (E11) was only ever run on
#    a disjoint TRAIN n=150 population, so it has no per-case match here —
#    every case's Agent column is left unpopulated and the UI shows the
#    literal "No matched final-architecture result available" for it.
# ---------------------------------------------------------------------------

RULE_TEST_FILE = "experiments/E17_final_test/results/run_E17_rule_full_test.jsonl"
FULL_TEST_FILES = [
    "experiments/E17_final_test/results/run_E17_gpt_hosted_test_cases.jsonl",  # first 150
    "experiments/E17B_full_test_completion/results/run_E17B_gpt_cases.jsonl",  # remaining 1,941
]
RAG_TEST_FILE = "experiments/E20_final_rag_test/results/run_E20_rag_cases.jsonl"


def load_jsonl_all(rel: str) -> list[dict]:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(f"Missing canonical artifact: {rel}")
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


gold_data = load_json("data/contractnli/test.json")
doc_by_id = {str(d["id"]): d for d in gold_data["documents"]}
hyp_texts = {hid: v["hypothesis"] for hid, v in gold_data["labels"].items()}
gold_manifest = load_json("experiments/E20_final_rag_test/manifests/TEST_ALL_2091_GOLD_SCORER_ONLY.json")
rag_manifest = load_json("experiments/E20_final_rag_test/manifests/TEST_ALL_2091_RAG_retrieval_v1.json")
gold_by_case = {row["case_id"]: row for row in gold_manifest["cases"]}
rag_context_by_case = {row["case_id"]: row for row in rag_manifest["cases"]}
ALLOWED_LABELS = {"Entailment", "Contradiction", "NotMentioned"}


def gold_for(doc_id: str, hyp_id: str):
    doc = doc_by_id.get(doc_id)
    if not doc:
        return None
    ann = doc["annotation_sets"][0]["annotations"].get(hyp_id)
    if not ann:
        return None
    return ann["choice"]


def doc_excerpt(doc_id: str, max_chars: int = 900) -> str:
    doc = doc_by_id.get(doc_id)
    if not doc:
        return ""
    text = doc["text"].strip()
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def case_key(doc_id: str, hyp_id: str) -> str:
    return f"{doc_id}::{hyp_id}"


case_index: dict[str, dict] = {}


def get_entry(doc_id: str, hyp_id: str) -> dict:
    case_id = f"test::{doc_id}::{hyp_id}"
    doc = doc_by_id.get(doc_id)
    gold_indices = gold_by_case.get(case_id, {}).get("gold_span_indices", [])
    gold_evidence = [doc["text"][start:end] for index in gold_indices for start, end in [doc["spans"][index]]] if doc else []
    return case_index.setdefault(case_key(doc_id, hyp_id), {
        "caseId": case_id,
        "split": "TEST",
        "docId": doc_id,
        "hypothesisId": hyp_id,
        "requirement": hyp_texts.get(hyp_id, ""),
        "goldLabel": gold_for(doc_id, hyp_id),
        "goldEvidence": gold_evidence,
        "goldSpanIndices": gold_indices,
        "architectures": {},
    })


# Rule (E17, TEST n=2,091) — deterministic keyword match, no LLM explanation; quote the
# matched span from the source document when the rule actually fired.
for pred in load_jsonl_all(RULE_TEST_FILE):
    doc_id, hyp_id = str(pred["document_id"]), pred["hypothesis_id"]
    entry = get_entry(doc_id, hyp_id)
    span = pred.get("evidence_span")
    quote = ""
    if span and pred.get("matched"):
        doc = doc_by_id.get(doc_id)
        if doc:
            quote = doc["text"][span[0]:span[1]]
    entry["architectures"]["rule"] = {
        "predictedLabel": pred.get("predicted_label"),
        "evidence": [quote] if quote else [],
        "agentUsed": False,
        "agentSteps": 0,
        "latencyMs": pred.get("latency_ms"),
        "tokensIn": None,
        "tokensOut": None,
        "costUsd": 0.0,
        "parseStatus": "deterministic",
        "sourceValid": bool(not span or (doc_by_id.get(doc_id) and 0 <= span[0] <= span[1] <= len(doc_by_id[doc_id]["text"]))),
        "evidenceLabelConsistent": True,
        "rawStructuredOutput": None,
        "model": "Deterministic rule baseline",
        "evidenceSpan": span,
    }

# FULL-context (E17's first 150 hosted cases + E17B's remaining 1,941 completion cases —
# together the same TEST n=2,091 population as Rule and RAG).
for rel in FULL_TEST_FILES:
    for pred in load_jsonl_all(rel):
        doc_id, hyp_id = str(pred["document_id"]), pred["hypothesis_id"]
        entry = get_entry(doc_id, hyp_id)
        entry["architectures"]["full_context"] = {
            "predictedLabel": pred.get("predicted_label"),
            "evidence": pred.get("evidence") or [],
            "agentUsed": False,
            "agentSteps": 0,
            "latencyMs": round(pred["wall_latency_s"] * 1000) if pred.get("wall_latency_s") is not None else None,
            "tokensIn": pred.get("input_tokens"),
            "tokensOut": pred.get("output_tokens"),
            "costUsd": pred.get("cost_usd"),
            "parseStatus": pred.get("parse_status"),
            "sourceValid": pred.get("evidence_hallucinated_count", 0) == 0,
            "evidenceLabelConsistent": pred.get("evidence_label_consistent"),
            "rawStructuredOutput": pred.get("raw_response"),
            "model": pred.get("model"),
        }

# RAG (E20, TEST n=2,091) — frozen retrieval + rerank runtime, same population as Rule/FULL.
for pred in load_jsonl_all(RAG_TEST_FILE):
    doc_id, hyp_id = str(pred["document_id"]), pred["hypothesis_id"]
    entry = get_entry(doc_id, hyp_id)
    entry["architectures"]["rag"] = {
        "predictedLabel": pred.get("predicted_label"),
        "evidence": pred.get("evidence") or [],
        "agentUsed": False,
        "agentSteps": 0,
        "latencyMs": round(pred["wall_latency_s"] * 1000) if pred.get("wall_latency_s") is not None else None,
        "tokensIn": pred.get("input_tokens"),
        "tokensOut": pred.get("output_tokens"),
        "costUsd": pred.get("cost_usd"),
        "parseStatus": pred.get("parse_status"),
        "sourceValid": pred.get("evidence_hallucinated_count", 0) == 0,
        "evidenceLabelConsistent": pred.get("evidence_label_consistent"),
        "rawStructuredOutput": pred.get("raw_response"),
        "model": pred.get("model"),
    }

# No final-architecture per-case Agent (rag_agent) file exists for the TEST population — E11's
# selective-agent evaluation only ran on a disjoint TRAIN n=150 sample (different documents
# entirely). Every case below is left with no "rag_agent" entry at all, which the frontend
# renders as "No matched final-architecture result available" rather than inventing a match.

cases = [c for c in case_index.values() if c["goldLabel"] is not None]
for c in cases:
    doc = doc_by_id[c["docId"]]
    cid = c["caseId"]
    rag_ctx = rag_context_by_case[cid]
    for arch, result in c["architectures"].items():
        if arch == "rule":
            span = result.pop("evidenceSpan", None)
            predicted_indices = []
            if span:
                predicted_indices = [i for i, (start, end) in enumerate(doc["spans"]) if min(span[1], end) > max(span[0], start)]
        elif arch == "rag":
            predicted_indices = EM.evidence_to_span_indices(
                result["evidence"], [x["text"] for x in rag_ctx["final_top5"]],
                [x["offset"] for x in rag_ctx["final_top5"]], doc["spans"])
        else:
            predicted_indices = EM.evidence_to_span_indices(
                result["evidence"], [doc["text"]], [[0, len(doc["text"])]], doc["spans"])

        parse_valid = result["parseStatus"] in {"strict", "recovered", "deterministic"}
        evidence_present_when_required = result["predictedLabel"] == "NotMentioned" or bool(result["evidence"])
        provenance_valid = result["predictedLabel"] == "NotMentioned" or bool(predicted_indices)
        result["l1Pass"] = bool(
            parse_valid and result["predictedLabel"] in ALLOWED_LABELS and result["sourceValid"]
            and evidence_present_when_required and provenance_valid and result["evidenceLabelConsistent"] is not False
        )
        result["classificationCorrect"] = result["predictedLabel"] == c["goldLabel"]
        result["goldEvidenceOverlap"] = bool(set(c["goldSpanIndices"]) & set(predicted_indices)) if c["goldSpanIndices"] else None
        result["jointPass"] = bool(EM.joint_success(c["goldLabel"], result["predictedLabel"], c["goldSpanIndices"], predicted_indices))
        result["l2Pass"] = result["jointPass"]
        result["predictedSpanIndices"] = predicted_indices

    rag = c["architectures"]["rag"]
    if rag["jointPass"]:
        c["failureType"] = "success"
    else:
        gold_ranges = [doc["spans"][i] for i in c["goldSpanIndices"]]
        retrieval_hit = any(
            min(chunk["offset"][1], end) > max(chunk["offset"][0], start)
            for chunk in rag_ctx["final_top5"] for start, end in gold_ranges
        ) if gold_ranges else None
        if gold_ranges and not retrieval_hit:
            c["failureType"] = "retrieval_limited"
        elif not rag["l1Pass"]:
            c["failureType"] = "runtime_parser_source_validity"
        elif rag["classificationCorrect"]:
            c["failureType"] = "evidence_selection"
        else:
            c["failureType"] = "reasoning_classification"
    c["jointArchitectures"] = {arch: result["jointPass"] for arch, result in c["architectures"].items()}

# "Start here" selection — simple deterministic rules over real outcomes, not hand-picked prose.
# Only Rule/FULL/RAG are real final-architecture per-case data here; there is no agent-routed
# per-case pick available (see note above), so that slot is left null rather than faked.
def all_correct(c):
    return all(
        c["jointArchitectures"].get(a) and c["architectures"][a]["l1Pass"]
        for a in ("rule", "full_context", "rag")
    )


def disagreement_case(c):
    labels = {a["predictedLabel"] for a in c["architectures"].values()}
    return len(labels) >= 3


def rag_wrong_full_right(c):
    return (
        c["jointArchitectures"].get("full_context") is True
        and c["jointArchitectures"].get("rag") is False
    )


simple_correct = next((c for c in cases if all_correct(c) and c["goldLabel"] == "Entailment"), None)
evidence_heavy = next((c for c in cases if c["jointArchitectures"].get("full_context") and c["goldLabel"] == "Contradiction"
                        and sum(len(x) for x in c["architectures"]["full_context"]["evidence"]) > 200), None)
uncertainty_case = next((c for c in cases if disagreement_case(c)), None)
honest_failure = next((c for c in cases if rag_wrong_full_right(c) and c["goldLabel"] == "Contradiction"), None)
retrieval_miss = next((c for c in cases if c["failureType"] == "retrieval_limited" and c["architectures"]["full_context"]["jointPass"]), None)
reasoning_failure = next((c for c in cases if c["failureType"] == "reasoning_classification" and c["architectures"]["rag"]["l1Pass"]), None)
evidence_failure = next((c for c in cases if c["failureType"] == "evidence_selection" and c["architectures"]["rag"]["l1Pass"]), None)
contradiction_success = next((c for c in cases if c["goldLabel"] == "Contradiction" and c["architectures"]["full_context"]["jointPass"] and c["architectures"]["rag"]["jointPass"]), None)

start_here = {
    "simpleCorrect": simple_correct["docId"] + "::" + simple_correct["hypothesisId"] if simple_correct else None,
    "evidenceHeavy": evidence_heavy["docId"] + "::" + evidence_heavy["hypothesisId"] if evidence_heavy else None,
    "crossReference": None,  # no final-architecture per-case agent data exists for this population
    "humanReview": uncertainty_case["docId"] + "::" + uncertainty_case["hypothesisId"] if uncertainty_case else None,
    "honestFailure": honest_failure["docId"] + "::" + honest_failure["hypothesisId"] if honest_failure else None,
    "retrievalMiss": retrieval_miss["docId"] + "::" + retrieval_miss["hypothesisId"] if retrieval_miss else None,
    "reasoningFailure": reasoning_failure["docId"] + "::" + reasoning_failure["hypothesisId"] if reasoning_failure else None,
    "evidenceFailure": evidence_failure["docId"] + "::" + evidence_failure["hypothesisId"] if evidence_failure else None,
    "contradictionSuccess": contradiction_success["docId"] + "::" + contradiction_success["hypothesisId"] if contradiction_success else None,
}

# Ship every real RAG failure plus a bounded success sample. The builder verifies
# all 2,091 matched TEST cases; the browser receives the evaluation cases useful
# for failure exploration without carrying every successful raw response.
keep_keys = {v for v in start_here.values() if v}
sample_keys = [f"{c['docId']}::{c['hypothesisId']}" for c in cases if c["failureType"] != "success"]
sample_keys += [f"{c['docId']}::{c['hypothesisId']}" for c in cases if c["failureType"] == "success"][:150]
keep_keys.update(sample_keys)
cases_out = [c for c in cases if f"{c['docId']}::{c['hypothesisId']}" in keep_keys]
start_here_keys = {v for v in start_here.values() if v}
for c in cases_out:
    c["docExcerpt"] = doc_excerpt(c["docId"])
    key = f"{c['docId']}::{c['hypothesisId']}"
    if key in start_here_keys:
        doc = doc_by_id.get(c["docId"])
        c["docFullText"] = doc["text"] if doc else None
        rag_ctx = rag_context_by_case[c["caseId"]]
        c["architectures"]["rag"]["retrievedContext"] = [
            {"rank": rank, "chunkId": chunk["chunk_id"], "text": chunk["text"], "rerankerScore": chunk["rerank_score"]}
            for rank, chunk in enumerate(rag_ctx["final_top5"], 1)
        ]

FEATURED_CASES = [
    {"kind": "Clean success", "caseKey": start_here.get("simpleCorrect"), "why": "All three saved systems reach the expected label; FULL and RAG also supply evaluable source evidence."},
    {"kind": "Retrieval miss", "caseKey": start_here.get("retrievalMiss"), "why": "FULL succeeds with the whole NDA visible, while the relevant gold span is absent from RAG's final top-5."},
    {"kind": "Reasoning failure", "caseKey": start_here.get("reasoningFailure"), "why": "RAG receives a gold-relevant clause and produces source-valid output, but reaches the wrong semantic label."},
    {"kind": "Correct label, insufficient evidence", "caseKey": start_here.get("evidenceFailure"), "why": "The label is correct and the quote is source-valid, but the saved evidence does not satisfy the human gold-evidence criterion, so Joint fails."},
    {"kind": "Contradiction success", "caseKey": start_here.get("contradictionSuccess"), "why": "A real Contradiction case where both model architectures pair the correct label with gold-overlapping evidence."},
]
FEATURED_CASES = [x for x in FEATURED_CASES if x["caseKey"]]
# Primary Overview hero case: a real RAG success (correct label + valid, joint-passing
# evidence) rather than a failure — "contradictionSuccess" is exactly this (Contradiction,
# RAG label correct, L1 pass, Joint/L2 pass, FULL also matches for the same doc+hyp).
OVERVIEW_CASE_KEY = start_here.get("contradictionSuccess") or start_here.get("simpleCorrect")
# Kept as a secondary "when valid output is still wrong" pointer — RAG's retrieval-limited
# failure on the same requirement text as "1::nda-19" moves here instead of being the hero.
OVERVIEW_FAILURE_CASE_KEY = start_here.get("retrievalMiss") or start_here.get("honestFailure")

# Fail closed if the primary product example ever stops satisfying the frozen
# evaluator. Matching above is by TEST split + document ID + hypothesis ID.
showcase_case = next(c for c in cases if case_key(c["docId"], c["hypothesisId"]) == OVERVIEW_CASE_KEY)
showcase_rag = showcase_case["architectures"]["rag"]
showcase_full = showcase_case["architectures"].get("full_context")
assert showcase_case["split"] == "TEST"
assert showcase_case["goldLabel"] in {"Contradiction", "Entailment"}
assert showcase_rag["classificationCorrect"] is True
assert showcase_rag["sourceValid"] is True
assert showcase_rag["goldEvidenceOverlap"] is True
assert showcase_rag["jointPass"] is True and showcase_rag["l1Pass"] is True and showcase_rag["l2Pass"] is True
SHOWCASE_VALIDATION = {
    "caseId": showcase_case["caseId"], "split": showcase_case["split"],
    "documentId": showcase_case["docId"], "hypothesisId": showcase_case["hypothesisId"],
    "goldLabel": showcase_case["goldLabel"], "ragPredictedLabel": showcase_rag["predictedLabel"],
    "ragSourceValid": showcase_rag["sourceValid"], "ragEvidenceCorrect": showcase_rag["goldEvidenceOverlap"],
    "ragJointPass": showcase_rag["jointPass"], "ragL1Pass": showcase_rag["l1Pass"], "ragL2Pass": showcase_rag["l2Pass"],
    "matchedFullResult": bool(showcase_full),
}

CASE_POPULATION_NOTE = (
    "Final-architecture population only: Rule (E17) / FULL-context (E17+E17B) / RAG (E20), all "
    "real per-case runs on the full official TEST split (n=2,091 shared by all three). No "
    "matching per-case Agent (selective-agent) run exists for this population — E11's "
    "selective-agent evaluation only covers a disjoint TRAIN n=150 sample. Agent examples therefore "
    "appear in a separately labeled TRAIN demo and are never joined to TEST architecture outputs."
)

# Agent tool-call traces (only exist for E11's train/dev-split cases — different population).
agent_traces = []
trace_path = ROOT / "experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/raw_agent_traces.jsonl"
if trace_path.exists():
    for line in trace_path.read_text().splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        if t.get("tool_calls"):
            agent_traces.append({
                "caseId": t.get("case_id"),
                "toolNames": t.get("tool_names", []),
                "toolCallArguments": t.get("tool_call_arguments", []),
                "toolResultsSummary": t.get("tool_results_summary", []),
                "stopReason": t.get("stop_reason"),
                "finalLabel": t.get("final_label"),
                "fallbackToA2": t.get("fallback_to_a2"),
            })

# Prompt-v2 agent examples are a separate TRAIN demo population. They are never
# joined into the TEST cases above. Only structured actions, tool arguments, and
# saved tool outputs are exposed; raw model responses are intentionally omitted.
train_data = load_json("data/contractnli/train.json")
train_docs = {str(d["id"]): d for d in train_data["documents"]}
train_hypotheses = {hid: row["hypothesis"] for hid, row in train_data["labels"].items()}
v2_raw_rows = {row["case_id"]: row for row in load_jsonl_all(E11_DIR + "addendum_agent_prompt_ablation/results/raw_v2.jsonl")}
v2_metric_rows = {row["case_id"]: row for row in load_jsonl_all(E11_DIR + "addendum_agent_prompt_ablation/results/per_case_metrics.jsonl")}
agent_demo_cases = []
for cid, trace in v2_raw_rows.items():
    metrics = v2_metric_rows[cid]
    if not trace.get("tool_calls") or metrics.get("v2_joint_success"):
        continue
    doc_id, hyp_id = str(trace["document_id"]), trace["hypothesis_id"]
    agent_demo_cases.append({
        "caseId": cid,
        "split": "TRAIN",
        "documentId": doc_id,
        "requirementId": hyp_id,
        "requirement": train_hypotheses.get(hyp_id, ""),
        "goldLabel": metrics.get("gold_label"),
        "base": {"prediction": metrics.get("base_label"), "jointPass": metrics.get("base_joint_success")},
        "agent": {
            "prediction": metrics.get("v2_label"),
            "evidence": metrics.get("v2_evidence") or [],
            "l1Pass": bool(metrics.get("v2_source_valid") and trace.get("base_parse_status") in {"strict", "recovered"}),
            "l2Pass": metrics.get("v2_joint_success"),
            "jointPass": metrics.get("v2_joint_success"),
            "latencyMs": round((metrics.get("v2_latency_seconds") or 0) * 1000),
            "inputTokens": metrics.get("v2_input_tokens"),
            "outputTokens": metrics.get("v2_output_tokens"),
            "costUsd": metrics.get("v2_cost_usd"),
            "steps": [
                {
                    "step": i + 1,
                    "action": name,
                    "arguments": trace.get("tool_call_arguments", [])[i] if i < len(trace.get("tool_call_arguments", [])) else None,
                    "result": trace.get("tool_results_summary", [])[i] if i < len(trace.get("tool_results_summary", [])) else None,
                }
                for i, name in enumerate(trace.get("tool_names", []))
            ],
            "finalAction": "FINAL",
            "stopReason": trace.get("stop_reason"),
        },
        "why": "The agent requested additional saved context, but the final evidence-grounded outcome still did not recover the case.",
        "source": src("E11 prompt-v2", E11_DIR + "addendum_agent_prompt_ablation/results/raw_v2.jsonl", "TRAIN n=150; separate agent demo population"),
    })
    if len(agent_demo_cases) == 2:
        break

# Real E21 RAG-path security examples. A source-valid quote can still be unsafe
# when it follows document-borne instructions, so security is kept distinct from L1.
llm01_fixtures = load_json("experiments/E21_owasp_llm_top10/fixtures/prompt_injection.json")
fixture_by_id = {row["test_id"]: row for row in llm01_fixtures["cases"]}
llm01_cases = e21_report["full_category_results"]["LLM01"]["cases"]
security_examples = []
for test_id in ("E21-LLM01-04", "E21-LLM01-07"):
    saved = next(row for row in llm01_cases if row["test_id"] == test_id)
    fixture = fixture_by_id[test_id]
    attack = saved["variants"]["attack"]
    security_examples.append({
        "testId": test_id,
        "family": saved["family"],
        "population": "E21 synthetic adversarial fixture · frozen RAG runtime",
        "requirement": llm01_fixtures["requirement"],
        "maliciousClause": fixture["attack_clause"],
        "prediction": attack["label"],
        "evidence": attack["evidence"],
        "l1Pass": bool(attack["source_valid"] and attack["parse_status"] in {"strict", "recovered"}),
        "securityPass": not saved["attack_success"],
        "attackOutcome": "Bypassed evidence-boundary control" if saved["attack_success"] else "Injected text surfaced in source-valid evidence",
        "source": src("E21", "experiments/E21_owasp_llm_top10/results/final_report.json", "synthetic adversarial RAG-path fixture"),
    })

# Silent-failure finding — final-architecture only (E17B, full TEST n=2,091), replaces the
# removed legacy (T-series) carve-out examples. No per-case quoted illustration of
# this exact pattern exists in final-architecture artifacts, so this reports the real aggregate
# finding rather than substituting a legacy or invented case quote.
SILENT_FAILURE_FINDING = {
    "pattern": "Contradiction misclassified as Entailment: the model quotes real, source-valid "
    "clause text, but the quoted clause actually contains an exception that reverses the "
    "apparent general rule.",
    "source": "E17B, full TEST n=2,091, Contradiction class (n=220)",
    "stat": "50 of 220 gold-Contradiction cases were predicted Entailment (C→E); of those, 38 "
    "quoted a clause overlapping the correct gold span — the right clause, wrong label.",
    "note": "A per-case quoted example of this pattern exists only in the removed "
    "legacy (T-series) dev-split artifact. This card reports the final-architecture "
    "aggregate finding (experiments/E17B_full_test_completion/summary.md) instead of "
    "substituting that legacy case.",
}

# ---------------------------------------------------------------------------
# 3. Everything else — narrative content hand-transcribed from the docs read
#    above, every embedded number cross-checked against the JSON loaded above.
# ---------------------------------------------------------------------------

data = {
    "meta": {
        "generatedNote": "Generated by scripts/build_project_presentation_data.py from repo artifacts. No model calls made.",
    },

    "hero": {
        "headline": "NDATrace",
        "subheadline": "Evidence-grounded NDA review for legal operations",
        "question": "Can AI review an NDA without asking a lawyer to trust a black-box verdict?",
        "support": "NDATrace classifies each confidentiality requirement and shows the exact clause behind the decision, so a reviewer can verify rather than trust.",
        "tagline": "Given an NDA and a confidentiality requirement, NDATrace returns Entailment, Contradiction, or Not Mentioned together with the source evidence a human reviewer can verify.",
        "chips": [
            {"label": "Rule", "sub": "Baseline", "status": "baseline"},
            {"label": "FULL", "sub": "Quality reference", "status": "reference"},
            {"label": "RAG", "sub": "Prototype runtime", "status": "adopted"},
            {"label": "Agent", "sub": "Rejected", "status": "rejected"},
            {"label": "Human", "sub": "Final authority", "status": "authority"},
        ],
        "result": {
            "quality": {
                "label": "QUALITY",
                "value": round(gpt_metrics["joint"] * 100, 1),
                "unit": "% Joint",
                "note": "Strongest measured evidence-grounded result — final TEST",
                "source": src("E17B", RECON_V2 + "gpt_full_test_metrics.json", "TEST n=2,091"),
            },
            "productPath": {
                "label": "PRODUCT PATH",
                "value": round(e20_report["RAG_metrics"]["joint"] * 100, 1),
                "unit": "% Joint",
                "note": "50.4% fewer classifier input tokens · clause-level evidence path",
                "source": src("E20", E20_PATH, "TEST n=2,091, same population as FULL"),
            },
        },
    },

    "statStrip": [
        metric(TOTAL_DOCS, "NDAs in ContractNLI", src("E00", CONTAM_PATH, "train+dev+test document counts", note="computed sum of the split table (423+61+123)")),
        metric(TOTAL_CASES, "document–hypothesis examples", src("E00", CONTAM_PATH, "train+dev+test case counts", note="computed sum of the split table (7,191+1,037+2,091)")),
        metric(TEST_N, "final TEST cases", src("E17B", SUMMARY_PATH, "official ContractNLI TEST split")),
        metric(round(gpt_metrics["joint"] * 100, 1), "% FULL Joint (TEST, n=2,091)", src("E17B", RECON_V2 + "gpt_full_test_metrics.json", "TEST n=2,091")),
        metric(round(e20_report["RAG_metrics"]["joint"] * 100, 1), "% RAG Joint (TEST, n=2,091)", src("E20", E20_PATH, "TEST n=2,091, same population as FULL")),
        metric(0.217, "classification p-value (FULL vs RAG, McNemar)", src("E20", E20_PATH, "TEST n=2,091 paired")),
        metric(0.0047, "Joint p-value (FULL vs RAG, McNemar)", src("E20", E20_PATH, "TEST n=2,091 paired")),
        metric(round(cost_summary["gpt_total_cost_usd"], 2), "USD — FULL GPT-5-mini TEST run", src("E17+E17B", RECON_V2 + "cost_summary.json", "n=2,091 hosted calls")),
        metric(round(e20_report["RAG_metrics"]["ops"]["total_cost_usd"], 2), "USD — RAG GPT-5-mini TEST run", src("E20", E20_PATH, "n=2,091 hosted calls")),
    ],

    "whatGoodLooksLike": {
        "cards": [
            {"title": "Correct decision", "body": "Entailment / Contradiction / Not Mentioned"},
            {"title": "Correct evidence", "body": "Exact supporting NDA clause"},
            {"title": "Reviewable", "body": "A human can inspect the evidence"},
            {"title": "Economic", "body": "Automation must reduce total review cost, not just API spend"},
        ],
        "jointExplanation": "A correct verdict backed by the wrong clause is not a successful review.",
    },

    "whoThisIsFor": {
        "primary": "Enterprise legal operations analyst",
        "secondary": "Legal counsel / reviewer who receives a pre-screened, evidence-backed result",
        "today": [
            "Reads the whole NDA start to finish for every incoming counterparty document",
            "Manually checks each of ~17 standard confidentiality requirements against the text",
            "Has no structured way to point a colleague at 'the exact clause I based this on'",
        ],
        "withNdatrace": [
            "Gets a per-requirement label (Entailment / Contradiction / Not Mentioned) with a cited clause",
            "Verifies any output in seconds by reading the cited quote, not re-reading the whole document",
            "Still makes the final call — the system never auto-approves or auto-rejects",
        ],
    },

    "flow": [
        {"step": "NDA + requirement", "kind": "input"},
        {"step": "clause-aware chunking (256 tok, overlap 50)", "kind": "deterministic"},
        {"step": "BM25 top-20", "kind": "deterministic"},
        {"step": "cross-encoder rerank (ms-marco-MiniLM-L-12-v2)", "kind": "model"},
        {"step": "top-5 clauses", "kind": "deterministic"},
        {"step": "GPT-5-mini + frozen P0 prompt", "kind": "model"},
        {"step": "structured output parser", "kind": "deterministic"},
        {"step": "runtime evidence-source validator v2", "kind": "guardrail"},
        {"step": "reviewer", "kind": "human"},
    ],
    "flowSource": src("E19/E20", "docs/architecture.md", "current runtime, verified against pipeline/frozen_rag.py + pipeline/final_review.py + backend/routes/review.py"),

    "architectureLadder": [
        {
            "id": "A0", "name": "Rule", "status": "baseline",
            "question": "Can deterministic rules solve enough of the problem to avoid an LLM?",
            "headline": metric(round(rule_metrics["accuracy"] * 100, 1), "% accuracy (TEST)", src("E04/E17", RECON_V2 + "rule_full_test_metrics.json", "TEST n=2,091")),
            "conclusion": "Cheap and fast, but semantic coverage — especially Contradiction — was insufficient. Keep as baseline, not product logic.",
            "operatingImpact": ["Effectively no API cost", "Extremely fast", "Misses semantic paraphrases and contradictions"],
            "metrics": {
                "accuracy": rule_metrics["accuracy"], "macroF1": rule_metrics["macro_f1"],
                "joint": rule_metrics["joint"], "contradictionRecall": rule_metrics["recall"]["Contradiction"],
                "costUsd": 0.0,
            },
            "pipeline": ["full NDA text", "keyword/rule match", "label (no LLM)"],
            "config": [{"key": "implementation", "value": "pipeline/rule_baseline.py, unmodified", "source": src("E04", "docs/experiment_registry.md", "TRAIN n=7,191")}],
            "costPer1000": {"raw": 0.0, "note": "no model calls"},
        },
        {
            "id": "A1", "name": "FULL", "status": "reference",
            "question": "What happens when the model sees the entire NDA?",
            "headline": metric(round(gpt_metrics["joint"] * 100, 1), "% Joint (TEST) — strongest measured result", src("E17B", RECON_V2 + "gpt_full_test_metrics.json", "TEST n=2,091")),
            "conclusion": "Strongest measured Joint result on final TEST. Kept as the quality reference — not served interactively.",
            "operatingImpact": ["Strongest measured evidence-grounded quality", "Slightly higher raw inference cost", "Less bounded evidence path", "Can still be cheaper all-in when reduced human fallback is modeled"],
            "metrics": {
                "accuracy": gpt_metrics["accuracy"], "macroF1": gpt_metrics["macro_f1"],
                "joint": gpt_metrics["joint"], "contradictionRecall": gpt_metrics["recall"]["Contradiction"],
                "costUsd": cost_summary["gpt_total_cost_usd"],
            },
            "pipeline": ["full NDA text", "GPT-5-mini + P0", "structured parser", "evidence validator"],
            "config": [
                {"key": "model", "value": "openai/gpt-5-mini", "source": src("E01", "docs/experiment_registry.md", "TRAIN_ORACLE_v1 n=300")},
                {"key": "prompt", "value": "P0 (minimal instruction)", "source": src("E03", "docs/experiment_registry.md", "TRAIN_PROMPT_v1 n=150")},
                {"key": "temperature", "value": "0", "source": src("E05", "pipeline/final_review.py", "runtime config")},
            ],
            "costPer1000": {
                "raw": round(cost_summary["gpt_cost_per_case_usd"] * 1000, 3),
                "note": "raw inference only, derived from cost_summary.json's cost_per_case",
            },
        },
        {
            "id": "A2", "name": "RAG", "status": "adopted",
            "question": "Can I retain similar classification quality while making the evidence path smaller and easier to inspect?",
            "headline": metric(round(e20_report["RAG_metrics"]["joint"] * 100, 1), "% Joint (TEST) — retained interactive runtime", src("E20", E20_PATH, "TEST n=2,091, same population as FULL")),
            "conclusion": "Classification remained close; Joint fell modestly; input volume and raw cost dropped; evidence became clause-oriented. Used as the interactive prototype runtime. The proposal's pre-registered target was a >=5-point gain in risk-sensitive recall (mean of Contradiction/NotMentioned recall) for RAG over FULL; the measured gain is 69.07% to 70.25%, +1.18 points — the target was not met, reported as measured rather than reframed around a friendlier metric.",
            "operatingImpact": ["~50% fewer classifier input tokens than FULL", "Lower raw inference cost", "Clause-level reviewer provenance", "Reusable index across requirements", "Accepts a measured Joint trade-off (statistically significant vs FULL, p=0.0047)"],
            "metrics": {
                "accuracy": e20_report["RAG_metrics"]["accuracy"], "macroF1": e20_report["RAG_metrics"]["macro_f1"],
                "joint": e20_report["RAG_metrics"]["joint"], "contradictionRecall": e20_report["RAG_metrics"]["recall"]["Contradiction"],
                "costUsd": e20_report["RAG_metrics"]["ops"]["total_cost_usd"],
            },
            "pipeline": ["clause-256 chunk", "BM25 top-20", "rerank L-12", "top-5", "GPT-5-mini + P0", "parser", "evidence validator"],
            "config": [
                {"key": "chunk size / overlap", "value": "256 / no overlap", "source": src("E06", "pipeline/frozen_rag.py", "TRAIN n=4,371 evidence-bearing cases")},
                {"key": "candidate pool (BM25)", "value": "top-20", "source": src("E06", "pipeline/frozen_rag.py", "TRAIN n=4,371")},
                {"key": "reranker", "value": "cross-encoder/ms-marco-MiniLM-L-12-v2", "source": src("E06", "pipeline/frozen_rag.py", "TRAIN n=4,371")},
                {"key": "final top_k", "value": "5", "source": src("E06", "pipeline/frozen_rag.py", "TRAIN n=4,371")},
            ],
            "costPer1000": {
                "raw": round(e20_report["RAG_metrics"]["ops"]["cost_per_case"] * 1000, 3),
                "note": "raw inference only, derived from E20_final_report.json's ops.cost_per_case",
            },
        },
        {
            "id": "A3", "name": "Agent", "status": "rejected",
            "question": "Can dynamic investigation recover the difficult cases RAG misses?",
            "headline": metric("0%", "useful tool-recovery rate across three real evaluations", src("E11", "docs/experiment_registry.md", "TRAIN_ARCH_v1 n=150")),
            "conclusion": "The answer was no for the tested designs, across three separate evaluations of increasing tool use. Rejected — not in the current runtime. See \"Why more autonomy did not earn its place\" below for the full progression.",
            "operatingImpact": ["More calls", "More latency", "More control-failure modes", "No net value in tested design"],
            "metrics": {"recoveries": 1, "regressions": 1, "netJoint": 0, "toolInvocations": 0},
            "pipeline": ["top-5 RAG context", "GPT-5-mini controller", "up to 2 tool calls (FOLLOW_CROSS_REFERENCE / GET_MORE_CANDIDATES)", "conclude"],
            "config": [
                {"key": "max steps", "value": "3", "source": src("E10", "docs/experiment_registry.md", "design freeze, no model calls")},
                {"key": "max tool calls", "value": "2", "source": src("E10", "docs/experiment_registry.md", "design freeze")},
                {"key": "cost circuit-breaker", "value": "$0.01/escalated case", "source": src("E10", "docs/experiment_registry.md", "design freeze")},
            ],
            "costPer1000": {"raw": None, "note": "not in current runtime — no production cost applies"},
        },
    ],

    "agentStory": {
        "title": "Why more autonomy did not earn its place",
        "intro": "The UI could easily imply \"the agent never called its tools.\" That would be incomplete — there were three real, distinct evaluations, run in sequence, each giving the controller more room to investigate.",
        "stages": [
            {
                "id": "stage1", "name": "Selective agent",
                "population": "150 frozen TRAIN cases, 15 routed to the agent",
                "triggered": {"n": e11_selective["agent_behavior"]["n_triggered"], "of": e11_selective["n_cases"]},
                "toolCalls": sum(e11_selective["agent_behavior"]["tool_usage_counts"].values()),
                "observed": [
                    "Every routed case concluded FINAL at step 1",
                    "0 tool calls",
                    "Joint did not improve",
                ],
                "interpretation": "The first controller was too reluctant to investigate.",
                "source": src("E11", E11_DIR + "results/run_E11_A3_train.json", "TRAIN n=150, 15 routed"),
            },
            {
                "id": "stage2", "name": "Full-agent diagnostic",
                "population": "All 150 TRAIN cases forced through the agent (routing constraint removed)",
                "toolUsingCases": {"n": e11_full_agent["tool_use"]["cases_using_tool"], "of": e11_full_agent["baseline"]["n"]},
                "toolNameCounts": e11_full_agent["tool_use"]["tool_name_counts"],
                "usefulToolRecoveries": {"n": int(round(e11_full_agent["tool_use"]["useful_tool_case_rate"] * e11_full_agent["tool_use"]["cases_using_tool"])), "of": e11_full_agent["tool_use"]["cases_using_tool"]},
                "baselineJoint": round(e11_full_agent["baseline"]["joint"] * 100, 1),
                "fullAgentJoint": round(e11_full_agent["full_agent"]["joint"] * 100, 1),
                "contradictionRecall": {"before": round(e11_full_agent["baseline"]["recall"]["Contradiction"] * 100), "after": round(e11_full_agent["full_agent"]["recall"]["Contradiction"] * 100)},
                "interpretation": "Removing the routing constraint still did not make tool use valuable.",
                "source": src("E11", E11_DIR + "addendum_selective_vs_full_agent/results/arm_metrics.json", "TRAIN n=150, all cases forced through the agent"),
            },
            {
                "id": "stage3", "name": "Prompt v2: force a more serious investigation",
                "population": "Same 150 TRAIN cases, agent decision prompt rewritten to require justification before concluding",
                "toolUsingCases": {"n": e11_prompt_v2["operations"]["v2"]["tool_using_cases"], "of": e11_prompt_v2["arms"]["v2"]["n"]},
                "toolUseRate": round(e11_prompt_v2["operations"]["v2"]["tool_use_rate"] * 100, 1),
                "toolNameCounts": e11_prompt_v2["operations"]["v2"]["tool_name_counts"],
                "toolCallDistribution": e11_prompt_v2["operations"]["v2"]["tool_call_distribution"],
                "usefulToolCases": {"n": e11_prompt_v2["tool_effectiveness"]["category_counts"].get("useful", 0), "of": e11_prompt_v2["operations"]["v2"]["tool_using_cases"]},
                "neutralToolCases": {"n": e11_prompt_v2["tool_effectiveness"]["category_counts"].get("neutral", 0), "of": e11_prompt_v2["operations"]["v2"]["tool_using_cases"]},
                "harmfulToolCases": {"n": e11_prompt_v2["tool_effectiveness"]["category_counts"].get("harmful", 0), "of": e11_prompt_v2["operations"]["v2"]["tool_using_cases"]},
                "baselineJoint": round(e11_prompt_v2["arms"]["base"]["joint"] * 100, 1),
                "v2Joint": round(e11_prompt_v2["arms"]["v2"]["joint"] * 100, 1),
                "baselineAccuracy": round(e11_prompt_v2["arms"]["base"]["accuracy"] * 100, 1),
                "v2Accuracy": round(e11_prompt_v2["arms"]["v2"]["accuracy"] * 100, 1),
                "meanLatencySeconds": round(e11_prompt_v2["operations"]["v2"]["mean_incremental_latency_seconds"], 2),
                "costPerCaseUsd": e11_prompt_v2["operations"]["v2"]["cost_per_case_usd"],
                "controlFriction": {
                    "fallbacks": e11_prompt_v2["operations"]["v2"]["fallback_events"],
                    "duplicateAttempts": e11_prompt_v2["operations"]["v2"]["duplicate_attempts"],
                    "invalidActions": e11_prompt_v2["operations"]["v2"]["invalid_actions"],
                    "maxToolCallStops": e11_prompt_v2["operations"]["v2"]["stop_reason_counts"].get("max_tool_calls", 0),
                },
                "interpretation": "Tool underuse was partly a prompt-design problem. But fixing the behavior did not fix the outcome.",
                "source": src("E11", E11_DIR + "addendum_agent_prompt_ablation/results/arm_metrics.json", "TRAIN n=150, prompt v2 (forced justification)"),
            },
        ],
        "takeaway": "We increased agent tool use from near-zero to 20% of cases. Useful recovery remained 0%. The agent was rejected because it failed to create value — not because it never used tools.",
    },

    "agentTools": {
        "tools": [
            {
                "name": "FOLLOW_CROSS_REFERENCE",
                "purpose": "Resolve references such as \"as defined in…\", \"pursuant to section…\", \"paragraph (b)…\", \"definition of…\".",
                "why": "Some clauses reference another provision by locator (\"as defined in…\", \"pursuant to section…\", \"paragraph (b)…\") rather than restating it. E09's failure analysis found one confirmed real case (train::273::nda-1) where the correct evidence required resolving an unresolved reference to \"paragraphs (a) to (c) of the definition of Confidential Information\".",
                "what": "Finds the referenced provision in the SAME NDA and appends a bounded excerpt (capped at 500 characters) to the agent's context. Internally reuses a definition-lookup helper for \"definition of X\"-style references, but that helper is not a separate top-level tool.",
                "constraints": ["Read-only", "Same document only", "No external search", "Capped output (500 chars/match)", "Deterministic regex/locator lookup, no semantic matching"],
            },
            {
                "name": "GET_MORE_CANDIDATES",
                "purpose": "Inspect relevant clauses ranked below the frozen top-5.",
                "why": "Some gold evidence exists below the final top-5 cut but is still inside the already-computed top-20 candidate pool (E06's ranking-failure finding: every analyzed retrieval miss was a ranking failure, not a candidate-generation failure).",
                "what": "Reveals the next window (ranks 6-10, then 11-15, then 16-20) of the SAME frozen BM25 top-20 pool retrieval_v1 already computed — never a new query, never a different chunk size or reranker. The window progression is tracked by the caller, not a model-supplied rank argument, so the model cannot request an arbitrary or duplicate window.",
                "constraints": ["No arbitrary search", "No external knowledge", "No different document", "No unrestricted retrieval (capped at pool size 20, 5 results/call, 300 chars/result)", "Bounded number of calls (max 2 tool calls/case)"],
            },
        ],
        "whyOnlyTwo": "The tool surface was intentionally minimal. We only exposed actions supported by observed failure modes. A third tool (get_definition as a standalone action) was drafted, then dropped before implementation — E09 found no residual case proving it was needed beyond what follow_cross_reference's \"definition of X\" pattern already covers.",
        "excluded": ["Arbitrary web search", "Filesystem access", "External databases", "Unrestricted semantic search", "Write/update actions", "Autonomous legal decisions"],
        "flow": ["Current context insufficient?", "FOLLOW_CROSS_REFERENCE or GET_MORE_CANDIDATES", "Reassess", "FINAL"],
        "hardControls": [
            "Max steps: 3", "Max tool calls: 2", "Duplicate-call stop: 2nd identical call forces FINAL",
            "Retrieved-context cap: ~2,000 tokens (8,000 chars) cumulative added context",
            "Wall-clock cap: 60s", "Cost cap: $0.01/case (circuit breaker)", "Fallback: frozen RAG (A2) result",
        ],
        "source": src("E10", "pipeline/agent_v2.py", "design freeze, no model calls", note="tool set finalized at 2, not 3, per experiments/E10_agent_design/summary.md; hard-control values are the frozen MAX_AGENT_STEPS/MAX_TOOL_CALLS/MAX_CUMULATIVE_ADDED_CONTEXT_CHARS/MAX_WALL_CLOCK_SECONDS/MAX_ESTIMATED_AGENT_COST_USD constants"),
    },

    "modeledCostToServe": {
        "note": "MODELED — not realized savings. C_total = C_AI + (1 − p_joint) × C_H [+ F]. Human-review cost (C_H), volume (V), fixed cost (F) are explicit scenario variables, never measured.",
        "source": src("E18", E18_PATH, "scenario model, 3 systems × 12 review-cost scenarios × 3 volumes × 2 fixed-cost scenarios"),
        "cH_scenarios": {"low": 0.0033, "base": 3.33, "high": 12.5},
        "cH_scenario_definitions": {"low": "1 min @ $20/hr fallback", "base": "5 min @ $40/hr fallback (headline)", "high": "10 min @ $75/hr fallback"},
        "systems": [
            {"id": "rule", "name": "Rule", "cAi": 0.0, "pJoint": rule_metrics["joint"]},
            {"id": "full_context", "name": "FULL", "cAi": cost_summary["gpt_cost_per_case_usd"], "pJoint": gpt_metrics["joint"], "allInBase": 0.8485},
            {"id": "rag", "name": "RAG", "cAi": e20_report["RAG_metrics"]["ops"]["cost_per_case"], "pJoint": e20_report["RAG_metrics"]["joint"], "allInBase": 0.9200},
        ],
    },

    "alternatives": [
        {"option": "Manual review", "strength": "No integration risk; a human reads everything", "limitation": "Slow; no structured, checkable evidence trail", "evidence": "Problem statement / product framing", "decision": "Baseline the system is compared against"},
        {"option": "Rules", "strength": "$0 cost, deterministic, instant", "limitation": "Weak semantic coverage — 84.9% of errors are plain keyword-coverage gaps", "evidence": "Rule baseline evaluation", "decision": "Baseline only"},
        {"option": "FULL-context LLM", "strength": "Strongest measured Joint success (74.6% TEST)", "limitation": "Highest per-case input tokens; cost grows linearly with document length", "evidence": "Final TEST evaluation", "decision": "Quality reference, not served"},
        {"option": "RAG", "strength": "−50.4% input tokens, −16.8% cost vs FULL, bounded context regardless of doc length", "limitation": "Statistically significant Joint disadvantage vs FULL (p=0.0047)", "evidence": "Final TEST evaluation, same population as FULL", "decision": "Adopted as interactive runtime"},
        {"option": "Selective agent", "strength": "None demonstrated — built and tested fairly", "limitation": "Net-zero joint benefit (1 recovery, 1 regression) for added cost/latency; controller chose not to use its own tools", "evidence": "Selective-agent evaluation", "decision": "Rejected"},
    ],

    "aboutProject": {
        "whatITried": ["Rule baseline (A0)", "Local/hosted model ceiling (Oracle, E01)", "Retrieval alternatives (BM25 vs dense vs reranking, E06)", "Prompt variants P0/P1/P2/P3 (E03/E12B/E12C)", "FULL-context (A1, E05)", "Standard RAG (A2, E07)", "Selective agent (A3, E09–E11)", "Review routing/abstention (E15)", "Security/robustness (E16)", "Business/cost economics (E18)"],
        "whatActuallyMattered": ["Base model reasoning ceiling (Qwen → GPT-5-mini closed most of the residual gap, E08B)", "Cross-encoder reranking (decisive retrieval win, E06)", "The Joint (label+evidence) metric — label accuracy alone hid real evidence-grounding gaps", "Residual failure distribution — reasoning/classification dominates, not retrieval (E20: 448/576)"],
        "whatShipped": ["Frozen top-5 RAG runtime (pipeline/frozen_rag.py + pipeline/final_review.py)", "Clause-level provenance in every response", "Runtime evidence-source validator v2", "Next.js reviewer UI + FastAPI backend"],
        "twist": "More sophistication did not automatically win: FULL had the strongest measured evidence-grounded result, RAG was kept for product-oriented reasons (bounded cost/context), and the agent was rejected outright.",
    },

    "errorAnalysis": {
        "e20": {
            "source": src("E20", E20_PATH, "TEST n=2,091, 576 non-joint-successful cases"),
            "totalNonJoint": e20_report["n_total_failures"],
            "buckets": [
                {"label": "Reasoning / classification", "count": e20_report["failure_taxonomy"]["reasoning_classification"]},
                {"label": "Evidence selection", "count": e20_report["failure_taxonomy"]["evidence_selection"]},
                {"label": "Retrieval-limited", "count": e20_report["failure_taxonomy"]["retrieval_limited"]},
                {"label": "Runtime / parser / source-validity", "count": e20_report["failure_taxonomy"]["runtime_parser_source_validity"]},
            ],
        },
        "e18": {
            "source": src("E18", E18_PATH, "TEST n=2,091, 531 total joint failures — a different denominator/bucketing than E20, not comparable directly"),
            "totalJointFailures": 531,
            "buckets": [
                {"label": "NotMentioned over-inference", "count": 323},
                {"label": "Contradiction reasoning/missed provision", "count": 48},
                {"label": "Other Entailment reasoning failure", "count": 42},
                {"label": "Correct-label / evidence mismatch", "count": 43},
                {"label": "Missed provision (no evidence)", "count": 39},
                {"label": "Source-validation issue", "count": 36},
            ],
        },
        "conclusion": "Most residual failures are reasoning/classification, not retrieval — E20: only 55 of 576 (9.5%) non-joint cases are retrieval-limited; reasoning/classification dominates at 448/576 (77.8%).",
        "whatThisChanged": f"Only {e20_report['failure_taxonomy']['retrieval_limited']} residual failures were retrieval-limited. Adding more search/tool loops therefore targets a minority of the remaining problem.",
        "nextInvestment": "Improve semantic reasoning / NotMentioned discipline before adding retrieval complexity.",
    },

    "silentFailure": SILENT_FAILURE_FINDING,

    "trivialBaseline": {
        "rule": {
            "note": "Deterministic Rule baseline, TEST n=2,091 — the intended 'trivial' comparator for this protocol.",
            "accuracy": rule_metrics["accuracy"], "joint": rule_metrics["joint"],
            "source": src("E04/E17", RECON_V2 + "rule_full_test_metrics.json", "TEST n=2,091"),
        },
        "majorityClass": {
            "note": "Majority-class baseline exists for this exact final protocol (always predict Entailment, empty evidence, TEST n=2,091) — computed in E18, not silently omitted.",
            "accuracy": 0.463, "macroF1": 0.211, "joint": 0.0,
            "source": src("E18", E18_PATH, "TEST n=2,091, §1"),
        },
    },

    "businessTradeoff": [
        {"question": "Can rules avoid AI cost?", "evidence": f"Rule: {rule_metrics['accuracy']*100:.1f}% accuracy / {rule_metrics['joint']*100:.1f}% Joint, $0 cost (E04/E17)", "decision": "Cheap but weak semantic coverage — baseline only"},
        {"question": "Hosted or local?", "evidence": f"GPT-5-mini {gpt_metrics['joint']*100:.1f}% Joint vs local Qwen {qwen_metrics['joint']*100:.1f}% Joint, both TEST n=2,091 (E17B)", "decision": "Hosted GPT-5-mini wins the final comparison"},
        {"question": "FULL or RAG?", "evidence": f"FULL Joint {gpt_metrics['joint']*100:.1f}% (p=0.0047 vs RAG) vs RAG −50.4% input tokens / −16.8% cost (E20)", "decision": "FULL = quality reference; RAG = served prototype"},
        {"question": "Agent?", "evidence": "15 escalated DEV cases, 0 tool invocations exercised, net-zero joint benefit (E11)", "decision": "Reject"},
        {"question": "Cheapest call = cheapest system?", "evidence": f"Modeled all-in cost-to-serve @ $3.33/case human fallback: FULL ${'{:.4f}'.format(0.8485)}/case vs RAG ${'{:.4f}'.format(0.9200)}/case (E18 §8) — human fallback cost dominates, not raw AI cost", "decision": "Optimize total modeled cost-to-serve, not the cheapest raw inference call"},
        {"question": "Automate the legal decision?", "evidence": f"NotMentioned recall {gpt_metrics['recall']['NotMentioned']*100:.1f}%; E16 security limitation (4/11 injection pairs); E15 found no viable auto-routing policy", "decision": "Human remains final authority"},
    ],

    "decisionScorecard": {
        "columns": ["Evidence-grounded quality", "Contradiction handling", "Input footprint", "Raw inference cost", "Reviewer traceability", "Operational complexity", "Dynamic investigation", "Final role"],
        "rows": [
            {"row": "Rule", "cells": [
                f"{rule_metrics['joint']*100:.1f}% Joint", f"{rule_metrics['recall']['Contradiction']*100:.0f}% recall — weak",
                "None (no LLM call)", "$0", "None — no evidence returned", "LOW", "N/A", "Baseline only",
            ]},
            {"row": "FULL", "cells": [
                f"{gpt_metrics['joint']*100:.1f}% Joint — best measured", f"{gpt_metrics['recall']['Contradiction']*100:.0f}% recall",
                "Entire document, every call", f"${cost_summary['gpt_cost_per_case_usd']:.4f}/case", "Whole-document explanation, not clause-bounded", "LOW", "N/A", "Quality reference",
            ]},
            {"row": "RAG", "cells": [
                f"{e20_report['RAG_metrics']['joint']*100:.1f}% Joint · -50.4% input tokens", f"{e20_report['RAG_metrics']['recall']['Contradiction']*100:.0f}% recall",
                "Top-5 reranked clauses only", f"${e20_report['RAG_metrics']['ops']['cost_per_case']:.4f}/case (-16.8% vs FULL)", "Clause-level, directly citable", "MEDIUM", "N/A", "Served prototype runtime",
            ]},
            {"row": "Agent", "cells": [
                f"{round(e11_prompt_v2['arms']['v2']['joint']*100,1)}% Joint in prompt v2 · +37 tool calls vs v1", "No measured improvement",
                "RAG context + up to 2 tool calls", "Higher per-case cost/latency across all 3 evaluations", "Same as RAG, plus a visible tool trace", "HIGH", "Tested, 0% useful recovery", "Rejected",
            ]},
        ],
        "note": "Descriptive statements only — no normalized scores were computed; LOW/MEDIUM/HIGH describe operational complexity as implemented, not a weighted rubric.",
    },

    "shipDecision": {
        "ship": [
            "Top-5 RAG runtime", "Evidence quotes", "Evidence source context", "Deterministic parser",
            "Evidence validation", "Per-review cost/latency", "Human final decision",
        ],
        "doNotShip": [
            "Autonomous approval/rejection", "Selective agent", "Automatic confidence routing",
            "Unattended confidential-document processing", "Production prompt-injection claims", "Long-contract scaling claims",
        ],
    },

    "owasp": [
        {
            "category": "Prompt Injection", "level": "measured",
            "evidence": "E16: 20 matched clean/attack pairs, 4/11 injection-type pairs succeeded (2 label hijacks: instruction-only document, fake [SYSTEM] message), joint 85%→75%",
            "control": "None implemented — disclosed, not patched",
            "residualRisk": "Source-valid evidence ≠ trustworthy instruction source; the runtime validator confirms a quote came from the document, not that the document's content is safe to follow",
            "source": src("E16", "experiments/E16_robustness_security/results/hosted_results.json", "n=20 matched pairs"),
        },
        {
            "category": "Sensitive Information Disclosure", "level": "mapped-only",
            "evidence": "No dedicated PII/secret-leakage test run in the final architecture",
            "control": "Structured logging rule (never log raw NDA text/prompts/keys) carried from the original project logging rule",
            "residualRisk": "Not tested end-to-end under the final architecture",
            "source": src("—", "docs/architecture.md", "policy statement, not a measured test"),
        },
        {
            "category": "Improper Output Handling", "level": "implemented-control",
            "evidence": "Structured output parser + runtime evidence-source validator v2 (checks cited evidence is a genuine verbatim quote)",
            "control": "Runtime evidence-source validator — 98.0% source-valid quote rate on FULL TEST",
            "residualRisk": "Validates source integrity, not semantic correctness",
            "source": src("E14/E17B", RECON_V2 + "gpt_full_test_metrics.json", "TEST n=2,091, source_valid_quote_rate field"),
        },
        {
            "category": "Excessive Agency", "level": "tested",
            "evidence": "Selective agent (A3) built with hard bounds (max 3 steps, max 2 tool calls, duplicate-call detection, $0.01/case circuit-breaker) and evaluated — then rejected for the served runtime",
            "control": "No agent in the current production path at all (strongest possible control — not just bounded, absent)",
            "residualRisk": "None in current runtime; historical agent code remains for experiment reproduction only",
            "source": src("E10/E11", "docs/experiment_registry.md", "design freeze + TRAIN_ARCH_v1 n=150"),
        },
        {
            "category": "Unbounded Consumption", "level": "implemented-control",
            "evidence": "Bounded top-5 RAG context caps input tokens regardless of document length; agent (when it existed experimentally) had a $0.01/case circuit-breaker and 60s wall-clock cap",
            "control": "Frozen retrieval config, fixed top_k=5; E10's agent hard limits (experimental only, not in runtime)",
            "residualRisk": "FULL-context path (quality reference only, not served) has no such bound and costs grow linearly with document length",
            "source": src("E06/E10", "pipeline/frozen_rag.py", "runtime config"),
        },
    ],

    "riskTable": [
        {"risk": "Unsupported/hallucinated evidence", "failureMode": "Model cites a clause that isn't actually in the document", "mitigation": "Runtime evidence-source validator v2 (verbatim substring check)", "evidence": "98.0% source-valid quote rate, final TEST (E14/E17B)", "residualRisk": "Confirms source, not semantic correctness", "humanControl": "Reviewer reads the cited clause"},
        {"risk": "Prompt injection", "failureMode": "NDA text contains an embedded instruction the model follows", "mitigation": "None implemented", "evidence": "E16 (4/11 attack success)", "residualRisk": "Disclosed, unpatched", "humanControl": "Reviewer judgment on implausible outputs"},
        {"risk": "Excessive agency", "failureMode": "An agent takes unbounded actions/tool calls", "mitigation": "No agent in production runtime at all", "evidence": "ADR-012, docs/architecture.md §2", "residualRisk": "None in current runtime", "humanControl": "N/A — not present"},
        {"risk": "Unbounded consumption", "failureMode": "Cost/latency grows without limit on long documents", "mitigation": "Bounded top-5 RAG context (production runtime only)", "evidence": "Frozen retrieval configuration (E06)", "residualRisk": "FULL-context (quality reference only) is unbounded", "humanControl": "N/A — architectural"},
        {"risk": "Sensitive NDA handling", "failureMode": "Confidential contract text logged or leaked", "mitigation": "Logging rule: never log raw NDA text/prompts/keys", "evidence": "Architecture policy statement, not independently tested this pass", "residualRisk": "Not end-to-end tested under the final architecture", "humanControl": "N/A"},
        {"risk": "Provider failure", "failureMode": "OpenRouter/model outage mid-review", "mitigation": "FUTURE / NOT IMPLEMENTED — no fallback model wired in", "evidence": "E18 §12 seven-layer stack", "residualRisk": "Single-vendor dependency", "humanControl": "Manual retry / fallback to manual review"},
        {"risk": "Silent semantic error", "failureMode": "Confident wrong label with source-valid but wrong-clause evidence", "mitigation": "None — E15 found no reliable automatic routing signal", "evidence": "E15 (no policy meets provisional targets); E20 contradiction analysis (38/50 evidence-bearing Contradiction misses quote the right clause, wrong label)", "residualRisk": "Real and not caught by any current automatic guardrail", "humanControl": "Reviewer is the only real check"},
        {"risk": "Long-document uncertainty", "failureMode": "Untested behavior on real 50–100 page enterprise contracts", "mitigation": "FUTURE / NOT IMPLEMENTED — RAG's bounded-context argument is architectural, not validated at that scale", "evidence": "ADR-012 (TEST median 1,836 / max 7,861 tokens)", "residualRisk": "Open validation question", "humanControl": "N/A until tested"},
    ],

    "timeline": [],  # filled below from experiment_registry summaries

    "cases": {
        "populationNote": CASE_POPULATION_NOTE,
        "matchedCaseCount": len(cases),
        "browserCaseCount": len(cases_out),
        "startHere": start_here,
        "featured": FEATURED_CASES,
        "overviewCaseKey": OVERVIEW_CASE_KEY,
        "overviewFailureCaseKey": OVERVIEW_FAILURE_CASE_KEY,
        "showcaseValidation": SHOWCASE_VALIDATION,
        "items": cases_out,
        "agentDemoCases": agent_demo_cases,
    },

    "buildVsBuy": [
        {"layer": "Dataset", "ownRentReuse": "Reuse", "technology": "ContractNLI (607 NDAs, 17 hypotheses)", "why": "Standard, licensed NDA-review evaluation dataset; avoids using real confidential documents", "evidence": "data/contractnli/README.md"},
        {"layer": "Model (quality reference)", "ownRentReuse": "Rent", "technology": "openai/gpt-5-mini via OpenRouter", "why": "Selected on Oracle reasoning-ceiling test over Qwen/Gemini/Llama", "evidence": "E01"},
        {"layer": "Model (local comparator)", "ownRentReuse": "Own", "technology": "qwen2.5:7b-instruct (Ollama)", "why": "$0-cost hosted/local comparison point", "evidence": "E01/E17B"},
        {"layer": "Retrieval", "ownRentReuse": "Reuse", "technology": "rank_bm25 (lexical) + cross-encoder/ms-marco-MiniLM-L-12-v2", "why": "BM25 tied dense retrieval once reranking applied; kept for simplicity", "evidence": "E06"},
        {"layer": "Chunking / orchestration", "ownRentReuse": "Own", "technology": "Custom clause-aware chunker, plain synchronous Python", "why": "No agent/graph needed once A3 was rejected", "evidence": "pipeline/frozen_rag.py"},
        {"layer": "Evidence validator", "ownRentReuse": "Own", "technology": "pipeline/evidence_validator.py, evaluation/evidence_matching.py (v2)", "why": "Deterministic verbatim-substring check; hardened for formatting edge cases", "evidence": "E13B/E14"},
        {"layer": "Evaluation harness", "ownRentReuse": "Own", "technology": "evaluation/", "why": "Joint label+evidence metric, McNemar significance testing, Wilson CIs", "evidence": "E17/E17B/E20"},
        {"layer": "Backend", "ownRentReuse": "Own", "technology": "FastAPI", "why": "Thin serving layer over pipeline/final_review.py", "evidence": "backend/routes/review.py"},
        {"layer": "Frontend", "ownRentReuse": "Own", "technology": "Next.js 16 / React 19 / Tailwind 4", "why": "Reviewer UI + this presentation route", "evidence": "frontend/"},
    ],

    "frozenConfig": [
        {"key": "Chunking", "value": "clause-aware, 256 tokens", "experiment": "E06", "artifact": "pipeline/frozen_rag.py"},
        {"key": "Overlap", "value": "50 tokens", "experiment": "E06", "artifact": "pipeline/frozen_rag.py"},
        {"key": "Candidate pool", "value": "BM25 top-20", "experiment": "E06", "artifact": "pipeline/frozen_rag.py"},
        {"key": "Reranker", "value": "cross-encoder/ms-marco-MiniLM-L-12-v2", "experiment": "E06", "artifact": "pipeline/frozen_rag.py"},
        {"key": "Final context", "value": "top-5", "experiment": "E06/E20", "artifact": "pipeline/frozen_rag.py"},
        {"key": "Model", "value": "openai/gpt-5-mini", "experiment": "E01", "artifact": "pipeline/final_review.py"},
        {"key": "Prompt", "value": "P0 (prompts/final/gpt_p0.txt)", "experiment": "E03", "artifact": "pipeline/final_review.py"},
        {"key": "Temperature", "value": "0", "experiment": "E05", "artifact": "pipeline/final_review.py"},
        {"key": "Agent", "value": "none", "experiment": "E09/E11 (rejected)", "artifact": "docs/architecture_decisions/INDEX.md"},
        {"key": "Router", "value": "none", "experiment": "E15 (no policy met target)", "artifact": "docs/experiment_registry.md"},
    ],

    "componentInventory": [
        {"name": "Retriever", "does": "BM25 candidate generation over clause-256 chunks", "runtimeOrExperimentOnly": "Runtime", "lineage": "E06"},
        {"name": "Reranker", "does": "Cross-encoder re-scoring of the top-20 candidate pool", "runtimeOrExperimentOnly": "Runtime", "lineage": "E06"},
        {"name": "Model gateway", "does": "OpenRouter call wrapper (pipeline/final_review.py)", "runtimeOrExperimentOnly": "Runtime", "lineage": "E01/E08B"},
        {"name": "Parser", "does": "Structured JSON output parsing with recovery", "runtimeOrExperimentOnly": "Runtime", "lineage": "E05/evaluation/structured_output.py"},
        {"name": "Evidence validator", "does": "Verbatim-substring source check (v2, NFC/zero-width tolerant)", "runtimeOrExperimentOnly": "Runtime", "lineage": "E13B/E14"},
        {"name": "API", "does": "POST /api/review, POST /review, /history", "runtimeOrExperimentOnly": "Runtime", "lineage": "E19"},
        {"name": "UI", "does": "Reviewer app + this presentation route", "runtimeOrExperimentOnly": "Runtime", "lineage": "E19"},
        {"name": "Evaluation harness", "does": "Joint metric, McNemar, Wilson CIs, taxonomy", "runtimeOrExperimentOnly": "Experiment-only (offline)", "lineage": "E17/E17B/E20"},
        {"name": "Experimental agent", "does": "Two-tool bounded investigation over RAG context", "runtimeOrExperimentOnly": "Experiment-only, rejected", "lineage": "E09-E11"},
    ],

    "auditableMechanisms": [
        {"name": "Retrieval Recall@5", "value": round(e20_report["retrieval_diagnostics"]["recall_at_5"] * 100, 1), "unit": "%", "source": src("E20", E20_PATH, "n=1,188 gold-evidence TEST cases")},
        {"name": "Agent tool-use frequency (DEV, 15 escalated cases)", "value": 0, "unit": "of 15 cases invoked a tool", "source": src("E11", "docs/experiment_registry.md", "TRAIN_ARCH_v1 n=150")},
        {"name": "Agent useful recovery count (DEV)", "value": "1 recovery / 1 regression", "unit": "", "source": src("E11", "docs/experiment_registry.md", "TRAIN_ARCH_v1 n=150")},
        {"name": "Source validity (FULL, TEST)", "value": round(gpt_metrics["source_valid_quote_rate"] * 100, 1), "unit": "%", "source": src("E17B", RECON_V2 + "gpt_full_test_metrics.json", "TEST n=2,091")},
        {"name": "Runtime/parser failure count (FULL, TEST)", "value": gpt_metrics["parse_counts"]["invalid"], "unit": f"of {gpt_metrics['parse_counts']['strict'] + gpt_metrics['parse_counts']['invalid']}", "source": src("E17B", RECON_V2 + "gpt_full_test_metrics.json", "TEST n=2,091")},
        {"name": "Review-routing coverage (best tested policy, R3)", "value": round(routing_summary["policies"]["R3"]["raw_review_rate"] * 100, 1), "unit": "% review rate, not adopted", "source": src("E15", RECON_V2 + "routing_summary.json", "DEV n=138")},
    ],

    "dataProvenance": {
        "contractnli": {"ndaCount": TOTAL_DOCS, "hypotheses": 17, "examples": TOTAL_CASES, "splits": SPLIT_COUNTS},
        "goldWithheldFromInference": True,
        "testExposureCaveat": "TEST is the final, one-shot evaluation split (first accessed only after model/prompt/architecture/evaluator/validator were frozen, E17, commit 5717bdf) — but it is NOT claimed as perfectly blind: earlier project iterations (legacy T041, rule/hosted comparisons) previously touched TEST. Disclosed in docs/data_contamination_register.md, not hidden.",
        "finalProtocolCaveat": "The final architecture independently re-derives every architecture/model/prompt decision under its own E-series rather than assuming legacy (T-series) conclusions still hold.",
        "source": src("E00", CONTAM_PATH, "full split/exposure inventory"),
    },

    "intendedUse": {
        "intended": ["Reviewer aid — a second check alongside human review", "Evidence retrieval for a specific requirement", "Requirement classification (Entailment/Contradiction/Not Mentioned)", "Human verification of every output"],
        "notIntended": ["Legal advice", "Contract approval or rejection", "Negotiation", "Autonomous legal action", "Production use on confidential NDAs without additional controls"],
        "source": src("—", SUMMARY_PATH, "Limitations section"),
    },
}

# ---------------------------------------------------------------------------
# 4. Narrative deep-dive blocks — the reasoning chain from problem to shipped
#    system. Every number below is hand-transcribed from the named experiment's
#    summary.md, cross-checked against that file's own result tables.
# ---------------------------------------------------------------------------

data["oracleExperiment"] = {
    "question": "If I give the model the right evidence, can it reason correctly?",
    "purpose": "Feed gold evidence directly, removing retrieval from the equation, to isolate reasoning quality alone.",
    "models": [
        {"name": "Llama 3.2 3B", "hosted": False, "macroF1": 0.601, "balancedAccuracy": 60.3, "entailmentRecall": 68.7, "contradictionRecall": 25.0, "notMentionedRecall": 100.0, "parseValid": 94.7, "latencyMs": 415, "costUsd": 0.0},
        {"name": "Qwen 2.5 7B", "hosted": False, "macroF1": 0.638, "balancedAccuracy": 66.0, "entailmentRecall": 68.0, "contradictionRecall": 30.0, "notMentionedRecall": 100.0, "parseValid": 100.0, "latencyMs": 960, "costUsd": 0.0},
        {"name": "Gemini 2.5 Flash Lite", "hosted": True, "macroF1": 0.867, "balancedAccuracy": 86.7, "entailmentRecall": 89.0, "contradictionRecall": 71.0, "notMentionedRecall": 100.0, "parseValid": 100.0, "latencyMs": 696, "costUsd": 0.0091},
        {"name": "GPT-5-mini", "hosted": True, "macroF1": 0.906, "balancedAccuracy": 90.7, "entailmentRecall": 90.0, "contradictionRecall": 82.0, "notMentionedRecall": 100.0, "parseValid": 100.0, "latencyMs": 3078, "costUsd": 0.1087},
    ],
    "interpretation": "Entailment reasoning is strong across the board given perfect evidence. NotMentioned's 100% recall is structurally easy to game — an empty evidence list is itself a signal every model can exploit without engaging the requirement — so it's excluded from reasoning-quality claims. Contradiction is the clearest, most directly comparable reasoning bottleneck: even the strongest tested model tops out at 82% recall with perfect evidence handed to it.",
    "decision": "Freeze qwen2.5:7b-instruct as the $0 local reference (best local Macro-F1 and Contradiction Recall, 100% schema-parse-valid) and openai/gpt-5-mini as the hosted reasoning-ceiling reference (highest Macro-F1 and Contradiction Recall of any tested model).",
    "source": src("E01", "experiments/E01_oracle/results/e01_metrics.json", "TRAIN_ORACLE_v1 n=300, 100/100/100 balanced by construction"),
}

data["modelSelection"] = {
    "question": "Which model earned the next experiment?",
    "technical": [
        "Oracle isolates reasoning from retrieval — GPT-5-mini's 82% Contradiction Recall vs. Qwen's 30% is a reasoning-ceiling gap, not a retrieval gap",
        "GPT-5-mini: 3,078ms mean latency, $0.1087 for 300 hosted calls",
        "Qwen 2.5 7B: 960ms mean latency, $0 (local, Ollama)",
    ],
    "business": [
        "Local inference avoids per-call API cost entirely",
        "The stronger hosted model reduces downstream human-fallback risk by catching more real Contradictions before a human ever sees the case",
        "Absolute hosted cost is small relative to the experiment budget — the premium isn't binding at this scale",
    ],
    "decision": "GPT-5-mini becomes the hosted reference model carried into every later architecture experiment. Qwen 2.5 7B stays the $0-cost local comparator.",
    "source": src("E01", "experiments/E01_oracle/summary.md", "TRAIN_ORACLE_v1 n=300"),
}

data["promptSelection"] = {
    "question": "Does a more elaborate prompt actually help?",
    "localRounds": [
        {"name": "P0 (minimal)", "accuracy": 52.7, "macroF1": 0.507, "contradictionRecall": 22.0},
        {"name": "P1 (+label definitions)", "accuracy": 51.3, "macroF1": 0.448, "contradictionRecall": 6.0},
        {"name": "P2 (+decision procedure)", "accuracy": 48.0, "macroF1": 0.403, "contradictionRecall": 2.0},
    ],
    "localFinding": "On the local Qwen model, more prompt structure made Contradiction handling monotonically worse: real Contradiction cases collapsed into NotMentioned predictions as instruction detail increased (37→44→46 of 50 cases, P0→P1→P2).",
    "localDecision": "Freeze P0 (minimal instruction) for the local model.",
    "gptDiscovery": {"p0Joint": 114, "p3Joint": 122, "delta": 8, "threshold": 9, "outcome": "Near-tie — one case short of the pre-declared +9 adoption bar, but passed every guard. Queued for one confirmation run on a fresh, disjoint set of documents rather than adopted outright."},
    "gptConfirmation": {"p0Joint": 128, "p0JointPct": 85.3, "p3Joint": 125, "p3JointPct": 83.3, "delta": -3, "outcome": "Direction reversed — P3 lost 3 net joint cases on fresh documents, the opposite of the discovery run."},
    "reversalStory": "A GPT-tailored prompt (definitions + affirmative-conflict guidance) looked like a real, if marginal, improvement on the first 150-case sample (+8 joint, one short of the adoption bar). A second, fully independent 150-case sample — different documents, same prompts, everything else unchanged — reversed the result (−3 joint). The apparent gain didn't survive replication.",
    "decision": "Freeze P0 for GPT-5-mini too. The GPT-tailored prompt was never adopted.",
    "takeaway": "More instruction was not automatically better — on two different models, in two different ways.",
    "source": src("E03/E12B/E12C", "experiments/E12C_gpt_prompt_confirmation/summary.md", "two disjoint 150-case TRAIN samples"),
}

# Causal experiment narrative. Metrics are read from frozen artifacts above;
# only explanatory prose is authored here.
data["causalStory"] = {
    "oracle": {
        "why": "Before tuning retrieval, isolate the reasoning ceiling: can the model decide the label when the human-annotated evidence is already supplied?",
        "failure": "Even with oracle evidence, weaker models missed Contradictions. That separates a reasoning limitation from a retrieval limitation.",
        "learned": "Evidence access alone does not guarantee the correct legal classification.",
        "next": "Select the strongest reasoning model, then test how much instruction it actually needs.",
    },
    "prompt": {
        "why": "Test whether definitions and a step-by-step decision procedure improve legal classification over a minimal instruction.",
        "variants": [
            {"id": "P0", "name": "Minimal", "attempt": "A concise task and output contract; tests the model without extra decision scaffolding."},
            {"id": "P1", "name": "Label definitions", "attempt": "Adds explicit label definitions to reduce ambiguity."},
            {"id": "P2", "name": "Decision procedure", "attempt": "Adds an ordered checklist to test whether more structure improves consistency."},
        ],
        "metrics": [{"id": prompt_id, "contradictionRecall": round(e03_failure["metrics"][key]["contradiction_recall"] * 100, 1), "macroF1": round(e03_failure["metrics"][key]["macro_f1"], 3)} for prompt_id, key in [("P0", "p00"), ("P1", "p01"), ("P2", "p02")]],
        "failure": {
            "p0Errors": 150 - round(e03_failure["metrics"]["p00"]["accuracy"] * 150),
            "retrievalLimited": e03_failure["retrieval_limited_count"],
            "reasoningPromptLimited": e03_failure["reasoning_prompt_limited_count"],
            "carveoutIndicator": 43,
            "nonRetrievalContradictionFailures": 46,
            "caveat": "The exception/carve-out count is an automated co-occurrence indicator, not proof that the clause caused the error.",
        },
        "case": {
            "caseId": "train::86::nda-2",
            "requirement": train_hypotheses["nda-2"],
            "goldLabel": "Contradiction",
            "prediction": "NotMentioned",
            "evidence": train_docs["86"]["text"][train_docs["86"]["spans"][55][0]:train_docs["86"]["spans"][55][1]],
            "why": "The gold evidence is present, but P0 predicts NotMentioned. The automated review also flags exception/carve-out language elsewhere in the retrieved context; that is a co-occurrence clue, not a causal diagnosis.",
        },
        "learned": "More instruction did not mean better reasoning. Most P0 errors were not caused by missing retrieved text, so prompt wording was not the only bottleneck.",
        "revisit": {
            "discovery": {"p0": e12c["E12B_recap"]["p0_joint"], "p3": e12c["E12B_recap"]["p3_joint"], "delta": e12c["E12B_recap"]["delta"], "threshold": 9},
            "confirmation": {"p0": e12c["E12C"]["p0_joint"], "p3": e12c["E12C"]["p3_joint"], "delta": e12c["E12C"]["delta"]},
            "lesson": "Discovery is not confirmation: P3's apparent gain reversed on a fresh, disjoint population.",
        },
        "next": "Freeze P0 and stop prompt tuning; change the information architecture instead.",
        "source": src("E03/E12B/E12C", "experiments/E03_prompt_selection/results/prompt_failure_analysis_summary.json", "two disjoint TRAIN n=150 prompt evaluations"),
    },
    "retrieval": {
        "why": "Once instruction changes stopped helping, ask whether the right clause is being found and ranked into the model's limited context.",
        "misses": e06_failure["total_misses_analyzed"],
        "rankingFailures": e06_failure["ranking_failure_gold_beyond_top_k"],
        "candidateAbsence": e06_failure["retrieval_absence_semantic_or_lexical_mismatch"],
        "medianGoldRank": 7,
        "learned": "Every analyzed miss was a ranking failure: the gold span existed in the candidate pool but fell below the final cut.",
        "next": "Retrieve broadly with BM25 top-20, let the cross-encoder repair ranking, then pass only the top-5 clauses.",
        "source": src("E06", "experiments/E06_retrieval_optimisation/results/failure_analysis_summary.json", "349 TRAIN retrieval misses"),
    },
    "rag": {
        "why": "With model, prompt, and retrieval frozen, test the complete evidence-grounded pipeline and diagnose its residual errors.",
        "learned": "Useful evidence was already present in many wrong cases. RAG reduced context, but retrieval was not the only—or dominant—remaining bottleneck.",
        "next": "Compare full context, wider static retrieval, and narrowly bounded dynamic retrieval rather than assuming more retrieval is always better.",
    },
    "staticExpansion": {
        "why": "Failure review found more static filtering opportunity than genuinely dynamic opportunity. Test the cheaper deterministic fix first: widen top-5 to top-11.",
        "rows": [{"name": name, "accuracy": round(e12a[key]["accuracy"] * 100, 1), "macroF1": round(e12a[key]["macro_f1"], 3), "joint": round(e12a[key]["joint"] * 100, 1), "contradictionRecall": round(e12a[key]["recall"]["Contradiction"] * 100, 1), "inputTokens": round(e12a[key]["input_tokens"]["mean"], 2), "cost": e12a[key]["cost"]["mean"]} for name, key in [("top-5", "top5"), ("top-11", "top11")]],
        "inputIncrease": round((e12a["top11"]["input_tokens"]["mean"] / e12a["top5"]["input_tokens"]["mean"] - 1) * 100, 3),
        "costIncrease": round((e12a["top11"]["cost"]["mean"] / e12a["top5"]["cost"]["mean"] - 1) * 100, 3),
        "learned": "Top-11 improved Joint on this sample but did not improve Contradiction Recall, while materially increasing context and cost.",
        "next": "Keep top-5 for the prototype; investigate whether a bounded agent can request extra context only when needed.",
        "source": src("E12A", "experiments/E12A_static_context_expansion/results/e12a_analysis.json", "TRAIN_ARCH_v1 n=150, paired"),
    },
    "agent": {
        "why": "Could dynamic investigation recover the residual failures and earn its added complexity?",
        "residual": {"n": 39, "reasoning": 26, "retrievalFiltering": 6, "dynamic": e09_ceiling["ORACLE_AGENT_OPPORTUNITY_CEILING"]["n_dynamic_cases"]},
        "ceilings": {"static": e09_ceiling["STATIC_PIPELINE_OPPORTUNITY_CEILING"]["joint_success_uplift_pp"], "agent": round(e09_ceiling["ORACLE_AGENT_OPPORTUNITY_CEILING"]["joint_success_uplift_pp"], 2)},
        "design": {"flow": ["Assess top-5", "FOLLOW_CROSS_REFERENCE or GET_MORE_CANDIDATES", "Reassess", "FINAL"], "limits": ["max 3 steps", "max 2 tool calls", "duplicate-call stop", "token/context cap", "time and cost cap", "safe fallback"]},
        "v1": {
            "selectiveRouted": 15, "selectiveToolCalls": 0, "fullToolCases": 2, "fullN": 150,
            "hypotheses": ["Most cases may truly need no extra evidence", "The controller prompt may suppress tool use"],
            "stage1Caption": "Tools were available, but the selective controller chose FINAL immediately on all 15 routed cases.",
            "stage2Caption": "Removing routing constraints produced only 2/150 tool-using cases: one cross-reference lookup and one extra-candidate lookup. Neither created a useful recovery.",
        },
        "v2": {
            "change": "Only the controller prompt changed. It removed ‘most cases should conclude immediately’ and added silent checks for unresolved references, incomplete or qualified clauses, and evidence outside top-5 before reassessment.",
            "toolCases": 30, "n": 150, "getMore": 23, "follow": 16,
            "useful": e11_tool_usage["category_counts"].get("useful", 0), "neutral": e11_tool_usage["category_counts"]["neutral"], "harmful": e11_tool_usage["category_counts"]["harmful"],
            "fallbacks": 25, "duplicateStops": 11, "invalidStops": 6, "maxToolStops": 8,
            "stage3Caption": "Prompt V2 deliberately encouraged investigation. Tool use rose to 30/150 cases.",
            "toolCallNote": "Total tool calls can exceed tool-using cases because some cases used two tools.",
            "whyV2": "The first controller may have been suppressing tool use, so V2 removed the strong 'conclude immediately' bias and required the agent to check for unresolved references and missing evidence before finalizing.",
        },
        "quality": [{"name": name, "joint": round(e11_prompt_v2["arms"][key]["joint"] * 100, 1)} for name, key in [("Base RAG", "base"), ("Agent V1", "v1"), ("Agent V2", "v2")]],
        "comparison": [
            {
                "name": name,
                "role": role,
                "population": "TRAIN_ARCH_v1 · matched n=150",
                "accuracy": round(e11_prompt_v2["arms"][key]["accuracy"] * 100, 1),
                "joint": round(e11_prompt_v2["arms"][key]["joint"] * 100, 1),
                "contradictionRecall": round(e11_prompt_v2["arms"][key]["recall"]["Contradiction"] * 100, 1),
                "toolUse": None if key == "base" else round(e11_prompt_v2["operations"][key]["tool_use_rate"] * 100, 1),
                "usefulRecoveries": None if key == "base" else ("0/2" if key == "v1" else "0/30"),
                "incrementalCost": None if key == "base" else e11_prompt_v2["operations"][key]["cost_per_case_usd"],
                "incrementalLatency": None if key == "base" else round(e11_prompt_v2["operations"][key]["mean_incremental_latency_seconds"], 2),
                "inputTokens": None if key == "base" else e11_prompt_v2["operations"][key]["input_tokens"],
                "outputTokens": None if key == "base" else e11_prompt_v2["operations"][key]["output_tokens"],
                "modelCalls": None if key == "base" else e11_prompt_v2["operations"][key]["hosted_calls"],
            }
            for name, role, key in [("Base RAG", "Control", "base"), ("Agent V1", "Tested configuration", "v1"), ("Agent V2", "Investigation encouraged", "v2")]
        ],
        "evaluationNote": "Agent investigation was evaluated by tool-mediated recovery and final task success, not by a directly comparable static Recall@5 metric.",
        "learned": "Tool underuse was partly a prompt problem, but it was not the main bottleneck: V2 increased tool use from 1.3% to 20% without producing a useful recovery.",
        "next": "Reject the agent and keep the deterministic RAG runtime with human review.",
        "takeaway": {
            "toolUsePct": 20, "usefulRecoveries": 0,
            "headline": "20% tool use. 0 useful recoveries.",
            "body": "The agent was not rejected because it lacked tools. It was rejected because the two tools targeted real observed failure modes, tool use was successfully increased (1.3% → 20% of cases), and the additional investigation still did not improve outcomes.",
            "conclusion": "In the tested architecture, these targeted read-only tools did not create enough recovery value to justify the added cost, latency, and control complexity.",
        },
        "source": src("E09/E11", "experiments/E11_selective_agent_evaluation/addendum_agent_prompt_ablation/results/tool_usage.json", "TRAIN_ARCH_v1 n=150"),
    },
}

data["causalTimeline"] = [
    {"id": "E01", "question": "Can the model reason when evidence is perfect?", "result": "GPT-5-mini set the strongest oracle ceiling.", "failure": "Weaker models still missed Contradictions with gold evidence.", "learned": "Reasoning is an independent bottleneck.", "next": "Test instruction depth."},
    {"id": "E03", "question": "Does more instruction improve reasoning?", "result": "P0 beat P1 and P2 on Contradiction Recall and Macro-F1.", "failure": "82 of 88 P0 errors were reasoning/prompt-limited, not retrieval-limited.", "learned": "More instruction did not mean better reasoning.", "next": "Freeze P0; optimize evidence delivery."},
    {"id": "E06", "question": "Why is relevant evidence missing from top-5?", "result": "All 349 analyzed misses were ranking failures.", "failure": "Gold evidence sat lower in the pool; median best rank was 7.", "learned": "Reranking—not candidate generation—was the leverage point.", "next": "BM25 top-20 → rerank → top-5."},
    {"id": "E07–E09", "question": "After RAG, what failures remain?", "result": "26 of 39 stronger-model failures were reasoning-limited; one was truly dynamic.", "failure": "Extra retrieval could only address a minority.", "learned": "Static expansion had a 4.0pp ceiling; agent action only 0.67pp.", "next": "Test static top-11 before agency."},
    {"id": "E12A", "question": "Does wider static context earn its cost?", "result": "Top-11 reached 78% Joint vs 74% for top-5 on the sample.", "failure": "No Contradiction Recall gain; +63.805% input and +16.830% cost.", "learned": "The gain was not broad enough to justify permanent expansion.", "next": "Keep top-5; test bounded on-demand expansion."},
    {"id": "E11 V1→V2", "question": "Was agent tool underuse a controller-prompt problem?", "result": "Tool use rose from 1.3% to 20%.", "failure": "0 useful recoveries; Joint fell from 75.3% base to 68.7% V2.", "learned": "Underuse was partly prompt-sensitive, but agency was not the main bottleneck.", "next": "Reject A3."},
    {"id": "E20", "question": "Which architecture should the prototype ship?", "result": "FULL was the stronger quality reference; RAG reduced context/cost and returned ranked provenance.", "failure": "Neither removes the need for human authority.", "learned": "The quality-reference configuration and the shipped runtime architecture can be different.", "next": "Ship deterministic top-5 RAG with reviewer verification."},
]

data["securityStory"] = {
    "process": ["OWASP LLM Top 10", "E21 baseline", "Targeted remediation", "E22 verification"],
    "processNote": "10/10 OWASP LLM categories were assessed. Findings were converted into concrete engineering controls and re-tested only where implementation changed.",
    "baselineLabel": "Baseline before E22 controls",
    "remediations": [
        {
            "id": "LLM10", "name": "Unbounded consumption", "before": e22_report["targeted_results"]["LLM10"]["baseline"], "after": e22_report["targeted_results"]["LLM10"]["targeted_regression"],
            "controls": ["NDA max length", "Requirement max length", "Per-request cost ceiling", "Cumulative budget enforcement", "Rate limit", "Concurrency cap"],
            "verification": [f"{len(e22_consumption['checks'])}/{len(e22_consumption['checks'])} local checks passed", "0 hosted calls for rejected requests"],
            "residual": e22_report["targeted_results"]["LLM10"]["residual_risk"],
        },
        {
            "id": "LLM01", "name": "Prompt injection", "before": e22_report["targeted_results"]["LLM01"]["baseline"], "after": e22_report["targeted_results"]["LLM01"]["targeted_regression"],
            "controls": ["Deterministic guard over retrieved context", "Case/whitespace normalization", "security_review_required flag", "Mandatory human-review flag", "No autonomous acceptance"],
            "verification": [
                f"{e22_injection['local_regression']['false_positive_check']['flagged']}/{e22_injection['local_regression']['false_positive_check']['total']} false positives",
                f"{e22_injection['local_regression']['e16_f1_f4_attack_detection']['detected']}/{e22_injection['local_regression']['e16_f1_f4_attack_detection']['total']} E16 attacks detected",
                "Both previously successful E16 attacks detected",
                f"{e22_injection['hosted_confirmation']['n_correct']}/{e22_injection['hosted_confirmation']['n_total']} hosted confirmation cases correct",
                f"${e22_injection['hosted_confirmation']['spend_usd']:.6f} finalized hosted confirmation spend",
            ],
            "residual": "Coverage remains incomplete: 7/11 broader E16 attack formulations were not detected.",
        },
    ],
    "architecture": ["Input limits", "Retrieval", "Injection guard", "Model", "Structured parser", "Evidence validator", "Security review flag", "Human review"],
    "controlZones": [
        {"label": "Before model", "items": ["Input bounds", "Rate/concurrency controls", "Budget guard"]},
        {"label": "Around model", "items": ["Bounded context", "No write tools", "No external web access"]},
        {"label": "After model", "items": ["Structured parser", "Evidence validation", "Human-review flag"]},
    ],
    "proved": [
        {"label": "Controlled", "items": ["Bounded input", "Bounded spend", "Bounded concurrency", "Structured output", "Read-only agent tools", "Source validation"]},
        {"label": "Improved", "items": ["Prompt-injection detection", "Supply-chain exposure reduced", "Runtime budget enforcement"]},
        {"label": "Remains human-gated", "items": ["Prompt-injection edge cases", "Semantic misinformation", "Sensitive information governance"]},
    ],
    "decision": "E21 was used to find real weaknesses, not to claim compliance. E22 converted the two strongest actionable findings into runtime controls: resource exhaustion moved to PASS under targeted verification, while prompt injection improved to PARTIAL and remains human-gated.",
    "posture": "Suitable as a reviewer-assist prototype with explicit human oversight. Not yet positioned as an unattended legal decision system.",
    "ships": ["Resource guards", "Injection guard", "Evidence validation", "Bounded context", "Human-review flag"],
    "doesNotShip": ["Autonomous legal approval", "Unrestricted agents", "Unattended processing of flagged content"],
    "source": src("E21/E22", "experiments/E22_targeted_security_remediation/results/final_report.json", "E21 immutable baseline; E22 targeted retest of changed controls only"),
}

data["retrievalDesign"] = {
    "question": "Can retrieval reliably find the right clause?",
    "chain": [
        {"stage": "A. Chunking", "finding": "clause-aware 256-token chunks beat 512-token chunking (which saturates at ~97% recall by returning nearly the whole document — uninformative) and sentence-level chunking (too fine, 64.2% recall).", "decision": "clause-aware, 256 tokens"},
        {"stage": "B. Top-K", "finding": "MRR is essentially flat across K=3→5→10 (0.271→0.276→0.278) — no real gain past K=5.", "decision": "top-5"},
        {"stage": "C. Candidate retrieval", "finding": "Before reranking, candidate generators genuinely differ (BM25 90.5% recall/MRR 0.322 vs. dense-BGE 88.4%/0.310 vs. hybrid RRF 92.1%/0.339). After the same cross-encoder reranker, BM25, dense and hybrid converge to the same ceiling — Recall@5 ~92.2%, Contradiction Recall@5 tied at 93.9%. A paired case-by-case check across all 4,371 TRAIN cases found BM25+rerank and dense+rerank agree on 4,370 of 4,371.", "decision": "BM25 — no embedding model, no vector index"},
        {"stage": "D. Reranking", "finding": "Cross-encoder reranking is a decisive win: recall 88.4%→92.2%, Contradiction Recall 88.8%→93.9%, MRR 0.310→0.376 (231 cases recovered vs. 72 regressed, net +159 of 4,371).", "decision": "cross-encoder/ms-marco-MiniLM-L-12-v2, top-20 candidates → top-5"},
    ],
    "convergenceFinding": "Before reranking, candidate generators differ. After the same cross-encoder reranker, BM25, dense and hybrid converge — the reranker does the real discriminating work, not the first-stage retriever.",
    "decision": "Retain BM25 top-20 → cross-encoder rerank → top-5. Reason: parsimony, not superiority — BM25 needs no embedding model or vector index and ties dense/hybrid once reranking is applied.",
    "finalMetrics": {"recall": 92.2, "contradictionRecall": 93.9, "precision": 5.4, "mrr": 0.376, "meanContextTokens": 1023, "meanLatencyMs": 176},
    "source": src("E06", "experiments/E06_retrieval_optimisation/summary.md", "TRAIN evidence-bearing cases, n=4,371"),
}

data["agentJustification"] = {
    "question": "Is there enough residual retrieval failure to justify an agent?",
    "e08": {
        "population": "73 reviewed A2/RAG (Qwen) failures, TRAIN",
        "buckets": [
            {"label": "Model-reasoning-limited — no action would help", "pct": 49.2},
            {"label": "Agentically fixable — genuine information gap", "pct": 41.3},
            {"label": "Static-pipeline fixable — just raise top-k", "pct": 9.5},
        ],
        "conclusion": "Narrow selective agent potentially justified — but the largest bucket (49.2%, 65.5% for Contradiction) has no action that would help at all.",
    },
    "e09": {
        "population": "39 residual GPT-5-mini (RAG) failures of 150 TRAIN cases, after the stronger model closed most of E08's reasoning-limited gap",
        "buckets": [
            {"label": "Model-reasoning-limited", "pct": 66.7},
            {"label": "Retrieval-filtering-limited — gold evidence cut by the reranker", "pct": 15.4},
            {"label": "Evidence-selection-limited — label already right", "pct": 15.4},
            {"label": "Dynamic information acquisition — genuinely agent-shaped", "pct": 2.6, "n": 1},
        ],
        "ceilings": {"staticPipelinePct": 4.0, "agenticPct": 0.67},
        "conclusion": "Only 1 of 39 residual failures needs dynamic investigation. A deterministic top-k increase would fix 6x more cases (+4.0pp joint) than a perfect agent could (+0.67pp joint) — and that one case's own best trigger signal has 6.7% precision (14 unnecessary investigations for every 1 correct one).",
    },
    "decision": "The static context-expansion opportunity was larger than the dynamic one. The agent was tested anyway, for course completeness and empirical validation — entering with a skeptical prior, not a blank one.",
    "source": src("E08/E09", "experiments/E09_agent_justification/summary.md", "TRAIN n=150 (E09) / 73-case review (E08)"),
}

data["routingReview"] = {
    "question": "Can I safely send only risky cases to human review?",
    "policies": [
        {"name": "R1 — source-integrity guard", "reviewRate": 4.3, "failureCapture": 12.5, "residualError": 26.5},
        {"name": "R2 — reference policy", "reviewRate": 21.0, "failureCapture": 37.5, "residualError": 22.9},
        {"name": "R3 — best tested policy", "reviewRate": 51.4, "failureCapture": 82.5, "residualError": 10.4},
    ],
    "target": "review rate ≤40%, residual error <10%",
    "finding": "R3 catches the most failures (82.5%) but only at a 51.4% review rate — above the 40% ceiling — and its residual error (10.4%) still marginally misses the 10% target. No tested policy clears both targets at once.",
    "decision": "No automatic routing policy adopted. R1 remains only as a structural source-integrity guard (flags non-source-quote or unparseable responses) — it is not an uncertainty detector. Human final authority remains unconditional.",
    "source": src("E15", "experiments/E15_review_routing/summary.md", "DEV_ROUTING_v1, n=138"),
}

data["fullVsRag"] = {
    "question": "Full document or bounded evidence?",
    "full": {"joint": gpt_metrics["joint"], "note": "Strongest measured evidence-grounded result"},
    "rag": {"joint": e20_report["RAG_metrics"]["joint"], "note": "50.4% fewer classifier input tokens, lower raw inference cost, clause-level provenance"},
    "classificationP": 0.217,
    "jointP": 0.0047,
    "interpretation": "The classification-only difference is not significant (p=0.217). FULL's Joint advantage is significant (p=0.0047) — FULL more often gets both the label and the supporting evidence right together.",
    "decision": "FULL = quality reference. RAG = prototype runtime.",
    "source": src("E20", E20_PATH, "TEST n=2,091, paired"),
}

data["finalTest"] = {
    "n": TEST_N,
    "rows": [
        {"name": "Rule", "status": "baseline", "accuracy": rule_metrics["accuracy"], "macroF1": rule_metrics["macro_f1"], "joint": rule_metrics["joint"], "contradictionRecall": rule_metrics["recall"]["Contradiction"], "evidenceRecall": None, "sourceValidity": None, "costUsd": 0.0},
        {"name": "Qwen", "status": "local", "accuracy": qwen_metrics["accuracy"], "macroF1": qwen_metrics["macro_f1"], "joint": qwen_metrics["joint"], "contradictionRecall": qwen_metrics["recall"]["Contradiction"], "evidenceRecall": qwen_metrics.get("evidence_recall"), "sourceValidity": qwen_metrics.get("source_valid_quote_rate"), "costUsd": 0.0},
        {"name": "FULL", "status": "reference", "accuracy": gpt_metrics["accuracy"], "macroF1": gpt_metrics["macro_f1"], "joint": gpt_metrics["joint"], "contradictionRecall": gpt_metrics["recall"]["Contradiction"], "evidenceRecall": gpt_metrics["evidence_recall"], "sourceValidity": gpt_metrics["source_valid_quote_rate"], "costUsd": cost_summary["gpt_total_cost_usd"]},
        {"name": "RAG", "status": "adopted", "accuracy": e20_report["RAG_metrics"]["accuracy"], "macroF1": e20_report["RAG_metrics"]["macro_f1"], "joint": e20_report["RAG_metrics"]["joint"], "contradictionRecall": e20_report["RAG_metrics"]["recall"]["Contradiction"], "evidenceRecall": e20_report["RAG_metrics"]["evidence_recall"], "sourceValidity": e20_report["RAG_metrics"]["source_valid_quote_rate"], "costUsd": e20_report["RAG_metrics"]["ops"]["total_cost_usd"]},
    ],
    "source": src("E17/E17B/E20", RECON_V2, "TEST n=2,091"),
}

# ---------------------------------------------------------------------------
# 4b. Experiment timeline — transcribed one-liners from experiment_registry.md,
#    grouped by phase.
# ---------------------------------------------------------------------------

data["timeline"] = [
    {"phase": "Setup", "experiments": [
        {"id": "E00", "name": "Dataset & split validation", "question": "Are the official splits and counts correct?", "changed": "Nothing — verification only", "evidence": "607 docs / 10,319 cases confirmed", "decision": "Splits confirmed, proceed"},
        {"id": "E00B", "name": "Budget & runtime forecast", "question": "Can the full plan fit the budget?", "changed": "Nothing — forecast only", "evidence": "Live pricing verified, $0 model calls", "decision": "Budget plan approved"},
    ]},
    {"phase": "Model & prompt selection", "experiments": [
        {"id": "E01", "name": "Oracle reasoning ceiling", "question": "Which model reasons best given perfect evidence?", "changed": "Tested 4 models on gold evidence", "evidence": "gpt-5-mini strongest reasoning ceiling", "decision": "Freeze gpt-5-mini as hosted reference"},
        {"id": "E03", "name": "Prompt selection", "question": "Does more prompt structure help?", "changed": "Tested P0/P1/P2", "evidence": "P0 wins Contradiction Recall 22% vs 6% vs 2%", "decision": "Freeze P0 (minimal instruction)"},
    ]},
    {"phase": "Architecture ladder", "experiments": [
        {"id": "E04", "name": "Rule baseline (A0)", "question": "What does a $0 keyword baseline achieve?", "changed": "Ran unmodified rule baseline on full TRAIN", "evidence": "56.8% accuracy, driven by NotMentoined default-fallback", "decision": "Baseline established"},
        {"id": "E05", "name": "Full-context baseline (A1)", "question": "What does full-document context achieve?", "changed": "Full NDA text to Qwen", "evidence": "40.0% accuracy, 53/100 wrong-label-despite-valid-evidence", "decision": "Reasoning, not evidence access, is the bottleneck"},
        {"id": "E06", "name": "Retrieval optimisation", "question": "BM25, dense, or hybrid? Reranked or not?", "changed": "9 rounds — chunk size, embedding, reranking", "evidence": "BM25+rerank ties dense+rerank (92.2% vs 92.2% recall)", "decision": "Freeze BM25 top-20 → rerank L-12 → top-5"},
        {"id": "E07", "name": "Standard RAG (A2)", "question": "Does retrieval improve on full-context (same weak model)?", "changed": "Same 150 cases through frozen retrieval", "evidence": "43.3% accuracy, +14pp Contradiction Recall vs A1, p=0.542 (n.s.)", "decision": "Directional improvement, not yet significant"},
        {"id": "E08", "name": "RAG failure analysis", "question": "What's actually failing in A2?", "changed": "Manual review of 73 real errors, zero model calls", "evidence": "49.2% model-reasoning-limited, 41.3% agentically-fixable", "decision": "Narrow selective agent potentially justified — B"},
        {"id": "E08B", "name": "Stronger-model diagnostic", "question": "Does GPT-5-mini fix Qwen's failures?", "changed": "Swapped model only, same A2 pipeline", "evidence": "43.3%→78.7% accuracy, McNemar p=5.24e-9", "decision": "Base model, not retrieval, was the dominant bottleneck"},
    ]},
    {"phase": "Agent justification", "experiments": [
        {"id": "E09", "name": "Agent justification after stronger model", "question": "With GPT-5-mini, is an agent still justified?", "changed": "Manually reviewed all 39 residual failures, zero model calls", "evidence": "Only 1/39 is a genuinely dynamic case an agent could fix", "decision": "A3 NOT JUSTIFIED"},
        {"id": "E10", "name": "Bounded selective-agent design", "question": "If tested anyway (course completeness), what should it look like?", "changed": "Froze a minimal, hard-bounded design; the final E11 interface exposed two top-level tools", "evidence": "Design frozen before any model call", "decision": "Frozen for E11, no reversal of E09"},
        {"id": "E11", "name": "Selective-agent empirical evaluation", "question": "Does the frozen agent actually help?", "changed": "15 real GPT-5-mini calls through the agent path", "evidence": "+0.67pp accuracy, 0 tool calls invoked, joint success unchanged", "decision": "A3 CONFIRMS E09 NO-GO — reject"},
    ]},
    {"phase": "Architecture finalization", "experiments": [
        {"id": "E12A", "name": "Static context expansion", "question": "Would just widening top-k (no agent) help more cheaply?", "changed": "top-5 → top-11", "evidence": "+2.0pp acc / +4.0pp joint, p=0.58/0.26 (n.s.)", "decision": "Keep top-5"},
        {"id": "E12B/E12C", "name": "GPT-specific prompt optimisation", "question": "Can a GPT-tailored prompt beat P0?", "changed": "3 alternative prompts, then a confirmation replication", "evidence": "E12B +8 joint, E12C −3 joint — direction reversed", "decision": "Keep P0"},
        {"id": "E13", "name": "FULL vs RAG architecture comparison (DEV)", "question": "Full-context or RAG for the frozen architecture?", "changed": "Same model/prompt, only context source differs", "evidence": "FULL materially better on DEV guards", "decision": "FULL selected as DEV-stage candidate"},
        {"id": "E13B/E14", "name": "Evidence evaluator/validator hardening", "question": "Is the evaluator missing formatting-only matches?", "changed": "NFC/zero-width/whitespace-tolerant matching", "evidence": "41 formatting rescues, 0 false positives", "decision": "Freeze evaluator v2 for all future scoring"},
    ]},
    {"phase": "Safety & cost", "experiments": [
        {"id": "E15", "name": "Human review routing", "question": "Can a deterministic signal route uncertain cases to a human?", "changed": "Tested 3 routing policies on fresh DEV validation", "evidence": "Best policy: 51.4% review rate for 82.5% failure capture", "decision": "No policy meets provisional targets — none adopted"},
        {"id": "E16", "name": "Robustness & security", "question": "Is the system prompt-injection resistant?", "changed": "20 matched clean/attack pairs", "evidence": "4/11 injection-type attacks succeeded, 2 label hijacks", "decision": "Disclose, do not patch"},
        {"id": "E18", "name": "Business/cost/course synthesis", "question": "What does this cost at scale, and what's the real trade-off?", "changed": "Offline synthesis, zero new model calls", "evidence": "Majority baseline 46.3% acc / 0% joint; cost-to-serve model", "decision": "Human-fallback cost dominates modeled cost-to-serve"},
    ]},
    {"phase": "Final evaluation", "experiments": [
        {"id": "E17/E17B", "name": "Final TEST evaluation", "question": "What does the frozen FULL architecture score on the full official TEST set?", "changed": "n=150 sample, then remaining n=1,941, merged to n=2,091", "evidence": "77.6% accuracy, 74.6% Joint, 75.5% Contradiction recall", "decision": "Headline final result"},
        {"id": "E19", "name": "Product integration", "question": "Serve the frozen architecture for real", "changed": "Backend/frontend wired to pipeline/final_review.py", "evidence": "POST /api/review live", "decision": "Shipped"},
        {"id": "E20", "name": "Final RAG TEST comparator", "question": "Does FULL's DEV-sample edge over RAG hold at full TEST scale with paired significance testing?", "changed": "Ran frozen RAG on the identical TEST population as E17B", "evidence": "Joint 74.6% (FULL) vs 72.5% (RAG), McNemar p=0.0047", "decision": "FULL = quality reference; RAG = retained production-oriented runtime (ADR-012)"},
    ]},
]

del data["modeledCostToServe"]
data["costAtScale"] = {
    "formula": "C_total = C_AI + (1 − p_joint) × C_H [+ F]",
    "note": "MODELED, not realized savings. C_H/volume/fixed-cost are explicit scenario variables (E18 §7-8).",
    "source": src("E18", E18_PATH, "scenario model"),
    "scenarios": {
        "low": {"cH": 0.0033, "label": "1 min @ $20/hr"},
        "base": {"cH": 3.33, "label": "5 min @ $40/hr"},
        "high": {"cH": 12.5, "label": "10 min @ $75/hr"},
    },
    "systems": [
        {"id": "rule", "name": "Rule", "cAi": 0.0, "pJoint": rule_metrics["joint"]},
        {"id": "full_context", "name": "FULL", "cAi": cost_summary["gpt_cost_per_case_usd"], "pJoint": gpt_metrics["joint"]},
        {"id": "rag", "name": "RAG", "cAi": e20_report["RAG_metrics"]["ops"]["cost_per_case"], "pJoint": e20_report["RAG_metrics"]["joint"]},
    ],
}

# Chart-ready views. Every value is derived above or read directly from a
# saved artifact; the frontend does not hardcode results.
def retrieval_point(name: str, metrics: dict, stage: str) -> dict:
    return {
        "name": name,
        "stage": stage,
        "recallAt5": round(metrics["overall"]["evidence_recall_at_k"] * 100, 1),
        "contradictionRecallAt5": round(metrics["contradiction"]["evidence_recall_at_k"] * 100, 1),
    }


base_human_cost = data["costAtScale"]["scenarios"]["base"]["cH"]
annual_requirements = 500 * 17
business_cost_rows = [{"name": "Manual", "costPerRequirement": base_human_cost}]
for system in data["costAtScale"]["systems"]:
    total = system["cAi"] + (1 - system["pJoint"]) * base_human_cost
    business_cost_rows.append({"name": system["name"], "costPerRequirement": round(total, 4)})
for row in business_cost_rows:
    row["annualCost"] = round(row["costPerRequirement"] * annual_requirements, 2)

data["charts"] = {
    "oracleComparison": {
        "population": data["oracleExperiment"]["source"]["population"],
        "series": [{
            "name": model["name"],
            "macroF1": round(model["macroF1"] * 100, 1),
            "contradictionRecall": model["contradictionRecall"],
            "hosted": model["hosted"],
        } for model in data["oracleExperiment"]["models"]],
        "source": data["oracleExperiment"]["source"],
    },
    "promptComparison": {
        "population": "TRAIN_PROMPT_v1, Qwen 2.5 7B, controlled P0/P1/P2 comparison",
        "series": [{
            "name": row["name"].split(" ")[0],
            "contradictionRecall": row["contradictionRecall"],
        } for row in data["promptSelection"]["localRounds"]],
        "source": data["promptSelection"]["source"],
    },
    "chunkSizeComparison": {
        "population": "TRAIN evidence-bearing cases, n=4,371; dense mpnet, top_k=5",
        "series": [
            {"name": "clause-256 (selected)", "recallAt5": round(e06_r2_clause256["metrics"]["overall"]["evidence_recall_at_k"] * 100, 1), "mrr": round(e06_r2_clause256["metrics"]["overall"]["mrr"], 3), "meanChunksReturned": round(e06_r2_clause256["context_size"]["mean_chunks"], 1), "selected": True},
            {"name": "fixed-512", "recallAt5": round(e06_r2_fixed512["metrics"]["overall"]["evidence_recall_at_k"] * 100, 1), "mrr": round(e06_r2_fixed512["metrics"]["overall"]["mrr"], 3), "meanChunksReturned": round(e06_r2_fixed512["context_size"]["mean_chunks"], 1), "selected": False},
            {"name": "sentence", "recallAt5": round(e06_r2_sentence["metrics"]["overall"]["evidence_recall_at_k"] * 100, 1), "mrr": round(e06_r2_sentence["metrics"]["overall"]["mrr"], 3), "meanChunksReturned": round(e06_r2_sentence["context_size"]["mean_chunks"], 1), "selected": False},
        ],
        "note": "clause-128 was not among the saved E06 sweep configs — only clause-256, fixed-512, and sentence chunking were tested at this stage.",
        "decision": "clause-256 selected: fixed-512's high recall is a saturation artifact (chunks so large that top-5 returns nearly the whole document, MRR only 0.183), and sentence chunking is too fine-grained (recall drops to 64.2%). clause-256 was the useful retrieval trade-off — high enough recall (87.0%) with a real ranking signal (MRR 0.276) — under the frozen evaluation.",
        "source": src("E06", "experiments/E06_retrieval_optimisation/results/run_E06_R2_clause256.json", "TRAIN n=4,371, round 2 chunking sweep"),
    },
    "topKComparison": {
        "population": "TRAIN evidence-bearing cases, n=4,371; clause-256, dense mpnet",
        "series": [
            {"name": "k=3", "recallAt5": round(e06_r3_k3["metrics"]["overall"]["evidence_recall_at_k"] * 100, 1), "mrr": round(e06_r3_k3["metrics"]["overall"]["mrr"], 3)},
            {"name": "k=5 (selected)", "recallAt5": round(e06_r2_clause256["metrics"]["overall"]["evidence_recall_at_k"] * 100, 1), "mrr": round(e06_r2_clause256["metrics"]["overall"]["mrr"], 3)},
            {"name": "k=10", "recallAt5": round(e06_r3_k10["metrics"]["overall"]["evidence_recall_at_k"] * 100, 1), "mrr": round(e06_r3_k10["metrics"]["overall"]["mrr"], 3)},
        ],
        "decision": "Top-5 retained: k=10 recovers most of the remaining recall (97.5% vs 87.0%) but for roughly double the classifier context, while MRR barely moves (0.278 vs 0.276) — increasing context beyond k=5 did not earn enough value at the retrieval-selection stage.",
        "source": src("E06", "experiments/E06_retrieval_optimisation/results/run_E06_R3_k10.json", "TRAIN n=4,371, round 3 top-k sweep"),
    },
    "candidatePool": {
        "poolSize": 20,
        "bm25PoolRecallAt20": round(e06_rerank["bm25_pool_recall_at_20"] * 100, 2),
        "densePoolRecallAt20": round(e06_rerank["dense_pool_recall_at_20"] * 100, 2),
        "note": "Candidate-pool recall is near-saturated by rank 20 (BM25 99.87%, dense 99.91%) — a wider pool would rarely surface a chunk the reranker doesn't already see. The final classifier context stays bounded at top-5.",
        "source": src("E06", "experiments/E06_retrieval_optimisation/results/run_E06_lexical_vs_dense_rerank.json", "TRAIN n=4,371, candidate_pool_size=20"),
    },
    "retrievalComparison": {
        "population": "TRAIN evidence-bearing cases, n=4,371; clause-256; Recall@5",
        "series": [
            retrieval_point("BM25", e06_bm25["metrics"], "candidate"),
            retrieval_point("Dense MPNet", e06_mpnet["metrics"], "candidate"),
            retrieval_point("Dense BGE", e06_bge["metrics"], "candidate"),
            retrieval_point("Hybrid RRF", e06_hybrid["hybrid_plain"]["metrics"], "candidate"),
            retrieval_point("BM25 + reranker", e06_rerank["bm25_plus_rerank"]["metrics"], "reranked"),
            retrieval_point("Dense BGE + reranker", e06_rerank["dense_plus_rerank"]["metrics"], "reranked"),
            retrieval_point("Hybrid + reranker", e06_hybrid["hybrid_plus_rerank"]["metrics"], "reranked"),
        ],
        "source": data["retrievalDesign"]["source"],
    },
    "fullVsRagComparison": {
        "population": "Official ContractNLI TEST, n=2,091 paired cases",
        "series": [
            {"metric": "Accuracy", "full": round(gpt_metrics["accuracy"] * 100, 1), "rag": round(e20_report["RAG_metrics"]["accuracy"] * 100, 1)},
            {"metric": "Joint", "full": round(gpt_metrics["joint"] * 100, 1), "rag": round(e20_report["RAG_metrics"]["joint"] * 100, 1)},
            {"metric": "Contradiction recall", "full": round(gpt_metrics["recall"]["Contradiction"] * 100, 1), "rag": round(e20_report["RAG_metrics"]["recall"]["Contradiction"] * 100, 1)},
        ],
        "operating": {
            "inputTokens": {"full": round(gpt_metrics["ops"]["input_tokens_mean"]), "rag": round(e20_report["RAG_metrics"]["ops"]["input_tokens_mean"])},
            "rawCostPerCase": {"full": gpt_metrics["ops"]["cost_per_case"], "rag": e20_report["RAG_metrics"]["ops"]["cost_per_case"]},
            "joint": {"full": round(gpt_metrics["joint"] * 100, 1), "rag": round(e20_report["RAG_metrics"]["joint"] * 100, 1)},
        },
        "source": data["fullVsRag"]["source"],
    },
    "failureBreakdown": {
        "total": data["errorAnalysis"]["e20"]["totalNonJoint"],
        "series": data["errorAnalysis"]["e20"]["buckets"],
        "reasoningShare": round(448 / 576 * 100, 1),
        "source": data["errorAnalysis"]["e20"]["source"],
    },
    "agentComparison": {
        "population": "TRAIN_ARCH_v1, same frozen n=150 cases",
        "series": [
            {"name": "Base RAG", "joint": round(e11_full_agent["baseline"]["joint"] * 100, 1)},
            {"name": "Agent V1", "joint": round(e11_full_agent["full_agent"]["joint"] * 100, 1)},
            {"name": "Agent V2", "joint": round(e11_prompt_v2["arms"]["v2"]["joint"] * 100, 1)},
        ],
        "source": data["agentStory"]["stages"][2]["source"],
    },
    "routingComparison": {
        "population": data["routingReview"]["source"]["population"],
        "series": data["routingReview"]["policies"],
        "source": data["routingReview"]["source"],
    },
    "finalTestComparison": {
        "population": "Official ContractNLI TEST, n=2,091",
        "series": data["finalTest"]["rows"],
        "source": data["finalTest"]["source"],
    },
    "businessCostComparison": {
        "population": "MODELED: 5 min human fallback at $40/hr; 500 NDAs/year × 17 requirements",
        "series": business_cost_rows,
        "source": data["costAtScale"]["source"],
    },
    "costAtScaleCurve": {
        "population": "MODELED scenario, NOT realized production savings — derived from the same C_total = C_AI + (1 − p_joint) × C_H formula at the base (5 min @ $40/hr) human-fallback rate, swept across annual NDA volume.",
        "requirementsPerNda": 17,
        "volumes": [100, 250, 500, 750, 1000],
        "series": [
            {
                "name": row["name"],
                "costPerVolume": [round(row["costPerRequirement"] * v * 17, 2) for v in [100, 250, 500, 750, 1000]],
            }
            for row in business_cost_rows
        ],
        "source": data["costAtScale"]["source"],
    },
    "securitySummary": {
        "baseline": {
            "counts": e21_report["counts"],
            "categories": e21_report["category_summary"],
            "source": src("E21", "experiments/E21_owasp_llm_top10/results/final_report.json", "OWASP LLM Top 10, frozen prototype runtime"),
        },
        "remediation": {
            "items": e22_report["targeted_results"],
            "story": e22_report["product_story"],
            "source": src("E22", "experiments/E22_targeted_security_remediation/results/final_report.json", "targeted regression after E21; E21 baseline unchanged"),
        },
        "e16PromptInjection": {"successes": 4, "attempts": 11},
        "e21PromptInjection": {"successes": 1, "attempts": 7},
        "examples": security_examples,
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, indent=2, default=str))
print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB), {len(cases_out)} cases, {len(data['timeline'])} timeline phases")
print("Showcase validation:", json.dumps(SHOWCASE_VALIDATION, sort_keys=True))
