# NDATrace reasoning-depth redesign audit

## Structural diagnosis

The previous report was accurate but too compressed around final architecture metrics. Its experiment table carried useful evidence, yet the prose mostly summarised outcomes instead of exposing the engineering expectations, surprises, rejected alternatives and weaknesses of the evaluation. The original FULL baseline for the five-point risk-sensitive-recall target had only recently been corrected, and the agent/routing evidence did not receive space proportional to its importance. Cost reporting separated inference and human review but did not yet use a defensible investigation proxy to demonstrate why quality can reverse the apparent price ranking.

This redesign starts from a new HTML source and new SVG-generation script. No paragraph, table markup, style sheet or figure from the previous report is imported. Frozen experiment artifacts remain authoritative inputs because “fresh” writing must not change measured history.

## New organising argument

The report is no longer an experiment diary. Its argument is:

1. Rules establish that semantic interpretation is necessary.
2. Oracle evidence shows that model reasoning must be tested before retrieval is optimised.
3. Controlled experiments eliminate prompt, dense-retrieval and context complexity that did not earn its place.
4. FULL's significant Joint advantage is the central unexpected result.
5. RAG remains a bounded-context product hypothesis, not the quality winner.
6. Agent and routing failures justify mandatory human review.
7. Business value depends on reviewer behaviour, not sub-cent inference alone.

## Authoritative fresh workflow

| Purpose | Authoritative file |
| --- | --- |
| Editable report source | `reports/NDATrace_Reasoning_Report_Source.html` |
| Submitted HTML output | `reports/NDATrace_Final_Report.html` |
| Figure generator | `scripts/generate_reasoning_report_assets.py` |
| HTML publisher | `scripts/build_reasoning_report.py` |
| Offline verifier | `scripts/verify_reasoning_report.py` |
| Evidence map | `reports/NDATrace_Reasoning_Evidence_Map.md` |
| Evidence-to-decision chain | `reports/NDATrace_Evidence_to_Decision_Map.md` |
| UI-to-report content map | `reports/NDATrace_UI_to_Report_Map.md` |
| Notebook plot inventory | `reports/NDATrace_Notebook_Plot_Inventory.md` |
| Report-file cleanup proposal | `reports/NDATrace_Report_File_Audit.md` |
| Professor compliance | `reports/NDATrace_Professor_Compliance.md` |

The submitted HTML is now self-contained: the publisher embeds all nine generated SVGs and the verifier rejects external image, script or stylesheet dependencies. Previous HTML and editable-source versions remain preserved pending the cleanup approval listed in `NDATrace_Report_File_Audit.md`. The project UI was audited as an analytical index; its strongest verified retrieval, multi-agent and modeled volume-economics findings were incorporated with explicit interpretation boundaries. Frozen experiments, UI, demo script, predictions and gold labels remain unchanged.
