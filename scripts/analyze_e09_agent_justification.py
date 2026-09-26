#!/usr/bin/env python3
"""
E09 Stage B -- final agent-justification analysis over the manually-reviewed 39 GPT joint
failures (experiments/E09_agent_justification/results/residual_review_bundle.json).

The per-case primary-bucket assignment below (MANUAL_TAXONOMY) is the result of a full manual
read of every one of the 39 cases' requirement, GPT prediction/evidence, retrieved top-5 context,
gold label, and gold evidence text (all assembled by scripts/build_e09_residual_review_bundle.py)
-- NOT a heuristic/keyword classifier. Zero model calls anywhere in this script.

Produces: the failure-bucket decomposition, oracle-action fields, runtime-observable-signal
prevalence/precision/recall over all 150 cases, the Static Pipeline Opportunity Ceiling, the
Oracle Agent Opportunity Ceiling, and the whole-population escalation-volume framing.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

E08B_DIR = REPO / "experiments/E08B_stronger_model_diagnostic"
E07_DIR = REPO / "experiments/E07_standard_rag"
E09_DIR = REPO / "experiments/E09_agent_justification"
BUNDLE_PATH = E09_DIR / "results/residual_review_bundle.json"
OUT_CSV = E09_DIR / "results/gpt_residual_failure_analysis.csv"
OUT_SIGNALS = E09_DIR / "results/signal_prevalence_150case.json"
OUT_CEILING = E09_DIR / "results/oracle_agent_opportunity_ceiling.json"
OUT_DECISION = E09_DIR / "results/e09_decision.json"

# =============================================================================
# Manual taxonomy -- assigned by direct reading of every case's requirement, GPT evidence,
# retrieved top-5 context, and gold evidence (see summary.md sections 5-8 for the full
# per-case reasoning). Primary bucket + oracle-action fields, one row per case_id.
# =============================================================================
MANUAL_TAXONOMY: dict[str, dict] = {
    # --- Group A: gold=NotMentioned, GPT false positive (11 cases). All read directly: GPT
    # quotes a REAL, verbatim, topically-relevant definitional/exclusion clause and over-
    # generalizes to a specific hypothesis the clause does not actually address. Evidence was
    # present and correctly located -- the failure is inferential specificity, not missing
    # information. 7/11 share hypothesis nda-1 ("expressly identified"); a second cluster-worthy
    # pattern, not independently agentic.
    "train::126::nda-1": dict(bucket="MODEL_REASONING_LIMITED", note="Quotes a real 'circumstances ought to be treated as confidential' definitional clause; over-generalizes to contradict the specific 'expressly identified' marking requirement. Evidence present, verbatim, correctly located.", oracle_action="none"),
    "train::187::nda-1": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-1 pattern: quotes a general 'deemed confidential' definitional clause, treats it as contradicting an explicit-marking requirement it doesn't actually address.", oracle_action="none"),
    "train::278::nda-1": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-1 pattern.", oracle_action="none"),
    "train::279::nda-1": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-1 pattern -- quotes the standard confidentiality-obligation clause, not the marking requirement.", oracle_action="none"),
    "train::320::nda-1": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-1 pattern; one of 3 evidence quotes is a minor non-verbatim paraphrase (source_valid_evidence=False for the case) but the wrong-label driver is the same overgeneralization, not the paraphrase.", oracle_action="none"),
    "train::328::nda-1": dict(bucket="MODEL_REASONING_LIMITED", note="Quotes a broad 'in any manner whatsoever' definition clause; plausible over-read, possibly compounded by a borderline/noisy gold annotation, but evidence was present and real.", oracle_action="none"),
    "train::439::nda-2": dict(bucket="MODEL_REASONING_LIMITED", note="Hypothesis nda-2 ('Confidential Information shall only include technical information') -- GPT over-generalizes from a broad information-category definition to a specific exclusivity claim not actually made.", oracle_action="none"),
    "train::222::nda-3": dict(bucket="MODEL_REASONING_LIMITED", note="Quotes broad category-definition clauses (1.1.1, 1.1.6); over-generalizes to entail 'may include verbally conveyed information' which the clauses don't specifically state.", oracle_action="none"),
    "train::350::nda-10": dict(bucket="MODEL_REASONING_LIMITED", note="Quotes a general non-disclosure-to-third-parties clause; does not actually address disclosing the FACT that the agreement was negotiated -- overgeneralization from topic similarity.", oracle_action="none"),
    "train::379::nda-17": dict(bucket="MODEL_REASONING_LIMITED", note="Quotes 3 general confidentiality/return/legal-disclosure clauses, none of which grant a specific 'may copy' permission -- overgeneralization.", oracle_action="none"),
    "train::94::nda-13": dict(bucket="MODEL_REASONING_LIMITED", note="Quotes the standard third-party-acquired-information exclusion clause -- a genuinely reasonable read that arguably DOES support the hypothesis; likely compounded by borderline gold-label noise (a known ContractNLI annotation-quality issue), not a missing-information problem.", oracle_action="none"),

    # --- Group B: gold=Entailment/Contradiction, gold evidence in the BM25 top-20 candidate
    # pool but cut by the reranker before the final top-5 -- identical to E08's own
    # reranker-limited diagnostic (5 of these 6 are the SAME case_ids E08 found for Qwen; the
    # information gap is architectural, not model-specific, so it persists under GPT too).
    "train::160::nda-10": dict(bucket="RETRIEVAL_FILTERING_LIMITED", note="Gold evidence at BM25 top-20 rank 2, cut by the reranker before top-5 -- same case E08 flagged for Qwen.", oracle_action="expand_final_k"),
    "train::247::nda-10": dict(bucket="RETRIEVAL_FILTERING_LIMITED", note="Gold evidence at BM25 top-20 rank 6, cut before top-5.", oracle_action="expand_final_k"),
    "train::353::nda-10": dict(bucket="RETRIEVAL_FILTERING_LIMITED", note="Gold evidence at BM25 top-20 rank 9, cut before top-5.", oracle_action="expand_final_k"),
    "train::379::nda-10": dict(bucket="RETRIEVAL_FILTERING_LIMITED", note="Gold evidence at BM25 top-20 rank 3, cut before top-5.", oracle_action="expand_final_k"),
    "train::518::nda-10": dict(bucket="RETRIEVAL_FILTERING_LIMITED", note="Gold evidence at BM25 top-20 rank 1 (!), still cut before top-5 by the reranker.", oracle_action="expand_final_k"),
    "train::438::nda-2": dict(bucket="RETRIEVAL_FILTERING_LIMITED", note="GPT's LABEL is correct (Contradiction) but gold evidence (rank 6) was cut before top-5, so joint success fails on evidence recall alone -- correct-label/joint-fail case, retrieval-filtering root cause.", oracle_action="expand_final_k"),

    # --- Group C1: gold present in final top-5, GPT's OWN returned evidence overlaps gold, but
    # the final label is still wrong -- necessary evidence was correctly located and quoted,
    # reasoning over it was wrong. 7/12 share hypothesis nda-17 (confuses general "disclosure"
    # exceptions with a specific "copying" prohibition -- a real semantic distinction the model
    # collapses).
    "train::102::nda-19": dict(bucket="MODEL_REASONING_LIMITED", note="GPT's own quoted evidence overlaps gold; concludes Entailment where the same evidence supports Contradiction. Pure reasoning failure over correctly-identified evidence.", oracle_action="none"),
    "train::141::nda-7": dict(bucket="MODEL_REASONING_LIMITED", note="Same pattern -- correct evidence quoted, wrong conclusion drawn.", oracle_action="none"),
    "train::178::nda-17": dict(bucket="MODEL_REASONING_LIMITED", note="Quotes the flat 'shall not copy without prior written consent' clause (gold evidence) but still concludes Entailment for 'may copy in some circumstances' -- conflates a written-consent exception with a circumstantial one.", oracle_action="none"),
    "train::239::nda-17": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-17 copy-vs-disclose confusion pattern, correct evidence present.", oracle_action="none"),
    "train::248::nda-10": dict(bucket="MODEL_REASONING_LIMITED", note="Correct evidence overlaps gold; label flipped from Entailment to Contradiction anyway -- reasoning error, not missing information.", oracle_action="none"),
    "train::276::nda-17": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-17 pattern.", oracle_action="none"),
    "train::316::nda-17": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-17 pattern.", oracle_action="none"),
    "train::338::nda-17": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-17 pattern.", oracle_action="none"),
    "train::466::nda-15": dict(bucket="MODEL_REASONING_LIMITED", note="Evidence overlaps gold (one quote has a minor non-verbatim variant) but label is wrong -- reasoning error over available evidence, not a retrieval gap.", oracle_action="none"),
    "train::473::nda-17": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-17 pattern.", oracle_action="none"),
    "train::551::nda-20": dict(bucket="MODEL_REASONING_LIMITED", note="Correct evidence quoted, wrong label -- reasoning failure.", oracle_action="none"),
    "train::92::nda-17": dict(bucket="MODEL_REASONING_LIMITED", note="Same nda-17 copy-vs-disclose confusion pattern (also E08B's own worst-case output-token calibration example) -- correct evidence quoted, wrong label.", oracle_action="none"),

    # --- Group C2: gold present in final top-5, but GPT's returned evidence does NOT overlap
    # gold (3/4 return EMPTY evidence and default to NotMentioned despite the relevant clause
    # being shown). One case (273::nda-1) is the single genuine dynamic-information-acquisition
    # candidate found across all 39 cases.
    "train::178::nda-20": dict(bucket="MODEL_REASONING_LIMITED", note="The SAME document/context as train::178::nda-17 (where GPT DID quote the relevant return-clause for a different hypothesis) -- here GPT returns empty evidence and predicts NotMentioned despite the same clause being present. Inconsistent attention across hypotheses on identical context, not missing information.", oracle_action="none"),
    "train::273::nda-1": dict(bucket="DYNAMIC_INFORMATION_ACQUISITION", note="Gold evidence is itself a cross-reference: '\"Target Confidential Information\" means Information falling within paragraphs (a) to (c) of the definition of \"Confidential Information\"' -- resolving this requires locating the referenced (a)-(c) sub-clauses, which may live in a different part of the document than what retrieval surfaced. GPT returned empty evidence/NotMentioned, consistent with not having the referenced text. PASSES all 6 strict agentic criteria: context references an unresolved external definition; the referenced content could change the decision; which paragraphs to fetch is case-specific (document structure varies); a single fixed rule (e.g. always append 'the next N sentences') is not reliable across differently-structured NDAs; the cross-reference wording ('paragraphs (a) to (c) of the definition of X') is a concrete, inference-time-observable signal; and fetching it would change the model's available information.", oracle_action="follow_cross_reference"),
    "train::438::nda-20": dict(bucket="MODEL_REASONING_LIMITED", note="Same document as train::438::nda-2 (in Group B) -- the relevant return/destroy clause for nda-20 IS in the shown top-5, but GPT returns empty evidence/NotMentioned rather than recognizing the mandatory-return language contradicts 'may retain some Confidential Information.'", oracle_action="none"),
    "train::603::nda-15": dict(bucket="MODEL_REASONING_LIMITED", note="GPT's own quoted evidence explicitly references 'paragraph 1.5' by number, and clause 1.5 itself (the actual ownership-retention gold evidence) IS present in the same shown top-5 -- GPT failed to connect its own cross-reference to the clause it was already given, concluding Contradiction instead of Entailment.", oracle_action="none"),

    # --- Group C3: classification correct, joint fails on evidence recall/validity alone --
    # sufficient reasoning to reach the right label occurred; the evidence-selection step is
    # the only failure surface. No case-dependent action needed (the label was already right).
    "train::273::nda-10": dict(bucket="EVIDENCE_SELECTION_LIMITED", note="Correct label; evidence overlaps only part of a multi-span gold answer (below the 0.5 joint threshold) -- a partial-coverage evidence-selection issue, not a missing-information one.", oracle_action="none"),
    "train::317::nda-13": dict(bucket="EVIDENCE_SELECTION_LIMITED", note="Correct label; GPT's quoted evidence is real and source-valid but does not overlap the specific gold span -- picked a different (also plausible) supporting sentence.", oracle_action="none"),
    "train::318::nda-2": dict(bucket="EVIDENCE_SELECTION_LIMITED", note="Correct label; partial gold-span coverage below the 0.5 joint threshold.", oracle_action="none"),
    "train::352::nda-12": dict(bucket="EVIDENCE_SELECTION_LIMITED", note="Correct label; evidence quote has a verbatim/formatting mismatch (source_valid_evidence=False) and does not overlap gold.", oracle_action="none"),
    "train::500::nda-13": dict(bucket="EVIDENCE_SELECTION_LIMITED", note="Correct label; evidence quote not verbatim-valid and does not overlap gold.", oracle_action="none"),
    "train::515::nda-2": dict(bucket="EVIDENCE_SELECTION_LIMITED", note="Correct label; evidence quote not verbatim-valid and does not overlap gold.", oracle_action="none"),
}


def main() -> int:
    bundle = json.load(open(BUNDLE_PATH))
    cases = {c["case_id"]: c for c in bundle["cases"]}
    assert set(cases) == set(MANUAL_TAXONOMY), "taxonomy coverage mismatch -- every one of the 39 residuals must have exactly one assigned bucket"
    assert len(MANUAL_TAXONOMY) == 39

    from collections import Counter
    bucket_counts = Counter(v["bucket"] for v in MANUAL_TAXONOMY.values())
    print("Bucket counts (of 39 failures):", dict(bucket_counts))

    # --- Write the per-case CSV ---
    csv_fields = ["case_id", "document_id", "hypothesis_id", "gold_label", "gpt_predicted_label",
                  "classification_correct", "gpt_source_valid_evidence", "gpt_gold_evidence_overlap",
                  "retrieval_contains_gold_in_final_top5", "bm25_top20_gold_rank",
                  "primary_bucket", "oracle_action_needed", "review_note"]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        for cid, c in sorted(cases.items()):
            tax = MANUAL_TAXONOMY[cid]
            row = {k: c.get(k) for k in csv_fields if k in c}
            row["primary_bucket"] = tax["bucket"]
            row["oracle_action_needed"] = tax["oracle_action"]
            row["review_note"] = tax["note"]
            w.writerow(row)
    print(f"wrote {OUT_CSV}")

    # --- Contradiction-specific breakdown ---
    contradiction_ids = [cid for cid, c in cases.items() if c["gold_label"] == "Contradiction"]
    assert len(contradiction_ids) == 15
    contradiction_bucket_counts = Counter(MANUAL_TAXONOMY[cid]["bucket"] for cid in contradiction_ids)
    contradiction_cls_wrong_ids = [cid for cid in contradiction_ids if not cases[cid]["classification_correct"]]
    assert len(contradiction_cls_wrong_ids) == 12
    contradiction_cls_wrong_had_sufficient_evidence = sum(
        1 for cid in contradiction_cls_wrong_ids if cases[cid]["retrieval_contains_gold_in_final_top5"])
    print(f"Contradiction bucket counts: {dict(contradiction_bucket_counts)}")
    print(f"Of 12 Contradiction classification-wrong cases, "
          f"{contradiction_cls_wrong_had_sufficient_evidence} had gold evidence already in the final top-5")

    # --- Correct-label/joint-fail (7 cases) breakdown ---
    correct_joint_fail_ids = [cid for cid, c in cases.items() if c["classification_correct"]]
    assert len(correct_joint_fail_ids) == 7
    correct_joint_fail_bucket_counts = Counter(MANUAL_TAXONOMY[cid]["bucket"] for cid in correct_joint_fail_ids)
    print(f"Correct-label/joint-fail (7) bucket counts: {dict(correct_joint_fail_bucket_counts)}")

    # --- Signal prevalence across ALL 150 cases (pre-declared: exception cue, score margin,
    # cross-reference-to-named-provision cue) ---
    retrieved = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    chunk_text_by_case = {c["case_id"]: c["ranked_chunk_text"] for c in retrieved["cases"]}
    rerank_scores_by_case = {c["case_id"]: c["ranked_chunk_rerank_scores"] for c in retrieved["cases"]}
    all_gpt_rows = {r["case_id"]: r for r in
                     csv.DictReader(open(E08B_DIR / "results/gpt5mini_failure_analysis.csv"))}
    assert len(all_gpt_rows) == 150

    EXCEPTION_KEYWORDS = ("except", "provided that", "unless", "notwithstanding", "other than",
                          "carve-out", "carve out")
    CROSS_REF_PATTERNS = ("of the definition of", "as defined in", "pursuant to section",
                          "pursuant to clause", "under clause", "under section",
                          "as set forth in section", "as provided in section",
                          "in accordance with section", "paragraph (a)", "paragraphs (a)")

    def has_exception_cue(cid: str) -> bool:
        ctx = " ".join(chunk_text_by_case[cid]).lower()
        return any(k in ctx for k in EXCEPTION_KEYWORDS)

    def has_cross_ref_cue(cid: str) -> bool:
        ctx = " ".join(chunk_text_by_case[cid]).lower()
        return any(p in ctx for p in CROSS_REF_PATTERNS)

    def score_margin(cid: str) -> float | None:
        s = rerank_scores_by_case[cid]
        return s[0] - s[1] if len(s) >= 2 else None

    dynamic_ids = {cid for cid, v in MANUAL_TAXONOMY.items() if v["bucket"] == "DYNAMIC_INFORMATION_ACQUISITION"}

    def evaluate_signal(name: str, fn) -> dict:
        tp = fp = fn_ = tn = 0
        for cid in all_gpt_rows:
            sig = fn(cid)
            is_dynamic = cid in dynamic_ids
            if sig and is_dynamic:
                tp += 1
            elif sig and not is_dynamic:
                fp += 1
            elif not sig and is_dynamic:
                fn_ += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn_) if (tp + fn_) else None
        escalation_rate = (tp + fp) / 150
        return {"signal": name, "tp": tp, "fp": fp, "fn": fn_, "tn": tn,
                "precision": precision, "recall": recall, "escalation_rate": escalation_rate}

    exception_success = sum(1 for cid, r in all_gpt_rows.items()
                             if r["joint_success"] == "True" and has_exception_cue(cid))
    exception_fail = sum(1 for cid, r in all_gpt_rows.items()
                          if r["joint_success"] != "True" and has_exception_cue(cid))
    n_success = sum(1 for r in all_gpt_rows.values() if r["joint_success"] == "True")
    n_fail = 150 - n_success

    margin_success = [score_margin(cid) for cid, r in all_gpt_rows.items()
                       if r["joint_success"] == "True" and score_margin(cid) is not None]
    margin_fail = [score_margin(cid) for cid, r in all_gpt_rows.items()
                    if r["joint_success"] != "True" and score_margin(cid) is not None]
    import statistics

    signals_result = {
        "exception_carveout_cue": {
            "prevalence_in_successes": exception_success / n_success,
            "prevalence_in_failures": exception_fail / n_fail,
            "prevalence_overall": (exception_success + exception_fail) / 150,
            "conclusion": "USELESS AS STANDALONE TRIGGER -- present in nearly all cases regardless of outcome, re-confirming E08's finding on Qwen now independently on GPT.",
        },
        "reranker_score_margin": {
            "mean_success": statistics.mean(margin_success), "mean_failure": statistics.mean(margin_fail),
            "median_success": statistics.median(margin_success), "median_failure": statistics.median(margin_fail),
            "conclusion": "NOT DISCRIMINATING -- success and failure distributions largely overlap.",
        },
        "cross_reference_to_named_provision_cue": evaluate_signal("cross_reference_to_named_provision_cue", has_cross_ref_cue),
    }
    with open(OUT_SIGNALS, "w") as f:
        json.dump(signals_result, f, indent=2, default=str)
    print(f"wrote {OUT_SIGNALS}")
    print(json.dumps(signals_result["cross_reference_to_named_provision_cue"], indent=2))

    # --- Whole-population opportunity (of ALL 150, not just the 39 failures) ---
    whole_pop = {
        "static_or_retrieval_fixable": bucket_counts["RETRIEVAL_FILTERING_LIMITED"],
        "dynamic_agent_residual": bucket_counts["DYNAMIC_INFORMATION_ACQUISITION"],
        "model_reasoning_limited": bucket_counts["MODEL_REASONING_LIMITED"],
        "evidence_selection_limited": bucket_counts["EVIDENCE_SELECTION_LIMITED"],
        "ambiguous_irreducible": bucket_counts.get("AMBIGUOUS_IRREDUCIBLE", 0),
        "output_protocol": bucket_counts.get("OUTPUT_PROTOCOL", 0),
    }
    whole_pop_pct_of_150 = {k: v / 150 for k, v in whole_pop.items()}
    print("Whole-population opportunity (count / % of all 150):")
    for k, v in whole_pop.items():
        print(f"  {k}: {v}/150 = {v/150:.1%}")

    # --- Static Pipeline Opportunity Ceiling (fix all 6 retrieval-filtering cases) ---
    n_joint_success_current = n_success  # 111
    static_ceiling_joint = n_joint_success_current + whole_pop["static_or_retrieval_fixable"]
    static_ceiling_accuracy_n = sum(1 for r in all_gpt_rows.values() if r["gold_label"] == r["predicted_label"]) \
        + sum(1 for cid in MANUAL_TAXONOMY if MANUAL_TAXONOMY[cid]["bucket"] == "RETRIEVAL_FILTERING_LIMITED"
              and not cases[cid]["classification_correct"])  # 5 of the 6 are also classification-wrong

    # --- Oracle Agent Opportunity Ceiling (fix the 1 genuinely dynamic case) ---
    dynamic_ceiling_joint = n_joint_success_current + whole_pop["dynamic_agent_residual"]
    dynamic_ceiling_accuracy_n = sum(1 for r in all_gpt_rows.values() if r["gold_label"] == r["predicted_label"]) \
        + sum(1 for cid in dynamic_ids if not cases[cid]["classification_correct"])

    ceiling_result = {
        "current_150case": {
            "accuracy": sum(1 for r in all_gpt_rows.values() if r["gold_label"] == r["predicted_label"]) / 150,
            "joint_success": n_joint_success_current / 150,
        },
        "STATIC_PIPELINE_OPPORTUNITY_CEILING": {
            "label": "Assumes all 6 RETRIEVAL_FILTERING_LIMITED cases are fixed by a deterministic "
                     "top-k increase (expand_final_k) -- NOT an agent action.",
            "joint_success_ceiling": static_ceiling_joint / 150,
            "joint_success_uplift_pp": (static_ceiling_joint - n_joint_success_current) / 150 * 100,
            "accuracy_ceiling": static_ceiling_accuracy_n / 150,
        },
        "ORACLE_AGENT_OPPORTUNITY_CEILING": {
            "label": "Upper bound only, NOT an expected result. Assumes the single genuinely "
                     "DYNAMIC_INFORMATION_ACQUISITION case is magically resolved by an agent and "
                     "no currently-correct case regresses.",
            "n_dynamic_cases": len(dynamic_ids),
            "joint_success_ceiling": dynamic_ceiling_joint / 150,
            "joint_success_uplift_pp": (dynamic_ceiling_joint - n_joint_success_current) / 150 * 100,
            "accuracy_ceiling": dynamic_ceiling_accuracy_n / 150,
        },
    }
    with open(OUT_CEILING, "w") as f:
        json.dump(ceiling_result, f, indent=2, default=str)
    print(f"wrote {OUT_CEILING}")
    print(json.dumps(ceiling_result, indent=2))

    # --- Final decision ---
    decision = {
        "decision": "A",
        "decision_label": "A3 NOT JUSTIFIED",
        "rationale": (
            "Of all 39 GPT joint failures (manually reviewed, no sampling), exactly 1 case "
            "(2.6% of failures, 0.67% of all 150 cases) passes the strict 6-criteria agentic-"
            "justification test. The dominant residual failure mode (26/39 = 66.7% of failures, "
            "17.3% of all 150 cases) is MODEL_REASONING_LIMITED -- necessary evidence was already "
            "present and, in most cases, already correctly located/quoted by GPT, but the model "
            "still drew the wrong conclusion. No agent action changes what information the model "
            "has in these cases; a second investigation step would only be 'think again,' which "
            "is explicitly excluded from counting as agentic. The second-largest bucket (6/39 = "
            "15.4% of failures, 4.0% of all 150) is RETRIEVAL_FILTERING_LIMITED -- gold evidence "
            "was in the BM25 top-20 pool every time but cut by the reranker before the final "
            "top-5 -- a STATIC, deterministic fix (raise final top_k) with a materially larger "
            "ceiling (+4.0pp joint success) than the single dynamic case's ceiling (+0.67pp). "
            "The one genuinely dynamic case's own trigger signal (cross-reference-to-named-"
            "provision) has only 6.7% precision across all 150 cases (1 true positive out of 15 "
            "cases it would fire on) -- an agent gated on this signal would investigate 14 cases "
            "unnecessarily for every 1 it correctly helps, for a ceiling gain of well under 1 "
            "percentage point. Combined with the historical T-series agent's own reversal at full "
            "scale (recovery/regression flipped between the dev sample and the full 2,091-case "
            "test set), the cost/complexity case for building A3 now is not supported by this "
            "evidence."
        ),
        "what_would_change_this": (
            "A future E-series experiment finding a materially larger genuinely-dynamic residual "
            "(e.g. after the static retrieval fix is applied and MODEL_REASONING_LIMITED itself is "
            "addressed via a downstream GPT-specific prompt experiment, if the remaining residual "
            "shifts composition), or a larger sample surfacing more cross-reference-style cases "
            "than this 150-case draw happened to contain."
        ),
        "not_claimed": "This is not a claim that an agent would fail to improve the final "
                       "benchmark if built anyway -- it is a claim that the evidence for building "
                       "one now, on this residual, is weak relative to a deterministic top-k fix.",
    }
    with open(OUT_DECISION, "w") as f:
        json.dump(decision, f, indent=2, default=str)
    print(f"wrote {OUT_DECISION}")
    print(json.dumps(decision, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
