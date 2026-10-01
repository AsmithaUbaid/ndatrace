#!/usr/bin/env python3
"""E24: render the two notebook figures from results/e24_analysis.json. Zero model calls."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
FIG_DIR = HERE / "figures"
FIG_DIR.mkdir(exist_ok=True)

A = json.loads((HERE / "results" / "e24_analysis.json").read_text())
S = A["summary_by_system"]

INK = "#17233B"; MUTED = "#5B6B82"; GRID = "#E4E9F0"
COLORS = {"rule": "#B9C2D0", "full": "#2F5FA8", "rag": "#0E8A7D"}
NAMES = {"rule": "Rule", "full": "FULL", "rag": "RAG"}


def fig_accuracy_joint():
    systems = ["rule", "full", "rag"]
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=150)
    x = range(len(systems))
    acc = [S[s]["accuracy"] * 100 for s in systems]
    joint = [S[s]["joint_correctness"] * 100 for s in systems]
    w = 0.32
    ax.bar([i - w / 2 for i in x], acc, width=w, label="Accuracy", color="#9FB3CC")
    ax.bar([i + w / 2 for i in x], joint, width=w, label="Joint correctness", color=[COLORS[s] for s in systems])
    for i, (a, j) in enumerate(zip(acc, joint)):
        ax.text(i - w / 2, a + 1.5, f"{a:.1f}", ha="center", fontsize=9, color=INK)
        ax.text(i + w / 2, j + 1.5, f"{j:.1f}", ha="center", fontsize=9, color=INK)
    ax.set_xticks(list(x)); ax.set_xticklabels([NAMES[s] for s in systems], fontsize=11)
    ax.set_ylim(0, 90); ax.set_ylabel("%")
    ax.set_title("E24: 49-case targeted evaluation (current architecture)", fontsize=13, fontweight="bold", color=INK, loc="left")
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for spine in ("top", "right"): ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "01_accuracy_joint.png")
    plt.close(fig)


def fig_test_vs_targeted():
    # Hardcoded from experiments/E20_final_rag_test and this experiment's own summary -- both
    # already-verified, saved results; not recomputed here.
    test_pop = {"rule": (59.0, 50.1), "full": (77.6, 74.6), "rag": (76.8, 72.5)}
    e24_pop = {s: (S[s]["accuracy"] * 100, S[s]["joint_correctness"] * 100) for s in ("rule", "full", "rag")}
    systems = ["rule", "full", "rag"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.3), dpi=150, sharey=True)
    for ax, (title, pop) in zip(axes, [("2,091-case TEST (official)", test_pop), ("49-case targeted (E24)", e24_pop)]):
        x = range(len(systems))
        acc = [pop[s][0] for s in systems]; joint = [pop[s][1] for s in systems]
        w = 0.32
        ax.bar([i - w / 2 for i in x], acc, width=w, label="Accuracy", color="#9FB3CC")
        ax.bar([i + w / 2 for i in x], joint, width=w, label="Joint", color=[COLORS[s] for s in systems])
        ax.set_xticks(list(x)); ax.set_xticklabels([NAMES[s] for s in systems], fontsize=10)
        ax.set_title(title, fontsize=11, color=MUTED)
        ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
        for spine in ("top", "right"): ax.spines[spine].set_visible(False)
    axes[0].set_ylabel("%"); axes[0].set_ylim(0, 90)
    axes[0].legend(frameon=False, loc="upper left", fontsize=9)
    fig.suptitle("Two populations, never merged into one number", fontsize=13, fontweight="bold", color=INK, x=0.03, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIG_DIR / "02_test_vs_targeted.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_accuracy_joint()
    fig_test_vs_targeted()
    print("Wrote figures/01_accuracy_joint.png, figures/02_test_vs_targeted.png")
