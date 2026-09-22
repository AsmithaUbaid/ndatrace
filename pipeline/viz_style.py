"""
Shared chart styling template for all NDATrace notebooks and reports.

Every notebook that plots a chart should import from here rather than
redefining colors inline, so every figure in the project reads as one
system. Palette follows the dataviz skill's validated default: categorical
slots 1-3 (blue/orange/aqua) pass the CVD-safety all-pairs check for <=3
series; the sequential ramp is the same blue hue, light->dark.

Usage in a notebook:

    from pipeline.viz_style import CATEGORICAL, SEQUENTIAL_HUE, apply_style, style_axes

    apply_style()  # once, near the top of the notebook

    fig, ax = plt.subplots()
    ax.bar(x, y, color=CATEGORICAL["Entailment"])
    style_axes(ax)
"""

from __future__ import annotations

import matplotlib as mpl

# --- Chart chrome & ink (light mode) ---
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"

# --- Categorical palette (fixed slot order - never cycle, never remap by meaning) ---
# Add new series to the END of this dict in a fixed order; do not reorder
# existing entries once a chart has shipped with them.
CATEGORICAL_SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

# Domain-specific fixed assignment for the three NDA classification labels,
# shared by every chart that plots them (notebooks 01, 05, 06, 08, ...).
CATEGORICAL = {
    "Entailment": CATEGORICAL_SLOTS[0],    # slot 1 - blue
    "Contradiction": CATEGORICAL_SLOTS[1],  # slot 2 - orange
    "NotMentioned": CATEGORICAL_SLOTS[2],   # slot 3 - aqua
}

# Single-hue sequential ramp for magnitude encodings (histograms, heatmaps).
SEQUENTIAL_HUE = CATEGORICAL_SLOTS[0]  # slot 1 blue

# Status colors - reserved for actual pass/fail/warn states, never series identity.
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}


def apply_style() -> None:
    """Apply shared rcParams. Call once per notebook, before plotting."""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRIDLINE,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK_PRIMARY,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRIDLINE,
        "grid.linewidth": 0.8,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "text.color": INK_PRIMARY,
        "font.family": "sans-serif",
        "legend.frameon": False,
    })


def style_axes(ax) -> None:
    """Recessive spines/grid per the dataviz skill's mark specs. Call per-axes."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="y", zorder=0)
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)


def savefig_kwargs() -> dict:
    """Common kwargs for plt.savefig() so exported PNGs keep the surface color."""
    return {"dpi": 120, "facecolor": SURFACE}
