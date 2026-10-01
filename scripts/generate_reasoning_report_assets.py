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
with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as stream:
    RULE = next(row for row in csv.DictReader(stream) if row["system"] == "rule")

NAVY = "#17324D"
BLUE = "#2563A6"
TEAL = "#0F766E"
ORANGE = "#C65D21"
RED = "#B33A3A"
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
    p = svg_start(1500, 700, "Classification is not evidence-grounded correctness", "Official ContractNLI TEST, identical 2,091-case population")
    systems = [
        ("Rule", float(RULE["accuracy"]), float(RULE["joint"]), BLUE),
        ("FULL", FULL["accuracy"], FULL["joint"], NAVY),
        ("RAG", RAG["accuracy"], RAG["joint"], TEAL),
    ]
    left, right, top, bottom = 315, 1400, 170, 590
    for pct in range(0, 101, 20):
        x = left + (right-left)*pct/100
        p += [f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x:.1f}" y="625" text-anchor="middle">{pct}%</text>']
    for i, (name, acc, joint, color) in enumerate(systems):
        y = 205 + i*130
        p.append(f'<text x="60" y="{y+48}" font-size="25" font-weight="700" fill="{color}">{name}</text>')
        for offset, metric, value, fill in [(0, "Accuracy", acc, color), (46, "Joint", joint, ORANGE)]:
            yy = y+offset
            width = (right-left)*value
            p += [f'<text class="small" x="170" y="{yy+24}">{metric}</text>',
                  f'<rect x="{left}" y="{yy}" width="{width:.1f}" height="31" rx="5" fill="{fill}"/>',
                  f'<text class="value" x="{left+width+12:.1f}" y="{yy+24}" fill="{fill}">{value:.1%}</text>']
    p += [
        '<text class="small" x="60" y="673">Joint requires the correct label and sufficient annotated-evidence overlap; it is stricter, but not a legal-adequacy judgment.</text>'
    ]
    write_svg("quality.svg", p)


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

    p += [f'<text x="990" y="155" font-size="24" font-weight="700" fill="{NAVY}">B. RAG sensitivity</text>',
          '<text class="small" x="990" y="185">Total cost as incremental rework varies; base verification time/rate changes by scenario</text>']
    x0, x1, y_top, y_bottom = 1030, 1720, 240, 690
    scenarios = [("3 min @ $30/h",3,30,BLUE),("5 min @ $40/h",5,40,TEAL),("10 min @ $60/h",10,60,RED)]
    ymax = 12000
    for val in (0,3000,6000,9000,12000):
        y=y_bottom-val/ymax*(y_bottom-y_top)
        p += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x0-12}" y="{y+6:.1f}" text-anchor="end">${val/1000:.0f}k</text>']
    for minute in (0,5,10,15,20):
        x=x0+(x1-x0)*minute/20
        p += [f'<line x1="{x:.1f}" y1="{y_top}" x2="{x:.1f}" y2="{y_bottom}" stroke="{GRID}" stroke-width="2"/>',
              f'<text class="small" x="{x:.1f}" y="725" text-anchor="middle">{minute}</text>']
    for label, verify_min, rate, color in scenarios:
        pts=[]
        for rework_min in range(21):
            total=VOLUME*(RAG["cost_per_case"]+verify_min/60*rate+(1-RAG["joint"])*rework_min/60*rate)
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
        '<text class="small" x="65" y="850">Fixed operating cost excluded because hosting, monitoring and support were not measured. Joint failure is only a scenario proxy for rework, not an observed workflow rate.</text>',
    ]
    write_svg("cost_to_serve.svg", p)


if __name__ == "__main__":
    architecture()
    quality()
    failures()
    costs()
    print(f"Wrote fresh SVG assets to {OUT}")
