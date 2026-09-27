#!/usr/bin/env python3
"""
Build the Category 2 negative battery (15 cases, IDs 031-045) from the
ContractNLI dev split, per NDATrace_100_eval_cases.md's Category 2.

Per the eval-case spec, this and Category 3 were meant to be frozen
"before Phase 0" alongside Category 1 (data/golden/golden_cases.json) -
they're built now, later than planned, but before any of the retrieval/
classification decisions they'd otherwise risk looking tuned against.

Unlike Category 1 (easy/medium/hard by difficulty), Category 2 targets
five specific *negative families* - wrong behaviours a system could
plausibly exhibit (treating "may" as "shall", trusting a recital instead
of the operative clause, missing a paraphrased requirement, etc). Same
proxy-matching approach as build_golden_cases.py: a keyword/structural
predicate approximates each family, with an honest fallback note when no
dev-set case matches.

Cases here are guaranteed distinct from Category 1's 30 cases (seeded
into the Selector's `used` set from the existing golden_cases.json) -
the two batteries never overlap.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from scripts.build_golden_cases import Selector, build_case_pool, contains_any


def load_category_1_used(pool: list[dict]) -> set[tuple[str, str]]:
    path = Path("data/golden/golden_cases.json")
    if not path.exists():
        return set()
    cases = json.loads(path.read_text())
    return {(c["doc_id"], c["hypothesis_id"]) for c in cases}


def build_category_2(pool: list[dict], pre_used: set[tuple[str, str]]) -> list[dict]:
    s = Selector(pool)
    s.used |= pre_used
    cases = []

    # --- Misleading wording (031-034) ---
    cases.append(s.pick("031", "NotMentioned",
        'Misleading wording - conditional "may" language could be misread as firm entailment',
        predicate=lambda c: contains_any(c["doc_text"], " may disclose", " may share", " may use")))
    cases.append(s.pick("032", "NotMentioned",
        'Misleading wording - future tense ("will establish/provide/implement") is intent, not fulfilment',
        predicate=lambda c: contains_any(c["doc_text"], "will establish", "will provide", "will implement")))
    cases.append(s.pick("033", "Entailment",
        'Misleading wording - double negative ("shall not fail to protect") reads as positive; must not be misread as Contradiction',
        predicate=lambda c: contains_any(c["evidence_text"], "shall not fail", "not fail to")))
    cases.append(s.pick("034", "Contradiction",
        'Misleading wording - "except as required by law" carve-out limits an apparently firm requirement',
        predicate=lambda c: contains_any(c["evidence_text"], "except as required by law", "required by applicable law", "required by law")))

    # --- Wrong section evidence (035-037) ---
    cases.append(s.pick("035", "NotMentioned",
        "Wrong section evidence - a hypothesis keyword appears early (definitions-like) in the doc but the real gold answer is Not Mentioned, not a definitions-section false positive",
        predicate=lambda c: any(
            w.lower() in c["doc_text"][:600].lower()
            for w in re.findall(r"[A-Za-z]{6,}", c["hyp_text"])
        )))
    cases.append(s.pick("036", "NotMentioned",
        "Wrong section evidence - topic language appears in the document's opening (recital-like) but no operative clause actually addresses it",
        predicate=lambda c: any(
            w.lower() in c["doc_text"][:400].lower()
            for w in re.findall(r"[A-Za-z]{6,}", c["hyp_text"])
        ), key=lambda c: c["doc_tokens"], reverse=True))
    cases.append(s.pick("037", "Entailment",
        "Wrong section evidence - correct label must rest on clause body content, not a heading-level keyword match",
        predicate=lambda c: c["span_count"] == 1 and contains_any(c["evidence_text"], "confidential", "disclos")))

    # --- Conflicting clauses (038-040) ---
    cases.append(s.pick("038", "Contradiction",
        "Conflicting clauses - evidence spans multiple locations, approximating one clause granting and another limiting the same right",
        predicate=lambda c: c["span_count"] >= 2))
    cases.append(s.pick("039", "Contradiction",
        "Conflicting clauses - amendment/override language should win over an earlier, superseded clause",
        predicate=lambda c: contains_any(c["evidence_text"], "amend", "supersede", "supersedes", "override")))
    cases.append(s.pick("040", "Contradiction",
        "Conflicting clauses - a specific exception should override an apparently general requirement",
        predicate=lambda c: contains_any(c["evidence_text"], "notwithstanding", "provided that", "provided, however")))

    # --- Keyword absence (041-043) ---
    cases.append(s.pick("041", "Entailment",
        "Keyword absence - requirement is met but stated with paraphrased/different terminology than the hypothesis - rule-based baseline (B02) is expected to fail here, LLM should not",
        predicate=lambda c: c["span_count"] == 1 and not any(
            w.lower() in c["evidence_text"].lower()
            for w in re.findall(r"[A-Za-z]{5,}", c["hyp_text"])
        )))
    cases.append(s.pick("042", "Entailment",
        'Keyword absence - legal synonym ("covenant"/"undertakes") used instead of the hypothesis\'s literal wording',
        predicate=lambda c: contains_any(c["evidence_text"], "covenant", "undertakes", "undertaking")))
    cases.append(s.pick("043", "Entailment",
        "Keyword absence - an abbreviation/defined short-form is used in place of the full term",
        predicate=lambda c: contains_any(c["evidence_text"], '"cd"', '"the company"', "hereinafter")))

    # --- Very long document (044-045) ---
    cases.append(s.pick("044", "Entailment",
        "Very long document - evidence located deep in a long NDA, retrieval must not degrade with document length",
        predicate=lambda c: c["span_count"] == 1, key=lambda c: c["doc_tokens"], reverse=True))
    cases.append(s.pick("045", "Entailment",
        "Very long document - multiple relevant spans scattered across a long document, all must be retrievable",
        predicate=lambda c: c["span_count"] >= 2, key=lambda c: (c["doc_tokens"], c["span_count"]), reverse=True))

    for c in cases:
        c["category"] = "negative_case"

    return cases


def main() -> int:
    data_dir = settings.data_path
    dev_path = data_dir / "dev.json"
    if not dev_path.exists():
        print(f"ERROR: {dev_path} not found. Run scripts/download_data.sh first.")
        return 1

    dataset = parse_contractnli_file(dev_path)
    pool = build_case_pool(dataset)
    pre_used = load_category_1_used(pool)
    print(f"Dev pool: {len(pool)} cases; {len(pre_used)} already used by Category 1 (excluded)")

    cases = build_category_2(pool, pre_used)

    out_path = Path("data/golden/negative_cases.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cases, indent=2))

    label_counts: dict[str, int] = {}
    fallback_count = 0
    for c in cases:
        label_counts[c["gold_label"]] = label_counts.get(c["gold_label"], 0) + 1
        if "[proxy:" in c["description"]:
            fallback_count += 1

    print(f"Wrote {len(cases)} negative cases to {out_path}")
    print(f"Label distribution: {label_counts}")
    print(f"Fallback selections (no keyword/structural match found): {fallback_count}/{len(cases)}")

    overlap = pre_used & {(c["doc_id"], c["hypothesis_id"]) for c in cases}
    assert not overlap, f"Category 2 overlaps Category 1 on: {overlap}"
    print("Verified: no overlap with Category 1's 30 cases.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
