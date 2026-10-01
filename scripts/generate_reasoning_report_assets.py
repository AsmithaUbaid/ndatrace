#!/usr/bin/env python3
"""Generate the reasoning-depth report's SVG figures from frozen artifacts.

No model calls are made. Economic components are deliberately separated into
measured inference and declared scenario assumptions.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/reasoning-assets"
OUT.mkdir(parents=True, exist_ok=True)

E20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
FULL = E20["full_vs_rag_same_population"]["FULL"]
RAG = E20["full_vs_rag_same_population"]["RAG"]
ORACLE = json.loads((ROOT / "experiments/E01_oracle/results/e01_metrics.json").read_text())
RERANK = json.loads((ROOT / "experiments/E06_retrieval_optimisation/results/run_E06_R5_rerank_comparison.json").read_text())
LEXICAL_DENSE = json.loads((ROOT / "experiments/E06_retrieval_optimisation/results/run_E06_lexical_vs_dense_rerank.json").read_text())
AGENT = json.loads((ROOT / "experiments/E11_selective_agent_evaluation/addendum_agent_prompt_ablation/results/arm_metrics.json").read_text())
ROUTING = json.loads((ROOT / "experiments/E15_review_routing/results/validation_results.json").read_text())["policies"]
with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as stream:
    RULE = next(row for row in csv.DictReader(stream) if row["system"] == "rule")

NAVY = "#17324D"
BLUE = "#2563A6"
TEAL = "#0F766E"
ORANGE = "#C65D21"
RED = "#B33A3A"
PURPLE = "#6B46C1"
INK = "#172033"
MUTED = "#5B667A"
GRID = "#D8E0E8"
PALE = "#F4F7FA"
WHITE = "#FFFFFF"

# Scenario assumptions, not observed workflow outcomes.
VOLUME = 1000
VERIFY_MINUTES = 5.0
REWORK_MINUTES = 10.0
LABOUR_RATE = 40.0
FIXED_COST = 0.0  # Excluded: hosting, monitoring and support were not measured.


def svg_start(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{WHITE}"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#172033}.title{font-size:40px;font-weight:700;fill:#17324D}.subtitle{font-size:22px;fill:#5B667A}.label{font-size:20px}.small{font-size:17px;fill:#5B667A}.value{font-size:20px;font-weight:700}.section{font-size:17px;font-weight:700;letter-spacing:1px}</style>',
        f'<text class="title" x="60" y="62">{html.escape(title)}</text>',
        f'<text class="subtitle" x="60" y="103">{html.escape(subtitle)}</text>',
    ]


def write_svg(name: str, parts: list[str]) -> None:
    parts.append("</svg>")
    (OUT / name).write_text("\n".join(parts), encoding="utf-8")


def architecture() -> None:
    p = svg_start(1600, 620, "Implemented NDATrace review path", "One semantic model call, bounded retrieval, deterministic controls, explicit reviewer authority")
    boxes = [
        (45, 220, 155, "NDA +\nrequirement", PALE, NAVY),
        (235, 220, 155, "Clause-aware\n256-token chunks", "#EDF4FB", BLUE),
        (425, 220, 135, "BM25\ntop-20", "#EDF4FB", BLUE),
        (595, 220, 155, "Cross-encoder\nrerank to 5", "#EDF4FB", BLUE),
        (785, 220, 155, "GPT-5-mini\nminimal prompt", "#FFF3E9", ORANGE),
        (975, 220, 175, "Parser + evidence\nsource validator", "#EDF8F5", TEAL),
        (1185, 220, 155, "Guards +\nresource limits", "#EDF8F5", TEAL),
        (1375, 220, 175, "Reviewer verifies +\nrecords decision", "#F3EEFA", "#7A4FA3"),
    ]
    for index, (x, y, w, label, fill, stroke) in enumerate(boxes):
        p.append(f'<rect x="{x}" y="{y}" width="{w}" height="110" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        lines = label.split("\n")
        for line_no, line in enumerate(lines):
            p.append(f'<text x="{x+w/2}" y="{y+47+line_no*27}" text-anchor="middle" font-size="18" font-weight="700">{html.escape(line)}</text>')
        if index < len(boxes) - 1:
            x2 = boxes[index + 1][0]
            p += [f'<line x1="{x+w+8}" y1="275" x2="{x2-12}" y2="275" stroke="{MUTED}" stroke-width="3"/>',
                  f'<polygon points="{x2-12},275 {x2-25},267 {x2-25},283" fill="{MUTED}"/>']
    p += [
        f'<rect x="235" y="400" width="515" height="72" rx="12" fill="#EDF4FB"/>',
        f'<text class="section" x="258" y="430" fill="{BLUE}">BUILT / REUSED</text>',
        '<text class="small" x="258" y="457">Retrieval and reranking libraries; per-document indexing owned by the project</text>',
        f'<rect x="785" y="400" width="155" height="72" rx="12" fill="#FFF3E9"/>',
        f'<text class="section" x="808" y="430" fill="{ORANGE}">RENTED</text>',
        '<text class="small" x="808" y="457">Hosted inference</text>',
        f'<rect x="975" y="400" width="575" height="72" rx="12" fill="#EDF8F5"/>',
        f'<text class="section" x="998" y="430" fill="{TEAL}">BUILT CONTROL PLANE</text>',
        '<text class="small" x="998" y="457">Validation, safeguards, FastAPI/Next.js workflow and recorded human decisions</text>',
        '<text class="small" x="60" y="555">Not present: agent loop, confidence gate, automatic approval, FULL fallback or gold-aware runtime logic.</text>',
    ]
    write_svg("architecture.svg", p)


def quality() -> None:
    p = svg_start(1500, 740, "Quality and inference-cost trade-off", "Official ContractNLI TEST, identical 2,091-case population")
    systems = [
        ("Rule", float(RULE["accuracy"]), float(RULE["joint"]), BLUE),
        ("FULL", FULL["accuracy"], FULL["joint"], NAVY),
        ("RAG", RAG["accuracy"], RAG["joint"], TEAL),
    ]
    p += [f'<text x="60" y="150" font-size="22" font-weight="700" fill="{NAVY}">A. Classification vs evidence-grounded correctness</text>',
          f'<text x="925" y="150" font-size="22" font-weight="700" fill="{NAVY}">B. Measured inference frontier</text>']
    left, right, top, bottom = 235, 820, 180, 595
    for pct in range(0, 101, 20):
        x = left + (right-left)*pct/100
        p += [f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x:.1f}" y="630" text-anchor="middle">{pct}%</text>']
    for i, (name, acc, joint, color) in enumerate(systems):
        y = 205 + i*128
        p.append(f'<text x="60" y="{y+47}" font-size="23" font-weight="700" fill="{color}">{name}</text>')
        for offset, metric, value, fill in [(0, "Accuracy", acc, color), (46, "Joint", joint, ORANGE)]:
            yy = y+offset
            width = (right-left)*value
            p += [f'<text class="small" x="145" y="{yy+24}">{metric}</text>',
                  f'<rect x="{left}" y="{yy}" width="{width:.1f}" height="31" rx="5" fill="{fill}"/>',
                  f'<text class="value" x="{left+width+12:.1f}" y="{yy+24}" fill="{fill}">{value:.1%}</text>']

    # Only hosted systems appear in this panel: the Rule baseline's local
    # compute was not monetised, so placing it at $0 would imply a false cost.
    x0, x1, y0, y1 = 965, 1405, 205, 595
    xmin, xmax, ymin, ymax = 0.0015, 0.0021, 0.70, 0.76
    for cost in (0.0015, 0.0017, 0.0019, 0.0021):
        x = x0 + (cost-xmin)/(xmax-xmin)*(x1-x0)
        p += [f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x:.1f}" y="630" text-anchor="middle">${cost:.4f}</text>']
    for joint in (0.70, 0.72, 0.74, 0.76):
        y = y1 - (joint-ymin)/(ymax-ymin)*(y1-y0)
        p += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x0-14}" y="{y+6:.1f}" text-anchor="end">{joint:.0%}</text>']
    points = [("FULL", FULL["cost_per_case"], FULL["joint"], NAVY), ("RAG", RAG["cost_per_case"], RAG["joint"], TEAL)]
    for name, cost, joint, color in points:
        x = x0 + (cost-xmin)/(xmax-xmin)*(x1-x0)
        y = y1 - (joint-ymin)/(ymax-ymin)*(y1-y0)
        p += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="{color}" stroke="{WHITE}" stroke-width="4"/>',
              f'<text class="value" x="{x+20:.1f}" y="{y-12:.1f}" fill="{color}">{name}</text>',
              f'<text class="small" x="{x+20:.1f}" y="{y+13:.1f}">{joint:.1%} Joint · ${cost:.5f}/case</text>']
    p += [
        '<text class="small" x="1130" y="668" text-anchor="middle">Measured API cost per case →</text>',
        '<text class="small" x="60" y="704">Joint requires the correct label and sufficient annotated-evidence overlap; it is stricter, but not a legal-adequacy judgment. Rule compute is unpriced.</text>'
    ]
    write_svg("quality.svg", p)


def oracle() -> None:
    p = svg_start(1500, 650, "Oracle evidence isolates model reasoning", "Balanced TRAIN_ORACLE_v1, n=300 per model; gold evidence supplied directly")
    models = [
        ("Llama 3.2 3B", "llama3.2:3b", MUTED),
        ("Qwen 2.5 7B", "qwen2.5:7b-instruct", BLUE),
        ("Gemini 2.5 Flash Lite", "google/gemini-2.5-flash-lite", TEAL),
        ("GPT-5-mini", "openai/gpt-5-mini", ORANGE),
    ]
    left, right, top, bottom = 330, 1410, 170, 545
    for pct in range(0, 101, 20):
        x = left + (right-left)*pct/100
        p += [f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x:.1f}" y="580" text-anchor="middle">{pct}%</text>']
    for i, (label, key, color) in enumerate(models):
        row = ORACLE[key]
        y = 190 + i*88
        macro = row["macro_f1"]
        contra = row["per_class_recall"]["Contradiction"]["recall"]
        p += [f'<text class="label" x="60" y="{y+37}" fill="{color}">{label}</text>',
              f'<rect x="{left}" y="{y}" width="{(right-left)*macro:.1f}" height="28" rx="4" fill="{color}"/>',
              f'<text class="value" x="{left+(right-left)*macro+10:.1f}" y="{y+22}" fill="{color}">{macro:.1%} macro-F1</text>',
              f'<rect x="{left}" y="{y+38}" width="{(right-left)*contra:.1f}" height="21" rx="4" fill="{ORANGE}" opacity="0.72"/>',
              f'<text class="small" x="{left+(right-left)*contra+10:.1f}" y="{y+55}">{contra:.0%} contradiction recall</text>']
    p.append('<text class="small" x="60" y="625">Decision: retain GPT-5-mini. Even with perfect evidence, weaker local models missed most contradictions; retrieval alone could not repair that reasoning ceiling.</text>')
    write_svg("oracle.svg", p)


def retrieval() -> None:
    p = svg_start(1700, 760, "Retrieval complexity had to earn its place", "E06, evidence-bearing TRAIN cases n=4,371; metrics are retrieval diagnostics, not classification accuracy")
    panels = [
        (55, "A. Chunking", [("Sentence", .642, MUTED), ("Clause-256", .870, BLUE), ("Fixed-512*", .978, ORANGE)], "*High recall returned nearly the whole document; MRR fell to 0.183."),
        (600, "B. First-stage Recall@5", [("Dense BGE", .884, MUTED), ("BM25", .905, BLUE), ("Hybrid", .921, TEAL)], "Before reranking, hybrid led; this was not the final comparison."),
        (1145, "C. After identical reranking", [("Dense", .92218, MUTED), ("BM25", .92235, BLUE)], "Only 1 of 4,371 cases differed; BM25 avoided an embedding index."),
    ]
    for x0, title, rows, note in panels:
        p.append(f'<text x="{x0}" y="165" font-size="22" font-weight="700" fill="{NAVY}">{title}</text>')
        for i, (label, value, color) in enumerate(rows):
            y = 210 + i*92
            p += [f'<text class="label" x="{x0}" y="{y+25}">{label}</text>',
                  f'<rect x="{x0}" y="{y+38}" width="440" height="28" rx="5" fill="{GRID}"/>',
                  f'<rect x="{x0}" y="{y+38}" width="{440*value:.1f}" height="28" rx="5" fill="{color}"/>',
                  f'<text class="value" x="{x0+440*value-8:.1f}" y="{y+60}" text-anchor="end" fill="{WHITE}">{value:.1%}</text>']
        p += [f'<rect x="{x0}" y="510" width="440" height="95" rx="10" fill="{PALE}"/>',
              f'<text class="small" x="{x0+18}" y="542">{html.escape(note[:58])}</text>',
              f'<text class="small" x="{x0+18}" y="568">{html.escape(note[58:116])}</text>',
              f'<text class="small" x="{x0+18}" y="594">{html.escape(note[116:])}</text>']
    before = RERANK["control"]["metrics"]["overall"]["evidence_recall_at_k"]
    after = RERANK["rerank"]["metrics"]["overall"]["evidence_recall_at_k"]
    p += [f'<rect x="55" y="645" width="1590" height="70" rx="12" fill="#EDF8F5"/>',
          f'<text class="section" x="80" y="675" fill="{TEAL}">FINAL DECISION</text>',
          f'<text class="label" x="265" y="676">Clause-256 → BM25 top-20 → cross-encoder top-5. Reranking raised Recall@5 {before:.1%} → {after:.1%} (231 recovered, 72 regressed).</text>',
          '<text class="small" x="265" y="704">Top-5 limits classifier context; candidate recall and final evidence quality are distinct stages.</text>']
    write_svg("retrieval.svg", p)


def agent() -> None:
    p = svg_start(1600, 720, "More agent activity did not create more value", "Three TRAIN evaluations on the same 150-case population; matched controls retained within each evaluator")
    rows = [
        ("Selective V1", 0, 74.0, 74.0, 0.000145, "15 routed; 0 tool calls"),
        ("Forced full-agent V1", 2/150, 75.3, 73.3, AGENT["operations"]["v1"]["cost_per_case_usd"], "2 tool cases; 0 useful"),
        ("Investigation prompt V2", 30/150, 75.3, 68.7, AGENT["operations"]["v2"]["cost_per_case_usd"], "30 tool cases; 0 useful"),
    ]
    p += [f'<text x="60" y="160" font-size="22" font-weight="700" fill="{NAVY}">Tool exposure</text>',
          f'<text x="575" y="160" font-size="22" font-weight="700" fill="{NAVY}">Joint correctness</text>',
          f'<text x="1200" y="160" font-size="22" font-weight="700" fill="{NAVY}">Added API cost</text>']
    for i, (name, tool_rate, base, result, cost, note) in enumerate(rows):
        y = 205 + i*125
        p += [f'<text class="label" x="60" y="{y+25}">{name}</text>',
              f'<text class="small" x="60" y="{y+52}">{note}</text>',
              f'<rect x="320" y="{y}" width="190" height="35" rx="5" fill="{GRID}"/>',
              f'<rect x="320" y="{y}" width="{190*tool_rate/.20:.1f}" height="35" rx="5" fill="{BLUE}"/>',
              f'<text class="value" x="520" y="{y+27}">{tool_rate:.1%}</text>',
              f'<line x1="650" y1="{y+18}" x2="{1070}" y2="{y+18}" stroke="{GRID}" stroke-width="8"/>']
        xb = 650 + (base-65)/15*420
        xr = 650 + (result-65)/15*420
        p += [f'<circle cx="{xb:.1f}" cy="{y+18}" r="11" fill="{MUTED}"/>',
              f'<circle cx="{xr:.1f}" cy="{y+18}" r="13" fill="{ORANGE}"/>',
              f'<text class="small" x="{xb:.1f}" y="{y+55}" text-anchor="middle">base {base:.1f}%</text>',
              f'<text class="small" x="{xr:.1f}" y="{y-8}" text-anchor="middle">agent {result:.1f}%</text>',
              f'<text class="value" x="1200" y="{y+27}">${cost:.6f}/case</text>']
    p += [f'<rect x="60" y="600" width="1480" height="70" rx="12" fill="#FFF3E9"/>',
          f'<text class="section" x="85" y="630" fill="{ORANGE}">DECISION</text>',
          '<text class="label" x="235" y="632">Reject the tested agent. Prompt V2 proved inactivity was partly fixable; zero useful recoveries proved activity was not benefit.</text>',
          '<text class="small" x="235" y="658">“Useful” is an outcome-associated proxy, not a causal estimate; these TRAIN results do not rule out different tools or tasks.</text>']
    write_svg("agent.svg", p)


def routing() -> None:
    p = svg_start(1500, 700, "Review workload did not buy a safe automation region", "E15 validation DEV n=138; provisional target: review ≤40% and residual Joint error <10%")
    x0, x1, y0, y1 = 220, 1390, 165, 575
    for rate in (0, .1, .2, .3, .4, .5, .6):
        x = x0 + rate/.6*(x1-x0)
        p += [f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x:.1f}" y="610" text-anchor="middle">{rate:.0%}</text>']
    for err in (0, .1, .2, .3):
        y = y1 - err/.3*(y1-y0)
        p += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x0-15}" y="{y+6:.1f}" text-anchor="end">{err:.0%}</text>']
    tx = x0 + .4/.6*(x1-x0); ty = y1 - .1/.3*(y1-y0)
    p += [f'<rect x="{x0}" y="{ty}" width="{tx-x0:.1f}" height="{y1-ty:.1f}" fill="#DFF3EA" opacity="0.8"/>',
          f'<line x1="{tx:.1f}" y1="{y0}" x2="{tx:.1f}" y2="{y1}" stroke="{TEAL}" stroke-dasharray="8 7" stroke-width="3"/>',
          f'<line x1="{x0}" y1="{ty:.1f}" x2="{x1}" y2="{ty:.1f}" stroke="{TEAL}" stroke-dasharray="8 7" stroke-width="3"/>']
    for name, color in (("R1", BLUE), ("R2", ORANGE), ("R3", RED)):
        j = ROUTING[name]["joint"]
        x = x0 + j["review_rate"]/.6*(x1-x0)
        y = y1 - j["residual_error_rate"]/.3*(y1-y0)
        p += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="{color}" stroke="{WHITE}" stroke-width="4"/>',
              f'<text class="value" x="{x+18:.1f}" y="{y-10:.1f}" fill="{color}">{name}</text>',
              f'<text class="small" x="{x+18:.1f}" y="{y+15:.1f}">{j["review_rate"]:.1%} review · {j["residual_error_rate"]:.1%} residual</text>']
    p += ['<text class="small" x="805" y="645" text-anchor="middle">Human review rate →</text>',
          '<text class="small" x="60" y="370" transform="rotate(-90 60 370)" text-anchor="middle">Residual Joint error among auto-handled cases →</text>',
          '<text class="small" x="245" y="557">Target region</text>',
          '<text class="small" x="60" y="680">Decision: no automatic routing policy. Structural/source-validity checks remain guards, not calibrated semantic confidence.</text>']
    write_svg("routing.svg", p)


def failures() -> None:
    p = svg_start(1500, 650, "RAG residual failures are mostly interpretive", "Official TEST: 576 mutually exclusive non-Joint cases")
    entries = [
        ("Reasoning / classification", E20["failure_taxonomy"]["reasoning_classification"], NAVY),
        ("Evidence selection", E20["failure_taxonomy"]["evidence_selection"], BLUE),
        ("Retrieval-limited", E20["failure_taxonomy"]["retrieval_limited"], ORANGE),
        ("Parser / source validity", E20["failure_taxonomy"]["runtime_parser_source_validity"], MUTED),
    ]
    left, max_width = 480, 820
    maximum = max(v for _, v, _ in entries)
    for i, (label, value, color) in enumerate(entries):
        y = 180+i*95
        width = max_width*value/maximum
        p += [f'<text class="label" x="60" y="{y+29}">{label}</text>',
              f'<rect x="{left}" y="{y}" width="{max_width}" height="42" rx="7" fill="{GRID}"/>',
              f'<rect x="{left}" y="{y}" width="{width:.1f}" height="42" rx="7" fill="{color}"/>',
              f'<text class="value" x="{left+width+15:.1f}" y="{y+29}" fill="{color}">{value} ({value/576:.1%})</text>']
    p.append('<text class="small" x="60" y="610">Targeted cases explain mechanisms; they do not change these population frequencies.</text>')
    write_svg("failure_distribution.svg", p)


def annual_volume_economics() -> None:
    """Counterfactual selective-fallback scenario requested for the report.

    This is deliberately separate from the mandatory-verification cost figure:
    it models human work only for non-Joint cases and therefore is not a claim
    about the implemented review policy or observed operating expenditure.
    """
    p = svg_start(1700, 850, "At enterprise review volumes, human fallback—not inference—drives the scenario", "17 requirements/NDA · 5 min human fallback/requirement · $40/hour · measured TEST Joint rates")
    volumes = [100, 250, 500, 750, 1000]
    human_per_requirement = 5 / 60 * 40
    systems = [
        ("Manual only", 0.0, 0.0, INK, "10 8"),
        ("Rule + human fallback", float(RULE["joint"]), 0.0, "#94A3B8", ""),
        ("RAG + human fallback", RAG["joint"], RAG["cost_per_case"], TEAL, ""),
        ("FULL + human fallback", FULL["joint"], FULL["cost_per_case"], PURPLE, ""),
    ]
    x0, x1, y0, y1 = 135, 1610, 210, 700
    ymax = 60000
    for value in range(0, 60000, 10000):
        y = y1 - value / ymax * (y1-y0)
        p += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x0-18}" y="{y+6:.1f}" text-anchor="end">${value/1000:.0f}k</text>']
    for volume in volumes:
        x = x0 + (volume-100)/900*(x1-x0)
        p += [f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}" stroke="{GRID}" stroke-width="1" opacity="0.45"/>',
              f'<text class="small" x="{x:.1f}" y="735" text-anchor="middle">{volume}</text>']
    x500 = x0 + 400/900*(x1-x0)
    p.append(f'<line x1="{x500:.1f}" y1="{y0}" x2="{x500:.1f}" y2="{y1}" stroke="{MUTED}" stroke-width="2" stroke-dasharray="3 5"/>')
    values_at_500 = {}
    for name, joint, inference, color, dash in systems:
        values = [v * 17 * (inference + (1-joint) * human_per_requirement) for v in volumes]
        pts = []
        for volume, value in zip(volumes, values):
            x = x0 + (volume-100)/900*(x1-x0)
            y = y1 - value/ymax*(y1-y0)
            pts.append(f"{x:.1f},{y:.1f}")
            p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color}"/>')
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        p.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="5"{dash_attr}/>' )
        values_at_500[name] = values[2]
    # Legend
    for i, (name, _, _, color, dash) in enumerate(systems):
        lx = 155 + (i % 2) * 430
        ly = 155 + (i // 2) * 34
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        p += [f'<line x1="{lx}" y1="{ly}" x2="{lx+55}" y2="{ly}" stroke="{color}" stroke-width="5"{dash_attr}/>',
              f'<circle cx="{lx+28}" cy="{ly}" r="6" fill="{color}"/>',
              f'<text class="small" x="{lx+70}" y="{ly+6}">{name}</text>']
    label_offsets = {"Manual only": -12, "Rule + human fallback": -12, "RAG + human fallback": -16, "FULL + human fallback": 28}
    for name, _, _, color, _ in systems:
        value = values_at_500[name]
        y = y1 - value/ymax*(y1-y0)
        p.append(f'<text class="value" x="{x500+85:.1f}" y="{y+label_offsets[name]:.1f}" fill="{color}">${value:,.0f}</text>')
    p += [
        f'<text class="small" x="{x500}" y="780" text-anchor="middle">500 NDAs/year: representative project scenario</text>',
        '<text class="small" x="870" y="820" text-anchor="middle">Annual NDA volume (scenario, not an observed company)</text>',
        '<text class="small" x="38" y="470" transform="rotate(-90 38 470)" text-anchor="middle">Modeled annual review cost (USD)</text>',
    ]
    write_svg("annual_volume_economics.svg", p)


def costs() -> None:
    p = svg_start(1800, 890, "Cost-to-serve: measured inference is the smallest component", "Two scenario views for 1,000 requirement reviews; all human-cost inputs are assumptions")
    systems = [
        ("Rule", 0.0, float(RULE["joint"]), BLUE),
        ("FULL", FULL["cost_per_case"], FULL["joint"], NAVY),
        ("RAG", RAG["cost_per_case"], RAG["joint"], TEAL),
    ]
    verify_case = VERIFY_MINUTES/60*LABOUR_RATE
    rework_case = REWORK_MINUTES/60*LABOUR_RATE
    totals = []
    for name, ai_case, joint, color in systems:
        ai = VOLUME*ai_case
        verify = VOLUME*verify_case
        rework = VOLUME*(1-joint)*rework_case
        totals.append((name, ai, verify, rework, ai+verify+rework+FIXED_COST, color))

    p += [f'<text x="65" y="155" font-size="24" font-weight="700" fill="{NAVY}">A. Architecture breakdown</text>',
          '<text class="small" x="65" y="185">Base: 5 min verification at $40/h for every case; additional 10 min × non-Joint rate as a rework proxy</text>']
    left, top, bottom = 120, 240, 690
    max_total = max(t[4] for t in totals)*1.08
    for val in (0, 2000, 4000, 6000):
        y = bottom-val/max_total*(bottom-top)
        p += [f'<line x1="{left}" y1="{y:.1f}" x2="870" y2="{y:.1f}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{left-12}" y="{y+6:.1f}" text-anchor="end">${val:,}</text>']
    for cx, (name, ai, verify, rework, total, color) in zip((270,500,730), totals):
        y0 = bottom
        for amount, fill in ((verify, "#B9C6D4"), (rework, ORANGE), (ai, color)):
            height = amount/max_total*(bottom-top)
            y1 = y0-height
            min_h = 4 if amount > 0 and height < 4 else height
            p.append(f'<rect x="{cx-65}" y="{y0-min_h:.1f}" width="130" height="{min_h:.1f}" fill="{fill}"/>')
            y0 -= height
        p += [f'<text class="value" x="{cx}" y="{y0-14:.1f}" text-anchor="middle">${total:,.0f}</text>',
              f'<text x="{cx}" y="730" font-size="23" font-weight="700" text-anchor="middle" fill="{color}">{name}</text>']

    # Inference-only inset prevents the measured sub-cent component from being
    # visually exaggerated in the stacked bars while still making it legible.
    p += [f'<rect x="585" y="192" width="300" height="122" rx="10" fill="{WHITE}" stroke="{GRID}" stroke-width="2"/>',
          f'<text class="section" x="605" y="216" fill="{NAVY}">INFERENCE-ONLY / 1,000</text>',
          f'<text class="small" x="605" y="242">Rule API: $0.00*</text>',
          f'<text class="small" x="605" y="265">FULL API: ${VOLUME*FULL["cost_per_case"]:.2f}</text>',
          f'<text class="small" x="605" y="288">RAG API: ${VOLUME*RAG["cost_per_case"]:.2f}</text>',
          '<text x="605" y="307" font-size="13" fill="#5B667A">*Local compute not monetised</text>']

    p += [f'<text x="990" y="155" font-size="24" font-weight="700" fill="{NAVY}">B. RAG sensitivity</text>',
          '<text class="small" x="990" y="185">Total cost as incremental rework varies; base verification time/rate changes by scenario</text>']
    x0, x1, y_top, y_bottom = 1030, 1720, 240, 690
    scenarios = [("3 min @ $30/h",3,30,BLUE),("5 min @ $40/h",5,40,TEAL),("10 min @ $60/h",10,60,RED)]
    scenario_maxima = [VOLUME*(RAG["cost_per_case"]+verify_min/60*rate+(1-RAG["joint"])*20/60*rate)
                       for _, verify_min, rate, _ in scenarios]
    ymax = (int(max(scenario_maxima)*1.12/1000)+1)*1000
    tick_step = 4000
    for val in range(0, ymax + 1, tick_step):
        y=y_bottom-val/ymax*(y_bottom-y_top)
        p += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x0-12}" y="{y+6:.1f}" text-anchor="end">${val/1000:.0f}k</text>']
    for minute in (0,5,10,15,20):
        x=x0+(x1-x0)*minute/20
        p += [f'<line x1="{x:.1f}" y1="{y_top}" x2="{x:.1f}" y2="{y_bottom}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x:.1f}" y="725" text-anchor="middle">{minute}</text>']
    zero_investigation = []
    for label, verify_min, rate, color in scenarios:
        pts=[]
        for rework_min in range(21):
            total=VOLUME*(RAG["cost_per_case"]+verify_min/60*rate+(1-RAG["joint"])*rework_min/60*rate)
            if rework_min == 0:
                zero_investigation.append((label, total, color))
            x=x0+(x1-x0)*rework_min/20
            y=y_bottom-total/ymax*(y_bottom-y_top)
            pts.append(f"{x:.1f},{y:.1f}")
        p.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="5"/>')
    for i,(label,_,_,color) in enumerate(scenarios):
        x=1030+i*225
        p += [f'<line x1="{x}" y1="775" x2="{x+35}" y2="775" stroke="{color}" stroke-width="6"/>',
              f'<text class="small" x="{x+45}" y="781">{label}</text>']
    p += [
        '<text class="small" x="1270" y="750">Additional investigation minutes per non-Joint proxy case</text>',
        '<rect x="65" y="780" width="26" height="26" fill="#B9C6D4"/><text class="small" x="102" y="800">Mandatory verification</text>',
        f'<rect x="300" y="780" width="26" height="26" fill="{ORANGE}"/><text class="small" x="337" y="800">Hypothetical rework</text>',
        f'<rect x="535" y="780" width="26" height="26" fill="{TEAL}"/><text class="small" x="572" y="800">Measured inference</text>',
        '<text class="small" x="65" y="850">Fixed operating cost excluded. Joint failure × added investigation time is an illustrative proxy, not an observed workflow relationship; at 0 added minutes, only mandatory verification + inference remain.</text>',
    ]
    write_svg("cost_to_serve.svg", p)


if __name__ == "__main__":
    architecture()
    oracle()
    retrieval()
    quality()
    agent()
    routing()
    failures()
    annual_volume_economics()
    costs()
    print(f"Wrote fresh SVG assets to {OUT}")
