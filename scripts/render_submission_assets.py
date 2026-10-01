#!/usr/bin/env python3
"""Generate final-report figures directly from canonical experiment artifacts."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/figures"
OUT.mkdir(parents=True, exist_ok=True)

E20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
FULL = E20["full_vs_rag_same_population"]["FULL"]
RAG = E20["full_vs_rag_same_population"]["RAG"]
with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as f:
    RULE = next(r for r in csv.DictReader(f) if r["system"] == "rule")

NAVY = "#19324D"
BLUE = "#3568AC"
TEAL = "#138A83"
AMBER = "#C57A2D"
INK = "#18243A"
MUTED = "#5C6B82"
GRID = "#DDE5EE"
PALE = "#F4F7FA"
WHITE = "#FFFFFF"


def font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def text(d, xy, value, size=28, color=INK, bold=False, anchor=None):
    d.text(xy, value, fill=color, font=font(size, bold), anchor=anchor)


def canvas(height=760):
    return Image.new("RGB", (1600, height), WHITE)


def architecture():
    im = canvas(720)
    d = ImageDraw.Draw(im)
    text(d, (70, 38), "NDATrace deployed review path", 43, NAVY, True)
    text(d, (70, 95), "Deterministic evidence controls around one bounded semantic decision", 26, MUTED)
    rows = [
        ("EVIDENCE DISCOVERY", 175, "#EEF3F8", BLUE, ["NDA + requirement", "256-token chunks", "BM25 top-20", "Rerank to top-5"]),
        ("REASONING + CONTROLS", 345, "#F8F3EC", AMBER, ["GPT-5-mini", "Structured result", "Source validation", "Security flags"]),
        ("HUMAN DECISION", 515, "#EDF6F3", TEAL, ["Label + evidence", "Reviewer verifies", "Approve / override / reject", "Recorded history"]),
    ]
    for label, y, fill, stroke, boxes in rows:
        d.rounded_rectangle((55, y, 1545, y + 125), radius=18, fill=fill)
        text(d, (78, y + 22), label, 18, stroke, True)
        centers = [250, 615, 980, 1345]
        for i, (cx, value) in enumerate(zip(centers, boxes)):
            d.rounded_rectangle((cx - 145, y + 50, cx + 145, y + 105), radius=10, fill=WHITE, outline=stroke, width=3)
            text(d, (cx, y + 78), value, 21, INK, False, "mm")
            if i < 3:
                d.line((cx + 150, y + 78, centers[i + 1] - 155, y + 78), fill=MUTED, width=3)
                d.polygon([(centers[i + 1] - 155, y + 78), (centers[i + 1] - 171, y + 69), (centers[i + 1] - 171, y + 87)], fill=MUTED)
    d.line((1345, 300, 1345, 345), fill=MUTED, width=3)
    d.polygon([(1345, 345), (1336, 329), (1354, 329)], fill=MUTED)
    d.line((1345, 470, 1160, 515), fill=MUTED, width=3)
    d.polygon([(1160, 515), (1172, 501), (1177, 520)], fill=MUTED)
    im.save(OUT / "submission_architecture.png", optimize=True)


def quality():
    im = canvas(720)
    d = ImageDraw.Draw(im)
    text(d, (70, 35), "Evidence-grounded quality on official TEST", 42, NAVY, True)
    text(d, (70, 90), "Same 2,091 cases; Joint requires the right label and supporting evidence", 25, MUTED)
    systems = [
        ("Rule", float(RULE["accuracy"]), float(RULE["joint"]), BLUE),
        ("FULL", FULL["accuracy"], FULL["joint"], NAVY),
        ("RAG", RAG["accuracy"], RAG["joint"], TEAL),
    ]
    x0, x1 = 360, 1490
    for p in (0, 25, 50, 75, 100):
        x = x0 + (x1 - x0) * p / 100
        d.line((x, 170, x, 625), fill=GRID, width=2)
        text(d, (x, 650), f"{p}%", 20, MUTED, anchor="mt")
    for i, (name, acc, joint, color) in enumerate(systems):
        base = 205 + i * 145
        text(d, (75, base + 48), name, 28, color, True, "lm")
        for j, (metric, value, fill) in enumerate((("Accuracy", acc, color), ("Joint", joint, AMBER))):
            y = base + j * 53
            text(d, (210, y + 17), metric, 21, MUTED, anchor="lm")
            d.rounded_rectangle((x0, y, x0 + (x1 - x0) * value, y + 34), radius=6, fill=fill)
            text(d, (x0 + (x1 - x0) * value + 13, y + 17), f"{value:.1%}", 21, fill, True, "lm")
    im.save(OUT / "submission_quality.png", optimize=True)


def failures():
    im = canvas(650)
    d = ImageDraw.Draw(im)
    text(d, (70, 35), "Why RAG missed Joint correctness", 42, NAVY, True)
    text(d, (70, 90), "Official TEST; 576 non-Joint cases; mutually exclusive categories", 25, MUTED)
    cats = [
        ("Reasoning / classification", "reasoning_classification", NAVY),
        ("Evidence selection", "evidence_selection", BLUE),
        ("Retrieval-limited", "retrieval_limited", AMBER),
        ("Parser / source validity", "runtime_parser_source_validity", MUTED),
    ]
    counts = E20["failure_taxonomy"]
    maximum = max(counts.values())
    x0, width = 535, 850
    for i, (label, key, color) in enumerate(cats):
        y = 175 + i * 100
        n = counts[key]
        text(d, (70, y + 22), label, 25, INK, anchor="lm")
        d.rounded_rectangle((x0, y, x0 + width, y + 44), radius=7, fill=GRID)
        end = x0 + width * n / maximum
        d.rounded_rectangle((x0, y, end, y + 44), radius=7, fill=color)
        text(d, (end + 16, y + 22), f"{n}  ({n / 576:.1%})", 23, color, True, "lm")
    text(d, (70, 596), "Interpretation: most residual failures remain reasoning failures, not missing retrieval alone.", 23, MUTED)
    im.save(OUT / "submission_failures.png", optimize=True)


def frontier():
    im = canvas(760)
    d = ImageDraw.Draw(im)
    text(d, (70, 35), "Quality-cost frontier", 42, NAVY, True)
    text(d, (70, 90), "Measured API inference cost and Joint correctness; official TEST n=2,091", 25, MUTED)
    left, top, right, bottom = 160, 155, 1470, 640
    for p in (40, 50, 60, 70, 80):
        y = bottom - (p - 35) / 50 * (bottom - top)
        d.line((left, y, right, y), fill=GRID, width=2)
        text(d, (left - 18, y), f"{p}%", 20, MUTED, anchor="rm")
    for cost in (0, .0005, .0010, .0015, .0020, .0025):
        x = left + cost / .0025 * (right - left)
        d.line((x, top, x, bottom), fill=GRID, width=2)
        text(d, (x, bottom + 23), f"${cost:.4f}", 19, MUTED, anchor="mt")
    pts = [
        ("Rule", float(RULE["api_cost_usd"]), float(RULE["joint"]), BLUE, (30, -34)),
        ("RAG", RAG["cost_per_case"], RAG["joint"], TEAL, (-35, -45)),
        ("FULL", FULL["cost_per_case"], FULL["joint"], NAVY, (35, 30)),
    ]
    coords = []
    for name, cost, joint, color, offset in pts:
        x = left + cost / .0025 * (right - left)
        y = bottom - (joint * 100 - 35) / 50 * (bottom - top)
        coords.append((x, y))
        d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=color, outline=WHITE, width=4)
        dx, dy = offset
        text(d, (x + dx, y + dy), f"{name}: {joint:.1%} | ${cost:.5f}", 22, color, True, "mm")
    d.line(coords, fill=MUTED, width=4)
    text(d, (left, top - 20), "Joint correctness (%)", 21, MUTED, True, "ls")
    text(d, ((left + right) / 2, 710), "Measured API cost per case", 23, INK, anchor="mm")
    im.save(OUT / "submission_frontier.png", optimize=True)


def cost_sensitivity():
    im = canvas(790)
    d = ImageDraw.Draw(im)
    text(d, (70, 35), "Cost-to-serve sensitivity", 42, NAVY, True)
    text(d, (70, 90), "Illustrative 1,000-case scenario; Joint is a proxy, not measured review avoidance", 25, MUTED)
    left, top, right, bottom = 160, 155, 1470, 650
    ymax = 3000
    for amount in (0, 1000, 2000, 3000):
        y = bottom - amount / ymax * (bottom - top)
        d.line((left, y, right, y), fill=GRID, width=2)
        text(d, (left - 18, y), f"${amount:,}", 20, MUTED, anchor="rm")
    for review in (0, 2, 4, 6, 8, 10):
        x = left + review / 10 * (right - left)
        d.line((x, top, x, bottom), fill=GRID, width=2)
        text(d, (x, bottom + 23), f"${review}", 20, MUTED, anchor="mt")
    series = [("FULL", FULL, NAVY), ("RAG", RAG, TEAL)]
    for name, data, color in series:
        points = []
        for step in range(101):
            review = step / 10
            total = 1000 * (data["cost_per_case"] + (1 - data["joint"]) * review)
            x = left + review / 10 * (right - left)
            y = bottom - total / ymax * (bottom - top)
            points.append((x, y))
        d.line(points, fill=color, width=6)
        x, y = points[-1]
        text(d, (x - 20, y - (24 if name == "FULL" else -24)), name, 23, color, True, "rm")
    text(d, (left, top - 20), "Modelled total cost for 1,000 cases (USD)", 21, MUTED, True, "ls")
    text(d, ((left + right) / 2, 720), "Assumed human-review cost per case", 23, INK, anchor="mm")
    text(d, (70, 762), "Formula: 1,000 x [measured AI cost + (1 - Joint) x assumed review cost].", 21, MUTED)
    im.save(OUT / "submission_cost_sensitivity.png", optimize=True)


if __name__ == "__main__":
    architecture()
    quality()
    failures()
    frontier()
    cost_sensitivity()
    print(f"Wrote submission figures to {OUT}")
