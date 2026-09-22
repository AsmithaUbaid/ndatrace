#!/usr/bin/env python3
"""
Build the Category 1 golden battery (30 cases) from the ContractNLI dev
split, per NDATrace_100_eval_cases.md Category 1 and WBS T007's golden
battery loader requirement.

The design doc's 30 slots each name a qualitative property ("legal
jargon", "buried in sub-clause", "longest NDA in dataset"). This script
approximates each with a measurable proxy - a keyword/regex search over
evidence text, a gold-evidence-span count, or a document token length -
and records in the case's description whether the proxy actually matched
that property, or fell back to the next-best distinct case. Selections
are drawn only from the dev split (never test), per the leakage-prevention
rule (Category 8, case 089): test-set cases are never used for tuning or
regression batteries.

Output: data/golden/golden_cases.json, matching the GoldCase schema
consumed by evaluation.harness.EvaluationHarness.load_gold_cases().
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings
from pipeline.parser import parse_contractnli_file

ENCODING = tiktoken.get_encoding("cl100k_base")


def build_case_pool(dataset) -> list[dict]:
    """Flatten (document, annotation) pairs into feature dicts for selection."""
    pool = []
    for doc, ann in dataset.all_cases():
        evidence_text = " ".join(s.text for s in ann.evidence_spans)
        pool.append({
            "doc_id": doc.doc_id,
            "hyp_id": ann.hypothesis_id,
            "hyp_text": ann.hypothesis_text,
            "label": ann.label,
            "span_indices": [s.span_index for s in ann.evidence_spans],
            "span_count": len(ann.evidence_spans),
            "evidence_text": evidence_text,
            "doc_text": doc.text,
            "doc_tokens": len(ENCODING.encode(doc.text)),
        })
    return pool


class Selector:
    """Picks distinct (doc_id, hyp_id) cases from the pool, slot by slot."""

    def __init__(self, pool: list[dict]):
        self.pool = pool
        self.used: set[tuple[str, str]] = set()

    def pick(self, case_id, label, description, predicate=None, key=None, reverse=False):
        """
        Pick the best available case for `label` matching `predicate`
        (a keyword/structural proxy for the slot's qualitative property).
        If no candidate matches, fall back to any unused case of that
        label, sorted by `key`, and note the fallback in the description.
        """
        available = [c for c in self.pool if c["label"] == label
                     and (c["doc_id"], c["hyp_id"]) not in self.used]

        matched = [c for c in available if predicate(c)] if predicate else available
        used_fallback = not matched
        candidates = matched if matched else available

        if key:
            candidates = sorted(candidates, key=key, reverse=reverse)

        if not candidates:
            raise RuntimeError(f"No available dev-set case left for slot {case_id} ({label})")

        chosen = candidates[0]
        self.used.add((chosen["doc_id"], chosen["hyp_id"]))

        note = " [proxy: no keyword/structural match found in dev set; nearest available case used]" if used_fallback else ""
        return {
            "case_id": case_id,
            "doc_id": chosen["doc_id"],
            "hypothesis_id": chosen["hyp_id"],
            "gold_label": chosen["label"],
            "gold_span_indices": chosen["span_indices"],
            "category": "golden_battery",
            "description": description + note,
        }


def contains_any(text: str, *keywords: str) -> bool:
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)


def has_nested_subclause_marker(text: str) -> bool:
    return bool(re.search(r"\b\d+\.\d+\.[a-z0-9]+\b|\([a-z]\)\s*\([ivxlc]+\)", text, re.IGNORECASE))


def build_category_1(pool: list[dict]) -> list[dict]:
    s = Selector(pool)
    cases = []

    # --- Entailment (001-010) ---
    cases.append(s.pick("001", "Entailment",
        "Easy entailment - single clause, short NDA, obvious match",
        predicate=lambda c: c["span_count"] == 1, key=lambda c: c["doc_tokens"]))
    cases.append(s.pick("002", "Entailment",
        "Easy entailment - standard boilerplate confidentiality language",
        predicate=lambda c: contains_any(c["evidence_text"], "confidential", "non-disclosure")))
    cases.append(s.pick("003", "Entailment",
        "Easy entailment - distinct NDA from case 001/002",
        predicate=lambda c: c["span_count"] == 1, key=lambda c: c["doc_tokens"], reverse=True))
    cases.append(s.pick("004", "Entailment",
        "Medium entailment - single-span evidence, distinct document",
        predicate=lambda c: c["span_count"] == 1))
    cases.append(s.pick("005", "Entailment",
        'Medium entailment - legal jargon ("strictest confidence" / "receiving party")',
        predicate=lambda c: contains_any(c["evidence_text"], "strictest confidence", "receiving party")))
    cases.append(s.pick("006", "Entailment",
        "Medium entailment - evidence split across two spans in one clause",
        predicate=lambda c: c["span_count"] == 2))
    cases.append(s.pick("007", "Entailment",
        "Hard entailment - evidence scattered across 3+ spans",
        predicate=lambda c: c["span_count"] >= 3))
    cases.append(s.pick("008", "Entailment",
        "Hard entailment - evidence buried in a deeply nested sub-clause",
        predicate=lambda c: has_nested_subclause_marker(c["evidence_text"])))
    cases.append(s.pick("009", "Entailment",
        "Hard entailment - evidence implied by combination of clauses (multi-span)",
        predicate=lambda c: c["span_count"] >= 2, key=lambda c: c["span_count"], reverse=True))
    cases.append(s.pick("010", "Entailment",
        "Entailment in the longest NDA in the dev split",
        key=lambda c: c["doc_tokens"], reverse=True))

    # --- Contradiction (011-020) ---
    cases.append(s.pick("011", "Contradiction",
        "Easy contradiction - explicit carve-out / exclusion",
        predicate=lambda c: contains_any(c["evidence_text"], "except", "carve", "exclu")))
    cases.append(s.pick("012", "Contradiction",
        '"Shall not" negative language',
        predicate=lambda c: contains_any(c["evidence_text"], "shall not", "will not")))
    cases.append(s.pick("013", "Contradiction",
        'Explicit exclusion list ("does not cover" / "does not apply")',
        predicate=lambda c: contains_any(c["evidence_text"], "does not cover", "does not apply", "not include")))
    cases.append(s.pick("014", "Contradiction",
        "Exception sub-clause negates an apparently supportive main clause",
        predicate=lambda c: c["span_count"] >= 2 and contains_any(c["evidence_text"], "except")))
    cases.append(s.pick("015", "Contradiction",
        "Time-limited obligation contradicts an open-ended requirement",
        predicate=lambda c: contains_any(c["evidence_text"], "period of", "year", "years", "term of")))
    cases.append(s.pick("016", "Contradiction",
        "Scope limitation contradicts a broad requirement",
        predicate=lambda c: contains_any(c["evidence_text"], "limited to", "solely", "only to")))
    cases.append(s.pick("017", "Contradiction",
        "Contradiction via a narrowing defined term",
        predicate=lambda c: contains_any(c["evidence_text"], "defined", "means", "definition")))
    cases.append(s.pick("018", "Contradiction",
        "Contradiction only visible when two clauses are read together",
        predicate=lambda c: c["span_count"] >= 2))
    cases.append(s.pick("019", "Contradiction",
        "Contradiction buried in a schedule/appendix reference",
        predicate=lambda c: contains_any(c["evidence_text"], "schedule", "appendix", "exhibit", "annex")))
    cases.append(s.pick("020", "Contradiction",
        "Contradiction in the shortest NDA in the dev split",
        key=lambda c: c["doc_tokens"]))

    # --- Not Mentioned (021-030) ---
    cases.append(s.pick("021", "NotMentioned",
        "Easy NM - requirement topic appears genuinely absent from the NDA",
        predicate=lambda c: not any(
            w.lower() in c["doc_text"].lower()
            for w in re.findall(r"[A-Za-z]{6,}", c["hyp_text"])
        )))
    cases.append(s.pick("022", "NotMentioned",
        "Easy NM - very short NDA with limited scope",
        key=lambda c: c["doc_tokens"]))
    cases.append(s.pick("023", "NotMentioned",
        "NM - standard NDA missing a non-solicitation clause",
        predicate=lambda c: contains_any(c["hyp_text"], "solicit")))
    cases.append(s.pick("024", "NotMentioned",
        "NM - related but distinct concept present (e.g. retention vs. destruction)",
        predicate=lambda c: contains_any(c["hyp_text"], "destroy", "destruction", "delete", "return")))
    cases.append(s.pick("025", "NotMentioned",
        'NM - similar wording present ("reasonable care") but different legal meaning',
        predicate=lambda c: contains_any(c["doc_text"], "reasonable care", "reasonable measures")))
    cases.append(s.pick("026", "NotMentioned",
        "NM - topic possibly referenced only in preamble, not an operative clause",
        predicate=lambda c: any(
            w.lower() in c["doc_text"][:800].lower()
            for w in re.findall(r"[A-Za-z]{6,}", c["hyp_text"])
        )))
    cases.append(s.pick("027", "NotMentioned",
        "Hard NM - NDA partially addresses related sub-requirements",
        predicate=lambda c: contains_any(c["hyp_text"], "third party", "third-party")))
    cases.append(s.pick("028", "NotMentioned",
        'Hard NM - "confidential" appears in the NDA but not in the relevant context',
        predicate=lambda c: contains_any(c["doc_text"], "confidential")))
    cases.append(s.pick("029", "NotMentioned",
        "Hard NM - long NDA with many clauses, none matching this requirement",
        key=lambda c: c["doc_tokens"], reverse=True))
    cases.append(s.pick("030", "NotMentioned",
        "NM despite a superficially comprehensive NDA (distinct remaining case)",
        key=lambda c: c["doc_tokens"]))

    return cases


def main() -> int:
    data_dir = settings.data_path
    dev_path = data_dir / "dev.json"
    if not dev_path.exists():
        print(f"ERROR: {dev_path} not found. Run scripts/download_data.sh first.")
        return 1

    dataset = parse_contractnli_file(dev_path)
    pool = build_case_pool(dataset)
    print(f"Dev pool: {len(pool)} (document, hypothesis) cases from {dataset.num_documents} documents")

    cases = build_category_1(pool)

    out_path = Path("data/golden/golden_cases.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cases, indent=2))

    label_counts = {}
    fallback_count = 0
    for c in cases:
        label_counts[c["gold_label"]] = label_counts.get(c["gold_label"], 0) + 1
        if "[proxy:" in c["description"]:
            fallback_count += 1

    print(f"Wrote {len(cases)} golden cases to {out_path}")
    print(f"Label distribution: {label_counts}")
    print(f"Fallback selections (no keyword/structural match found): {fallback_count}/{len(cases)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
