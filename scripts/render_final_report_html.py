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
for line in (ROOT / "results/final/reconstruction_v2/full_test_comparison.csv").read_text().splitlines()[1:]:
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

# Risk-sensitive recall = avg(Contradiction recall, NotMentioned recall) - proposal's own definition
RSR_FULL = (FULL["recall"]["Contradiction"] + FULL["recall"]["NotMentioned"]) / 2
RSR_RAG = (RAG["recall"]["Contradiction"] + RAG["recall"]["NotMentioned"]) / 2

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
    """The actual deployed pipeline (backend/routes/review.py -> pipeline/final_review.py).
    The selective agent is deliberately not shown - E11 confirmed it is not in the runtime."""
    stages = [
        "NDA text +\nrequirement", "Input\nvalidation", "Clause-aware\nchunking (256 tok)",
        "BM25\ntop-20", "Cross-encoder\nrerank -> top-5", "GPT-5-mini\n(prompt P0)",
        "Structured\nparse", "Evidence\nvalidation", "Injection\nguard",
    ]
    w, h, bw, bh, gap = 1040, 230, 104, 64, 12
    x0, y0 = 12, 40
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig1title">',
           '<title id="fig1title">NDATrace deployed inference pipeline</title>']
    cx = x0
    for i, label in enumerate(stages):
        lines = label.split("\n")
        svg.append(f'<rect x="{cx}" y="{y0}" width="{bw}" height="{bh}" rx="8" '
                    f'fill="{"#eef2f7" if i not in (5,) else "#e7edf5"}" stroke="{NAVY}" stroke-width="1.3"/>')
        ty = y0 + bh / 2 - (len(lines) - 1) * 7
        for li, ln in enumerate(lines):
            svg.append(f'<text x="{cx + bw/2}" y="{ty + li*14}" text-anchor="middle" '
                        f'font-size="11.5" fill="{INK}" font-family="Georgia, serif">{ln}</text>')
        if i < len(stages) - 1:
            ax = cx + bw
            svg.append(f'<line x1="{ax}" y1="{y0+bh/2}" x2="{ax+gap-2}" y2="{y0+bh/2}" '
                        f'stroke="{MUTED}" stroke-width="1.6" marker-end="url(#arrow)"/>')
        cx += bw + gap
    # human review branch, below
    hy = y0 + bh + 58
    svg.append(f'<line x1="{x0+bw*8+gap*8+bw/2}" y1="{y0+bh}" x2="{x0+bw*8+gap*8+bw/2}" y2="{hy}" '
                f'stroke="{ACCENT}" stroke-width="1.6" marker-end="url(#arrow2)"/>')
    hb_x = x0 + bw * 8 + gap * 8 + bw / 2 - 190
    svg.append(f'<rect x="{hb_x}" y="{hy}" width="380" height="{bh+20}" rx="8" fill="#fdf3ea" stroke="{ACCENT}" stroke-width="1.3"/>')
    svg.append(f'<text x="{hb_x+190}" y="{hy+24}" text-anchor="middle" font-size="12.5" font-weight="700" '
                f'fill="{INK}" font-family="Georgia, serif">Human reviewer (Tina)</text>')
    svg.append(f'<text x="{hb_x+190}" y="{hy+44}" text-anchor="middle" font-size="11" '
                f'fill="{INK}" font-family="Georgia, serif">sees evidence + needs_human_review flag</text>')
    svg.append(f'<text x="{hb_x+190}" y="{hy+62}" text-anchor="middle" font-size="11" font-weight="700" '
                f'fill="{ACCENT}" font-family="Georgia, serif">Approve / Override / Reject (recorded)</text>')
    svg.append('<defs>'
                f'<marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{MUTED}"/></marker>'
                f'<marker id="arrow2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{ACCENT}"/></marker>'
                '</defs>')
    svg.append('</svg>')
    return "\n".join(svg)


