#!/usr/bin/env python3
"""Render the final report's two figures from saved, scored TEST artifacts."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/figures"
E20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as file:
    RULE = next(row for row in csv.DictReader(file) if row["system"] == "rule")

INK = "#17233B"
MUTED = "#4F5D73"
GRID = "#DCE4EE"
BLUE = "#5578A5"
TEAL = "#167D80"
AMBER = "#C47A32"
BG = "#FFFFFF"


def font(size: int, bold: bool = False):
    path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"
    if Path(path).exists():
        return ImageFont.truetype(path, size)
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)


def label(draw, xy, value, size=26, color=INK, bold=False, anchor=None):
    draw.text(xy, value, fill=color, font=font(size, bold), anchor=anchor)


def quality_chart():
    image = Image.new("RGB", (1600, 650), BG)
    d = ImageDraw.Draw(image)
    label(d, (80, 32), "Quality on the same 2,091 TEST cases", 38, bold=True)
    label(d, (80, 88), "Joint requires the correct label and supporting evidence", 25, MUTED)
    systems = [
        ("Rule", float(RULE["joint"]), float(RULE["contradiction_recall"]), BLUE),
        ("FULL", E20["full_vs_rag_same_population"]["FULL"]["joint"], E20["full_vs_rag_same_population"]["FULL"]["recall"]["Contradiction"], TEAL),
        ("RAG", E20["RAG_metrics"]["joint"], E20["RAG_metrics"]["recall"]["Contradiction"], AMBER),
    ]
    x0, x1 = 330, 1510
    for pct in (0, 25, 50, 75, 100):
        x = x0 + (x1 - x0) * pct / 100
        d.line((x, 170, x, 580), fill=GRID, width=2)
        label(d, (x, 600), f"{pct}%", 22, MUTED, anchor="mt")
    for group, metric in enumerate(("Joint correctness", "Contradiction recall")):
        top = 205 + group * 195
        label(d, (80, top - 38), metric, 29, bold=True)
        for i, (name, joint, recall, color) in enumerate(systems):
            value = joint if group == 0 else recall
            y = top + i * 49
            label(d, (90, y + 14), name, 24, color, True, anchor="lm")
            d.rounded_rectangle((x0, y, x0 + (x1 - x0) * value, y + 31), radius=6, fill=color)
            label(d, (x0 + (x1 - x0) * value + 14, y + 15), f"{value:.1%}", 23, color, True, anchor="lm")
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(OUT / "final_quality.png", optimize=True)


def failure_chart():
    image = Image.new("RGB", (1600, 610), BG)
    d = ImageDraw.Draw(image)
    label(d, (80, 30), "Why RAG missed Joint correctness", 38, bold=True)
    label(d, (80, 86), "576 non-Joint cases in the 2,091-case TEST set", 25, MUTED)
    categories = [
        ("Reasoning or classification", "reasoning_classification", TEAL),
        ("Evidence selection", "evidence_selection", BLUE),
        ("Retrieval-limited", "retrieval_limited", AMBER),
        ("Parser or source validity", "runtime_parser_source_validity", MUTED),
    ]
    counts = E20["failure_taxonomy"]
    assert sum(counts.values()) == E20["n_total_failures"] == 576
    x0, x1 = 525, 1480
    for n in (0, 100, 200, 300, 400):
        x = x0 + (x1 - x0) * n / 500
        d.line((x, 155, x, 510), fill=GRID, width=2)
        label(d, (x, 530), str(n), 22, MUTED, anchor="mt")
    for i, (name, key, color) in enumerate(categories):
        y = 181 + i * 83
        count = counts[key]
        label(d, (80, y + 20), name, 25, INK, anchor="lm")
        bar_end = x0 + (x1 - x0) * count / 500
        d.rounded_rectangle((x0, y, bar_end, y + 41), radius=6, fill=color)
        label(d, (bar_end + 15, y + 20), f"{count}  ({count / 576:.1%})", 23, color, True, anchor="lm")
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(OUT / "rag_failure_taxonomy.png", optimize=True)


if __name__ == "__main__":
    quality_chart()
    failure_chart()
    print(f"Wrote figures to {OUT}")
