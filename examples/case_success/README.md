# Example: a correct, evidence-grounded result

One real case (`test::446::nda-5`) pulled directly from the final TEST evaluation run (E20,
2,091 cases, the same run the headline numbers in the README and final report come from). Full
structured data is in [`case.json`](case.json); this file is the step-by-step walkthrough.

## The pipeline, as it ran on this case

**1. Input.** A short NDA (Navidec, Incorporated — a one-page trade-secret agreement, 308 tokens)
and one of the 17 fixed ContractNLI requirements:

> "Receiving Party may share some Confidential Information with some of Receiving Party's
> employees."

**2. Retrieval** (`pipeline/frozen_rag.py`). Clause-aware chunking → BM25 top-20 → cross-encoder
rerank → top-5. Because this document is only 308 tokens, the top-5 chunks cover nearly the whole
NDA — this is an easy retrieval case, not a hard one. See `../case_failure/` for a harder one.

**3. Classification** (`pipeline/final_review.py`, GPT-5-mini + frozen GPT-P0 prompt). The model
returned:

```json
{"label": "Contradiction", "evidence": ["____________________ , agrees that, in consideration for being shown or told about certain trade secrets or property belonging to Navidec, Incorporated, ____________________, shall not disclose or cause to be disclosed, disseminated or distributed any information concerning said trade secret or property to any person, entity, business or other individual or company without the prior written permission of Navidec, Incorporated."]}
```

The cited clause is an unconditional non-disclosure obligation with no "may share with some
employees" carve-out — correctly read as contradicting the requirement.

**4. Runtime validation** (`pipeline/evidence_validator.py`). Checks only one thing: is the cited
quote a genuine, exact substring of the context the model was shown? Here: yes — 1/1 quotes
verbatim, 0 hallucinated. **This check has no access to the gold label** and cannot know whether
"Contradiction" is actually correct; it only confirms the model didn't fabricate its citation.

**5. Final classification returned to the reviewer:** label `Contradiction`, one cited clause,
`needs_human_review: false` (no injection flag, no parse issue, no source-validity failure), cost
$0.00123.

**6. Offline scoring** (`evaluation/`, the only place gold data is used — never at runtime). Gold
label is also `Contradiction`, gold evidence is the same clause. Label correct, evidence correct
→ **Joint correct**. This is one of the 1,515/2,091 cases (72.45%) that make up E20's headline
Joint-correctness number.

## Why this case is a good representative example

It's not cherry-picked for difficulty — it's a short, clean, genuinely typical case showing all
five pipeline stages agreeing: retrieval found the right clause, the model read it correctly, the
runtime validator confirmed it wasn't fabricated, and offline scoring confirms it matches gold.
For a harder case where some of these stages *don't* agree, see `../case_failure/`.