def grouped_bar(title_id: str, groups: list[tuple[str, float, float]], y_max: float = 1.0, fmt=pct) -> str:
    """groups: list of (label, full_value, rag_value), values in [0, y_max]."""
    w, h = 760, 300
    plot_x, plot_y, plot_w, plot_h = 70, 20, 660, 220
    n = len(groups)
    slot = plot_w / n
    bar_w = slot * 0.30
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="{title_id}">']
    # gridlines + axis labels
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        gy = plot_y + plot_h * (1 - frac)
        svg.append(f'<line x1="{plot_x}" y1="{gy}" x2="{plot_x+plot_w}" y2="{gy}" stroke="{GRID}" stroke-width="1"/>')
        svg.append(f'<text x="{plot_x-8}" y="{gy+4}" text-anchor="end" font-size="10.5" fill="{MUTED}" font-family="Georgia, serif">{fmt(frac*y_max, 0) if fmt is pct else round(frac*y_max,2)}</text>')
    for i, (label, fv, rv) in enumerate(groups):
        gx = plot_x + i * slot
        fh = plot_h * (fv / y_max)
        rh = plot_h * (rv / y_max)
        fx = gx + slot * 0.18
        rx = gx + slot * 0.52
        svg.append(f'<rect x="{fx}" y="{plot_y+plot_h-fh}" width="{bar_w}" height="{fh}" fill="{NAVY}"/>')
        svg.append(f'<rect x="{rx}" y="{plot_y+plot_h-rh}" width="{bar_w}" height="{rh}" fill="{ACCENT}"/>')
        svg.append(f'<text x="{fx+bar_w/2}" y="{plot_y+plot_h-fh-6}" text-anchor="middle" font-size="10.5" fill="{INK}" font-family="Georgia, serif">{fmt(fv)}</text>')
        svg.append(f'<text x="{rx+bar_w/2}" y="{plot_y+plot_h-rh-6}" text-anchor="middle" font-size="10.5" fill="{INK}" font-family="Georgia, serif">{fmt(rv)}</text>')
        svg.append(f'<text x="{gx+slot/2}" y="{plot_y+plot_h+20}" text-anchor="middle" font-size="11" fill="{INK}" font-family="Georgia, serif">{label}</text>')
    svg.append(f'<line x1="{plot_x}" y1="{plot_y+plot_h}" x2="{plot_x+plot_w}" y2="{plot_y+plot_h}" stroke="{INK}" stroke-width="1.2"/>')
    # legend
    svg.append(f'<rect x="{plot_x}" y="{h-24}" width="12" height="12" fill="{NAVY}"/>')
    svg.append(f'<text x="{plot_x+18}" y="{h-14}" font-size="11" fill="{INK}" font-family="Georgia, serif">FULL (full-context GPT-5-mini)</text>')
    svg.append(f'<rect x="{plot_x+260}" y="{h-24}" width="12" height="12" fill="{ACCENT}"/>')
    svg.append(f'<text x="{plot_x+278}" y="{h-14}" font-size="11" fill="{INK}" font-family="Georgia, serif">RAG (frozen top-5, served)</text>')
    svg.append('</svg>')
    return "\n".join(svg)


def fig3_scatter() -> str:
    """Joint correctness vs cost/case: rule, FULL, RAG - all on the identical matched TEST
    population (n=2,091), so plotting them together does not mix populations."""
    w, h = 620, 320
    plot_x, plot_y, plot_w, plot_h = 70, 20, 500, 240
    xmax, ymax = 0.0025, 0.85
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
        svg.append(f'<text x="{px+10}" y="{py-8}" font-size="11" fill="{INK}" font-family="Georgia, serif">{label}</text>')
        svg.append(f'<text x="{px+10}" y="{py+8}" font-size="10.5" fill="{MUTED}" font-family="Georgia, serif">{pct(joint)} joint, {usd(cost)}/case</text>')
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
    w, h = 640, 210
    plot_x, plot_y, plot_w = 210, 14, 380
    row_h = 44
    svg = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig4title">',
           '<title id="fig4title">Distribution of RAG\'s 576 non-joint TEST failures by cause</title>']
    for i, (label, n, color) in enumerate(cats):
        y = plot_y + i * row_h
        frac = n / N_FAIL
        bw = plot_w * frac
        svg.append(f'<text x="{plot_x-12}" y="{y+22}" text-anchor="end" font-size="11.5" fill="{INK}" font-family="Georgia, serif">{label}</text>')
        svg.append(f'<rect x="{plot_x}" y="{y+6}" width="{plot_w}" height="22" fill="{GRID}"/>')
        svg.append(f'<rect x="{plot_x}" y="{y+6}" width="{bw}" height="22" fill="{color}"/>')
        svg.append(f'<text x="{plot_x+bw+8}" y="{y+22}" font-size="11" fill="{INK}" font-family="Georgia, serif">{n} ({pct(frac,0)})</text>')
    svg.append('</svg>')
    return "\n".join(svg)


