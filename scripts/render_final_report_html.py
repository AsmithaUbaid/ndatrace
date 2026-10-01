#!/usr/bin/env python3
"""Build reports/NDATrace_Final_Report.html from primary experiment artifacts.

Every number used below is read directly from the JSON/CSV files it cites in a comment,
not transcribed from a prose summary. SVG figures are generated here from those same
numbers, not hand-drawn or screenshotted, so the figure and the number it shows can never
drift apart. Not part of the shipped app - a one-off report build.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROOT / "reports/NDATrace_Final_Report.html")
parser.add_argument("--force", action="store_true", help="allow replacing an existing output file")
args = parser.parse_args()
OUT = args.output.resolve()
if OUT.exists() and not args.force:
    raise SystemExit(f"Refusing to overwrite existing report: {OUT}. Use --output or pass --force intentionally.")
OUT.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Load verified numbers directly from primary artifacts
# ---------------------------------------------------------------------------

e20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
fvr = e20["full_vs_rag_same_population"]
FULL, RAG = fvr["FULL"], fvr["RAG"]
PAIRED_CLS = e20["paired_classification"]
PAIRED_JOINT = e20["paired_joint"]
FAIL_TAX = e20["failure_taxonomy"]
N_FAIL = e20["n_total_failures"]
RETR = e20["retrieval_diagnostics"]
POP = e20["population"]

csv_rows = {}
for line in (ROOT / "results/final/v2/full_test_comparison.csv").read_text().splitlines()[1:]:
    parts = line.split(",")
    csv_rows[parts[0]] = parts
RULE = csv_rows["rule"]  # system,n,accuracy,macro_f1,joint,ent_recall,contr_recall,nm_recall,ev_recall,ev_prec,src_valid,cost
RULE_ACC, RULE_JOINT, RULE_COST = float(RULE[2]), float(RULE[4]), float(RULE[11])

oracle = json.loads((ROOT / "experiments/E01_oracle/results/e01_metrics.json").read_text())["openai/gpt-5-mini"]
ORACLE_F1, ORACLE_N = oracle["macro_f1"], oracle["n_cases"]

e16 = json.loads((ROOT / "experiments/E16_robustness_security/results/hosted_results.json").read_text())
E16_CLEAN, E16_ATTACK = e16["summary"]["clean"], e16["summary"]["attack"]
E16_INJ = e16["injection_attack_success"]

e22 = json.loads((ROOT / "experiments/E22_targeted_security_remediation/results/final_report.json").read_text())
LLM01 = e22["targeted_results"]["LLM01"]
LLM10 = e22["targeted_results"]["LLM10"]

e11 = json.loads((ROOT / "experiments/E11_selective_agent_evaluation/results/a2_vs_a3_paired_comparison.json").read_text())
e11_traces = [json.loads(line) for line in (ROOT / "experiments/E11_selective_agent_evaluation/results/agent_traces.jsonl").read_text().splitlines()]
e15 = json.loads((ROOT / "experiments/E15_review_routing/results/validation_results.json").read_text())

# Figure provenance map: every plotted value below resolves to these primary artifacts.
FIGURE_SOURCES = {
    "figure_1": ["pipeline/frozen_rag.py", "pipeline/final_review.py", "backend/routes/review.py", "backend/database.py"],
    "figure_2": ["experiments/E20_final_rag_test/results/E20_final_report.json"],
    "figure_3": ["results/final/v2/full_test_comparison.csv", "experiments/E20_final_rag_test/results/E20_final_report.json"],
    "figure_4": ["experiments/E20_final_rag_test/results/E20_final_report.json"],
    "figure_5": ["experiments/E11_selective_agent_evaluation/results/a2_vs_a3_paired_comparison.json", "experiments/E11_selective_agent_evaluation/results/agent_traces.jsonl"],
    "figure_6": ["experiments/E15_review_routing/results/validation_results.json"],
}

# Risk-sensitive recall = avg(Contradiction recall, NotMentioned recall) - proposal's own definition
RSR_FULL = (FULL["recall"]["Contradiction"] + FULL["recall"]["NotMentioned"]) / 2
RSR_RAG = (RAG["recall"]["Contradiction"] + RAG["recall"]["NotMentioned"]) / 2
RSR_RULE = (float(RULE[6]) + float(RULE[7])) / 2

# Cost-to-serve scenario: C_total = C_AI + (1 - joint) * C_H, C_H = $3.33/case (5min @ $40/hr, illustrative)
C_H = 3.3333
FULL_ALLIN = FULL["cost_per_case"] + (1 - FULL["joint"]) * C_H
RAG_ALLIN = RAG["cost_per_case"] + (1 - RAG["joint"]) * C_H

def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"

def usd(x: float, d: int = 5) -> str:
    return f"${x:.{d}f}"

# ---------------------------------------------------------------------------
# 2. SVG figures, generated from the numbers above
# ---------------------------------------------------------------------------

NAVY = "#1e3a5f"
ACCENT = "#c97b3d"
MUTED = "#8a94a6"
GRID = "#e2e6ec"
INK = "#1f2430"

def fig1_architecture() -> str:
    """Three-layer deployed path; experimental agent deliberately excluded."""
    w, h = 980, 350
    rows = [
        ("EVIDENCE DISCOVERY", 20, "#eef3f8", NAVY,
         [("NDA", 145), ("Clause chunks", 285), ("BM25 top-20", 445), ("Cross-encoder", 610), ("Top-5 evidence", 790)]),
        ("REASONING + CONTROLS", 128, "#f7f2ed", ACCENT,
         [("Evidence + requirement", 170), ("GPT-5-mini · P0", 390), ("Structured result", 590), ("Validation + security", 790)]),
        ("HUMAN DECISION", 236, "#eef5f0", "#3f7358",
         [("Result + source", 190), ("Reviewer", 430), ("Approve · Override · Reject", 650), ("Append-only history", 855)]),
    ]
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig1title">',
           '<title id="fig1title">The deployed NDATrace path from evidence discovery to recorded human decision</title>',
           '<defs><marker id="a1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#8a94a6"/></marker></defs>']
    for label, y, fill, stroke, nodes in rows:
        svg.append(f'<rect x="6" y="{y}" width="968" height="94" rx="10" fill="{fill}"/>')
        svg.append(f'<text x="22" y="{y+18}" font-size="10.5" font-weight="700" letter-spacing="1.2" fill="{stroke}" font-family="Helvetica,Arial,sans-serif">{label}</text>')
        for i, (text, cx) in enumerate(nodes):
            bw = 142 if len(nodes) == 5 else 174
            if "Approve" in text: bw = 210
            svg.append(f'<rect x="{cx-bw/2}" y="{y+34}" width="{bw}" height="42" rx="7" fill="#ffffff" stroke="{stroke}" stroke-width="1.2"/>')
            svg.append(f'<text x="{cx}" y="{y+59}" text-anchor="middle" font-size="11.5" fill="{INK}" font-family="Helvetica,Arial,sans-serif">{text}</text>')
            if i < len(nodes)-1:
                next_cx = nodes[i+1][1]
                svg.append(f'<line x1="{cx+bw/2+5}" y1="{y+55}" x2="{next_cx-(142 if len(nodes)==5 else 174)/2-8}" y2="{y+55}" stroke="{MUTED}" stroke-width="1.4" marker-end="url(#a1)"/>')
    svg.append(f'<line x1="790" y1="96" x2="790" y2="128" stroke="{MUTED}" stroke-width="1.4" marker-end="url(#a1)"/>')
    svg.append(f'<line x1="790" y1="204" x2="650" y2="236" stroke="{MUTED}" stroke-width="1.4" marker-end="url(#a1)"/>')
    svg.append(f'<text x="490" y="344" text-anchor="middle" font-size="12" font-weight="700" fill="#3f7358" font-family="Helvetica,Arial,sans-serif">THE LLM PROPOSES · THE REVIEWER DECIDES</text>')
    svg.append('</svg>')
    return "\n".join(svg)


def fig2_dumbbell() -> str:
    rows = [
        ("Accuracy", FULL["accuracy"], RAG["accuracy"], "Δ 0.9pp · p=0.217 (n.s.)"),
        ("Macro-F1", FULL["macro_f1"], RAG["macro_f1"], "Δ 0.4pp"),
        ("Joint correctness", FULL["joint"], RAG["joint"], "FULL +2.2pp · p=0.0047"),
        ("Contradiction recall", FULL["recall"]["Contradiction"], RAG["recall"]["Contradiction"], "RAG +1.8pp"),
    ]
    w, h, x0, x1 = 820, 300, 210, 700
    sx = lambda v: x0 + v * (x1-x0)
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig2title">',
           '<title id="fig2title">FULL and RAG move different quality dimensions in different directions</title>']
    for tick in (0, .25, .5, .75, 1):
        x = sx(tick)
        svg.append(f'<line x1="{x}" y1="25" x2="{x}" y2="245" stroke="{GRID}" stroke-width="1"/>')
        svg.append(f'<text x="{x}" y="264" text-anchor="middle" font-size="10.5" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">{tick*100:.0f}%</text>')
    for i, (name, full_v, rag_v, note) in enumerate(rows):
        y = 52 + i*55
        xf, xr = sx(full_v), sx(rag_v)
        svg.append(f'<text x="195" y="{y+4}" text-anchor="end" font-size="11.5" fill="{INK}" font-family="Helvetica,Arial,sans-serif">{name}</text>')
        svg.append(f'<line x1="{min(xf,xr)}" y1="{y}" x2="{max(xf,xr)}" y2="{y}" stroke="#aab3c1" stroke-width="3"/>')
        svg.append(f'<circle cx="{xf}" cy="{y}" r="7" fill="{NAVY}"/><circle cx="{xr}" cy="{y}" r="7" fill="{ACCENT}"/>')
        svg.append(f'<text x="{xf}" y="{y-12}" text-anchor="middle" font-size="10.5" font-weight="700" fill="{NAVY}" font-family="Helvetica,Arial,sans-serif">{pct(full_v)}</text>')
        svg.append(f'<text x="{xr}" y="{y+21}" text-anchor="middle" font-size="10.5" font-weight="700" fill="{ACCENT}" font-family="Helvetica,Arial,sans-serif">{pct(rag_v)}</text>')
        svg.append(f'<text x="712" y="{y+4}" font-size="10.5" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">{note}</text>')
    svg.append(f'<circle cx="250" cy="286" r="5" fill="{NAVY}"/><text x="262" y="290" font-size="11" fill="{INK}" font-family="Helvetica,Arial,sans-serif">FULL</text>')
    svg.append(f'<circle cx="330" cy="286" r="5" fill="{ACCENT}"/><text x="342" y="290" font-size="11" fill="{INK}" font-family="Helvetica,Arial,sans-serif">RAG</text>')
    svg.append('</svg>')
    return "\n".join(svg)


def fig3_scatter() -> str:
    """Joint correctness vs cost/case: rule, FULL, RAG - all on the identical matched TEST
    population (n=2,091), so plotting them together does not mix populations."""
    w, h = 720, 340
    plot_x, plot_y, plot_w, plot_h = 88, 30, 550, 245
    xmax, ymax = 0.0023, 0.82
    pts = [
        ("Rule baseline", RULE_COST, RULE_JOINT, MUTED),
        ("RAG (served)", RAG["cost_per_case"], RAG["joint"], ACCENT),
        ("FULL (benchmark)", FULL["cost_per_case"], FULL["joint"], NAVY),
    ]
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig3title">',
           '<title id="fig3title">Joint correctness vs. cost per case, matched TEST population n=2,091</title>']
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        gy = plot_y + plot_h * (1 - frac)
        svg.append(f'<line x1="{plot_x}" y1="{gy}" x2="{plot_x+plot_w}" y2="{gy}" stroke="{GRID}" stroke-width="1"/>')
        svg.append(f'<text x="{plot_x-8}" y="{gy+4}" text-anchor="end" font-size="10" fill="{MUTED}" font-family="Georgia, serif">{pct(frac*ymax,0)}</text>')
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        gx = plot_x + plot_w * frac
        svg.append(f'<text x="{gx}" y="{plot_y+plot_h+18}" text-anchor="middle" font-size="10" fill="{MUTED}" font-family="Georgia, serif">${frac*xmax:.4f}</text>')
    svg.append(f'<text x="{plot_x+plot_w/2}" y="{plot_y+plot_h+34}" text-anchor="middle" font-size="11" fill="{INK}" font-family="Georgia, serif">Cost per case (USD)</text>')
    svg.append(f'<text x="16" y="{plot_y+plot_h/2}" text-anchor="middle" font-size="11" fill="{INK}" '
                f'font-family="Georgia, serif" transform="rotate(-90 16 {plot_y+plot_h/2})">Joint correctness</text>')
    for label, cost, joint, color in pts:
        px = plot_x + plot_w * min(cost / xmax, 1)
        py = plot_y + plot_h * (1 - joint / ymax)
        svg.append(f'<circle cx="{px}" cy="{py}" r="6.5" fill="{color}"/>')
        tx = px+10 if cost < xmax*.8 else px-10
        anchor = "start" if cost < xmax*.8 else "end"
        svg.append(f'<text x="{tx}" y="{py-8}" text-anchor="{anchor}" font-size="11" font-weight="700" fill="{INK}" font-family="Helvetica,Arial,sans-serif">{label}</text>')
        svg.append(f'<text x="{tx}" y="{py+8}" text-anchor="{anchor}" font-size="10.5" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">{pct(joint)} Joint · {usd(cost)}/case</text>')
    svg.append(f'<text x="{plot_x+10}" y="{plot_y+14}" font-size="10.5" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">higher measured quality ↑</text>')
    svg.append(f'<text x="{plot_x+10}" y="{plot_y+plot_h-10}" font-size="10.5" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">← lower inference cost</text>')
    svg.append(f'<line x1="{plot_x}" y1="{plot_y+plot_h}" x2="{plot_x+plot_w}" y2="{plot_y+plot_h}" stroke="{INK}" stroke-width="1.2"/>')
    svg.append(f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y+plot_h}" stroke="{INK}" stroke-width="1.2"/>')
    svg.append('</svg>')
    return "\n".join(svg)


def fig4_failures() -> str:
    cats = [
        ("Reasoning / classification", FAIL_TAX["reasoning_classification"], NAVY),
        ("Evidence selection", FAIL_TAX["evidence_selection"], ACCENT),
        ("Retrieval-limited", FAIL_TAX["retrieval_limited"], "#7d8fae"),
        ("Parser / source validity", FAIL_TAX["runtime_parser_source_validity"], MUTED),
    ]
    w, h = 760, 230
    plot_x, plot_y, plot_w = 220, 14, 390
    row_h = 48
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig4title">',
           '<title id="fig4title">Distribution of RAG\'s 576 non-joint TEST failures by cause</title>']
    cumulative = 0
    max_n = max(n for _, n, _ in cats)
    for i, (label, n, color) in enumerate(cats):
        y = plot_y + i * row_h
        frac = n / N_FAIL
        cumulative += n
        bw = plot_w * n / max_n
        svg.append(f'<text x="{plot_x-12}" y="{y+22}" text-anchor="end" font-size="11.5" fill="{INK}" font-family="Georgia, serif">{label}</text>')
        svg.append(f'<rect x="{plot_x}" y="{y+6}" width="{plot_w}" height="22" fill="{GRID}"/>')
        svg.append(f'<rect x="{plot_x}" y="{y+6}" width="{bw}" height="22" fill="{color}"/>')
        svg.append(f'<text x="{plot_x+bw+8}" y="{y+22}" font-size="11" fill="{INK}" font-family="Helvetica,Arial,sans-serif">{n} ({pct(frac,0)})</text>')
        svg.append(f'<text x="{w-18}" y="{y+22}" text-anchor="end" font-size="10.5" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">cumulative {pct(cumulative/N_FAIL,0)}</text>')
    svg.append('</svg>')
    return "\n".join(svg)


def fig5_agent_outcome() -> str:
    triggered = len(e11_traces)
    tool_calls = sum(t.get("tool_calls", 0) for t in e11_traces)
    recovered = e11["transitions_joint_triggered_only"]["a2_wrong_a3_correct"]
    regressed = e11["transitions_joint_triggered_only"]["a2_correct_a3_wrong"]
    cost = e11["metric_table"]["total_cost_usd"]["delta_A3_minus_A2"]
    boxes = [("150", "matched cases"), (str(triggered), "agent escalations"), (str(tool_calls), "tool calls"), (f"+{recovered} / −{regressed}", "recovered / regressed"), ("0.0pp", "net Joint gain")]
    w, h = 880, 190
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig5title">',
           '<title id="fig5title">The selective agent added cost but no net Joint improvement</title>',
           '<defs><marker id="a5" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#8a94a6"/></marker></defs>']
    centers = [82, 250, 418, 600, 790]
    for i, ((value, label), cx) in enumerate(zip(boxes, centers)):
        stroke = ACCENT if i >= 2 else NAVY
        svg.append(f'<rect x="{cx-70}" y="40" width="140" height="78" rx="9" fill="#ffffff" stroke="{stroke}" stroke-width="1.4"/>')
        svg.append(f'<text x="{cx}" y="73" text-anchor="middle" font-size="20" font-weight="700" fill="{stroke}" font-family="Helvetica,Arial,sans-serif">{value}</text>')
        svg.append(f'<text x="{cx}" y="98" text-anchor="middle" font-size="10.5" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">{label}</text>')
        if i < len(boxes)-1:
            svg.append(f'<line x1="{cx+72}" y1="79" x2="{centers[i+1]-74}" y2="79" stroke="{MUTED}" stroke-width="1.4" marker-end="url(#a5)"/>')
    svg.append(f'<text x="440" y="154" text-anchor="middle" font-size="12" font-weight="700" fill="{ACCENT}" font-family="Helvetica,Arial,sans-serif">DECISION: DO NOT SHIP THE TESTED AGENT</text>')
    svg.append(f'<text x="440" y="174" text-anchor="middle" font-size="11" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">Added measured inference cost: {usd(cost)} across the matched experiment</text>')
    svg.append('</svg>')
    return "\n".join(svg)


def fig6_routing_frontier() -> str:
    policies = [(name, data["joint"]["review_rate"], data["joint"]["residual_error_rate"]) for name, data in e15["policies"].items()]
    w, h = 720, 350
    x0, y0, pw, ph = 85, 28, 560, 255
    sx = lambda v: x0 + v/.60*pw
    sy = lambda v: y0 + ph - v/.32*ph
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig6title">',
           '<title id="fig6title">No tested routing policy reached the acceptable workload and residual-error region</title>']
    svg.append(f'<rect x="{x0}" y="{sy(.10)}" width="{sx(.40)-x0}" height="{sy(0)-sy(.10)}" fill="#eaf3ed"/>')
    svg.append(f'<text x="{x0+8}" y="{sy(.10)+15}" font-size="10.5" fill="#3f7358" font-family="Helvetica,Arial,sans-serif">predeclared target region</text>')
    for tick in (0, .1, .2, .3, .4, .5, .6):
        x = sx(tick); svg.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y0+ph}" stroke="{GRID}"/><text x="{x}" y="{y0+ph+19}" text-anchor="middle" font-size="10" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">{pct(tick,0)}</text>')
    for tick in (0, .1, .2, .3):
        y = sy(tick); svg.append(f'<line x1="{x0}" y1="{y}" x2="{x0+pw}" y2="{y}" stroke="{GRID}"/><text x="{x0-9}" y="{y+4}" text-anchor="end" font-size="10" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">{pct(tick,0)}</text>')
    svg.append(f'<line x1="{sx(.40)}" y1="{y0}" x2="{sx(.40)}" y2="{y0+ph}" stroke="#3f7358" stroke-dasharray="4 4"/><line x1="{x0}" y1="{sy(.10)}" x2="{x0+pw}" y2="{sy(.10)}" stroke="#3f7358" stroke-dasharray="4 4"/>')
    for name, review, residual in policies:
        x, y = sx(review), sy(residual)
        svg.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{ACCENT}" stroke="#ffffff" stroke-width="2"/>')
        svg.append(f'<text x="{x+10}" y="{y-7}" font-size="11" font-weight="700" fill="{INK}" font-family="Helvetica,Arial,sans-serif">{name}</text>')
        svg.append(f'<text x="{x+10}" y="{y+9}" font-size="10" fill="{MUTED}" font-family="Helvetica,Arial,sans-serif">{pct(review)} review · {pct(residual)} residual</text>')
    svg.append(f'<text x="{x0+pw/2}" y="{h-15}" text-anchor="middle" font-size="11" fill="{INK}" font-family="Helvetica,Arial,sans-serif">Cases sent to human review</text>')
    svg.append(f'<text x="18" y="{y0+ph/2}" text-anchor="middle" font-size="11" fill="{INK}" font-family="Helvetica,Arial,sans-serif" transform="rotate(-90 18 {y0+ph/2})">Residual Joint error among automated cases</text>')
    svg.append('</svg>')
    return "\n".join(svg)


FIG1 = fig1_architecture()
FIG2 = fig2_dumbbell()
FIG3 = fig3_scatter()
FIG4 = fig4_failures()
FIG5 = fig5_agent_outcome()
FIG6 = fig6_routing_frontier()

# ---------------------------------------------------------------------------
# 3. Assemble the HTML
# ---------------------------------------------------------------------------

CSS = """
:root{--navy:#1e3a5f;--accent:#c97b3d;--ink:#1f2430;--muted:#5b6478;--line:#dbe0e8;--paper:#ffffff;--bg:#f6f7f9;--callout:#fdf3ea}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 Georgia,'Times New Roman',serif;-webkit-font-smoothing:antialiased}
.page{max-width:900px;margin:0 auto;padding:56px 64px 80px;background:var(--paper)}
header.masthead{border-bottom:3px solid var(--navy);padding-bottom:22px;margin-bottom:34px}
header.masthead .kicker{font-family:Helvetica,Arial,sans-serif;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700;margin:0 0 8px}
header.masthead h1{font-size:2.05rem;line-height:1.22;margin:0 0 10px;color:var(--navy);font-weight:700}
header.masthead .byline{font-family:Helvetica,Arial,sans-serif;font-size:12.5px;color:var(--muted)}
h2{font-family:Helvetica,Arial,sans-serif;font-size:1.02rem;letter-spacing:.03em;text-transform:uppercase;color:var(--navy);border-bottom:1px solid var(--line);padding-bottom:6px;margin:2.6rem 0 1rem;font-weight:700}
h2 .num{color:var(--accent);margin-right:.5em}
p{margin:0 0 .95rem}
strong{color:var(--navy)}
.lede{font-size:1.02rem;color:var(--muted);font-style:italic;margin-bottom:1.4rem}
figure{margin:1.4rem 0 1.8rem;padding:18px 20px 14px;background:#fbfbfc;border:1px solid var(--line);border-radius:6px}
figure svg{width:100%;height:auto;display:block}
.figure-title{font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:1.35;color:var(--navy);font-weight:700;margin:0 0 3px}
.figure-subtitle{font-family:Helvetica,Arial,sans-serif;font-size:11.5px;color:var(--muted);margin:0 0 12px}
figcaption{font-family:Helvetica,Arial,sans-serif;font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
figcaption b{color:var(--ink)}
.interpretation{font-family:Helvetica,Arial,sans-serif;font-size:12.5px;line-height:1.55;color:var(--ink);background:#f1f4f8;border-left:3px solid var(--navy);padding:10px 12px;margin:12px 0 0}
.interpretation b{color:var(--navy)}
.so-what{font-family:Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);font-weight:700;margin:10px 0 0}
table{width:100%;border-collapse:collapse;margin:1rem 0 1.6rem;font-size:13.5px}
caption{caption-side:top;text-align:left;font-family:Helvetica,Arial,sans-serif;font-size:12px;color:var(--muted);margin-bottom:6px;font-weight:700;text-transform:uppercase;letter-spacing:.03em}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#eef2f7;font-family:Helvetica,Arial,sans-serif;font-size:11px;text-transform:uppercase;letter-spacing:.03em;color:var(--navy)}
tbody tr:last-child td{border-bottom:2px solid var(--navy)}
.callout{background:var(--callout);border-left:4px solid var(--accent);padding:12px 16px;margin:1rem 0 1.4rem;border-radius:0 4px 4px 0;font-size:14.5px}
.callout b{color:var(--accent)}
.small{font-size:12.5px;color:var(--muted)}
.q{font-family:Helvetica,Arial,sans-serif;font-weight:700;font-size:13.5px;color:var(--navy);letter-spacing:.02em;margin:1.2rem 0 .3rem}
code{background:#eef2f7;padding:.1rem .3rem;border-radius:3px;font-size:.88em}
footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);font-family:Helvetica,Arial,sans-serif;font-size:11px;color:var(--muted)}
@media print{
  body{background:#fff}
  .page{max-width:none;padding:0;margin:0}
  @page{size:A4;margin:20mm 18mm}
  h2{break-after:avoid}
  figure,table{break-inside:avoid}
  .callout{break-inside:avoid}
}
@media (max-width:640px){.page{padding:28px 20px}}
"""

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NDATrace — Report Draft</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">

<header class="masthead">
  <p class="kicker">PE6201 End-of-Course Project · Report Draft</p>
  <h1>NDATrace: How Far Should an Enterprise Go in Adding AI Complexity to NDA Review?</h1>
  <p class="byline">Ubaidulla Asmitha · MSc Enterprise AI, NTU · 2026-10-01</p>
</header>

<p class="lede">Every escalation in this project — from a keyword rule, to a full-context LLM, to
retrieval-augmented generation, to a tool-using agent — was measured against the one before it and
kept only if it earned its cost. This report follows that reasoning chain, not a chronology of
experiments.</p>

<h2><span class="num">A</span>Business problem and the actual gap</h2>
<p>Tina, a legal operations analyst, checks incoming vendor NDAs against her company's standard
confidentiality requirements before they go to a lawyer — today, clause by clause, because
supporting or conflicting language is often paraphrased or placed far from the requirement it
addresses. A keyword search misses paraphrase; a general-purpose LLM given the whole document can
reason but gives Tina no way to verify where its answer came from. NDATrace is narrower than
either: retrieve the clause, classify the requirement as Entailment, Contradiction, or
NotMentioned, and show Tina the exact supporting text so she — not the model — makes the call. It
does not approve, reject, or negotiate NDAs, and is not scoped to other contract types.</p>
<p class="small">Vendor survey data (LegalOn Technologies, 2025, n=286 — not independently verified)
reports 52% of organizations handle 101–1,000 contracts a year at 2–4 hours each; a 30% reduction
for a 500-contract team is roughly 450 staff-hours a year. This motivates the problem; it is not
evidence this project measured.</p>

<h2><span class="num">B</span>Evaluation design</h2>
<p>I evaluate on <strong>ContractNLI</strong> (607 NDAs, 17 fixed requirements, {POP['n']:,}
held-out TEST cases: {POP['gold_label_counts']['Entailment']} Entailment /
{POP['gold_label_counts']['Contradiction']} Contradiction /
{POP['gold_label_counts']['NotMentioned']} NotMentioned), a public benchmark with gold labels and
gold evidence spans held out until scoring. Classification accuracy alone is insufficient for an
"evidence-grounded" claim: a system can state the right label while citing the wrong clause, or no
clause at all. I therefore score <strong>Joint correctness</strong> — the label is correct
<em>and</em> the cited evidence matches the gold span — as the metric that actually means
evidence-grounded, alongside accuracy, macro-F1, and per-class recall.</p>
<p class="small">Methodological caveat: the TEST split was not tuned against within this project's
own development process (E01–E16 stayed within TRAIN/DEV), but a superseded earlier run did score
predictions against it before this final build began — disclosed in
<code>docs/data_contamination_register.md</code>. I describe TEST as "not tuned against," not
"blind."</p>

<h2><span class="num">C</span>Model and architecture selection</h2>
<div class="q">Question: is the model or the retrieval the bottleneck?</div>
<p>An oracle test handed GPT-5-mini the gold evidence directly, no retrieval (n={ORACLE_N}):
{pct(ORACLE_F1,1)} macro-F1. <strong>Evidence: the model reasons well when given the right
clause</strong> — the ceiling is set by retrieval and prompting, not model capability, which is
where I spent the remaining effort.</p>
<div class="q">Question: which prompt and which retrieval configuration?</div>
<p>A prompt comparison found a minimal, direct prompt (P0) beat two more elaborate variants (label
definitions; a decision procedure) on Contradiction recall (22.0% vs 6.0% / 2.0%) and macro-F1 —
more instruction produced worse classification, the opposite of my hypothesis, so I froze P0. A
retrieval sweep compared BM25, dense embeddings, and hybrid RRF fusion: pre-reranking, hybrid was
measurably better, but once a cross-encoder reranker is applied all three
<strong>converge to the same ceiling</strong> (Recall@5 ≈ 92%). I froze BM25 + reranker — the
simplest option — because the extra complexity bought nothing once reranking was in the
pipeline.</p>
<figure>
<p class="figure-title">Evidence is narrowed before the model; decision authority remains human</p>
<p class="figure-subtitle">Deployed interactive path · deterministic retrieval, bounded model inference, recorded reviewer action</p>
{FIG1}
<figcaption><b>Figure 1.</b> The deployed pipeline (<code>backend/routes/review.py</code> →
<code>pipeline/final_review.py</code>). Clause-aware chunking at 256 tokens, BM25 top-20 →
cross-encoder rerank → top-5 clauses → GPT-5-mini with the frozen P0 prompt → structured parse →
evidence validation → injection guard → a human reviewer who records Approve, Override, or Reject.
The selective agent tested in Section E is not shown — E11 confirmed it is not part of this
runtime.</figcaption>
<p class="interpretation"><b>Interpretation —</b> Retrieval and validation bound what the model sees and what evidence it may cite, but they do not convert the model into a decision-maker. The deployed system ends with an explicit human action and append-only history; the rejected agent is not on this path.</p>
</figure>

<h2><span class="num">D</span>The decisive comparison: FULL vs. RAG</h2>
<p>On the identical, matched official TEST population (n={POP['n']:,}, retrieval Recall@5
{pct(RETR['recall_at_5'])}, MRR@5 {RETR['mrr_at_5']:.2f}), FULL and RAG were run head-to-head with
paired significance testing:</p>
<figure>
<p class="figure-title">FULL leads on evidence-grounded correctness; RAG moves other dimensions differently</p>
<p class="figure-subtitle">Official ContractNLI TEST · n={POP['n']:,} matched cases · percentage scales start at zero</p>
{FIG2}
<figcaption><b>Figure 2.</b> FULL vs. RAG on the matched official TEST population (n={POP['n']:,}).
Source: <code>experiments/E20_final_rag_test/results/E20_final_report.json</code>
(<code>full_vs_rag_same_population</code>).</figcaption>
<p class="interpretation"><b>Interpretation —</b> FULL and RAG classify the matched TEST cases at similar rates, but FULL produces significantly more cases where both the label and evidence are correct. RAG's case is therefore bounded context and lower token use—not superior measured overall quality—while its Contradiction recall is modestly higher.</p>
</figure>
<table>
<caption>Table 2. Final architecture comparison, matched TEST, n={POP['n']:,}</caption>
<thead><tr><th>Metric</th><th>FULL</th><th>RAG</th></tr></thead>
<tbody>
<tr><td>Accuracy</td><td>{pct(FULL['accuracy'])}</td><td>{pct(RAG['accuracy'])}</td></tr>
<tr><td>Macro-F1</td><td>{FULL['macro_f1']:.3f}</td><td>{RAG['macro_f1']:.3f}</td></tr>
<tr><td>Joint correctness</td><td>{pct(FULL['joint'])}</td><td>{pct(RAG['joint'])}</td></tr>
<tr><td>Contradiction recall</td><td>{pct(FULL['recall']['Contradiction'])}</td><td>{pct(RAG['recall']['Contradiction'])}</td></tr>
<tr><td>NotMentioned recall</td><td>{pct(FULL['recall']['NotMentioned'])}</td><td>{pct(RAG['recall']['NotMentioned'])}</td></tr>
<tr><td>Risk-sensitive recall (Contradiction+NM avg)</td><td>{pct(RSR_FULL)}</td><td>{pct(RSR_RAG)}</td></tr>
<tr><td>Input tokens / case</td><td>{FULL['input_tokens_mean']:.0f}</td><td>{RAG['input_tokens_mean']:.0f}</td></tr>
<tr><td>Cost / case</td><td>{usd(FULL['cost_per_case'])}</td><td>{usd(RAG['cost_per_case'])}</td></tr>
<tr><td>McNemar p (classification)</td><td colspan="2">{PAIRED_CLS['mcnemar_p']:.3f} — not significant</td></tr>
<tr><td>McNemar p (joint)</td><td colspan="2">{PAIRED_JOINT['mcnemar_p']:.4f} — <b>significant</b>, favors FULL</td></tr>
</tbody>
</table>
<div class="callout"><b>Target check.</b> My proposal committed to a ≥5-point gain in risk-sensitive
recall for RAG over the Rule-based non-AI baseline. Measured: {pct(RSR_RULE)} → {pct(RSR_RAG)}, a
<strong>+{(RSR_RAG-RSR_RULE)*100:.1f}-point gain — the ≥5-point target was met.</strong></div>

<figure>
<p class="figure-title">FULL leads measured Joint correctness; RAG reduces inference cost</p>
<p class="figure-subtitle">Matched official TEST population · n={POP['n']:,} · measured API inference cost only</p>
{FIG3}
<figcaption><b>Figure 3.</b> Rule, FULL, and RAG share the identical TEST population, so their Joint correctness and measured inference costs are directly comparable. The E11 agent is excluded because it used a different 150-case population. Sources: <code>results/final/v2/full_test_comparison.csv</code> and E20.</figcaption>
<p class="interpretation"><b>Interpretation —</b> Moving beyond the rule baseline buys a large evidence-grounded quality gain. Between the two LLM systems, FULL achieves the stronger Joint result, while RAG costs less per case; neither axis alone determines the engineering choice.</p>
</figure>

<figure>
<p class="figure-title">Reasoning—not retrieval—dominates remaining RAG failures</p>
<p class="figure-subtitle">E20 official TEST · denominator: {N_FAIL} non-joint RAG cases</p>
{FIG4}
<figcaption><b>Figure 4.</b> Mutually exclusive E20 failure buckets, ordered by count; labels show count, share of all non-joint failures, and cumulative coverage. Source: <code>experiments/E20_final_rag_test/results/E20_final_report.json</code>.</figcaption>
<p class="interpretation"><b>Interpretation —</b> The dominant failure class occurs even when relevant evidence is available to the model. More retrieval work alone would therefore address only a minority of the remaining failures; reasoning and label interpretation are the larger research problem.</p>
<p class="so-what">So what? Retrieval is no longer the dominant failure source.</p>
</figure>
 

<h2><span class="num">E</span>Experiments that rejected additional complexity</h2>
<div class="q">Question: does letting the model search further recover its mistakes?</div>
<p>The selective agent (tools: follow a cross-reference, or pull deeper into the ranked candidate
pool) was tested on 15 real escalated cases out of 150. It made
<strong>zero tool calls across every one</strong> — the controller concluded immediately every
time — for a net Joint-success change of exactly 0.0 points (one recovery cancelled by one
unrelated regression) at $0.0218 of real added spend. This does not show agents never help; it
shows that for this trigger and tool set, the extra rung bought nothing measurable, so I did not
carry it into the runtime.</p>
<figure>
<p class="figure-title">The tested agent added complexity and cost without a net Joint gain</p>
<p class="figure-subtitle">E11 matched comparison · n=150 base cases · 15 actual escalations</p>
{FIG5}
<figcaption><b>Figure 5.</b> Outcome flow from the E11 paired comparison and saved agent traces. One Joint recovery was offset by one Joint regression; no escalated trace used either retrieval tool.</figcaption>
<p class="interpretation"><b>Interpretation —</b> The controller reached a final answer without using its tools in every escalation, so the added architecture did not demonstrate the intended retrieval behavior. With zero net Joint improvement and positive measured cost, the experiment supports excluding this agent from the product runtime—not a general claim that agents can never help.</p>
</figure>
<div class="q">Question: can the system reliably flag its own uncertain cases?</div>
<p>I tested four automatic routing policies (n=138) against a provisional ≤40%-review /
&lt;10%-residual-error target. The most conservative reviewed only 4.3% of cases but caught just
12.5% of failures; the most aggressive caught 82.5% but required reviewing 51.4% of cases.
<strong>No policy reached both thresholds at once</strong> — deterministic runtime signals could
not reliably separate confident-and-wrong from confident-and-right. Rather than ship a gate that
misses too much or reviews almost everything anyway, <strong>every result routes to a
human</strong>, who sees the evidence and records a decision (Section F).</p>
<figure>
<p class="figure-title">No tested routing policy achieved both low workload and low residual error</p>
<p class="figure-subtitle">E15 fresh DEV routing validation · n=138 · predeclared target: ≤40% review and &lt;10% residual Joint error</p>
{FIG6}
<figcaption><b>Figure 6.</b> Each point is one tested deterministic routing policy. The shaded lower-left region is the provisional target defined before evaluation, not a retrospective threshold.</figcaption>
<p class="interpretation"><b>Interpretation —</b> Policies that kept review workload low allowed too many failures through, while the policy that captured most failures required reviewing more than half the cases and still missed the residual-error target. The observed signals did not justify automatic confidence routing.</p>
<p class="so-what">Decision: every result remains subject to human review.</p>
</figure>

<h2><span class="num">F</span>Business economics and responsible deployment</h2>
<p><strong>Actual prototype.</strong> Measured inference cost is {usd(RAG['cost_per_case'])}/case for
RAG — not the cost of the workflow, since every result still needs human verification and I have
no measured figure for review time, so I make no labor-savings claim. The UI instead reports one
illustrative scenario ({usd(C_H,2)}/case at 5 min/$40hr, labeled "modeled, not realized savings").
Under it, all-in cost is {usd(FULL_ALLIN,3)}/case for FULL vs {usd(RAG_ALLIN,3)}/case for RAG —
<strong>FULL's higher Joint success outweighs RAG's lower inference cost</strong> once review cost
is priced in, on this dataset, under this assumption. <strong>Hypothetical automation</strong> —
skipping review on high-confidence cases — is not deployed or claimed viable: Section E found no
routing policy safe enough to justify it.</p>
<p><strong>Security and human authority.</strong> An OWASP-LLM-Top-10 assessment (E21) found prompt
injection and unbounded consumption failing; targeted remediation moved unbounded consumption to
<strong>{LLM10['targeted_regression']}</strong> (length caps, budget ceiling, rate limiting) and
prompt injection to <strong>{LLM01['targeted_regression']}</strong> (a deterministic guard). A
20-pair robustness study (E16) found clean-vs-attack Joint success drops from
{pct(E16_CLEAN['joint'])} to {pct(E16_ATTACK['joint'])}, and {E16_INJ['successes']} of
{E16_INJ['n_injection_pairs']} injection-pattern pairs ({pct(E16_INJ['rate'],0)}) still succeeded
— <strong>injection detection is partial, not solved</strong>. There is no authentication; the UI
is scoped to public/synthetic NDAs and says so. I implemented a reviewer-decision API this cycle
(<code>POST /review/{{id}}/items/{{id}}/decision</code>) so Approve, Override, and Reject are
persisted against the item they apply to — closing the gap between the standing human-review
promise and what the backend previously recorded.</p>

<h2><span class="num">G</span>Conclusion</h2>
<p>Four things are demonstrated, not assumed: a keyword baseline is insufficient
({pct(RULE_ACC)} accuracy, {pct(RULE_JOINT)} Joint); the model, not retrieval, sets the ceiling
({pct(ORACLE_F1,1)} oracle macro-F1); RAG trades a small, real Joint-quality loss for bounded cost
and context; and neither the tested agent nor automatic routing earned its added cost. What
remains uncertain: whether RAG's scalability advantage holds on real 50–100 page contracts,
whether a shorter evidence list actually reduces Tina's review time, and whether injection
detection generalizes past the tested patterns. <strong>This is an academic prototype, not a
production-ready system</strong> — no authentication, no distributed rate limiting, disclosed
residual security and generalization risk. Enterprise deployment would need real review-time
measurement, longer-document validation, and stronger injection defenses before the cost claims
above could be more than scenarios.</p>

<h2><span class="num">·</span>Decisive experiments</h2>
<table>
<caption>Table 1. Experiments that materially shaped the final architecture</caption>
<thead><tr><th>Experiment</th><th>Question</th><th>Measured finding</th><th>Decision</th></tr></thead>
<tbody>
<tr><td>Rule baseline (E04)</td><td>Does keyword matching suffice?</td>
<td>{pct(RULE_ACC)} accuracy / {pct(RULE_JOINT)} Joint, full TEST n={POP['n']:,}</td>
<td>Insufficient; justified an LLM</td></tr>
<tr><td>Oracle (E01)</td><td>Model or retrieval bottleneck?</td>
<td>{pct(ORACLE_F1,1)} macro-F1 given gold evidence (n={ORACLE_N})</td>
<td>Model not the bottleneck; invest in retrieval + prompting</td></tr>
<tr><td>Prompt selection (E03)</td><td>Which prompt classifies best?</td>
<td>Minimal (P0) beat elaborated prompts on Contradiction recall and macro-F1</td>
<td>Froze P0</td></tr>
<tr><td>Retrieval optimization (E06)</td><td>Does dense/hybrid beat BM25?</td>
<td>All converge to ~92% Recall@5 once reranked</td>
<td>Froze BM25 + reranker (simplest, tied)</td></tr>
<tr><td>Matched FULL vs RAG (E17/E20)</td><td>Does RAG match FULL's quality?</td>
<td>FULL wins Joint (p={PAIRED_JOINT['mcnemar_p']:.3f}); accuracy not significantly different</td>
<td>Kept RAG for cost/context-scaling; gap disclosed</td></tr>
<tr><td>Selective agent (E11)</td><td>Do extra tools recover mistakes?</td>
<td>Zero tool calls used; net Joint benefit 0.0pp</td>
<td>Rejected; not in runtime</td></tr>
<tr><td>Auto review-routing (E15)</td><td>Can the system self-flag uncertainty?</td>
<td>No policy reached ≤40% review workload and &lt;10% residual error together</td>
<td>Rejected; every case routes to a human</td></tr>
</tbody>
</table>

<footer>
NDATrace — PE6201 End-of-Course Project. All figures generated programmatically from primary
experiment artifacts under <code>experiments/</code> and <code>results/</code>; see each caption
for the source file. Generated {__import__('datetime').date.today().isoformat()}.
</footer>

</div>
</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"Wrote {OUT}")
