"""Figures sized for projection rather than for the page.

    python scripts/make_slide_figures.py

The report figures are drawn for an A4 column; on a projector their labels are
too small to read from the back of a room, and one of them sets the live model
beside the offline policy, whose perfect score is circular by construction and
would draw a question the slide cannot answer.  These redraw the held-out
evidence one message per figure.

Each is sized for a half-width slot on a 16:9 slide, because the deck pairs its
results two to a slide.  Type is set large relative to the canvas so it stays
legible once the figure is scaled into that slot.

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
from matplotlib.patches import Patch

from aistat.evaluation.analysis import (failure_taxonomy, made_a_selection,
                                        majority_by_case, pairwise_comparisons,
                                        report_validity, risk_coverage,
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
SIZE = (6.6, 3.9)               # half a 16:9 slide, with room for type

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 16,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.linewidth": 1,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "xtick.labelsize": 15, "ytick.labelsize": 16,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "savefig.dpi": 220, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.12, "grid.color": GRID, "grid.linewidth": 1,
})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name)
    plt.close(fig)
    print(f"  {name}")


def hbars(ax):
    ax.set_yticks(range(3), [LABEL[s] for s in ORDER])
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, zorder=0)


def accuracy(ss):
    """Selection accuracy with Wilson intervals: the headline result."""
    fig, ax = plt.subplots(figsize=SIZE)
    for i, s in enumerate(ORDER):
        r = ss.loc[s]
        v, lo, hi = r.selection_accuracy, r.acc_ci_low, r.acc_ci_high
        ax.barh([i], [v], height=0.58, color=SERIES[s], zorder=3,
                edgecolor=SURFACE, linewidth=2)
        ax.plot([lo, hi], [i, i], color=INK, lw=2.6, zorder=4)
        for x in (lo, hi):
            ax.plot([x, x], [i - 0.11, i + 0.11], color=INK, lw=2.6, zorder=4)
        # At the bar's root: at its end the value shared a height with the
        # interval, and the whisker ran through every figure.
        ax.text(0.025, i, f"{v:.0%}", ha="left", va="center", color="white",
                fontsize=21, fontweight="bold", zorder=5)
    hbars(ax)
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, .5, 1.0], ["0", "50%", "100%"])
    ax.set_xlabel("Chose a valid method · 95% intervals", fontsize=14,
                  color=MUTED, labelpad=10)
    save(fig, "accuracy.png")


def paired(pw):
    """The three paired comparisons, significance encoded in the mark itself."""
    rows = [("B_tools", "C_protocol", "C over B"),
            ("A_direct", "C_protocol", "C over A"),
            ("A_direct", "B_tools", "B over A")]
    fig, ax = plt.subplots(figsize=(4.4, 3.9))
    for i, (a, b, lab) in enumerate(rows):
        r = pw[(pw.system_a == a) & (pw.system_b == b)].iloc[0]
        d, lo, hi, p = (r.uplift_b_minus_a, r.uplift_ci_low,
                        r.uplift_ci_high, r.mcnemar_p)
        sig = p < 0.05
        col = SERIES["C_protocol"] if sig else MUTED
        ax.plot([lo, hi], [i, i], color=col, lw=3.4,
                linestyle="-" if sig else (0, (4, 3)), zorder=3)
        ax.scatter([d], [i], s=260, zorder=4, color=col if sig else SURFACE,
                   edgecolors=col, linewidths=2.8)
        # The readout sits in its own column right of the axes.  Inside the
        # axes it landed on the intervals it describes, and bbox_inches="tight"
        # overrides any margin set with subplots_adjust.
        # Points, not percent: a 25-point difference and a 25% relative rise
        # are different claims, and the axis is in points.
        pts = f"{d * 100:+.1f}".replace("-", "\u2212")
        ax.text(1.06, i - 0.04, f"{pts} pts  p = {p:.4f}", va="bottom",
                ha="left", fontsize=16, fontweight="bold",
                color=INK if sig else MUTED,
                transform=ax.get_yaxis_transform())
        ax.text(1.06, i + 0.04, "established" if sig else "not established",
                va="top", ha="left", fontsize=14,
                color=SERIES["C_protocol"] if sig else MUTED,
                fontweight="bold" if sig else "normal",
                transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK_2, lw=1.3, zorder=2)
    ax.set_yticks(range(3), [r[2] for r in rows])
    ax.set_ylim(2.55, -0.55)
    ax.set_xlim(-0.32, 0.45)
    ax.set_xticks([-0.25, 0, 0.25], ["−25", "0", "+25"])
    ax.xaxis.grid(True, zorder=0)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Difference, percentage points", fontsize=14, color=MUTED,
                  labelpad=10)
    save(fig, "paired.png")


def abstention(ss):
    """Declining on the design-hazard cases: the sharpest separation."""
    fig, ax = plt.subplots(figsize=SIZE)
    n_haz = 18
    for i, s in enumerate(ORDER):
        v = ss.loc[s].abstention_recall
        lo, hi = wilson_ci(round(v * n_haz), n_haz)
        ax.bar([i], [v], width=0.58, color=SERIES[s], zorder=3,
               edgecolor=SURFACE, linewidth=2)
        ax.plot([i, i], [lo, hi], color=INK, lw=2.6, zorder=4)
        ax.text(i, hi + 0.05, f"{v:.0%}", ha="center", va="bottom",
                fontsize=22, fontweight="bold", color=INK)
    ax.set_xticks(range(3), [LABEL[s] for s in ORDER])
    ax.set_ylim(0, 1.22)
    ax.set_yticks([0, .5, 1.0], ["0", "50%", "100%"])
    ax.yaxis.grid(True, zorder=0)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Declined correctly", fontsize=14, color=MUTED)
    save(fig, "abstention.png")


def validity(rv):
    """How often the finished report could be grounded in real calculations."""
    fig, ax = plt.subplots(figsize=SIZE)
    for i, s in enumerate(ORDER):
        r = rv.loc[s]
        v = r.report_valid_rate
        ax.barh([i], [v], height=0.58, color=SERIES[s], zorder=3,
                edgecolor=SURFACE, linewidth=2)
        ax.text(0.025, i, f"{v:.0%}", ha="left", va="center", color="white",
                fontsize=21, fontweight="bold", zorder=5)
        ax.text(1.03, i, f"{int(r.n_report_rejected)} rejected", ha="left",
                va="center", fontsize=15, color=INK_2,
                transform=ax.get_yaxis_transform())
    hbars(ax)
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, .5, 1.0], ["0", "50%", "100%"])
    ax.set_xlabel("Reports passing the provenance check", fontsize=14,
                  color=MUTED, labelpad=10)
    save(fig, "validity.png")


def failures(ft):
    """Where each system fails, by stage of the error taxonomy."""
    stages = [("design_validation", "Design validation", None),
              ("diagnostic_reasoning", "Diagnostic reasoning", "//"),
              ("problem_parsing", "Problem parsing", "..")]
    fig, ax = plt.subplots(figsize=SIZE)
    for i, s in enumerate(ORDER):
        left = 0
        for key, _, hatch in stages:
            k = int(ft[(ft.system == s) & (ft.failure_stage == key)].n.sum())
            if not k:
                continue
            ax.barh([i], [k], left=left, height=0.58, color=SERIES[s],
                    hatch=hatch, edgecolor=SURFACE, linewidth=2, zorder=3)
            if k >= 3:
                ax.text(left + k / 2, i, str(k), ha="center", va="center",
                        fontsize=16, fontweight="bold", color="white", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.12", fc=SERIES[s],
                                  ec="none"))
            left += k
    hbars(ax)
    ax.set_xlim(0, 34)
    ax.set_xlabel("Failed runs", fontsize=14, color=MUTED, labelpad=10)
    handles = [Patch(facecolor="#8496a6", edgecolor=SURFACE, hatch=h, label=l)
               for _, l, h in stages]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.42, -0.3),
              ncol=3, frameon=False, fontsize=12.5, handlelength=1.5,
              columnspacing=1.2)
    save(fig, "failures.png")


def coverage(rc):
    """Selective accuracy against coverage, labels joined by leaders.

    Labels sit in one column left of every point, each joined to its own dot.
    A rule-based offset once placed each label beside the other system's point.
    """
    fig, ax = plt.subplots(figsize=SIZE)
    pts = []
    for s in ORDER:
        r = rc[rc.system == s].iloc[0]
        pts.append((s, float(r.coverage), float(r.selective_accuracy)))
        ax.scatter([r.coverage], [r.selective_accuracy], s=300,
                   color=SERIES[s], zorder=4, edgecolors=SURFACE, linewidths=2)
    col_x = min(p[1] for p in pts) - 0.06
    placed = []
    for s, cov, acc in sorted(pts, key=lambda p: -p[2]):
        y = acc if not placed or placed[-1] - acc >= 0.085 else placed[-1] - 0.085
        placed.append(y)
        ax.annotate(f"{LABEL[s]}  {acc:.0%}", xy=(cov, acc), xytext=(col_x, y),
                    textcoords="data", ha="right", va="center", fontsize=15,
                    color=INK, zorder=5,
                    arrowprops=dict(arrowstyle="-", color=SERIES[s], lw=1.5,
                                    shrinkA=5, shrinkB=9))
    ax.set_xlim(0.52, 1.02)
    ax.set_ylim(0.55, 0.95)
    ax.set_xticks([0.6, 0.8, 1.0], ["60%", "80%", "100%"])
    ax.set_yticks([0.6, 0.7, 0.8, 0.9], ["60%", "70%", "80%", "90%"])
    ax.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel("Coverage: share of cases answered", fontsize=14,
                  color=MUTED, labelpad=10)
    ax.set_ylabel("Accuracy on those", fontsize=14, color=MUTED)
    save(fig, "coverage.png")


def main() -> int:
    s = made_a_selection(load_scores(RUN))
    ss = system_summary(s).set_index("system")
    accuracy(ss)
    paired(pairwise_comparisons(majority_by_case(s)))
    abstention(ss)
    validity(report_validity(s).set_index("system"))
    failures(failure_taxonomy(s))
    coverage(risk_coverage(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
