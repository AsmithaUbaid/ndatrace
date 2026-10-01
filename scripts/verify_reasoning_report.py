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
RESULT = ROOT / "reports/NDATrace_Reasoning_Verification.txt"
ASSETS = ["architecture.svg", "quality.svg", "failure_distribution.svg", "cost_to_serve.svg"]


class ReportText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.numbered_depth = 0
        self.prose: list[str] = []
        self.inclusive: list[str] = []

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
        if self.numbered_depth:
            self.inclusive.append(data)
        if any(tag == "p" and "analysis" in attrs.get("class", "").split() for tag, attrs in self.stack):
            self.prose.append(data)


def words(text: str) -> list[str]:
    return re.findall(r"\b[\w][\w’'\-]*\b", text)


checks: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    checks.append(f"PASS  {message}")
    print(checks[-1])


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    output = OUTPUT.read_text(encoding="utf-8")
    require(output == source, "published HTML exactly matches the fresh authoritative source")
    require(BACKUP.exists() and BACKUP.read_text(encoding="utf-8") != output, "previous report is preserved and differs from the redesign")
    require("NDATrace_Final_Report_HTML.md" not in source, "fresh report does not depend on the former editable source")
    require(source.count('<section id="s') == 8, "exactly eight required numbered sections")
    require(source.count('class="table-title"') == 10, "all ten report tables have explicit titles")
    require(source.count("<figure>") == source.count("<figcaption>") == 4, "all four figures have captions")

    parser = ReportText()
    parser.feed(source)
    prose_count = len(words(" ".join(parser.prose)))
    inclusive_count = len(words(" ".join(parser.inclusive)))
    require(1020 <= prose_count <= 1380, f"analytical prose count {prose_count} is within 1,200 +/-15%")
    require(inclusive_count > prose_count, f"inclusive numbered-section count {inclusive_count} transparently includes tables and captions")

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

    risks = {name: (values[3] + values[4]) / 2 for name, values in official.items()}
    target_delta = (risks["RAG"] - risks["FULL"]) * 100
    rule_delta = (risks["RAG"] - risks["Rule"]) * 100
    require(round(target_delta, 1) == 1.2 and "+1.2 points" in source, "original RAG-versus-FULL target result recomputes to +1.2 points")
    require(round(rule_delta, 1) == 16.6 and "+16.6 points" in source, "supplementary RAG-versus-Rule result recomputes to +16.6 points")
    require("At least +5.0 percentage points" in source and "Not achieved" in source, "historical target is preserved and correctly failed")

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
    require("1 recovery, 1 regression; net 0" in source and "$0.0218" in source, "agent Joint transition and incremental cost are disclosed")
    require(abs(paired["metric_table"]["joint_overall"]["delta_A3_minus_A2"]) < 1e-12,
            "saved agent comparison confirms zero net Joint change")

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
    require("Fixed operating cost excluded" in cost_svg and "Joint failure is only a scenario proxy" in cost_svg,
            "cost figure distinguishes excluded fixed cost and hypothetical rework")

    for asset in ASSETS:
        path = ROOT / "reports/reasoning-assets" / asset
        require(path.exists() and path.stat().st_size > 1500, f"fresh figure exists and is non-trivial: {asset}")
        ET.parse(path)
        require(f'reasoning-assets/{asset}' in source, f"fresh source references {asset}")
    refs = re.findall(r'<img src="([^"]+)"', source)
    require(all((SOURCE.parent / ref).exists() for ref in refs), "all local report image links resolve")
    require(not re.search(r'figures/submission_|docs/images/', source), "no former report figures are reused")

    required_families = ["Majority", "Oracle", "prompts", "retrieval", "Reranking", "FULL", "agent", "routing", "robust", "Targeted", "operating cost"]
    matrix_text = source[source.index("Table 2."):source.index("</tbody></table></div>", source.index("Table 2."))]
    require(all(term.lower() in matrix_text.lower() for term in required_families), "experimental matrix covers every required family")
    forbidden = ["perfectly blind", "achieved ROI", "RAG proved superior", "zero compute cost", "validated autonomous legal review"]
    require(not any(term.lower() in source.lower() for term in forbidden), "unsupported or contradictory conclusion phrases are absent")
    require("NDATrace_Reasoning_Evidence_Map.md" in (ROOT / "reports/NDATrace_Reasoning_Audit.md").read_text(), "fresh workflow identifies its evidence map")
    require((ROOT / "reports/NDATrace_Professor_Compliance.md").exists(), "professor compliance matrix exists")

    summary = checks + ["", "ALL FRESH-REPORT CHECKS PASSED (offline; zero model calls)",
                        f"Analytical prose count: {prose_count}",
                        f"Inclusive Sections 1-8 count: {inclusive_count}",
                        "Counting note: inclusive count includes headings, table cells and captions; references and metadata are excluded."]
    RESULT.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n" + "\n".join(summary[-4:]))


if __name__ == "__main__":
    main()
