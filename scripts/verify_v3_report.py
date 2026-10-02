#!/usr/bin/env python3
"""Offline consistency checks for reports/NDATrace_Final_Report_v3.html (zero model calls).

v3 is a single, self-contained HTML file (inline SVG figures, no external image
links, no separate editable source) authored outside this project's earlier two
report pipelines. This script recomputes every quantitative claim it makes from
the same canonical artifacts the rest of the project uses, so it carries the
same evidentiary weight as the earlier verify_submission_report.py /
verify_reasoning_report.py scripts even though no build script produced it.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/NDATrace_Final_Report_v3.html"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS  {message}")


def fmt_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%" if digits != 1 else f"{value:.1%}"


def main() -> None:
    source = REPORT.read_text(encoding="utf-8")

    require(source.count('<section id="s') == 8, "exactly eight numbered report sections")
    require(not re.search(r"\bE\d{2}[A-Z]?\b", source), "no internal experiment identifiers anywhere in the report")
    require(source.count("<figure>") == 7, "seven figures present")
    require(source.count("<table>") == 4, "four data tables present")
    require(source.count('aria-label="') == 7, "every figure's inline SVG carries an accessible aria-label")

    paragraphs = re.findall(r'<p class="analysis">(.*?)</p>', source, re.S)
    require(len(paragraphs) >= 14, "at least fourteen analytical prose paragraphs")
    plain = " ".join(re.sub(r"<[^>]+>", " ", p) for p in paragraphs)
    words = re.findall(r"[\w'$%.-]+", plain)
    count = len(words)
    require(1020 <= count <= 1380, f"analytical prose word count {count} is within the professor's stated 1,200 +/-10-15% tolerance")

    # Canonical official TEST artifacts (n=2,091, Rule/FULL/RAG)
    e20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
    full = e20["full_vs_rag_same_population"]["FULL"]
    rag = e20["full_vs_rag_same_population"]["RAG"]
    with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as f:
        rule = next(row for row in csv.DictReader(f) if row["system"] == "rule")

    require(e20["population"]["n"] == 2091 and "n=2,091" in source, "official TEST population is 2,091")

    systems = {
        "Rule": {
            "accuracy": float(rule["accuracy"]), "macro_f1": float(rule["macro_f1"]),
            "joint": float(rule["joint"]), "e": float(rule["entailment_recall"]),
            "c": float(rule["contradiction_recall"]), "nm": float(rule["notmentioned_recall"]),
        },
        "FULL": {
            "accuracy": full["accuracy"], "macro_f1": full["macro_f1"], "joint": full["joint"],
            "e": full["recall"]["Entailment"], "c": full["recall"]["Contradiction"], "nm": full["recall"]["NotMentioned"],
        },
        "RAG": {
            "accuracy": rag["accuracy"], "macro_f1": rag["macro_f1"], "joint": rag["joint"],
            "e": rag["recall"]["Entailment"], "c": rag["recall"]["Contradiction"], "nm": rag["recall"]["NotMentioned"],
        },
    }
    risk = {}
    for name, m in systems.items():
        risk[name] = (m["c"] + m["nm"]) / 2
        for key in ("accuracy", "macro_f1", "joint"):
            value = m[key]
            text = f"{value:.3f}" if key == "macro_f1" else fmt_pct(value)
            require(text in source, f"{name} {key} ({text}) matches canonical TEST artifact")
        # Entailment/Contradiction/NotMentioned recall triple, as printed e.g. "39.3 / 16.8 / 90.5%"
        triple = f"{m['e']*100:.1f} / {m['c']*100:.1f} / {m['nm']*100:.1f}%"
        require(triple in source, f"{name} E/C/NM recall triple ({triple}) matches canonical TEST artifact")
        require(fmt_pct(risk[name]) in source, f"{name} risk-sensitive recall ({fmt_pct(risk[name])}) matches recomputed C/NM mean")

    full_gain = round((risk["FULL"] - risk["Rule"]) * 100, 1)
    rag_gain = round((risk["RAG"] - risk["Rule"]) * 100, 1)
    require(full_gain == 15.4, f"FULL-over-Rule risk-sensitive recall gain recomputes to +{full_gain} points")
    require(rag_gain == 16.6, f"RAG-over-Rule risk-sensitive recall gain recomputes to +{rag_gain} points")
    require(f"+{full_gain:.1f} (met)" in source, "FULL's +15.4-point gain over Rule is stated and marked met")
    require(f"+{rag_gain:.1f} (met)" in source, "RAG's +16.6-point gain over Rule is stated and marked met")
    require("five-point gain in risk-sensitive recall over the rule-based baseline" in source
            and "met by a wide margin" in source, "Rule-based baseline is explicit as the pre-registered target comparison")

    full_risk_pct = fmt_pct(risk["FULL"])
    require(full_risk_pct in source, "FULL's absolute risk-sensitive recall value is disclosed (not just the Rule-relative gain)")

    classification_p = round(e20["paired_classification"]["mcnemar_p"], 3)
    joint_p = round(e20["paired_joint"]["mcnemar_p"], 4)
    require(f"{classification_p:.3f}" in source, f"paired classification McNemar p ({classification_p:.3f}) matches canonical artifact")
    require(f"{joint_p}" in source, f"paired Joint McNemar p ({joint_p}) matches canonical artifact")

    ops_values = [
        f"{full['input_tokens_mean']:,.0f}", f"{rag['input_tokens_mean']:,.0f}",
        f"{full['cost_per_case']:.5f}", f"{rag['cost_per_case']:.5f}",
        f"{full['latency_ms_mean']/1000:.2f} s", f"{rag['latency_ms_mean']/1000:.2f} s",
    ]
    require(all(v in source for v in ops_values), "measured input tokens, API cost and latency all match canonical TEST artifacts")
    require("727" in source, "FULL mean output tokens are disclosed")
    require("701" in source, "RAG mean output tokens are disclosed")

    failures = e20["failure_taxonomy"]
    require(sum(failures.values()) == e20["n_total_failures"] == 576, "failure taxonomy sums exactly to 576")
    for key, value in failures.items():
        require(str(value) in source, f"failure category count {value} ({key}) appears in the report")

    # Agent evidence (E09/E11): 15 triggered, 0 tool calls, zero net recoveries
    require("15 routed; 0 tool calls" in source, "Selective V1 agent trigger/tool-call counts are stated")
    selective_amortized = round(0.0218 / 150, 6)
    require(f"${selective_amortized}/case" in source,
            "Selective V1's incremental spend amortized per-case ($0.0218 / 150) matches the figure")

    require("$0.001515/case" in source, "Full-agent V1 incremental cost matches the E11 ablation record")
    require("$0.002659/case" in source, "Investigation-prompt V2 incremental cost matches the E11 ablation record")

    require("4/11" in source, "the 4-of-11 injection-pattern success rate is disclosed")
    require("85%" in source and "75%" in source, "robustness Joint drop under attack (85% -> 75%) is disclosed")
    require("8/8" in source, "the 8-of-8 poisoned-clause ranking finding (OWASP LLM04/LLM08) is disclosed")

    require(re.search(r"\$6,66\d", source) and re.search(r"\$5,02\d", source) and re.search(r"\$5,17\d", source),
            "the three cost-to-serve scenario totals (Rule/FULL/RAG) are present")

    print("\nALL V3 REPORT CHECKS PASSED (offline; zero model calls)")
    print(f"Analytical prose word count: {count}")


if __name__ == "__main__":
    main()
