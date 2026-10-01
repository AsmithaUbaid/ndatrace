# Report-file retention and cleanup proposal

No file was deleted or moved during consolidation. Destructive cleanup is awaiting explicit approval.

## Retain: authoritative workflow

- `reports/NDATrace_Final_Report.html` — only submission report; self-contained publication.
- `reports/NDATrace_Reasoning_Report_Source.html` — editable source template.
- `reports/reasoning-assets/*.svg` — reproducible intermediate figure sources embedded at build time.
- `scripts/generate_reasoning_report_assets.py`, `scripts/build_reasoning_report.py`, `scripts/verify_reasoning_report.py` — active generation and verification workflow.
- `reports/NDATrace_Reasoning_Verification.txt` — latest verification record.
- `reports/NDATrace_Evidence_to_Decision_Map.md`, `NDATrace_UI_to_Report_Map.md`, `NDATrace_Notebook_Plot_Inventory.md`, `NDATrace_Professor_Compliance.md`, `NDATrace_Reasoning_Evidence_Map.md`, `NDATrace_Reasoning_Audit.md` — supporting audit evidence, not submission competitors.

## Retain: experiment and reproducibility evidence

Everything under `experiments/`, `results/`, `data/`, `pipeline/`, `evaluation/`, `docs/architecture_decisions/` and the project UI. Original E18/E24 plots remain in place as immutable experiment evidence.

## Proposed archive (useful history, not deletion)

Move to `reports/archive/`:

- `NDATrace_Final_Report.pre-cost-redesign.html`
- `NDATrace_Final_Report.pre-current-prompt.html`
- `NDATrace_Final_Report.pre-reasoning-redesign.html`
- `NDATrace_Final_Report.pre-ui-refinement.html`
- `NDATrace_Reasoning_Report_Source.pre-ui-refinement.html`
- `NDATrace_Final_Report_HTML.pre-cost-redesign.md`
- `NDATrace_Final_Report_HTML.pre-reasoning-redesign.md`
- `NDATrace_Report_Audit.md` if its useful history should be preserved separately.

## Proposed deletion after archive verification

- `reports/NDATrace_Final_Report.md` — obsolete PDF-oriented narrative source.
- `reports/NDATrace_Final_Report_HTML.md` — superseded editable source.
- `reports/NDATrace_Final_Report.pdf` and `output/pdf/NDATrace_Final_Report.pdf` — competing generated submission formats; delete only if the course submission truly requires HTML only.
- `reports/figures/submission_*.png` — old report-only generated figures, provided no remaining document references them.
- `scripts/render_submission_html.py`, `scripts/verify_submission_report.py`, `scripts/render_final_report_html.py`, `scripts/render_final_report_pdf.py` — obsolete report-generation routes, provided repository-wide dependency search remains empty after README/documentation reference updates.

## Ambiguities retained for user decision

- Whether a PDF export is still required by the learning-management system.
- Whether historical audit Markdown should be archived or retained beside the active audit set.
- Whether old PNGs are referenced by any external presentation or submitted video not represented in the repository.

Completed cleanup in this pass: **none**. The report and README now designate one authoritative HTML, but historical files remain untouched until approval.
