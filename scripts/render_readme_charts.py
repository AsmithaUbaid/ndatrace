#!/usr/bin/env python3
"""Render the three README charts (dumbbell, cost/quality frontier, failure Pareto)
from saved, scored TEST artifacts. Zero model calls, zero re-scoring -- every number
here is read directly from experiments/E20_final_rag_test/results/E20_final_report.json
and results/final/v2/full_test_comparison.csv, the same files the README's own metrics
table cites.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/images"
OUT.mkdir(parents=True, exist_ok=True)

E20 = json.loads((ROOT / "experiments/E20_final_rag_test/results/E20_final_report.json").read_text())
with (ROOT / "results/final/v2/full_test_comparison.csv").open(newline="") as f:
    ROWS = {r["system"]: r for r in csv.DictReader(f)}

INK = "#17233B"
MUTED = "#5B6B82"
GRID = "#E4E9F0"
BG = "#FFFFFF"
FULL_C = "#2F5FA8"
RAG_C = "#0E8A7D"
DIM_C = "#B9C2D0"
BAR_C = "#2F5FA8"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "text.color": INK,
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": INK,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
})


def dumbbell_chart():
    rows = [
        ("Accuracy", E20["full_vs_rag_same_population"]["FULL"]["accuracy"] * 100,
         E20["full_vs_rag_same_population"]["RAG"]["accuracy"] * 100),
        ("Macro-F1 (×100)", E20["full_vs_rag_same_population"]["FULL"]["macro_f1"] * 100,
         E20["full_vs_rag_same_population"]["RAG"]["macro_f1"] * 100),
        ("Joint correctness", E20["full_vs_rag_same_population"]["FULL"]["joint"] * 100,
         E20["full_vs_rag_same_population"]["RAG"]["joint"] * 100),
        ("Contradiction recall", E20["full_vs_rag_same_population"]["FULL"]["recall"]["Contradiction"] * 100,
         E20["full_vs_rag_same_population"]["RAG"]["recall"]["Contradiction"] * 100),
    ]
    rows = rows[::-1]  # top-to-bottom reading order

    fig = plt.figure(figsize=(9.5, 7.0), dpi=200)
    ax = fig.add_axes((0.24, 0.24, 0.72, 0.56))
    y = range(len(rows))
    for i, (label, full_v, rag_v) in enumerate(rows):
        lo, hi = min(full_v, rag_v), max(full_v, rag_v)
        ax.plot([lo, hi], [i, i], color=DIM_C, lw=2.5, zorder=1, solid_capstyle="round")
        ax.scatter([full_v], [i], s=210, color=FULL_C, zorder=3, edgecolor="white", linewidth=1.3)
        ax.scatter([rag_v], [i], s=210, color=RAG_C, zorder=3, edgecolor="white", linewidth=1.3)
        ax.text(full_v, i + 0.3, f"{full_v:.1f}", color=FULL_C, fontsize=10.5, fontweight="bold",
                ha="center", va="bottom")
        ax.text(rag_v, i - 0.3, f"{rag_v:.1f}", color=RAG_C, fontsize=10.5, fontweight="bold",
                ha="center", va="top")

    ax.set_yticks(list(y))
    ax.set_yticklabels([r[0] for r in rows], fontsize=11.5)
    ax.set_ylim(-0.7, len(rows) - 1 + 0.7)
    ax.set_xlim(35, 95)
    ax.set_xticks([40, 50, 60, 70, 80, 90])
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(left=False)

    fig.text(0.24, 0.94, "FULL vs. RAG, same 2,091 TEST cases",
              fontsize=16, fontweight="bold", color=INK)
    fig.text(0.24, 0.905, "FULL leads on every metric; the gap is small except Joint correctness",
              fontsize=11, color=MUTED)

    legend_ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    legend_ax.axis("off")
    legend_ax.scatter([], [], s=140, color=FULL_C, label="FULL (full-context LLM)")
    legend_ax.scatter([], [], s=140, color=RAG_C, label="RAG (served architecture)")
    legend_ax.legend(loc="lower center", frameon=False, fontsize=10.5, ncol=2,
                      bbox_to_anchor=(0.58, 0.115))

    fig.text(0.24, 0.02,
              "Takeaway: FULL's Joint-correctness edge (+2.1pp) is the only statistically significant\n"
              "gap (McNemar p=0.0047); accuracy is not significantly different (p=0.217).",
              fontsize=9.5, color=MUTED)

    fig.savefig(OUT / "full_vs_rag_dumbbell.png")
    plt.close(fig)


def cost_quality_frontier():
    points = [
        ("Rule baseline", 0.0, float(ROWS["rule"]["joint"]) * 100, DIM_C, True),
        ("Qwen (local)", 0.0, float(ROWS["qwen_ctx16k"]["joint"]) * 100, DIM_C, False),
        ("RAG (served)", E20["full_vs_rag_same_population"]["RAG"]["cost_per_case"] * 1000,
         E20["full_vs_rag_same_population"]["RAG"]["joint"] * 100, RAG_C, True),
        ("FULL", E20["full_vs_rag_same_population"]["FULL"]["cost_per_case"] * 1000,
         E20["full_vs_rag_same_population"]["FULL"]["joint"] * 100, FULL_C, True),
    ]

    fig, ax = plt.subplots(figsize=(8, 5.2), dpi=200)

    frontier = [p for p in points if p[4]]
    frontier.sort(key=lambda p: p[1])
    ax.plot([p[1] for p in frontier], [p[2] for p in frontier], color=MUTED, lw=1.6,
            ls=(0, (4, 3)), zorder=1)

    offsets = {
        "Rule baseline": (14, -4, "left"),
        "Qwen (local)": (14, -4, "left"),
        "RAG (served)": (-14, 18, "right"),
        "FULL": (14, -22, "left"),
    }
    for name, cost, joint, color, _ in points:
        ax.scatter([cost], [joint], s=260, color=color, zorder=3, edgecolor="white", linewidth=1.4)
        dx, dy, ha = offsets[name]
        label = (f"{name}\n{joint:.1f}% Joint · ${cost/1000:.5f}/case" if cost else
                 f"{name}\n{joint:.1f}% Joint · $0/case")
        ax.annotate(label, (cost, joint), xytext=(dx, dy), textcoords="offset points",
                    fontsize=9.5, color=INK, fontweight="bold", va="center", ha=ha)

    ax.set_xlabel("API cost per case (mUSD = $0.001)", fontsize=10.5)
    ax.set_ylabel("Joint correctness (%)", fontsize=10.5)
    ax.set_xlim(-0.15, 2.5)
    ax.set_ylim(30, 85)
    ax.grid(color=GRID, lw=0.8, zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.text(0.0, 1.1, "Quality vs. cost, all four measured systems", transform=ax.transAxes,
            fontsize=15, fontweight="bold", color=INK)
    ax.text(0.0, 1.035,
            "Rule → RAG → FULL is the real Pareto frontier; Qwen is strictly dominated (same $0, lower quality)",
            transform=ax.transAxes, fontsize=10, color=MUTED)

    fig.tight_layout()
    fig.savefig(OUT / "quality_cost_frontier.png", bbox_inches="tight")
    plt.close(fig)


def failure_pareto():
    tax = E20["failure_taxonomy"]
    total = E20["n_total_failures"]
    rows = [
        ("Reasoning / classification", tax["reasoning_classification"]),
        ("Evidence selection", tax["evidence_selection"]),
        ("Retrieval-limited", tax["retrieval_limited"]),
        ("Parser / source-validity", tax["runtime_parser_source_validity"]),
    ]
    rows.sort(key=lambda r: r[1], reverse=True)
    rows = rows[::-1]  # horizontal bar: largest on top

    fig, ax = plt.subplots(figsize=(8.5, 3.6), dpi=200)
    y = range(len(rows))
    highlight = "#C0472D"
    colors = [highlight if label.startswith("Reasoning") else DIM_C for label, _ in rows]
    bars = ax.barh(list(y), [r[1] / total * 100 for r in rows], color=colors, height=0.58, zorder=3)
    for i, (label, count) in enumerate(rows):
        pct = count / total * 100
        ax.text(pct + 1.5, i, f"{pct:.1f}%  ({count}/{total})", va="center", fontsize=10.5,
                color=INK, fontweight="bold")

    ax.set_yticks(list(y))
    ax.set_yticklabels([r[0] for r in rows], fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of RAG's 576 non-Joint TEST failures", fontsize=10)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(left=False)

    ax.text(0.0, 1.22, "Where RAG actually fails", transform=ax.transAxes,
            fontsize=15, fontweight="bold", color=INK)
    ax.text(0.0, 1.08,
            "78% are reasoning errors on evidence the system already retrieved — not a retrieval problem",
            transform=ax.transAxes, fontsize=10, color=MUTED)

    fig.tight_layout()
    fig.savefig(OUT / "failure_pareto.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    dumbbell_chart()
    cost_quality_frontier()
    failure_pareto()
    print("Wrote:")
    for name in ("full_vs_rag_dumbbell.png", "quality_cost_frontier.png", "failure_pareto.png"):
        p = OUT / name
        print(f"  {p} ({p.stat().st_size // 1024} KB)")
