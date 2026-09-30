# E13B — Evidence Evaluator Hardening — RESULTS (offline; zero model calls; no TEST access)

**Outcome: A — EVIDENCE_EVALUATOR_V2 APPROVED.** v2 recovers formatting-only evidence mismatches, introduces no false positives, regresses nothing, and changes none of the frozen E13/E12/E11 decisions. Ledger unchanged at **$2.8044**. Not committed.

## 1. Current evaluator (v1) — audit map
| Function | Purpose | Normalization today | Known weakness | Canonical? | Duplicated? |
|---|---|---|---|---|---|
| `evidence_to_span_indices` | model quote → gold-annotation span indices (`text.find`, first occurrence per chunk; overlap in original doc coordinates) | **none** (exact substring) | fails on line-break/whitespace/zero-width differences | no (was a script-local copy) | **5 copies**: analyze_e05 (doc-level variant), e07, e08, e08b, e11; e12a/e12b/e13 import e08b's |
| `pipeline.evidence_validator.validate_evidence` | source-valid check at inference (`q in context`) + NotMentioned-no-evidence consistency | none (exact) | same artefact drops correct quotes as "hallucinated" | canonical for inference (v1) | used by all runners; left **unchanged** (production module) |
| `joint_success` (per case) | joint label+evidence, τ=0.5, NM ⇒ no spans | n/a | none (depends on mapping) | canonical = `evaluation.metrics.joint_label_evidence_correctness` | **5 per-case copies**: e04, e05, e07, e08b, e11 (+ `TAU_EVIDENCE=0.5` constant in each) |
| `retrieval_contains_gold` | did RAG context cover a gold span | char-offset overlap (no text) | none | script-local | 3 copies: e03, e07, e08b |
| `map_chunks_to_gold_span_indices`, Recall@K/MRR | retrieval metrics | char-offset overlap | none | `evaluation.scorer` / `retrieval_eval` | no |
Evidence Recall = share of evidence-bearing gold cases whose mapped spans overlap gold; Evidence Precision = share of cases that cited evidence whose mapped spans overlap gold (both duplicated in each analyzer).
**Decision:** one canonical implementation now exists (`evaluation/evidence_matching.py`); historical scripts were **not** rewritten and raw outputs not touched; future evaluation paths import the canonical module. v1 mapping is reproduced by `evidence_to_span_indices_v1` and verified equal to the historical copies (test on random data + exact reproduction of every reported joint value).

