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
BACKUP = ROOT / "reports/NDATrace_Final_Report.pre-cost-redesign.html"
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


def fmt_pct(value: float) -> str:
    return f"{value:.1%}"


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    rendered = HTML.read_text(encoding="utf-8")
    body = source.split("<!-- report-body-start -->", 1)[1].split("<!-- report-body-end -->", 1)[0]

    require(BACKUP.exists(), "pre-redesign HTML backup exists")
    require(HTML.read_bytes() != BACKUP.read_bytes(), "redesigned HTML differs from its backup")
    require(len(re.findall(r"^## [1-8]\. ", body, flags=re.M)) == 8, "exactly eight numbered report sections")
    require(not re.search(r"\bE\d{2}[A-Z]?\b", body), "no internal experiment identifiers in main narrative")
    require(rendered.count("<figure>") == 5, "five selected report figures rendered")
    require(rendered.count("<table") == 11, "report tables plus the architecture-ladder, full-experiment and agent appendix tables rendered")

    count = prose_word_count(source)
    require(1020 <= count <= 1380, f"main-prose word count {count} is within the professor's stated 1,200 +/-10-15% tolerance")
    require(f"Word count: {count:,} words" in rendered, "rendered word-count declaration matches source")

    e20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
    full = e20["full_vs_rag_same_population"]["FULL"]
    rag = e20["full_vs_rag_same_population"]["RAG"]
    with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as f:
        rule = next(row for row in csv.DictReader(f) if row["system"] == "rule")

    systems = {
        "Rule": {
            "accuracy": float(rule["accuracy"]), "macro_f1": float(rule["macro_f1"]),
            "joint": float(rule["joint"]), "c": float(rule["contradiction_recall"]),
            "nm": float(rule["notmentioned_recall"]),
        },
        "FULL": {
            "accuracy": full["accuracy"], "macro_f1": full["macro_f1"], "joint": full["joint"],
            "c": full["recall"]["Contradiction"], "nm": full["recall"]["NotMentioned"],
        },
        "RAG": {
            "accuracy": rag["accuracy"], "macro_f1": rag["macro_f1"], "joint": rag["joint"],
            "c": rag["recall"]["Contradiction"], "nm": rag["recall"]["NotMentioned"],
        },
    }
    for name, metrics in systems.items():
        risk = (metrics["c"] + metrics["nm"]) / 2
        expected = [fmt_pct(metrics[k]) for k in ("accuracy", "joint", "c", "nm")] + [f"{metrics['macro_f1']:.3f}", fmt_pct(risk)]
        require(all(value in source for value in expected), f"official TEST {name} metrics match canonical artifacts")
    require(e20["population"]["n"] == 2091 and "2,091" in source, "official TEST population is 2,091")
    require("Official TEST benchmark - 2,091 cases" in source and "Curated development evaluation - 49 cases" in source,
            "official and curated populations are visibly separated")

    full_risk = (full["recall"]["Contradiction"] + full["recall"]["NotMentioned"]) / 2
    rag_risk = (rag["recall"]["Contradiction"] + rag["recall"]["NotMentioned"]) / 2
    require(round((rag_risk - full_risk) * 100, 1) == 1.2, "RAG-versus-FULL risk-sensitive gain recomputes to +1.2 points")
    require("Problem Statement" in source and "FULL-context" in source and "only +1.2 points" in source
            and "not achieved" in source, "original FULL-context baseline and unmet five-point target are explicit")
    require("rule-based, non-AI baseline" in source and "+16.6-point gain" in source,
            "the rule-based comparison is disclosed as a secondary, explicit data point")

    e24 = json.loads((ROOT / "experiments/E24_targeted_evaluation/results/e24_analysis.json").read_text())
    require(e24["n_cases"] == 49, "targeted evaluation population is 49")
    for system in ("rule", "full", "rag"):
        metrics = e24["summary_by_system"][system]
        expected = [fmt_pct(metrics["accuracy"]), f"{metrics['macro_f1']:.3f}",
                    fmt_pct(metrics["joint_correctness"]), fmt_pct(metrics["contradiction_recall"])]
        require(all(value in source for value in expected), f"targeted {system} metrics match saved analysis")
    for group, n in (("golden", 30), ("negative", 15)):
        ids = [case_id for case_id, systems_case in e24["case_level"].items() if systems_case["rule"]["group"] == group]
        require(len(ids) == n, f"targeted {group} subgroup count is {n}")
        for system in ("rule", "full", "rag"):
            values = [e24["case_level"][case_id][system] for case_id in ids]
            accuracy = sum(v["label_correct"] for v in values) / n
            joint = sum(v["joint_correct"] for v in values) / n
            require(f"{accuracy:.1%} / {joint:.1%}" in source,
                    f"{group} {system} accuracy/Joint is present and recomputed")

    full_output_files = [
        ROOT / "experiments/E17_final_test/results/run_E17_gpt_hosted_test_cases.jsonl",
        ROOT / "experiments/E17B_full_test_completion/results/run_E17B_gpt_cases.jsonl",
    ]
    full_outputs = [json.loads(line)["output_tokens"] for path in full_output_files for line in path.open()]
    full_output_mean = sum(full_outputs) / len(full_outputs)
    require(len(full_outputs) == 2091 and round(full_output_mean) == 727, "FULL output-token mean recomputes to approximately 727")
    ops_values = [
        f"{full['input_tokens_mean']:,.0f}", f"{rag['input_tokens_mean']:,.0f}",
        f"{full['cost_per_case']:.5f}", f"{rag['cost_per_case']:.5f}",
        f"{full['latency_ms_mean']/1000:.2f}", f"{rag['latency_ms_mean']/1000:.2f}",
    ]
    require(all(value in source for value in ops_values), "tokens, API costs and latency match official artifacts")
    require("approximately 727" in source and "701" in source, "FULL and RAG output-token means are disclosed")

    failures = e20["failure_taxonomy"]
    require(sum(failures.values()) == e20["n_total_failures"] == 576, "failure taxonomy sums exactly to 576")
    require(all(str(value) in source for value in failures.values()), "all four failure counts appear in the report")

    volume, minutes, rate = 1000, 5, 40.0
    verify_per_case = minutes / 60 * rate
    totals = {
        "Rule": volume * verify_per_case,
        "FULL": volume * (verify_per_case + full["cost_per_case"]),
        "RAG": volume * (verify_per_case + rag["cost_per_case"]),
    }
    require(round(totals["Rule"], 2) == 3333.33 and round(totals["FULL"], 2) == 3335.36 and round(totals["RAG"], 2) == 3335.02,
            "current-workflow cost totals recompute from measured and assumed inputs")
    require("5/60 x $40" in source and "$3.33 per case" in source, "verification-cost assumption and arithmetic are explicit")
    require("Incremental rework | Omitted" in source and "Fixed operating cost | Omitted" in source,
            "unmeasured rework and fixed costs are not silently set to zero")
    require("no case skips review" in source and "local compute not monetised" in source,
            "mandatory review and Rule compute boundary are explicit")

    for figure in FIGURES:
        path = ROOT / "reports/figures" / figure
        minimum_size = 2_000 if path.suffix == ".svg" else 10_000
        require(path.exists() and path.stat().st_size > minimum_size, f"figure exists and is non-trivial: {figure}")
        require(f"figures/{figure}" in source, f"figure is referenced by editable source: {figure}")
    local_targets = []
    for attr in re.findall(r'(?:src|href)="([^"]+)"', rendered):
        if not re.match(r"^[a-z]+://", attr) and not attr.startswith("#"):
            local_targets.append((HTML.parent / attr).resolve())
    require(all(path.exists() for path in local_targets), "all local HTML image/link targets resolve")

    forbidden = ["target was met", "RAG is superior overall", "zero compute cost", "autonomous legal review"]
    require(not any(phrase.lower() in body.lower() for phrase in forbidden), "no known conclusion contradictions remain")
    require("Report evidence map" in source and all(f"Figure {n}" in source for n in range(1, 6)),
            "table/figure-to-source provenance map covers all figures")
    require("Quality-control summary" in source, "quality-control summary is present")
    require("Remaining methodological and submission limitations" in source, "remaining limitations list is present")
    print("\nALL REPORT CHECKS PASSED (offline; zero model calls)")


if __name__ == "__main__":
    main()
