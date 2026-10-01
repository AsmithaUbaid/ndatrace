# NDATrace final report audit

Date: 1 October 2026. Scope: evidence chain, editable HTML report, figure generation and offline verification. No model inference was run, and no frozen experiment artifact or PDF deliverable was changed.

## Material findings and resolutions

- **Success-criterion baseline:** the original Problem Statement (Section 7) specifies the ≥5-point risk-sensitive-recall target against FULL-context LLM processing, not against the rule-based baseline. Measured against FULL, RAG's gain is only +1.2 points (69.1% to 70.3%); the originally proposed target was not achieved. The rule-based, non-AI baseline named in Section 4 is reported separately as a secondary comparison: RAG improves +16.6 points over Rule (53.6% to 70.3%). Both numbers are stated explicitly rather than picking one silently; RAG was retained as the bounded-context prototype on efficiency and individual-case grounds, not because it met the original quality target.
- **Cost interpretation:** the earlier report showed measured API cost and a hypothetical selective-review sensitivity chart but not the current mandatory-review workflow. A stacked current-workflow comparison (Rule/FULL/RAG at 1,000 requirement reviews, same human-verification assumption applied to all three) was built, then removed: at this scenario's scale the $3.33/case verification cost dwarfs the sub-cent API difference between architectures, so the three bars were visually indistinguishable and the chart risked misrepresenting a real but tiny difference. The same numbers are kept in the Table 5 "Cost-model input" text instead, which is accurate without implying a visual contrast that doesn't exist. It still omits unmeasured incremental rework and fixed cost and does not equate Rule's zero API spend with zero compute.
- **Population separation:** official TEST (n=2,091) remains the only population-level benchmark. The curated DEV battery (n=49; golden n=30; negative n=15; evidence-quality n=4) remains diagnostic and is not pooled with TEST.
- **Verification coverage:** the previous checker covered headline quality values, subgroup recomputation, figure existence and word count. It now also checks the original target and baseline, all official and targeted summary metrics, token/cost/latency values, failure arithmetic, cost-model arithmetic and exclusions, figure provenance, local links and known contradictory claims.
- **Duplicate workflows:** multiple historical report and figure scripts exist. They are retained for provenance, but only the authoritative HTML path below should be used for this submission. The PDF source and renderer are explicitly outside this workflow.

## Report inventory

| Component | Existing state | Source verified | Decision | Authoritative role |
| --- | --- | --- | --- | --- |
| `reports/NDATrace_Final_Report_HTML.md` | Editable HTML-specific source | Yes | Improve | **Single report source** |
| `scripts/render_submission_html.py` | Generates styled standalone HTML shell with local figure links | Yes | Keep | **Single HTML renderer** |
| `scripts/render_submission_assets.py` | Programmatic figures from saved artifacts and declared assumptions | Yes | Improve | **Single submission figure generator** |
| `scripts/verify_submission_report.py` | Offline consistency checker | Yes | Improve | **Single final verifier** |
| `reports/NDATrace_Final_Report.html` | Final editable/rendered deliverable | Generated | Replace via authoritative renderer | **Submission output** |
| `reports/figures/submission_*.png` | Five report figures | Yes | Keep; cost-breakdown chart built then removed as not meaningful | **Submission assets** |
| `reports/NDATrace_Final_Report.md` | PDF-oriented source | Previously audited | Keep unchanged | Non-authoritative for HTML |
| `scripts/render_final_report_html.py` | Older HTML workflow | Yes | Retain for provenance; do not use | Legacy |
| `scripts/render_report_figures.py` | Older figure workflow | Yes | Retain for provenance; do not use | Legacy |
| `reports/NDATrace_Final_Report.pre-cost-redesign.*` | Snapshot before this redesign | Byte-preserved | Keep | Recovery backup |
| Frozen experiment outputs and notebooks | Canonical measurements | Yes | Keep unchanged | Evidence inputs only |

## Authoritative regeneration sequence

Run from `ndatrace/`:

1. `python3 scripts/render_submission_assets.py`
2. `python3 scripts/render_submission_html.py`
3. `python3 scripts/verify_submission_report.py`

The cost chart formula is `volume × (measured API inference per case + assumed base verification per case)`. Its current inputs are 1,000 requirement reviews, five verification minutes per result and $40/hour. The resulting base verification cost is $3.3333 per case. Fixed operating cost and incremental rework are excluded because neither was measured; a deployment budget must add them rather than interpret them as zero.
