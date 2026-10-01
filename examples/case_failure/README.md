# Example: a genuine failure (reasoning, not retrieval or validation)

One real case (`test::77::nda-20`) pulled directly from the final TEST evaluation run (E20) — one
of the 576 non-Joint RAG results, not a constructed or hypothetical example. Full structured data
is in [`case.json`](case.json); this file is the step-by-step walkthrough of **why** it failed.
See [`docs/failure_analysis.md`](../../docs/failure_analysis.md) for how this one case fits into
the full 2,091-case failure breakdown.

## The pipeline, as it ran on this case

**1. Input.** A German-law supplier confidentiality agreement (617 tokens) and the requirement:

> "Receiving Party may retain some Confidential Information even after the return or destruction
> of Confidential Information."

**2. Retrieval.** The top-5 retrieved chunks **do include** clause 9 — the exact clause the gold
label is based on. This rules out retrieval as the cause of what follows.

**3. Classification.** The model returned:

```json
{"label": "Entailment", "evidence": [
  "At the end of the contract the receiving party shall return the confidential information and any possibly extant copies after receipt of a written request, provided that this is technically feasible and does not violate the retention obligations.",
  "As an alternative to that, the receiving party can also ensure in writing the destruction of the received documentation if that is technically feasible."
]}
```

**4. Runtime validation.** Both quotes are genuine, exact substrings of the retrieved context —
**0 hallucinated, `is_valid: true`.** This is the key point of this example: a clean pass from the
runtime validator does not mean the result is correct. The validator checks sourcing, never
reasoning.

**5. What actually went wrong.** Clause 9 is a mandatory obligation: the receiving party *must*
return or destroy the confidential information at the end of the contract — there is no "may
retain" option. The model quoted exactly the right clause but inverted its polarity: it seems to
have read "return OR destroy" as offering a choice that implicitly permits retention in the
meantime, and labeled the requirement "Entailment" instead of "Contradiction." The citation is
real; the inference drawn from it is wrong.

**6. Offline scoring.** Gold label is `Contradiction`. Predicted label `Entailment` is wrong →
label incorrect → **not Joint correct**, regardless of how clean the cited evidence is.

## Failure category

**`reasoning_classification`** — verified against the exact rule `scripts/analyze_e20_rag_test.py`
uses to build the taxonomy in the final report (gold evidence *was* in the retrieved context, so
it is excluded from `retrieval_limited` by that rule's own definition; the label was wrong, so it
is excluded from `evidence_selection` too). 448 of RAG's 576 non-Joint cases (77.8%) fall in this
same category — this one case is representative of the dominant failure mode, not an outlier.

## Why this matters for the "more retrieval" question

This case is direct evidence for a claim made in the final report and `docs/failure_analysis.md`:
**more retrieval depth would not have fixed this case.** The retriever already found the right
clause. The failure is entirely in how the model reasoned about a clause it correctly retrieved —
a polarity/negation misread, not a missing-evidence problem. It's also why the system ships with
**no automatic confidence gate**: the runtime validator — the only automatic check that exists —
passes this case cleanly. Only a human reviewer, reading the cited clause against the requirement,
would catch it. That's exactly what the reviewer decision flow in the live product
(`POST /review/{review_id}/items/{item_id}/decision`) exists for.
