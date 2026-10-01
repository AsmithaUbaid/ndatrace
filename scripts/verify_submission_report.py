#!/usr/bin/env python3
"""Offline consistency checks for the final analytical HTML report (zero model calls)."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from render_submission_html import prose_word_count

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/NDATrace_Final_Report_HTML.md"
HTML = ROOT / "reports/NDATrace_Final_Report.html"
BACKUP = ROOT / "reports/NDATrace_Final_Report.pre-current-prompt.html"
FIGURES = [
    "submission_architecture.png",
    "submission_quality.png",
    "submission_failures.png",
    "submission_frontier.png",
    "submission_cost_sensitivity.png",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS  {message}")


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    rendered = HTML.read_text(encoding="utf-8")
    body = source.split("<!-- report-body-start -->", 1)[1].split("<!-- report-body-end -->", 1)[0]

    require(BACKUP.exists(), "pre-revision HTML backup exists")
    require(HTML.read_bytes() != BACKUP.read_bytes(), "revised HTML differs from its backup")
    require(len(re.findall(r"^## [1-8]\. ", body, flags=re.M)) == 8, "exactly eight numbered report sections")
    require(not re.search(r"\bE\d{2}[A-Z]?\b", body), "no internal experiment identifiers in main narrative")
    require(rendered.count("<figure>") == 5, "five selected report figures rendered")
    require(rendered.count("<table") == 7, "five report tables plus build/rent and evidence-map tables rendered")

    count = prose_word_count(source)
    require(1080 <= count <= 1320, f"main-prose word count {count} is within 1,200 +/-10%")
    require(f"Word count: {count:,} words" in rendered, "rendered word-count declaration matches source")

    e20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
    full = e20["full_vs_rag_same_population"]["FULL"]
    rag = e20["full_vs_rag_same_population"]["RAG"]
    with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as f:
        rule = next(row for row in csv.DictReader(f) if row["system"] == "rule")
    expected = {
        f"{float(rule['accuracy']):.1%}", f"{float(rule['joint']):.1%}",
        f"{full['accuracy']:.1%}", f"{full['joint']:.1%}",
        f"{rag['accuracy']:.1%}", f"{rag['joint']:.1%}",
        f"{full['cost_per_case']:.5f}", f"{rag['cost_per_case']:.5f}",
    }
    require(all(value in source for value in expected), "official TEST quality and cost values match canonical artifacts")
    require(e20["population"]["n"] == 2091 and "2,091" in source, "official TEST population is 2,091")
    require("Official TEST benchmark - 2,091 cases" in source and "Curated development evaluation - 49 cases" in source,
            "official and curated populations are visibly separated")

    e24 = json.loads((ROOT / "experiments/E24_targeted_evaluation/results/e24_analysis.json").read_text())
    require(e24["n_cases"] == 49, "targeted evaluation population is 49")
    for group, n in (("golden", 30), ("negative", 15)):
        ids = [case_id for case_id, systems in e24["case_level"].items() if systems["rule"]["group"] == group]
        require(len(ids) == n, f"targeted {group} subgroup count is {n}")
        for system in ("rule", "full", "rag"):
            values = [e24["case_level"][case_id][system] for case_id in ids]
            accuracy = sum(v["label_correct"] for v in values) / n
            joint = sum(v["joint_correct"] for v in values) / n
            require(f"{accuracy:.1%} / {joint:.1%}" in source,
                    f"{group} {system} accuracy/Joint is present and recomputed")

    for figure in FIGURES:
        path = ROOT / "reports/figures" / figure
        require(path.exists() and path.stat().st_size > 10_000, f"figure exists and is non-trivial: {figure}")

    require("Report evidence map" in source, "table/figure-to-source evidence map is present")
    require("Quality-control summary" in source, "quality-control summary is present")
    require("Remaining methodological and submission limitations" in source, "remaining limitations list is present")
    print("\nALL REPORT CHECKS PASSED (offline; zero model calls)")


if __name__ == "__main__":
    main()
