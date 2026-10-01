#!/usr/bin/env python3
"""Strict offline verification for the fresh reasoning-depth HTML report."""
from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/NDATrace_Reasoning_Report_Source.html"
OUTPUT = ROOT / "reports/NDATrace_Final_Report.html"
BACKUP = ROOT / "reports/NDATrace_Final_Report.pre-reasoning-redesign.html"
UI_REFINEMENT_BACKUP = ROOT / "reports/NDATrace_Final_Report.pre-ui-refinement.html"
RESULT = ROOT / "reports/NDATrace_Reasoning_Verification.txt"
ASSETS = ["architecture.svg", "oracle.svg", "retrieval.svg", "quality.svg", "agent.svg", "routing.svg", "failure_distribution.svg", "annual_volume_economics.svg", "cost_to_serve.svg"]


class ReportText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.numbered_depth = 0
        self.prose: list[str] = []
        self.inclusive: list[str] = []
        self.document: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        data = dict(attrs)
        self.stack.append((tag, data))
        if tag == "section" and data.get("id", "").startswith("s"):
            self.numbered_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "section" and self.numbered_depth:
            self.numbered_depth -= 1
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        tags = [tag for tag, _ in self.stack]
        if "style" in tags or "script" in tags or "svg" in tags or "Word counts:" in data:
            return
        self.document.append(data)
        if self.numbered_depth:
            self.inclusive.append(data)
        if any(tag == "p" and "analysis" in attrs.get("class", "").split() for tag, attrs in self.stack):
            self.prose.append(data)


def words(text: str) -> list[str]:
    return re.findall(r"\b(?:\d{1,3}(?:,\d{3})+|[\w][\w’'\-]*)\b", text)