## 2. v2 specification (frozen in config.yaml before any historical re-scoring)
- **Policy:** try v1 exact substring in every context text first; only if the quote matches nowhere exactly, try the normalized substring; recover the match to ORIGINAL character offsets; apply the unchanged span-overlap/joint semantics. ⇒ every v1 mapping is preserved bit-for-bit; v2 can only add mappings.
- **Unicode:** NFC per base+combining-mark cluster (NFKC rejected: compatibility mappings could alter numbers/semantics, e.g. superscript 2, fractions, ligatures — a unit test pins that these still do not match).
- **Zero-width:** U+200B, U+200C, U+200D, U+2060, U+FEFF deleted.
- **Whitespace:** every `str.isspace()` char (space, tab, CR/LF, NBSP, U+2000–200A, U+2028/9, U+202F, U+205F, U+3000, …) collapses in runs to one ordinary space; leading/trailing trimmed.
- **Not done:** case-folding, punctuation edits (curly vs straight quotes stay different), word/negation edits, ellipsis segmentation, soft hyphens, fuzzy/edit-distance/embedding/synonym/paraphrase/LLM matching, gold-aware repair, case-specific exceptions.
- **Offset mapping:** each normalized character stores the original (start, end) of the cluster or whitespace-run that produced it; a normalized match maps to `[start(first char), end(last char))` in the original text.
- **Multiple matches:** existing v1 policy preserved — per context text only the first (leftmost) occurrence counts, every text containing the quote contributes, gold-blind and deterministic; exact-first means an exactly-formatted occurrence wins over a normalized earlier one. source-valid = at least one genuine occurrence. Ambiguity diagnostic: 0 of the 41 rescued quotes had more than one occurrence.
- **Versioning:** `evidence_evaluator_v1` = exact-substring; `evidence_evaluator_v2` = exact-first + formatting-normalized fallback (`CURRENT_EVIDENCE_EVALUATOR = v2`).
- **Joint semantics and τ unchanged:** E/C = correct label + |gold∩pred|/|gold| ≥ **τ = 0.5** (empty gold ⇒ label suffices); NotMentioned = correct label + no predicted spans. τ was only identified/recorded (`evaluation.evidence_matching.TAU_EVIDENCE`, identical to `evaluation.metrics`' default), not tuned.

## 3. Tests
**40 unit tests added** (`tests/test_evidence_matching.py`): exact match unchanged; 6 whitespace variants (multiple spaces, line break, tab, CRLF, NBSP, thin space) each requiring the ORIGINAL span to be recovered; 5 zero-width characters; NFC equivalence; the real E13 zero-width case; **9 adversarial negatives** that must NOT match (removed negation, added negation, missing word, changed legal term, changed number 30→60, changed party, paraphrase, case change, inserted punctuation) plus the three spec examples (shall not→shall, 30→60 days, may→shall); word-boundary bridging (`foo bar` ≠ `foobar`); curly-vs-straight quotes and ellipsis-joined quotes deliberately unmatched; multi-occurrence policy incl. gold-on-second-occurrence; absolute-coordinate offset recovery with chunk offsets; joint-semantics equivalence to `evaluation.metrics`; v1 == historical script implementation on 200 random cases and v1 ⊆ v2. **Suite: 338 → 378, all passing.**

## 4. Historical re-scoring (stored outputs only; v1 reproduces each experiment's reported joint exactly)
| Run | joint v1→v2 | Evid. recall v1→v2 | Evid. precision v1→v2 | source-valid records v1→v2 | mappings changed |
|---|---|---|---|---|---|
| E05 Qwen full-context | 42→43 | .250→.260 | .287→.299 | 53→57 | 4 |
| E07 Qwen RAG | 50→51 | .290→.310 | .358→.383 | 49→54 | 5 |
| E08B GPT-RAG | 111→113 | .860→.880 | .835→.854 | 97→100 | 3 |
| E11 A2 (=E08B) / A3 | 111→113 / 111→113 | .860→.880 / .840→.860 | .835→.854 / .824→.843 | 97→100 / 93→97 | 3 / 4 |
| E12A top-11 | 117→119 | .910→.930 | .843→.861 | 102→106 | 4 |
| E12B P0 / P1 / P2 / P3 | 114→116 / 112→113 / 106→107 / 122→122 | .850→.870 / .850→.860 / .850→.860 / .920→.920 | .825→.845 / .802→.811 / .787→.796 / .885→.885 | 100→102 / 103→104 / 104→105 / 103→103 | 2 / 1 / 1 / 0 |
| E12C P0 / P3 | 128→128 / 125→126 | .920→.920 / .900→.910 | .929→.929 / .891→.901 | 94→97 / 96→99 | 3 / 3 |
| E13 FULL / RAG | 116→120 / 113→114 | .900→.930 / .840→.840 | .857→.886 / .816→.816 | 96→101 / 97→100 | 5 / 3 |
**Total: 41 unit-level changed mappings (38 unique records; E11-A2 repeats E08B's 3). 0 v1-valid→v2-invalid regressions of any kind** (no span lost, no source-valid true→false, no joint success→fail); E05/E07 Qwen also had 4/5 rescues. Not re-scored: E01/E03 (label-only), E04 (no model evidence), any TEST artifact.

## 5. Manual review of EVERY changed case (all 38 unique records; no sampling)
For each: model quote vs recovered original NDA text vs normalization responsible vs recovered span vs gold overlap. **38/38 = TRUE FORMATTING RESCUE; 0 FALSE POSITIVE; 0 AMBIGUOUS.** Automatic proof for all 41 rescued quotes: quote and recovered slice are identical after deleting whitespace/zero-width characters and NFC.
Responsible transformation: line-break / whitespace-run merges in 38/38 (E13 `69::nda-2` also has zero-width spaces); no NBSP-only or NFC-only case occurred historically (covered by unit tests). Observations: (i) many rescued quotes are long merged multi-sentence quotes that cover several annotated spans — v1's existing overlap semantics for any verbatim multi-span quote, unchanged; (ii) newly mapped evidence on NotMentioned-gold cases (E05/E07 `94::nda-16`, `350::nda-10`) occurred only where the label was already wrong, so no NotMentioned case flipped joint success→fail; (iii) several changes only add spans to already-mapped cases. Full per-case table: notebook §6 and `results/rescoring_case_records.json`.

## 6. Decision-stability checks (frozen rules re-applied offline; NOT new benchmarks)
- **E13 (FULL vs RAG):** FULL joint 116→**120**, RAG 113→**114** (net −3 → **−6**); Evidence Recall FULL .900→.930, RAG .840→.840 (gap −6.0→**−9.0pp**); Evidence Precision FULL .857→.886, RAG .816→.816 (gap −4.2→**−7.0pp**). Contradiction and Macro-F1 are label-based (unchanged). Guards 3 and 4 still fail, net ≤ 0 → **B remains B**. (The earlier E13 post-hoc sensitivity, which also segmented ellipsis-joined quotes, gave FULL 121; frozen v2 does not segment ellipses, so `15::nda-12` is not rescued — 120.)
- **E12B prompt statuses:** P0 114→116, P1 112→113, P2 106→107, P3 122→122; P3 vs P0 net +8→**+6** (near-tie unchanged), P1 −2→−3 (no benefit), P2 −8→−9 (harmful) → same statuses; Contradiction/Macro-F1 unchanged.
- **E12C confirmation:** P0 128→128, P3 125→**126**: net −3 → **−2**, band **NO CONFIRMATION** under both. **One nuance to record:** the E12C narrative said P3 failed the evidence-precision guard (−3.8pp); under v2 that gap is **−2.8pp, which would pass** — the decision does not rest on it (net joint ≤ 0 alone gives NO CONFIRMATION). Pooled joint 242/247 → 244/248 (+5 → +4); E12B +6 vs E12C −2: the manifest reversal remains. **KEEP P0 unchanged.**
- **E11 agent:** A2 111→113, A3 111→113; net joint **0 → 0**; joint fail→success 1 and success→fail 1 under both (McNemar p = 1.0). Decision C (A3 confirms E09 no-go) unchanged.
**No frozen decision changes under v2; no stop condition triggered.**

## 7. Retrieval metrics
Unaffected: Recall@K, MRR and `retrieval_contains_gold` use chunk-vs-gold character-offset overlap (`evaluation.scorer.map_chunks_to_gold_span_indices`), not text matching. Left unchanged.

## 8. Acceptance criteria (architecture-neutral)
1 formatting-variant unit tests pass ✅ · 2 adversarial negatives stay non-matches ✅ · 3 no unexplained v1-valid→invalid ✅ (0) · 4 every changed case reviewed, formatting-only ✅ · 5 no false positives ✅ · 6 E13/E12/E11 sensitivity documented ✅. The normalization rules were fixed before re-scoring and not extended after seeing which arm benefits (the rescue set is dominated by line-break merges that affect every model; FULL simply produced more of them).

## 9. Final evaluator status: **A — EVIDENCE_EVALUATOR_V2 APPROVED**
Recommended (not done here): make v2 the default for the final TEST benchmark and for any future analyzer; optionally adopt the same normalization in the inference-time validator later (production change, separately reviewed).

## 10. Residual limitations (outside the frozen v2 spec; not fixed)
Quotes still unmatched under v2 (counts in `results/rescoring_summary.json`): curly-vs-straight quotes (E13 FULL 3, RAG 0; E07 2; others ≤1), ellipsis-joined quotes (E13 FULL 1, E12C P0 1, E05 1), and paraphrase/truncation/PDF artefacts (dominant for Qwen E05/E07: ~29 each). **These were deliberately not added** (spec frozen before re-scoring; adding rules after seeing which arm benefits is barred). If a future evaluator version wants typographic-quote or ellipsis handling it needs its own predeclared spec — and note that it would again favour the arm that emits more such quotes (currently FULL), so it should be decided on principle, not on outcome. Long merged quotes that cover many annotated spans are not penalised by the overlap-based joint metric (pre-existing).

## 11. Confirmations
Zero model calls; **no TEST access** (no new code references test.json or TEST artifacts); ledger unchanged at **$2.8044**; no prompt/retrieval/architecture/pipeline change; historical raw prediction files not modified; τ unchanged; joint semantics unchanged; retrieval scoring unchanged.

New files: `evaluation/evidence_matching.py`; `tests/test_evidence_matching.py`; `scripts/{e13b_rescore_historical.py, e13b_stability_checks.py}`; `experiments/E13B_evidence_evaluator_hardening/{README.md, config.yaml, summary.md, E13B_evidence_evaluator_hardening.ipynb (executed), results/{rescoring_summary.json, rescoring_case_records.json, stability_checks.json, manual_audit.json}}`. Modified: `docs/experiment_registry.md`.

---

# FINAL REVIEW ADDENDUM (approved): evidence_evaluator_v2 FROZEN

**`evidence_evaluator_v2` is frozen as the canonical evaluator (`evaluation/evidence_matching.py`, `CURRENT_EVIDENCE_EVALUATOR = "evidence_evaluator_v2"`) and is the DEFAULT for all future final evaluation, including the final TEST benchmark.** v1 remains identifiable (`evidence_to_span_indices_v1`, `EVIDENCE_EVALUATOR_V1`). Historical reports remain versioned as originally produced (v1); future analyses that cite earlier metrics must state the evaluator version. Historical raw outputs are not rewritten.
Frozen scope: exact-first, then NFC / zero-width removal / whitespace-collapse fallback with original-offset recovery; τ = 0.5 and joint semantics unchanged; retrieval scoring (chunk-vs-gold character overlap) unaffected.
**Intentional non-coverage (not to be added now):** curly-vs-straight quotes, ellipsis-joined quotes, paraphrases, truncation, broader PDF/OCR artefacts. Case `15::nda-12` therefore stays unmapped under frozen v2; the earlier E13 post-hoc scorer (FULL = 121) is **not** canonical — canonical v2 E13 FULL joint = **120**.
**Merged-quote limitation (v1 and v2):** the overlap-based metric can let a long merged quote cover multiple annotated spans without penalising excess evidence; not to be changed before TEST unless a separate predeclared evaluator experiment is approved.
**Decision stability (preserved):** E13 FULL 116→120, RAG 113→114, RAG−FULL −3→−6, evidence gaps −9pp recall / −7pp precision, **B remains B** (FULL remains the preferred DEV architecture candidate); E12B P3 vs P0 +8→+6 (near-tie); E12C −3→−2, still NO CONFIRMATION (its historical evidence-precision guard failure would no longer fail under v2, but net joint ≤ 0 independently gives no confirmation), **KEEP P0**; E11 net joint 0→0, agent conclusion unchanged.
**Later productionization task (NOT done here):** `pipeline/evidence_validator.py` (inference-time, v1 exact check) is deliberately unmodified — E13B fixes offline evaluation only; aligning the runtime validator would change system behaviour and must be a separate production experiment/change.
**TEST:** E13B accessed no test.json, TEST predictions, or TEST evaluation artifacts; the final TEST benchmark has not started.