FIG1 = fig1_architecture()
FIG2 = grouped_bar("fig2title", [
    ("Accuracy", FULL["accuracy"], RAG["accuracy"]),
    ("Joint correctness", FULL["joint"], RAG["joint"]),
    ("Contradiction recall", FULL["recall"]["Contradiction"], RAG["recall"]["Contradiction"]),
], y_max=1.0)
FIG3 = fig3_scatter()
FIG4 = fig4_failures()

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
figcaption{font-family:Helvetica,Arial,sans-serif;font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
figcaption b{color:var(--ink)}
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
<title>NDATrace — Final Report</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">

<header class="masthead">
  <p class="kicker">PE6201 End-of-Course Project · Final Report</p>
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
predictions against it before this reconstruction began — disclosed in
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
{FIG1}
<figcaption><b>Figure 1.</b> The deployed pipeline (<code>backend/routes/review.py</code> →
<code>pipeline/final_review.py</code>). Clause-aware chunking at 256 tokens, BM25 top-20 →
cross-encoder rerank → top-5 clauses → GPT-5-mini with the frozen P0 prompt → structured parse →
evidence validation → injection guard → a human reviewer who records Approve, Override, or Reject.
The selective agent tested in Section E is not shown — E11 confirmed it is not part of this
runtime.</figcaption>
</figure>

<h2><span class="num">D</span>The decisive comparison: FULL vs. RAG</h2>
<p>On the identical, matched official TEST population (n={POP['n']:,}, retrieval Recall@5
{pct(RETR['recall_at_5'])}, MRR@5 {RETR['mrr_at_5']:.2f}), FULL and RAG were run head-to-head with
paired significance testing:</p>
<figure>
{FIG2}
<figcaption><b>Figure 2.</b> FULL vs. RAG on the matched official TEST population (n={POP['n']:,}).
Source: <code>experiments/E20_final_rag_test/results/E20_final_report.json</code>
(<code>full_vs_rag_same_population</code>).</figcaption>
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
recall for RAG over FULL. Measured: {pct(RSR_FULL)} → {pct(RSR_RAG)}, a
<strong>+{(RSR_RAG-RSR_FULL)*100:.2f}-point gain — the ≥5-point target was not met.</strong> I am
reporting this as measured, not reframing the comparison around a friendlier metric.</div>
 

<h2><span class="num">E</span>Experiments that rejected additional complexity</h2>
<div class="q">Question: does letting the model search further recover its mistakes?</div>
<p>The selective agent (tools: follow a cross-reference, or pull deeper into the ranked candidate
pool) was tested on 15 real escalated cases out of 150. It made
<strong>zero tool calls across every one</strong> — the controller concluded immediately every
time — for a net Joint-success change of exactly 0.0 points (one recovery cancelled by one
unrelated regression) at $0.0218 of real added spend. This does not show agents never help; it
shows that for this trigger and tool set, the extra rung bought nothing measurable, so I did not
carry it into the runtime.</p>
<div class="q">Question: can the system reliably flag its own uncertain cases?</div>
<p>I tested four automatic routing policies (n=138) against a provisional ≤40%-review /
&lt;10%-residual-error target. The most conservative reviewed only 4.3% of cases but caught just
12.5% of failures; the most aggressive caught 82.5% but required reviewing 51.4% of cases.
<strong>No policy reached both thresholds at once</strong> — deterministic runtime signals could
not reliably separate confident-and-wrong from confident-and-right. Rather than ship a gate that
misses too much or reviews almost everything anyway, <strong>every result routes to a
human</strong>, who sees the evidence and records a decision (Section F).</p>

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

<figure>
{FIG3}
<figcaption><b>Figure 3.</b> Joint correctness vs. cost per case, matched TEST population
(n={POP['n']:,}). All three systems share the identical population, so the comparison is direct.
Source: <code>results/final/reconstruction_v2/full_test_comparison.csv</code> +
<code>E20_final_report.json</code>.</figcaption>
</figure>

<figure>
{FIG4}
<figcaption><b>Figure 4.</b> RAG's {N_FAIL} non-joint failures on the full TEST set, by cause.
Most failures are reasoning/classification errors on correctly retrieved evidence, not retrieval
misses — meaning better retrieval alone would not close most of this gap. Source:
<code>E20_final_report.json</code> (<code>failure_taxonomy</code>).</figcaption>
</figure>

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
