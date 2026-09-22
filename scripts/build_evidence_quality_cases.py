#!/usr/bin/env python3
"""
Build the Category 7 evidence quality eval battery (5 cases, IDs
081-085) from NDATrace_100_eval_cases.md's Category 7 - entirely free,
reuses already-collected RAG predictions (run_T018_prompt_v2.jsonl) and
the existing chunker/retriever pipeline. No new API calls.

081/084/085 are retrieval-level checks (does the retrieved evidence
cover the real gold span, and does it rank first?) - these reuse the
`retrieved_span_indices` already saved on each Prediction, which is
built from real retrieval, not re-derived here.

082 is a structural chunker check: does a ContractNLI gold span ever get
split across more than one sentence-level chunk? Verified directly
against the chunker's output for real documents in the sample.

083 reuses pipeline/evidence_validator.py's existing guarantee (already
unit-tested) that a NotMentioned label paired with non-empty evidence is
flagged as inconsistent - confirmed here against a real NotMentioned
case's retrieval-only output (no evidence field exists until a
classify() call runs; the retrieval side already returns no chunks
"forced" onto NotMentioned cases beyond normal top-k, so this reports
the code-level guarantee rather than mining a specific live output).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from pipeline.chunker import sentence_chunk
from pipeline.config import settings
from pipeline.evidence_validator import validate_evidence
from pipeline.parser import parse_contractnli_file
from scripts.run_oracle_experiment import SEED, stratified_sample


def main() -> int:
    harness = EvaluationHarness()
    rag = harness.load_results("runs/run_T018_prompt_v2.jsonl")[0]

    dataset = parse_contractnli_file(settings.data_path / "dev.json")
    sample = stratified_sample(dataset, 150, SEED)
    ann_by_key = {(doc.doc_id, ann.hypothesis_id): (doc, ann) for doc, ann in sample}

    output = []

    # --- 081: evidence supports the label (Entailment case, gold span covered) ---
    match = next(
        (p for p in rag.predictions
         if ann_by_key[(p.doc_id, p.hypothesis_id)][1].label == "Entailment"
         and p.predicted_label.value == "Entailment"
         and any(s.span_index in p.retrieved_span_indices for s in ann_by_key[(p.doc_id, p.hypothesis_id)][1].evidence_spans)),
        None,
    )
    output.append({
        "case_id": "081", "doc_id": match.doc_id, "hypothesis_id": match.hypothesis_id,
        "gold_label": "Entailment", "category": "evidence_quality",
        "description": (
            "Evidence supports the label - real Entailment case where the retrieved evidence "
            "covers at least one real gold span, and the final label was correct."
        ),
    })

    # --- 082: evidence is complete - gold span not split across chunk boundaries ---
    split_count, whole_count, total = 0, 0, 0
    example_doc_id = None
    for doc, ann in sample:
        if not ann.evidence_spans:
            continue
        chunks = sentence_chunk(doc.text)
        for span in ann.evidence_spans:
            total += 1
            covering = [c for c in chunks if span.start_char < c.end_char and span.end_char > c.start_char]
            if len(covering) <= 1:
                whole_count += 1
                if example_doc_id is None:
                    example_doc_id, example_hyp_id = doc.doc_id, ann.hypothesis_id
            else:
                split_count += 1
    output.append({
        "case_id": "082", "doc_id": example_doc_id or "", "hypothesis_id": example_hyp_id or "",
        "gold_label": "Entailment", "category": "evidence_quality",
        "description": (
            f"Evidence is complete - not cut mid-sentence. Checked all {total} gold spans across "
            f"the 150-case sample against sentence-level chunk boundaries: {whole_count}/{total} "
            f"({whole_count/total:.1%}) are fully contained in a single chunk, {split_count} span "
            "more than one. Sentence-level chunking (the winning method, T023 round 2) never "
            "splits mid-sentence by construction - most gold spans (annotator-drawn, not aligned "
            "to our chunk boundaries) still land inside one chunk, though a real minority don't."
        ),
    })

    # --- 083: no false evidence for NotMentioned (code-level guarantee) ---
    nm_result = validate_evidence(context="Some retrieved context.", evidence=[], label="NotMentioned")
    bad_result = validate_evidence(context="Some retrieved context.", evidence=["a quote"], label="NotMentioned")
    output.append({
        "case_id": "083", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "evidence_quality",
        "description": (
            f"No false evidence for Not Mentioned - code-level guarantee via "
            f"pipeline/evidence_validator.py, not a mined live case: empty evidence + NotMentioned "
            f"is_valid={nm_result.is_valid} (expected True); non-empty evidence + NotMentioned "
            f"is_valid={bad_result.is_valid} (expected False, correctly flagged as inconsistent). "
            "Also enforced by the classify() prompt's own rule (prompts/classify_v2.txt: "
            "'If the label is NotMentioned, evidence must be an empty list')."
        ),
    })

    # --- 084: best evidence is rank 1 ---
    match = next(
        (p for p in rag.predictions
         if p.retrieved_span_indices
         and any(s.span_index == p.retrieved_span_indices[0] for s in ann_by_key[(p.doc_id, p.hypothesis_id)][1].evidence_spans)),
        None,
    )
    output.append({
        "case_id": "084", "doc_id": match.doc_id, "hypothesis_id": match.hypothesis_id,
        "gold_label": ann_by_key[(match.doc_id, match.hypothesis_id)][1].label, "category": "evidence_quality",
        "description": (
            "Best evidence is rank 1 - real case where the first-ranked retrieved span "
            "(post-rerank, post-rule-boost) is a genuine gold evidence span, not just present "
            "somewhere in the retrieved set."
        ),
    })

    # --- 085: Contradiction evidence points to the contradicting clause ---
    match = next(
        (p for p in rag.predictions
         if ann_by_key[(p.doc_id, p.hypothesis_id)][1].label == "Contradiction"
         and p.predicted_label.value == "Contradiction"
         and any(s.span_index in p.retrieved_span_indices for s in ann_by_key[(p.doc_id, p.hypothesis_id)][1].evidence_spans)),
        None,
    )
    if match is not None:
        output.append({
            "case_id": "085", "doc_id": match.doc_id, "hypothesis_id": match.hypothesis_id,
            "gold_label": "Contradiction", "category": "evidence_quality",
            "description": (
                "Contradiction evidence points to the contradicting clause - real case where "
                "retrieval covered the actual gold Contradiction span, and classification was "
                "correct."
            ),
        })
    else:
        output.append({
            "case_id": "085", "doc_id": "", "hypothesis_id": "", "gold_label": "Contradiction",
            "category": "evidence_quality",
            "description": (
                "Contradiction evidence points to the contradicting clause "
                "[proxy: no case in the 150-sample simultaneously has correct Contradiction "
                "prediction AND gold-span coverage - noted honestly rather than forced]."
            ),
        })

    out_path = Path("data/golden/evidence_quality_cases.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(output)} evidence quality eval cases to {out_path}")
    for c in output:
        print(f"  {c['case_id']}: {c['description'][:80]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
