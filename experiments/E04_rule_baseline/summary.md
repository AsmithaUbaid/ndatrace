# E04 — Rule-Based Classification Baseline — COMPLETE

**Stage A (below): audit of the existing historical rule baseline and a proposal for how E04
should measure it.** **Stage B (results in the final section, "Stage B — Results"): the
approved design (reuse `pipeline/rule_baseline.py` unmodified, no tuning, no new rule family)
was run on the full official TRAIN split.** `A0_rule_baseline_v1` is now frozen.

## 1. Research question

"How far can a cheap deterministic rule-based classifier go on NDA compliance classification
before using an LLM?" This is a classification-rules experiment only -- not retrieval
optimisation (E06 is already frozen and untouched here) and not prompt selection
(`classification_prompt_v1` is untouched here).

## 2. Audit of the existing rule baseline

| Component | Current behavior | Historical result | Reusable? | Problems / leakage risk |
|---|---|---|---|---|
| **Input representation** | `doc.text` -- the full NDA document, lowercased for matching | Used identically in every historical run (B02, evidence-comparison, T041) | Yes, unmodified -- see section 3 for why this is the *right* choice, not just inherited | None -- full text is public per-document info available at inference time |
| **Rule mechanism** (`pipeline/rule_baseline.py`) | Per-hypothesis (17 fixed IDs) literal positive/negative keyword-phrase lists; first-match `str.find()`, case-insensitive | Same code since B02 (WBS T014) | Yes, as code/architecture | See "Historical contamination" below -- the specific phrase lists carry disclosed exposure |
| **Decision priority** | negative match -> Contradiction; else positive match -> Entailment; else -> NotMentioned | Unchanged since B02 | Yes | NotMentioned is a pure default fallback -- structurally the "easy" label here too, same caveat as Oracle's NotMentioned (E01) |
| **Negation logic** | None generic -- negation is baked into literal pre-composed phrases (e.g. `"shall not solicit"` as its own full string), not detected algorithmically | Unchanged since B02 | Yes, with caveat: this means novel negation phrasings not in the literal list are invisible to the rule, by design (deliberately crude, per the module's own docstring) | No leakage risk; a genuine coverage gap, expected for a "cheap" baseline |
| **Contradiction-specific patterns** | None beyond the same per-hypothesis negative-phrase list -- no exception/carve-out handling, no cross-clause reasoning | Unchanged since B02 | Yes | Directly relevant: E03 already found 43/46 of Qwen's non-retrieval-limited Contradiction failures co-occurred with an exception/carve-out indicator (`experiments/E03_prompt_selection/summary.md`) -- the rule baseline has *zero* mechanism for this at all, so its Contradiction recall is expected to be weak for the same underlying reason, independent of any LLM |
| **Evidence output** | `classify_with_span` returns the character span of the *first* matching phrase (not the whole clause), mapped to overlapping `doc.spans` indices for scoring (`scripts/run_full_rule_baseline_test.py`'s pattern) | Added after B02's original run specifically to support Evidence Recall/Precision/MRR comparison against semantic retrieval (`docs/experiments.md`) | Yes -- see section 6, sufficient for the joint metric | None identified -- see section 6 |
| **Confidence / fallback logic** | None in the module itself -- callers (harness/`Prediction`) stamp a flat `confidence=1.0` regardless of match; no abstention | Unchanged since B02 | N/A for E04 (confidence/abstention is a separate reconstruction-v2 phase, not E04's scope) | None |

**Historical rule experiments found**: exactly one build (B02, WBS T014). No ADR or dated
Decisions Log entry shows the keyword lists being iteratively revised in response to measured
accuracy -- unlike the LLM prompt lineage (v1-v6), there is no "rule v2/v3" history. The module
was reused three times after its initial build, each time as a fixed artifact: (1) the
Evidence Recall/Precision/MRR comparison against semantic retrieval, (2) fusion into RAG
retrieval via RRF (`query_rerank_and_boost`, adopted), (3) the final T041 test-set evaluation
(both a 500-case subsample and the full 2,091-case TEST split). None of these reuses modified
the keyword lists themselves.

## 3. What does the rule baseline see? (full text vs. retrieved excerpts vs. matched clauses)

**Audited, not assumed**: every historical invocation (`scripts/run_full_rule_baseline_test.py`,
and by inspection the same call pattern in the original B02/evidence-comparison scripts) passes
`doc.text` -- the complete NDA document string -- to `classify_with_span`/`classify_by_keywords`.
This is **(A) full NDA text**, never (B) retrieved excerpts or (C) pre-matched clauses.

**Proposed for E04, and justified rather than silently inherited**: keep (A) full NDA text.
Reasoning, applying the brief's own stated principle ("A0 should not inherit unnecessary
LLM-era complexity unless needed"):
- Retrieval (`retrieval_v1`: BM25 -> clause_256 -> top-20 -> rerank -> top-5) exists to solve a
  problem A0 doesn't have -- fitting content into an LLM's cost/context budget. A rule-based
  keyword classifier pays no per-token cost and has no context-window limit; substring search
  over the full document is already trivially cheap (single-digit milliseconds per case, per
  the runtime estimate in section 13).
- Routing A0 through `retrieval_v1` would *actively hurt* it for no gain: retrieval_v1's own
  measured evidence-recall ceiling is ~92% (E06) -- capping the rule baseline's candidate text
  at that ceiling would introduce a retrieval-miss failure mode into a component whose entire
  value proposition is being simple and having no such failure mode.
  Feeding A0 the whole document lets it find a keyword match anywhere the document contains
  one, which is the fairest and cheapest way to answer "how far can *rules alone* go."
- This also matches unbroken historical precedent (no invented behavior change), which the
  brief explicitly warns against silently altering.

## 4. No gold leakage (design-level check)

The proposed R0 (section 9) uses only: `doc.text` (public document content) and the fixed,
split-invariant hypothesis ID / hypothesis text (identical across TRAIN/DEV/TEST, not sourced
from any split's labels or documents). No gold label, gold evidence span, or annotation
metadata is read by `classify_by_keywords`/`classify_with_span` at inference time --
confirmed by reading the full function bodies (section 2 table); neither function takes a
label or gold-span argument.

## 5. Output requirement

Confirmed already met by the existing code: `classify_by_keywords`/`classify_with_span` always
return exactly one of `{Entailment, Contradiction, NotMentioned}`, with `classify_with_span`
additionally returning either a real matched-phrase character span or `None`. No change needed
for Stage A.

## 6. Evidence requirement -- can the current implementation satisfy the joint metric?

**Yes, structurally adequate as-is.** Audit of the mechanism
(`scripts/run_full_rule_baseline_test.py`'s pattern, reused verbatim for E04):
- For Entailment/Contradiction: the matched phrase's character span is intersected against
  every span in the document's full `doc.spans` list (interval-overlap test); any span whose
  bounds contain or overlap the matched phrase is recorded as a `retrieved_span_indices` entry.
  This is a genuine, non-fabricated evidence claim -- it names the actual document location the
  rule fired on, not "the whole document was inspected." The scorer then checks this list
  against the case's real gold span indices exactly as it does for retrieval predictions
  (`evaluation.scorer`), so the rule baseline is scored on the same footing as any other
  architecture.
- For NotMentioned: `classify_with_span` returns `span=None` whenever no rule fires, which maps
  to an empty `retrieved_span_indices` list -- no evidence is ever fabricated for this label.
- **One real, disclosed limitation, not a bug**: the evidence is always the single *first*
  matching phrase occurrence, never multiple spans or the surrounding clause boundary. This is
  appropriate for "cheap and interpretable" (section 9's own stated priority) but means Evidence
  Recall for the rule baseline will structurally be lower than a system that returns a whole
  clause, even when the label is right -- expected, not a defect, and should be reported as
  such rather than treated as a gap needing repair.

**No structural repair is proposed.** The mechanism already exists in
`scripts/run_full_rule_baseline_test.py`'s pattern; E04 Stage B would extract this into a small
reusable function (`evaluation/rule_scoring.py` or similar) rather than duplicate it inline,
per the notebooks-vs-pipeline rule -- a code-organization task, not a semantic fix.

## 7. TRAIN only for development -- and historical contamination disclosure

**Proposed E04 development universe: full official TRAIN split only** (423 documents x 17
hypotheses = 7,191 cases, verified directly against `data/contractnli/train.json` -- not a
stale count from a comment). DEV and TEST are not touched anywhere in E04.

**Historical exposure, disclosed plainly (not hidden or silently resolved)**: the *exact same
code and keyword lists* proposed for R0 have already been:
1. Evaluated on the full official **DEV** split (1,037 cases) as experiment B02, with accuracy
   59.9% / macro-F1 0.493 reported as a headline number in `docs/experiments.md`.
2. Evaluated on DEV's 614-case Entailment/Contradiction subset for the evidence-quality
   comparison against semantic retrieval (`docs/experiments.md`'s evidence-recall row).
3. Evaluated on the full official **TEST** split (2,091 cases, plus an earlier 500-case
   subsample) as part of T041's final architecture comparison.

**Is this outcome-driven tuning, or just visibility?** No historical record (`docs/decisions.md`,
`docs/experiments.md`) shows the keyword lists being revised after seeing DEV or TEST accuracy
-- there is no "rule v2" the way prompts went through v1-v6. The module's own docstring states
the keywords were written against ContractNLI's 17 canonical hypothesis *definition* texts
(split-invariant metadata, identical across TRAIN/DEV/TEST), not against DEV/TEST document
content or measured outcomes. This looks like a single hand-authored build, not iterative
DEV/TEST-outcome chasing.

**But it is still real exposure, and reconstruction-v2's own discipline (E00/E01/E03/E06) has
consistently treated even this milder form of visibility as worth disclosing rather than
assuming away.** This is flagged as an **unresolved decision for the user** (section 15), not
resolved unilaterally, with two options:

- **Option A (reuse + disclose)**: keep the exact historical keyword lists as R0, evaluate
  fresh on TRAIN only in Stage B, and prominently document this lineage/exposure in every E04
  artifact (as already done in `config.yaml`). Fast; the risk is low (visibility without proven
  outcome-chasing) but not zero.
- **Option B (rebuild blind)**: author a new keyword set referencing only the fixed hypothesis
  definition text (same split-invariant source used historically) with zero developer memory
  of, or reference to, the historical B02/T041 accuracy numbers or DEV/TEST document content --
  effectively re-deriving something very similar by construction, since the hypothesis
  definitions themselves haven't changed, but with a clean, defensible chain of custody.

No decision is made here -- **recommendation is Option A** (the exposure is disclosed and low-
severity, and reconstruction-v2's `docs/decisions.md`/`experiment_registry.md` pattern already
handles "known historical exposure, no outcome-chasing evidence" as an acceptable disclosed
caveat elsewhere), but this is exactly the kind of threshold-of-rigor call the brief's own
Stage A/Stage B gate exists to let the user make explicitly rather than have it decided
silently.

## 8. Proposed TRAIN development universe

Full TRAIN split, all 423 documents x 17 hypotheses = **7,191 cases**, natural (unbalanced)
class distribution: 3,530 Entailment / 2,820 NotMentioned / 841 Contradiction (verified
directly, section 4's script). No subsampling is proposed, unlike E01/E03's diagnostic
manifolds (TRAIN_ORACLE_v1/TRAIN_PROMPT_v1) -- those exist to control *hosted LLM cost*, which
does not apply here ($0, seconds of runtime for the full universe). A natural-distribution
accuracy/macro-F1 number is also more representative of real deployment composition than an
artificially balanced 50/50/50 sample, and using the full universe removes any question of
sampling variance in the reported floor.

## 9. Proposed simplest R0 rule baseline

**R0 = `pipeline/rule_baseline.py`, unmodified**, run fresh against the full TRAIN universe
(section 8), subject to the Option A/B decision in section 7. No new rule logic, no threshold
tuning, no case-specific patches -- this establishes the actual current floor before any
reconstruction-v2-specific rule engineering is considered, per section 9's own instruction not
to build a rule system before measuring the simple baseline.

## 10. Additional staged rule experiments -- none proposed yet

Per the brief's own "one knob at a time" / "do not overfit" instructions: **no R1/R2/R3 is
proposed in this Stage A document.** The brief's own example ladder (R1 negation, R2
Contradiction patterns, R3 exception/carve-out) is illustrative, not pre-authorized -- each
would need to be justified by a *specific, observed* R0 TRAIN failure pattern, not proposed
speculatively before R0 has even run. Given section 2's audit already surfaces one plausible
candidate (Contradiction recall likely weak due to zero exception/carve-out handling, echoing
E03's independent finding on the same dataset), this is flagged as a **hypothesis to check
against R0's real TRAIN failure data**, not a pre-approved R1.

## 11. Proposed metrics (Stage B)

Exactly as specified: Accuracy, Macro-F1, per-class recall (Entailment/Contradiction/
NotMentioned, Contradiction Recall reported with a 95% Wilson CI per the project's standing
convention), confusion matrix, Evidence Recall/Precision, joint label+evidence correctness,
mean/p90 latency, cost ($0), rule-fire rate (percentage of cases where at least one positive or
negative phrase matched) vs. default-fallback rate (percentage that reached NotMentioned purely
by no match, as distinct from genuine NotMentioned cases the rule correctly abstained on --
these need to be reported separately since NotMentioned is both a real label and the default
fallback).

## 12. Failure-analysis plan (Stage B)

Same evidence-based, non-forced-categorization methodology used in E03
(`scripts/analyze_e03_prompt_selection.py`'s pattern): tag failures with *observed* signals
(e.g. "rule fired on a distractor clause" = matched phrase's span does not overlap any gold
span while the case has gold evidence elsewhere; "default NotMentioned overuse" = case is
Entailment/Contradiction but no phrase matched at all; "conflicting rule matches" = both a
positive and negative phrase are present in the text, decision determined solely by priority
order) rather than pre-labeling from the brief's illustrative list. Keyword/heuristic-based
family tags will be explicitly marked as automated candidate signals, not confirmed manual
reads of every case, consistent with the wording discipline established in E03's summary.

## 13. Expected runtime

Single-digit seconds for the full 7,191-case run: pure Python substring search
(`str.find()` over documents of a few KB to ~40KB, at most ~10-15 keyword lookups per case) has
no I/O or model-call latency. The dominant cost will be JSON parsing of `train.json` and
evidence-span-to-`doc.spans` overlap computation, both cheap at this scale.

## 14. Files to create / change

**Stage A (this commit)**: `experiments/E04_rule_baseline/{README.md, config.yaml, summary.md}`,
`experiments/E04_rule_baseline/results/` (empty directory, created for Stage B). No code files
touched.

**Stage B (after approval)**:
- `scripts/run_e04_rule_baseline.py` (new -- loads full TRAIN, runs R0, scores, saves results;
  no LLM/API calls).
- Possibly a small `evaluation/rule_scoring.py` (new -- extracts the span-to-doc.spans overlap
  mapping from `scripts/run_full_rule_baseline_test.py`'s inline pattern into a reusable
  function, avoiding duplication per the notebooks-vs-pipeline rule).
- `scripts/analyze_e04_rule_baseline.py` (new -- metrics + failure analysis, mirroring
  `scripts/analyze_e03_prompt_selection.py`'s structure).
- `experiments/E04_rule_baseline/results/run_E04_R0_train.json`,
  `run_E04_R0_train_cases.jsonl`, `rule_failure_analysis.csv`.
- `experiments/E04_rule_baseline/E04_rule_baseline.ipynb`.
- `pipeline/rule_baseline.py` -- unmodified if Option A (section 7) is chosen; a new file
  (e.g. a `_v2` module or a documented in-place rewrite with lineage notes) if Option B is
  chosen -- **pending the user's decision**.

## 15. Unresolved issues (for explicit review)

1. **Option A vs. B (section 7)**: reuse the historical keyword lists with disclosure, or
   rebuild blind from the split-invariant hypothesis definitions only. Recommendation: A.
2. **Whether R1 (negation) or a Contradiction/exception-handling rule family will be needed at
   all** cannot be answered before R0's real TRAIN failure data exists -- section 2's audit
   only provides a plausible hypothesis, not a decision.
3. **Where the reusable evidence-scoring function should live** (`evaluation/rule_scoring.py`
   vs. inlining in the runner script) -- a minor code-organization call, not blocking Stage B
   approval.

Stage A ended here and was approved with one binding decision: **reuse
`pipeline/rule_baseline.py` unchanged as A0 (Option A, section 7) -- no rebuild, no new rules,
no tuning, no R1/R2 rule variants in E04.**

---

## Stage B — Results (run on approval, full TRAIN, R0 only)

**Verified before evaluation** (`scripts/run_e04_rule_baseline.py`): 423 TRAIN documents, 7,191
cases, natural class distribution exactly {Entailment: 3,530, NotMentioned: 2,820,
Contradiction: 841} -- matches section 8's proposal exactly. All 17 hypothesis IDs confirmed to
have a defined rule. `pipeline/rule_baseline.py` confirmed unmodified at run time (`git diff`
against commit `7d33d038f81a1b0da093bce70cb22e267c552f91`, the last commit touching the file,
is empty). No DEV, no TEST, no LLM/API call anywhere in this run.

### Classification metrics

| Metric | Value |
|---|---|
| Accuracy | 56.8% |
| Macro-F1 | 0.471 |
| Entailment Recall | 38.0% |
| **Contradiction Recall** | **17.2% [95% CI 14.8%, 19.9%]** |
| NotMentioned Recall | 92.2% |

### Confusion matrix (rows = gold, cols = predicted; order Entailment/Contradiction/NotMentioned)

- **Entailment**: `[1341, 170, 2019]`
- **Contradiction**: `[78, 145, 618]`
- **NotMentioned**: `[199, 21, 2600]`

### Rule-fire / default coverage

Overall: 27.2% of cases trigger some rule (22.5% positive-fired, 4.7% negative-fired); **72.8%
default to NotMentioned via no match at all.** By gold class: Entailment fires correctly on
1,341/3,530 (38.0%) and falls to default on 2,019/3,530 (57.2%); Contradiction fires correctly
on 145/841 (17.2%) and defaults on 618/841 (73.5%); NotMentioned correctly defaults on
2,600/2,820 (92.2%). **NotMentioned's strong recall is driven almost entirely by the default
fallback, not genuine detection** -- exactly the risk section 8 of the Stage A proposal flagged
in advance.

**Caveat, stated explicitly**: high NotMentioned recall is primarily driven by the default-to-
NotMentioned fallback and should not be interpreted as strong semantic understanding.

### Evidence metrics and joint label+evidence correctness

Using the frozen E00 evidence-hit semantics (matched-phrase span, interval-overlapped against
the document's annotated gold spans; full-document access never counts as evidence):

| Metric | Value |
|---|---|
| Evidence-bearing cases (Entailment+Contradiction) | 4,371 |
| Evidence Recall | 29.0% |
| Evidence Precision | 64.8% |
| Joint label+evidence correctness, overall | 48.2% |
| Joint, by class — Entailment | 21.8% |
| Joint, by class — Contradiction | 11.5% |
| Joint, by class — NotMentioned | 92.2% |

Evidence precision (64.8%) is markedly higher than evidence recall (29.0%): when the rule does
claim a span, it is usually a real gold span, but it either doesn't fire at all (the dominant
coverage gap) or fires on-topic without landing inside the specific annotated span (see the
"misaligned evidence" failure family below). NotMentioned's joint score equals its label recall
exactly, a structural property of the metric for a system whose only NotMentioned path is the
no-evidence default, not a separate achievement.

### Latency and cost

Mean 0.062ms/case, median 0.051ms, p90 0.118ms. Total wall time for all 7,191 cases: 0.67s.
Cost: **$0** — spend ledger unchanged.

### Failure analysis — errors classified only from observed data

3,105 of 7,191 cases (43.2%) are wrong. Breakdown (verified to sum exactly to 3,105):

| Count | % of errors | Failure family |
|---|---|---|
| 2,019 | 65.0% | Entailment→NotMentioned, no phrase matched (coverage gap) |
| 618 | 19.9% | Contradiction→NotMentioned, no phrase matched (coverage gap) |
| 220 | 7.1% | Rule fired on distractor text in a truly NotMentioned document (false positive) |
| 170 | 5.5% | Entailment case matched a negative phrase instead (wrong-direction conflict) |
| 78 | 2.5% | Contradiction case matched a positive phrase instead (wrong-direction conflict) |

**The data does not support exception/carve-out or negation-specific handling as the dominant
problem** — that was E03's finding on a different architecture (Qwen + retrieval_v1), and it
was deliberately not assumed to transfer here. E04's own errors point overwhelmingly (84.9%) at
**plain lexical/paraphrase coverage**: the literal keyword phrases in `RULES` simply don't
appear in how ~2,637 of these documents actually phrase the relevant clause. The remaining
15.1% is roughly evenly split between false-positive distractor fires and wrong-direction
phrase conflicts — neither large enough to be "the" secondary problem on its own.

Separately, among the 4,086 correct predictions, **361 (8.8% of all correct cases) have the
right label but a matched-phrase span that does not overlap the real annotated gold evidence**
— a distinct "right answer, wrong/coincidental reason" failure mode worth naming even though it
doesn't affect the accuracy number.

### Representative examples

- **Correct, evidence-aligned**: `train::34::nda-7` (Entailment, matched "consultants",
  evidence hit).
- **Coverage-gap miss**: multiple Contradiction cases where `rule_fired=False` and the label
  silently defaulted to NotMentioned — the majority failure mode by count.
- **False-positive distractor fire**: cases where "negotiat" (intended for nda-10,
  confidentiality-of-the-agreement) or "representatives" (intended for nda-7) appeared in an
  unrelated part of a truly NotMentioned document.
- **Misaligned evidence**: `train::86::nda-8` (Entailment, matched "shall notify" — correct
  label, but the matched location didn't overlap the specific annotated evidence span).

Full per-case detail: `results/rule_failure_analysis.csv` (7,191 rows).

### Did the evidence-span mechanism work correctly?

**Yes**, exactly as predicted in Stage A section 6 — no code repair was needed. Every
Entailment/Contradiction prediction with a rule match produced a real, checkable character span
correctly overlap-tested against the document's actual annotated spans; every NotMentioned
prediction correctly claimed zero evidence. The one disclosed limitation (single first-match
span only, no whole-clause boundary) behaved exactly as anticipated, manifesting as the
"misaligned evidence" family above rather than any crash or fabrication.

### Final A0 freeze

**`A0_rule_baseline_v1`** = `pipeline/rule_baseline.py` at commit
`7d33d038f81a1b0da093bce70cb22e267c552f91`, **unmodified**. Input: full NDA document text
(never `retrieval_v1`'s retrieved excerpts — A0 is a deliberately separate, cheaper
architecture; later comparisons must not assume a shared input pipeline with RAG). Rule
semantics: per-hypothesis literal positive/negative phrase lists, negative-first priority,
NotMentioned default. Evidence semantics: matched-phrase character span, interval-overlapped
onto the document's annotated span list; no evidence ever claimed for NotMentioned. TRAIN
evaluation manifest: full official TRAIN split (423 docs × 17 hypotheses, 7,191 cases, natural
distribution), verified directly. **Historical DEV/TEST exposure is disclosed, not hidden**:
this exact code was previously evaluated on the full official DEV split (B02) and the full
official TEST split (T041) in the T-series pre-reconstruction project — this TRAIN run is a
reconstruction-v2 **characterization** of a pre-existing, unmodified baseline, not a claim that
A0 was developed blind to DEV/TEST. No rule tuning was performed or is proposed.

### Comparison context with E03 — descriptive only, not an architecture verdict

E03 (`classification_prompt_v1` = P0, Qwen, 150-case *balanced* TRAIN_PROMPT_v1 sample):
accuracy 52.7%, Macro-F1 0.507, Contradiction Recall 22.0%. E04 (A0 rule baseline, full
*natural-distribution* TRAIN, 7,191 cases): accuracy 56.8%, Macro-F1 0.471, Contradiction
Recall 17.2%. **These are not directly comparable** — different populations (150 balanced vs.
7,191 natural), different class weightings (E03's sample gives Contradiction 33% weight vs. its
true ~12% share). The proper matched architecture comparison is E12's job, not E04's.

### Files created (Stage B)

- `scripts/run_e04_rule_baseline.py` (runner — verifies TRAIN universe, runs the frozen
  `classify_with_span`, writes per-case JSONL with full traceability).
- `scripts/analyze_e04_rule_baseline.py` (metrics + failure analysis, mirroring
  `scripts/analyze_e03_prompt_selection.py`'s structure).
- `experiments/E04_rule_baseline/results/run_E04_R0_train_cases.jsonl` (7,191 records),
  `run_E04_R0_train.json` (aggregate metrics), `run_E04_R0_train_wall_seconds.json`,
  `rule_failure_analysis.csv` (7,191 rows).
- `experiments/E04_rule_baseline/E04_rule_baseline.ipynb` (executed, zero errors).

**No changes were made to** `pipeline/rule_baseline.py`, `retrieval_v1`,
`classification_prompt_v1`, or any DEV/TEST file.