checks: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    checks.append(f"PASS  {message}")
    print(checks[-1])


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    output = OUTPUT.read_text(encoding="utf-8")
    require(output != source, "published HTML is generated from, rather than duplicated from, the editable source")
    require("{{" not in output, "published HTML contains no unresolved generation placeholders")
    require("reasoning-assets/" not in output and '<img src=' not in output, "published HTML has no external figure dependency")
    require(output.count('<svg role="img"') == 9, "all nine figures are embedded as accessible inline SVG")
    require("<script" not in output.lower() and "<link rel=" not in output.lower(), "published HTML has no JavaScript or external stylesheet dependency")
    require(BACKUP.exists() and BACKUP.read_text(encoding="utf-8") != output, "previous report is preserved and differs from the redesign")
    require(UI_REFINEMENT_BACKUP.exists() and UI_REFINEMENT_BACKUP.read_text(encoding="utf-8") != output,
            "pre-UI-refinement HTML is preserved and differs from the refined report")
    require("NDATrace_Final_Report_HTML.md" not in source, "fresh report does not depend on the former editable source")
    require(source.count('<section id="s') == 8, "exactly eight required numbered sections")
    require(source.count('class="table-title"') == 11, "all eleven main-report tables have explicit titles")
    require(source.count("<figure>") == source.count("<figcaption>") == 9, "all nine figures have captions")

    parser = ReportText()
    parser.feed(output)
    prose_count = len(words(" ".join(parser.prose)))
    inclusive_count = len(words(" ".join(parser.inclusive)))
    document_count = len(words(" ".join(parser.document)))
    require(1020 <= prose_count <= 1380, f"analytical prose count {prose_count} is within 1,200 +/-15%")
    require(inclusive_count > prose_count, f"inclusive numbered-section count {inclusive_count} transparently includes tables and captions")
    require(all(f"{value:,}" in output for value in (prose_count, inclusive_count, document_count)), "all three generated word counts are disclosed in the report")
    require(inclusive_count > 1380 and "substantially longer" in output, "table-inclusive length exceeds guidance and is explicitly flagged")

    e20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
    full = e20["full_vs_rag_same_population"]["FULL"]
    rag = e20["full_vs_rag_same_population"]["RAG"]
    with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as stream:
        rule = next(row for row in csv.DictReader(stream) if row["system"] == "rule")
    official = {
        "Rule": [float(rule[k]) for k in ("accuracy", "macro_f1", "joint", "contradiction_recall", "notmentioned_recall")],
        "FULL": [full["accuracy"], full["macro_f1"], full["joint"], full["recall"]["Contradiction"], full["recall"]["NotMentioned"]],
        "RAG": [rag["accuracy"], rag["macro_f1"], rag["joint"], rag["recall"]["Contradiction"], rag["recall"]["NotMentioned"]],
    }
    for name, values in official.items():
        expected = [f"{values[0]:.1%}", f"{values[1]:.3f}", f"{values[2]:.1%}", f"{values[3]:.1%}", f"{values[4]:.1%}"]
        require(all(item in source for item in expected), f"{name} official quality values match canonical TEST artifacts")
    require(e20["population"]["n"] == 2091 and "n=2,091" in source, "official TEST population is explicit")

    require("Original target versus achieved result" not in source and "Not achieved" not in source,
            "removed target-status table is absent from the analytical report")

    e24 = json.loads((ROOT / "experiments/E24_targeted_evaluation/results/e24_analysis.json").read_text())
    require(e24["n_cases"] == 49 and "Targeted DEV - n=49" in source, "targeted DEV remains a separate 49-case block")
    for system in ("rule", "full", "rag"):
        m = e24["summary_by_system"][system]
        vals = [f"{m['accuracy']:.1%}", f"{m['macro_f1']:.3f}", f"{m['joint_correctness']:.1%}", f"{m['contradiction_recall']:.1%}"]
        require(all(v in source for v in vals), f"targeted {system} metrics match executed analysis")
    notebook = json.loads((ROOT / "experiments/E24_targeted_evaluation/E24_targeted_evaluation.ipynb").read_text())
    require(sum(c.get("execution_count") is not None for c in notebook["cells"] if c["cell_type"] == "code") == 8,
            "targeted notebook contains eight executed code cells")

    traces = [json.loads(line) for line in (ROOT / "experiments/E11_selective_agent_evaluation/results/agent_traces.jsonl").open()]
    tool_calls = sum(int(row.get("tool_calls", 0)) for row in traces)
    require(len(traces) == 15 and tool_calls == 0, "agent trace set confirms 15 triggers and zero tool calls")
    paired = json.loads((ROOT / "experiments/E11_selective_agent_evaluation/results/a2_vs_a3_paired_comparison.json").read_text())
    require("1 recovery, 1 regression, net 0" in source and "$0.0218" in source, "agent Joint transition and incremental cost are disclosed")
    require(abs(paired["metric_table"]["joint_overall"]["delta_A3_minus_A2"]) < 1e-12,
            "saved agent comparison confirms zero net Joint change")

    full_agent = json.loads((ROOT / "experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/arm_metrics.json").read_text())
    prompt_v2 = json.loads((ROOT / "experiments/E11_selective_agent_evaluation/addendum_agent_prompt_ablation/results/arm_metrics.json").read_text())
    require(full_agent["tool_use"]["cases_using_tool"] == 2 and full_agent["tool_use"]["useful_tool_case_counts"] == [0, 2],
            "full-agent diagnostic confirms 2/150 tool cases and zero useful recoveries")
    require(round(full_agent["baseline"]["joint"] * 100, 1) == 75.3 and round(full_agent["full_agent"]["joint"] * 100, 1) == 73.3,
            "full-agent Joint values match its evaluator-specific control")
    v2_ops = prompt_v2["operations"]["v2"]
    require(v2_ops["tool_using_cases"] == 30 and sum(v2_ops["tool_name_counts"].values()) == 39 and v2_ops["fallback_events"] == 25,
            "prompt-V2 behavior confirms 30 tool cases, 39 calls and 25 fallbacks")
    require(prompt_v2["tool_effectiveness"]["category_counts"] == {"neutral": 29, "harmful": 1}
            and round(prompt_v2["arms"]["v2"]["joint"] * 100, 1) == 68.7,
            "prompt-V2 confirms zero useful tool-associated recoveries and 68.7% Joint")
    require(all(value in source for value in ("2/150 tool cases", "30/150 tool cases", "0/30 useful", "75.3% → 68.7%")),
            "report includes the complete three-stage agent progression")

    routing = json.loads((ROOT / "experiments/E15_review_routing/results/validation_results.json").read_text())["policies"]
    for policy, review, capture, residual in (("R1", .043, .125, .265), ("R2", .210, .375, .229), ("R3", .514, .825, .104)):
        values = routing[policy]["joint"]
        require(round(values["review_rate"], 3) == review and round(values["error_capture"], 3) == capture and round(values["residual_error_rate"], 3) == residual,
                f"{policy} routing workload/capture/residual values recompute")

    failure_counts = e20["failure_taxonomy"]
    require(sum(failure_counts.values()) == e20["n_total_failures"] == 576, "official failure categories sum exactly to 576")
    require(all(str(n) in (ROOT / "reports/reasoning-assets/failure_distribution.svg").read_text() for n in failure_counts.values()),
            "failure figure contains every canonical count")

    full_outputs = []
    for path in (ROOT / "experiments/E17_final_test/results/run_E17_gpt_hosted_test_cases.jsonl",
                 ROOT / "experiments/E17B_full_test_completion/results/run_E17B_gpt_cases.jsonl"):
        full_outputs.extend(json.loads(line)["output_tokens"] for line in path.open())
    require(len(full_outputs) == 2091 and round(sum(full_outputs) / len(full_outputs)) == 727, "FULL output tokens recompute to approximately 727")
    require(round(e20["RAG_metrics"]["ops"]["output_tokens_mean"]) == 701,
            "RAG output tokens recompute to approximately 701")
    require(all(value in source for value in ("2,279", "1,131", "$0.00202", "$0.00168", "7.31 s", "7.14 s")),
            "token, cost and latency values match official artifacts")

    volume, verify_minutes, rework_minutes, rate = 1000, 5, 10, 40
    expected_totals = {
        "Rule": volume * (verify_minutes / 60 * rate + (1 - official["Rule"][2]) * rework_minutes / 60 * rate),
        "FULL": volume * (full["cost_per_case"] + verify_minutes / 60 * rate + (1 - full["joint"]) * rework_minutes / 60 * rate),
        "RAG": volume * (rag["cost_per_case"] + verify_minutes / 60 * rate + (1 - rag["joint"]) * rework_minutes / 60 * rate),
    }
    cost_svg = (ROOT / "reports/reasoning-assets/cost_to_serve.svg").read_text()
    require(all(f"${value:,.0f}" in cost_svg for value in expected_totals.values()), "stacked cost totals match declared formula")
    require("Fixed operating cost excluded" in cost_svg and "illustrative proxy" in cost_svg,
            "cost figure distinguishes excluded fixed cost and hypothetical rework")
    root = ET.fromstring(cost_svg)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    sensitivity_polylines = root.findall("svg:polyline", ns)[-3:]
    sensitivity_points = [[tuple(map(float, pair.split(","))) for pair in line.attrib["points"].split()] for line in sensitivity_polylines]
    require(all(1030 <= x <= 1720 and 240 <= y <= 690 for points in sensitivity_points for x, y in points),
            "all cost-sensitivity curves remain inside the plotting boundary")
    require("INFERENCE-ONLY / 1,000" in cost_svg and "0 added minutes" in cost_svg,
            "cost figure exposes inference-only expense and zero-investigation interpretation")
    annual_svg = (ROOT / "reports/reasoning-assets/annual_volume_economics.svg").read_text()
    annual_requirements = 500 * 17
    annual_expected = {
        "Manual": annual_requirements * (5 / 60 * 40),
        "Rule": annual_requirements * ((1 - official["Rule"][2]) * 5 / 60 * 40),
        "RAG": annual_requirements * (rag["cost_per_case"] + (1 - rag["joint"]) * 5 / 60 * 40),
        "FULL": annual_requirements * (full["cost_per_case"] + (1 - full["joint"]) * 5 / 60 * 40),
    }
    require(all(f"${value:,.0f}" in annual_svg for value in annual_expected.values()),
            "annual-volume scenario labels recompute from measured Joint and declared human-cost assumptions")
    require("scenario, not an observed company" in annual_svg and "Counterfactual selective-fallback scenario" in source,
            "annual-volume plot is explicitly labeled as modeled and counterfactual")

    for asset in ASSETS:
        path = ROOT / "reports/reasoning-assets" / asset
        require(path.exists() and path.stat().st_size > 1500, f"fresh figure exists and is non-trivial: {asset}")
        ET.parse(path)
        require(f'reasoning-assets/{asset}' in source, f"fresh source references {asset}")
    refs = re.findall(r'<img src="([^"]+)"', source)
    require(len(refs) == 9 and all((SOURCE.parent / ref).exists() for ref in refs), "all editable-source figure links resolve")
    local_hrefs = [ref for ref in re.findall(r'<a href="([^"]+)"', source) if not re.match(r'https?://', ref)]
    require(local_hrefs and all((SOURCE.parent / ref).resolve().exists() for ref in local_hrefs),
            "all local experiment links in the matrix resolve")
    require(not re.search(r'figures/submission_|docs/images/', source), "no former report figures are reused")

    matrix_start = source.index('<div class="table-title">Table 4.')
    matrix_end = source.index("</table></div>", matrix_start) + len("</table></div>")
    matrix_text = source[matrix_start:matrix_end]
    required_families = ["Majority", "Rule", "Oracle", "prompt", "Chunk", "retrieval", "reranking", "Top-K", "FULL", "RAG", "Selective-agent", "Forced full-agent", "routing", "robust", "Targeted", "cost-to-serve"]
    require(all(term.lower() in matrix_text.lower() for term in required_families), "experimental matrix covers every required family")
    require(matrix_text.count('<th>') == 3 and '<colgroup><col><col><col></colgroup>' in matrix_text,
            "experimental matrix uses the required three-column structure")
    require(matrix_text.count('class="matrix-stage"') == 5 and all(stage in matrix_text for stage in (
        "Establish intelligence", "Optimize evidence", "Select architecture", "Test added autonomy", "Validate operations")),
        "experimental matrix contains all five ordered stage dividers")
    require(matrix_text.count('<tr><td>') == 13, "experimental matrix retains thirteen distinct evidence rows")
    require("thead{display:table-header-group}" in source and ".experiment-matrix .matrix-stage{break-after:avoid-page}" in source,
            "experimental matrix repeats headings and protects stage dividers in A4 print")
    forbidden = ["perfectly blind", "achieved ROI", "RAG proved superior", "zero compute cost", "validated autonomous legal review"]
    require(not any(term.lower() in source.lower() for term in forbidden), "unsupported or contradictory conclusion phrases are absent")
    require("NDATrace_Reasoning_Evidence_Map.md" in (ROOT / "reports/NDATrace_Reasoning_Audit.md").read_text(), "fresh workflow identifies its evidence map")
    require((ROOT / "reports/NDATrace_Professor_Compliance.md").exists(), "professor compliance matrix exists")
    ui_map = (ROOT / "reports/NDATrace_UI_to_Report_Map.md").read_text()
    require(all(term in ui_map for term in ("RAG versus Rule", "256 tok, overlap 50", "mandatory verification")),
            "UI-to-report map records the target, overlap and economics discrepancies")
    require((ROOT / "reports/NDATrace_Evidence_to_Decision_Map.md").exists(), "eight-stage evidence-to-decision map exists")
    require((ROOT / "reports/NDATrace_Notebook_Plot_Inventory.md").exists(), "complete notebook-plot inventory exists")
    cleanup = (ROOT / "reports/NDATrace_Report_File_Audit.md").read_text()
    require("No file was deleted or moved" in cleanup and "Proposed deletion" in cleanup, "cleanup audit preserves files pending approval")
    readme = (ROOT / "README.md").read_text()
    require("Authoritative final report" in readme and "NDATrace_Final_Report.html" in readme, "README designates the self-contained HTML as authoritative")

    summary = checks + ["", "ALL FRESH-REPORT CHECKS PASSED (offline; zero model calls)",
                        f"Analytical prose count: {prose_count}",
                        f"Inclusive Sections 1-8 count: {inclusive_count}",
                        f"Complete document count: {document_count}",
                        "Counting note: main count includes headings, table cells and captions; SVG label text and CSS are excluded."]
    RESULT.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n" + "\n".join(summary[-4:]))


if __name__ == "__main__":
    main()
