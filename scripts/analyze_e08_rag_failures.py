#!/usr/bin/env python3
"""
E08 RAG failure analysis (reconstruction-v2) -- diagnostic only, evaluator-side, zero LLM calls.

Reads ONLY E07's already-saved outputs (no reruns) plus one read-only, deterministic re-query
of the already-cached retrieval_v1 index (BM25 search + cross-encoder rerank -- both LOCAL,
non-LLM models already used throughout E06/E07 for identical diagnostic purposes; retrieval_v1
itself is never modified). Never calls Qwen/GPT-5-mini/Gemini.

Terminology (per explicit correction): `source_valid_evidence` (the existing evidence
validator's finding -- quote is verbatim, present in the shown context, structurally valid) is
kept strictly distinct from `gold_evidence_overlap` (does the quote's location actually overlap
the true annotated gold span). E07's "evidence_valid" field is renamed here to
`source_valid_evidence` for clarity; it was never a claim of correctness.

Produces the full case-level diagnostic record for the deterministic 73-case manual-review
union (retrieval-limited ALL + Contradiction failures ALL + wrong-label/source-valid-evidence
ALL + a fixed E05/E07-transition sample not already covered), classified into the refined
taxonomy: STATIC_PIPELINE_FIXABLE / AGENTICALLY_FIXABLE / MODEL_REASONING_LIMITED /
EVIDENCE_SELECTION_LIMITED / OUTPUT_FORMAT_LIMITED / AMBIGUOUS_MIXED, each further resolved into
the 4 quantification buckets used for the final A/B/C agent-justification decision.
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.reranker import rerank as cross_encoder_rerank  # noqa: E402
from pipeline.retriever import RetrievalResult  # noqa: E402
from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

E07_DIR = REPO / "experiments/E07_standard_rag"
E05_DIR = REPO / "experiments/E05_full_context"
E08_DIR = REPO / "experiments/E08_rag_failure_analysis"
RESULTS_DIR = E08_DIR / "results"

RETRIEVAL_V1 = dict(method="bm25", chunk_method="clause", chunk_size=256, chunk_overlap=50,
                     embedding_model=None)
CANDIDATE_POOL_SIZE = 20

EXCEPTION_KEYWORDS = ("except", "provided that", "unless", "notwithstanding", "other than",
                      "carve-out", "carve out")
CROSS_REF_PATTERN = re.compile(
    r"\b(Section|Article|Exhibit|Schedule|Paragraph|Clause|Appendix)\s+\d+", re.IGNORECASE)
DEFINED_TERM_PATTERN = re.compile(r'"([A-Z][A-Za-z ]{2,40})"')
DEFINITION_INTRO_PATTERN = re.compile(r'\b(means|shall mean|defined as|refers to)\b', re.IGNORECASE)


def load_json(path):
    return json.load(open(path))


def load_cases_and_context():
    cases = {json.loads(l)["case_id"]: json.loads(l)
             for l in open(E07_DIR / "results/run_E07_A2_train_cases.jsonl")}
    e05 = {json.loads(l)["case_id"]: json.loads(l)
           for l in open(E05_DIR / "results/run_E05_A1_train_cases.jsonl")}
    gold = {c["case_id"]: c for c in load_json(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json")["cases"]}
    retrieved = {c["case_id"]: c for c in load_json(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json")["cases"]}
    manifest = {c["case_id"]: c for c in load_json(E05_DIR / "TRAIN_ARCH_v1.json")["cases"]}
    train = load_json(REPO / "data/contractnli/train.json")
    doc_lookup = {d["id"]: d for d in train["documents"]}
    return cases, e05, gold, retrieved, manifest, doc_lookup


def evidence_to_span_indices(evidence, chunk_texts, chunk_offsets, doc_spans):
    indices = set()
    for quote in evidence:
        if not quote:
            continue
        for chunk_text, (c_start, c_end) in zip(chunk_texts, chunk_offsets):
            pos = chunk_text.find(quote)
            if pos == -1:
                continue
            a_start, a_end = c_start + pos, c_start + pos + len(quote)
            for idx, (s_start, s_end) in enumerate(doc_spans):
                if min(s_end, a_end) > max(s_start, a_start):
                    indices.add(idx)
    return indices


def runtime_signals(chunk_texts: list[str], hypothesis: str) -> dict:
    joined = " ".join(chunk_texts)
    cross_ref = bool(CROSS_REF_PATTERN.search(joined))
    exception_cue = any(k in joined.lower() for k in EXCEPTION_KEYWORDS)
    defined_terms = set(DEFINED_TERM_PATTERN.findall(joined))
    defined_term_missing = False
    for term in defined_terms:
        # crude check: is there a "term ... means/shall mean" pattern within the SAME retrieved text
        term_def_present = bool(re.search(
            re.escape(term) + r'["\']?\s*(shall\s+)?(means|shall mean|defined as|refers to)',
            joined, re.IGNORECASE))
        if not term_def_present:
            defined_term_missing = True
            break
    return {
        "cross_reference_cue": cross_ref,
        "exception_carveout_cue": exception_cue,
        "defined_term_missing_cue": defined_term_missing,
    }


def score_margin(rerank_scores: list[float]) -> float | None:
    if not rerank_scores or len(rerank_scores) < 2:
        return None
    return rerank_scores[0] - rerank_scores[-1]


def find_gold_chunk_text(chunk_texts: list[str], chunk_offsets: list[list[int]],
                          gold_span_idx: list[int], doc_spans: list[list[int]]) -> str | None:
    """Returns the text of whichever retrieved chunk actually overlaps the gold span -- used to
    check runtime signals SPECIFICALLY on the chunk that should have been used, not the whole
    5-chunk context (checking the whole context makes cross-reference/exception/defined-term
    cues fire on nearly every case, since NDAs reference other sections constantly -- a real,
    disclosed over-triggering risk this function exists to avoid)."""
    if not gold_span_idx:
        return None
    gold_char_spans = [doc_spans[i] for i in gold_span_idx]
    for chunk_text, (c_start, c_end) in zip(chunk_texts, chunk_offsets):
        for gs, ge in gold_char_spans:
            if min(c_end, ge) > max(c_start, gs):
                return chunk_text
    return None


def main() -> int:
    cases, e05, gold, retrieved, manifest, doc_lookup = load_cases_and_context()
    doc_spans_by_doc = {did: d["spans"] for did, d in doc_lookup.items()}

    # --- Recompute retrieval_contains_gold and gold_evidence_overlap for every case (terminology fix) ---
    diag = {}
    for cid, c in cases.items():
        g = gold[cid]
        rc = retrieved[cid]
        doc_spans = doc_spans_by_doc[c["document_id"]]
        gold_span_idx = g["gold_span_indices"]

        contains_gold = None
        if gold_span_idx:
            gold_char_spans = [doc_spans[i] for i in gold_span_idx]
            contains_gold = any(
                gs < ce and ge > cs
                for gs, ge in gold_char_spans
                for cs, ce in rc["ranked_chunk_offsets"]
            )

        overlap_idx = evidence_to_span_indices(c.get("evidence") or [], rc["ranked_chunk_text"],
                                                rc["ranked_chunk_offsets"], doc_spans)
        gold_evidence_overlap = bool(set(gold_span_idx) & overlap_idx) if gold_span_idx else None

        diag[cid] = {
            "retrieval_contains_gold": contains_gold,
            "gold_evidence_overlap": gold_evidence_overlap,
            "source_valid_evidence": c.get("evidence_valid"),  # renamed, same underlying value
        }

    # --- Build the deterministic manual-review union ---
    retrieval_limited = sorted(cid for cid, c in cases.items()
                                if c["gold_label"] != c["predicted_label"]
                                and diag[cid]["retrieval_contains_gold"] is False)
    contradiction_failures = sorted(cid for cid, c in cases.items()
                                     if c["gold_label"] == "Contradiction" and c["predicted_label"] != "Contradiction")
    wrong_valid_all = sorted(cid for cid, c in cases.items()
                              if c["gold_label"] in ("Entailment", "Contradiction")
                              and c["predicted_label"] != c["gold_label"]
                              and diag[cid]["source_valid_evidence"] is True)

    mandatory = set(retrieval_limited) | set(contradiction_failures) | set(wrong_valid_all)

    e05_gain = sorted(cid for cid, c in cases.items()
                       if e05[cid]["predicted_label"] != e05[cid]["gold_label"]
                       and c["predicted_label"] == c["gold_label"])
    e05_regress = sorted(cid for cid, c in cases.items()
                          if e05[cid]["predicted_label"] == e05[cid]["gold_label"]
                          and c["predicted_label"] != c["gold_label"])
    gain_new = [c for c in e05_gain if c not in mandatory]
    regress_new = [c for c in e05_regress if c not in mandatory]

    rng = random.Random(1000)
    sample_gain = sorted(rng.sample(gain_new, min(10, len(gain_new))))
    sample_regress = sorted(rng.sample(regress_new, min(10, len(regress_new))))

    review_union = sorted(mandatory | set(sample_gain) | set(sample_regress))
    print(f"Manual-review union: {len(review_union)} unique cases "
          f"(mandatory={len(mandatory)}, +{len(sample_gain)} gain sample, "
          f"+{len(sample_regress)} regression sample)")

    # --- Reranker-limited diagnostic for the 6 retrieval-limited cases (real, deterministic re-query) ---
    reranker_diag = {}
    for cid in retrieval_limited:
        c = manifest[cid]
        g = gold[cid]
        doc = doc_lookup[c["document_id"]]
        gold_span_idx = g["gold_span_indices"]
        if not gold_span_idx:
            continue
        gold_char_spans = [doc["spans"][i] for i in gold_span_idx]
        chunks, index = build_or_load_index(c["document_id"], doc["text"], **RETRIEVAL_V1)
        hits20 = index.search(c["hypothesis_text"], top_k=CANDIDATE_POOL_SIZE)

        def find_rank(scored_items):
            for rank, item in enumerate(scored_items, 1):
                chunk = item[0] if isinstance(item, tuple) else item.chunk
                if any(min(chunk.end_char, ge) > max(chunk.start_char, gs) for gs, ge in gold_char_spans):
                    return rank
            return None

        bm25_rank = find_rank(hits20)
        candidates = [RetrievalResult(chunk=ch, score=s) for ch, s in hits20]
        reranked20 = cross_encoder_rerank(c["hypothesis_text"], candidates, top_k=CANDIDATE_POOL_SIZE)
        rerank_rank = find_rank(reranked20)
        reranker_diag[cid] = {
            "bm25_top20_rank": bm25_rank, "post_rerank_rank_of_20": rerank_rank,
            "static_fix_k_needed": rerank_rank,
            "would_top10_include": rerank_rank is not None and rerank_rank <= 10,
        }

    # --- Full case-level classification for the review union ---
    rows = []
    for cid in review_union:
        c = cases[cid]
        rc = retrieved[cid]
        d = diag[cid]
        correct = c["gold_label"] == c["predicted_label"]
        sig = runtime_signals(rc["ranked_chunk_text"], "")  # whole-context signal (used only for Group A / reranker branches)
        gold_chunk_text = find_gold_chunk_text(rc["ranked_chunk_text"], rc["ranked_chunk_offsets"],
                                                gold[cid]["gold_span_indices"],
                                                doc_spans_by_doc[c["document_id"]])
        # Stricter, gold-chunk-specific signal for EVIDENCE_SELECTION_LIMITED cases -- checking
        # the WHOLE 5-chunk context over-triggers (NDAs reference other sections constantly).
        gold_chunk_sig = runtime_signals([gold_chunk_text], "") if gold_chunk_text else \
            {"cross_reference_cue": False, "exception_carveout_cue": False, "defined_term_missing_cue": False}
        margin = score_margin(rc["ranked_chunk_rerank_scores"])
        low_margin = margin is not None and margin < 1.0

        rerank_info = reranker_diag.get(cid, {})
        static_fix_k = rerank_info.get("static_fix_k_needed")

        # --- Classification decision tree ---
        failure_primary = None
        oracle_action_needed = "none_identified"
        oracle_action_target = None
        static_fix_possible = False
        dynamic_action_required = False
        recoverable_in_principle = False

        if correct:
            failure_primary = "n/a (correct)"
        elif c["parse_status"] == "invalid":
            failure_primary = "OUTPUT_FORMAT_LIMITED"
        elif cid in reranker_diag:
            # Reranker/filtering-limited: gold was in the BM25 top-20 candidate pool but the
            # cross-encoder demoted it below the frozen top-5 cutoff.
            if static_fix_k is not None:
                failure_primary = "STATIC_PIPELINE_FIXABLE"
                oracle_action_needed = "expand_candidate_window"
                oracle_action_target = f"increase final top-k to >= {static_fix_k}"
                static_fix_possible = True
                recoverable_in_principle = True
            else:
                failure_primary = "AGENTICALLY_FIXABLE"
                oracle_action_needed = "expand_candidate_set"
                oracle_action_target = "gold not found even in BM25 top-20 -- needs a re-query, not just a larger K"
                dynamic_action_required = True
                recoverable_in_principle = True
        elif d["gold_evidence_overlap"] is True:
            # Group A: model's OWN returned evidence overlaps gold, but the label is still wrong.
            # Signal checked on the GOLD CHUNK ITSELF (gold_chunk_sig), not the whole 5-chunk
            # context -- checking the whole context over-triggers, since NDAs reference other
            # sections constantly even in unrelated chunks (disclosed methodology fix, see
            # find_gold_chunk_text's docstring).
            if gold_chunk_sig["cross_reference_cue"] or gold_chunk_sig["defined_term_missing_cue"]:
                failure_primary = "AGENTICALLY_FIXABLE"
                oracle_action_needed = "follow_cross_reference" if gold_chunk_sig["cross_reference_cue"] else "retrieve_definition"
                oracle_action_target = "the gold-relevant chunk itself references another section/definition not in the retrieved context"
                dynamic_action_required = True
                recoverable_in_principle = True
            else:
                failure_primary = "MODEL_REASONING_LIMITED"
                oracle_action_needed = "none_identified"
                recoverable_in_principle = False
        elif d["gold_evidence_overlap"] is False and d["retrieval_contains_gold"] is True:
            # Group B: gold WAS in the top-5 context, but the model quoted a different chunk.
            # Signal checked on the GOLD CHUNK (the one that should have been used), same
            # over-triggering rationale as Group A above.
            failure_primary = "EVIDENCE_SELECTION_LIMITED"
            if gold_chunk_sig["cross_reference_cue"] or gold_chunk_sig["exception_carveout_cue"] or gold_chunk_sig["defined_term_missing_cue"]:
                oracle_action_needed = ("search_exception" if gold_chunk_sig["exception_carveout_cue"] else
                                        "follow_cross_reference" if gold_chunk_sig["cross_reference_cue"] else
                                        "retrieve_definition")
                oracle_action_target = "the gold-relevant chunk itself contains a disambiguating cue the model's chosen (wrong) chunk lacks"
                dynamic_action_required = True
                recoverable_in_principle = True
                failure_primary = "AGENTICALLY_FIXABLE"  # resolved: D -> B
            else:
                # All 5 candidate chunks were already given to the model; the correct one was
                # among them but not selected. No NEW information would help -- this is a
                # reading/attention failure over already-fully-available options, not an
                # information gap an agent's "retrieve more" mechanism addresses.
                oracle_action_needed = "none_identified"
                recoverable_in_principle = False
                failure_primary = "MODEL_REASONING_LIMITED"  # resolved: D -> C (default)
        elif c["gold_label"] == "NotMentioned":
            failure_primary = "MODEL_REASONING_LIMITED"
            oracle_action_needed = "none_identified"
        else:
            failure_primary = "AMBIGUOUS_MIXED"
            oracle_action_needed = "none_identified"

        quantification_bucket = {
            "STATIC_PIPELINE_FIXABLE": "static_pipeline_fixable",
            "AGENTICALLY_FIXABLE": "agentically_fixable",
            "MODEL_REASONING_LIMITED": "model_reasoning_limited",
            "OUTPUT_FORMAT_LIMITED": "evidence_output_ambiguous_other",
            "AMBIGUOUS_MIXED": "evidence_output_ambiguous_other",
            "n/a (correct)": "n/a (correct)",
        }[failure_primary]

        runtime_observable_signal = ",".join(
            k for k, v in sig.items() if v) or ("low_score_margin" if low_margin else "none")
        if low_margin:
            runtime_observable_signal = (runtime_observable_signal + ",low_score_margin"
                                          if runtime_observable_signal != "none" else "low_score_margin")

        # Secondary tag: the brief's category H (NOTMENTIONED_CONFUSION) is distinct from I
        # (EVIDENCE_SELECTION) -- a model that returns EMPTY evidence and defaults to
        # NotMentioned never engaged with any candidate chunk at all, vs. one that quotes a
        # real-but-wrong chunk. Both can resolve to the same primary bucket (the agent-
        # fixability judgment is the same either way), but the secondary tag preserves which
        # concrete behavior was observed.
        failure_secondary = None
        if not correct and c["predicted_label"] == "NotMentioned" and not (c.get("evidence") or []) \
                and c["gold_label"] in ("Entailment", "Contradiction"):
            failure_secondary = "H_NOTMENTIONED_CONFUSION_empty_evidence"

        rows.append({
            "case_id": cid, "gold_label": c["gold_label"], "predicted_label": c["predicted_label"],
            "correct": correct, "joint_success": c.get("evidence_valid") and correct,
            "retrieval_contains_gold": d["retrieval_contains_gold"],
            "source_valid_evidence": d["source_valid_evidence"],
            "gold_evidence_overlap": d["gold_evidence_overlap"],
            "bm25_top20_rank": rerank_info.get("bm25_top20_rank"),
            "post_rerank_rank_of_20": rerank_info.get("post_rerank_rank_of_20"),
            "would_top10_include": rerank_info.get("would_top10_include"),
            "score_margin": margin,
            "failure_primary": failure_primary,
            "failure_secondary": failure_secondary,
            "quantification_bucket": quantification_bucket,
            "runtime_observable_signal": runtime_observable_signal,
            "oracle_action_needed": oracle_action_needed,
            "oracle_action_target": oracle_action_target,
            "static_fix_possible": static_fix_possible,
            "dynamic_action_required": dynamic_action_required,
            "recoverable_in_principle": recoverable_in_principle,
            "in_e05_gain_sample": cid in sample_gain,
            "in_e05_regress_sample": cid in sample_regress,
            "manually_reviewed": True,
        })

    with open(RESULTS_DIR / "rag_failure_analysis.csv", "w", newline="") as f:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # --- Quantification ---
    error_rows = [r for r in rows if not r["correct"]]
    bucket_counts = Counter(r["quantification_bucket"] for r in error_rows)
    c_error_rows = [r for r in error_rows if r["gold_label"] == "Contradiction"]
    c_bucket_counts = Counter(r["quantification_bucket"] for r in c_error_rows)

    summary = {
        "manual_review_union_size": len(review_union),
        "mandatory_size": len(mandatory),
        "e05_gain_sample": sample_gain, "e05_regress_sample": sample_regress,
        "reranker_diag": reranker_diag,
        "reviewed_error_count": len(error_rows),
        "quantification_overall": dict(bucket_counts),
        "quantification_overall_pct": {k: round(v / len(error_rows) * 100, 1) for k, v in bucket_counts.items()},
        "quantification_contradiction": dict(c_bucket_counts),
        "quantification_contradiction_pct": {k: round(v / len(c_error_rows) * 100, 1) for k, v in c_bucket_counts.items()} if c_error_rows else {},
        "runtime_signal_frequencies": dict(Counter(r["runtime_observable_signal"] for r in error_rows)),
        "notmentioned_confusion_empty_evidence_count": sum(1 for r in error_rows if r["failure_secondary"] == "H_NOTMENTIONED_CONFUSION_empty_evidence"),
        "wrong_valid_group_a_gold_overlap": sum(1 for cid in wrong_valid_all if diag[cid]["gold_evidence_overlap"] is True),
        "wrong_valid_group_b_no_overlap": sum(1 for cid in wrong_valid_all if diag[cid]["gold_evidence_overlap"] is False),
    }
    with open(RESULTS_DIR / "agent_opportunity_quantification.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"wrote {RESULTS_DIR / 'rag_failure_analysis.csv'}")
    print(f"wrote {RESULTS_DIR / 'agent_opportunity_quantification.json'}")
    print(f"quantification overall: {dict(bucket_counts)}")
    print(f"quantification overall pct: {summary['quantification_overall_pct']}")
    print(f"quantification Contradiction: {dict(c_bucket_counts)}")
    print(f"quantification Contradiction pct: {summary['quantification_contradiction_pct']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
