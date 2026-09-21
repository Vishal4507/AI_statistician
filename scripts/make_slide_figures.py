"""Figures sized for projection rather than for the page.

    python scripts/make_slide_figures.py

The report figures are drawn for an A4 column; on a projector their labels are
too small to read from the back of a room, and one of them sets the live model
beside the offline policy, whose perfect score is circular by construction and
would draw a question the slide cannot answer.  These redraw the held-out
evidence one message per figure, at a type size that survives a projector.

Every value is computed from the recorded held-out run.  Nothing is typed in.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from aistat.evaluation.analysis import (made_a_selection, majority_by_case,
                                        pairwise_comparisons, report_validity,
                                        system_summary, wilson_ci)
from aistat.evaluation.runner import load_scores

OUT = ROOT / "reports" / "figures" / "slides"
RUN = "heldout_claude-haiku-4-5"

ORDER = ["A_direct", "B_tools", "C_protocol"]
SERIES = {"A_direct": "#2f6fd0", "B_tools": "#dd6027", "C_protocol": "#129b68"}
LABEL = {"A_direct": "A · Direct", "B_tools": "B · Tools only",
         "C_protocol": "C · Protocol"}
INK, INK_2, MUTED, GRID = "#16222e", "#4a5a69", "#8496a6", "#e2e9f0"
SURFACE = "#ffffff"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 15,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.linewidth": 1,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "xtick.labelsize": 14, "ytick.labelsize": 15,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "savefig.dpi": 200, "savefig.bbox": "tight",
    "grid.color": GRID, "grid.linewidth": 1,
})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name)
    plt.close(fig)
    print(f"  {name}")


def accuracy(ss):
    """Selection accuracy with Wilson intervals: the headline result."""
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    for i, s in enumerate(ORDER):
        r = ss.loc[s]
        v, lo, hi = r.selection_accuracy, r.acc_ci_low, r.acc_ci_high
        ax.barh([i], [v], height=0.56, color=SERIES[s], zorder=3,
                edgecolor=SURFACE, linewidth=2)
        ax.plot([lo, hi], [i, i], color=INK, lw=2.4, zorder=4,
                solid_capstyle="butt")
        for x in (lo, hi):
            ax.plot([x, x], [i - 0.1, i + 0.1], color=INK, lw=2.4, zorder=4)
        # The value sits at the bar's root.  At the bar's end it shared a
        # height with the interval, so the whisker ran through every figure.
        ax.text(0.025, i, f"{v:.0%}", ha="left", va="center",
                color="white", fontsize=20, fontweight="bold", zorder=5)
    ax.set_yticks(range(3), [LABEL[s] for s in ORDER])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, .25, .5, .75, 1.0], ["0", "25%", "50%", "75%", "100%"])
    ax.xaxis.grid(True, zorder=0)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Chose an admissible method   ·   whiskers are 95% intervals",
                  fontsize=13, color=MUTED, labelpad=12)
    save(fig, "accuracy.png")


def paired(pw):
    """The three paired comparisons, significance encoded in the mark itself."""
    rows = [("B_tools", "C_protocol", "C over B"),
            ("A_direct", "C_protocol", "C over A"),
            ("A_direct", "B_tools", "B over A")]
    fig, ax = plt.subplots(figsize=(6.0, 4.4))
    for i, (a, b, lab) in enumerate(rows):
        r = pw[(pw.system_a == a) & (pw.system_b == b)].iloc[0]
        d, lo, hi, p = (r.uplift_b_minus_a, r.uplift_ci_low,
                        r.uplift_ci_high, r.mcnemar_p)
        sig = p < 0.05
        col = SERIES["C_protocol"] if sig else MUTED
        ax.plot([lo, hi], [i, i], color=col, lw=3.2,
                linestyle="-" if sig else (0, (4, 3)), zorder=3)
        ax.scatter([d], [i], s=240, zorder=4, color=col if sig else SURFACE,
                   edgecolors=col, linewidths=2.6)
        # The readout lives in its own column right of the axes.  Placed at
        # x=0.52 in axes coordinates it sat mid-plot, on top of the intervals
        # it describes -- and bbox_inches="tight" overrides subplots_adjust, so
        # a margin set that way never appears.  Beyond x=1 it cannot collide.
        verdict = "established" if sig else "not established"
        ax.text(1.04, i, f"{d:+.1%}", va="center", ha="left", fontsize=16,
                color=INK if sig else MUTED, fontweight="bold",
                transform=ax.get_yaxis_transform())
        ax.text(1.27, i, f"p = {p:.4f}", va="center", ha="left", fontsize=14,
                color=INK if sig else MUTED,
                transform=ax.get_yaxis_transform())
        ax.text(1.62, i, verdict, va="center", ha="left", fontsize=14,
                color=SERIES["C_protocol"] if sig else MUTED,
                fontweight="bold" if sig else "normal",
                transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK_2, lw=1.2, zorder=2)
    ax.set_yticks(range(3), [r[2] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(-0.32, 0.45)
    ax.set_xticks([-0.25, 0, 0.25], ["−25 pts", "0", "+25 pts"])
    ax.xaxis.grid(True, zorder=0)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Difference in accuracy, per-case majority, 48 cases",
                  fontsize=13, color=MUTED, labelpad=12)
    save(fig, "paired.png")


def abstention(ss):
    """Declining on the design-hazard cases: the sharpest separation."""
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    n_haz = 18
    for i, s in enumerate(ORDER):
        v = ss.loc[s].abstention_recall
        k = round(v * n_haz)
        lo, hi = wilson_ci(k, n_haz)
        ax.bar([i], [v], width=0.56, color=SERIES[s], zorder=3,
               edgecolor=SURFACE, linewidth=2)
        ax.plot([i, i], [lo, hi], color=INK, lw=2.4, zorder=4)
        ax.text(i, max(v, hi) + 0.05, f"{v:.0%}", ha="center", va="bottom",
                fontsize=20, fontweight="bold", color=INK)
    ax.set_xticks(range(3), [LABEL[s] for s in ORDER])
    ax.set_ylim(0, 1.18)
    ax.set_yticks([0, .5, 1.0], ["0", "50%", "100%"])
    ax.yaxis.grid(True, zorder=0)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Declined correctly", fontsize=13, color=MUTED)
    save(fig, "abstention.png")


def validity(rv):
    """How often the finished report could be grounded in real calculations."""
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    for i, s in enumerate(ORDER):
        r = rv.loc[s]
        v = r.report_valid_rate
        ax.barh([i], [v], height=0.56, color=SERIES[s], zorder=3,
                edgecolor=SURFACE, linewidth=2)
        ax.text(min(v, 0.97) - 0.02, i,
                f"{v:.0%}", ha="right", va="center", color="white",
                fontsize=19, fontweight="bold", zorder=5)
        ax.text(1.02, i, f"{int(r.n_report_rejected)} of {int(r.n_runs)} rejected",
                ha="left", va="center", fontsize=14, color=INK_2,
                transform=ax.get_yaxis_transform())
    ax.set_yticks(range(3), [LABEL[s] for s in ORDER])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, .5, 1.0], ["0", "50%", "100%"])
    ax.xaxis.grid(True, zorder=0)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Reports that passed the provenance contract",
                  fontsize=13, color=MUTED, labelpad=12)
    fig.subplots_adjust(right=0.76)
    save(fig, "validity.png")


def main() -> int:
    s = made_a_selection(load_scores(RUN))
    ss = system_summary(s).set_index("system")
    rv = report_validity(s).set_index("system")
    pw = pairwise_comparisons(majority_by_case(s))
    accuracy(ss)
    paired(pw)
    abstention(ss)
    validity(rv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
