"""Figures for the capstone report.

    python scripts/make_figures.py

Every value is read from results/*.jsonl -- nothing is typed in, so the figures
regenerate correctly after any new evaluation.

Palette is the validated categorical default (blue / orange / aqua), assigned in
fixed order to A / B / C so a system keeps its colour across every figure. Aqua
sits below 3:1 against the surface, so every mark carries a direct value label
rather than relying on the fill to be read.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aistat.env import load_dotenv
load_dotenv()          # credentials are project-local, not in a shell profile
warnings.filterwarnings("ignore")

import logging

import matplotlib
matplotlib.use("Agg")
# IBM Plex is preferred but rarely installed; the fallback is fine and the
# per-glyph warnings are pure noise.
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib.pyplot as plt
import pandas as pd

from aistat.evaluation.analysis import made_a_selection, wilson_ci
from aistat.evaluation.liveness import best_live_heldout

FIGS = ROOT / "reports" / "figures"
RESULTS = ROOT / "results"

# Categorical slots 1-3, fixed order. Colour follows the system, never its rank.
SERIES = {"A_direct": "#2a78d6", "B_tools": "#eb6834", "C_protocol": "#1baf7a"}
LABEL = {"A_direct": "A · Direct LLM", "B_tools": "B · With tools",
         "C_protocol": "C · Structured agent"}
ORDER = ["A_direct", "B_tools", "C_protocol"]

INK = "#0b0b0b"
INK_2 = "#52514e"
INK_3 = "#8a8985"
GRID = "#e6e6e3"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": ["IBM Plex Sans", "DejaVu Sans"],
    "font.size": 9, "text.color": INK,
    "axes.labelcolor": INK_2, "axes.edgecolor": GRID, "axes.linewidth": 0.8,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.7,
    "figure.dpi": 160, "savefig.dpi": 160, "savefig.bbox": "tight",
})


def load(name: str) -> pd.DataFrame:
    p = RESULTS / f"{name}_scores.jsonl"
    if not p.exists():
        return pd.DataFrame()
    df = pd.DataFrame([json.loads(l) for l in p.read_text().splitlines() if l.strip()])
    # Runs whose report was rejected are kept: they chose a method, and these
    # figures plot the choice.  Only runs that never reached a decision go.
    return made_a_selection(df) if len(df) else df


def title(ax, text: str, sub: str = "") -> None:
    ax.set_title(text, loc="left", fontsize=11, fontweight="600",
                 color=INK, pad=14 if sub else 8)
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=8.5,
                color=INK_3, va="bottom")


# ---------------------------------------------------------------- figure 1

def scale(df: pd.DataFrame) -> str:
    """Describe a run set from the run set, so a caption cannot go stale."""
    n_reps = int(df.rep.nunique()) if "rep" in df and len(df) else 1
    word = {1: "one", 2: "two", 3: "three", 4: "four"}.get(n_reps, str(n_reps))
    return (f"{len(df)} runs, {word} repetition"
            + ("s" if n_reps != 1 else ""))


def fig_accuracy(live: pd.DataFrame, offline: pd.DataFrame, *,
                 heads: tuple[str, str] = ("Claude Opus 5 — development set",
                                           "Offline policy — held-out set"),
                 out: str = "fig1_accuracy.png") -> None:
    """Selection accuracy with Wilson intervals, live beside offline."""
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.1), sharex=True)
    fig.subplots_adjust(wspace=0.42)
    panels = [(axes[0], live, heads[0], scale(live)),
              (axes[1], offline, heads[1], scale(offline))]

    for ax, df, head, sub in panels:
        if df.empty:
            ax.axis("off"); continue
        ys, vals, los, his, cols, labs = [], [], [], [], [], []
        for i, s in enumerate(ORDER):
            g = df[df.system == s]
            if g.empty:
                continue
            k, n = int(g.selection_correct.sum()), len(g)
            lo, hi = wilson_ci(k, n)
            ys.append(i); vals.append(k / n); los.append(lo); his.append(hi)
            cols.append(SERIES[s]); labs.append(f"{LABEL[s]}\n$n$ = {n}")

        ax.barh(ys, vals, height=0.5, color=cols, zorder=3,
                edgecolor=SURFACE, linewidth=2)
        # A Wilson interval on a perfect score can round a hair inside the
        # point estimate; clamp so the whisker is never negative.
        lower = [max(v - l, 0.0) for v, l in zip(vals, los)]
        upper = [max(h - v, 0.0) for v, h in zip(vals, his)]
        ax.errorbar(vals, ys, xerr=[lower, upper],
                    fmt="none", ecolor=INK_2, elinewidth=1.4, capsize=3.5, zorder=4)
        # Inside the bar, right-aligned. Outside labels collided with the
        # adjacent panel's axis text -- caught by looking at the render, which
        # no palette check would have found.
        for y, v in zip(ys, vals):
            ax.text(v - 0.02, y, f"{v:.0%}", va="center", ha="right",
                    fontsize=9.5, color="#ffffff", fontweight="600", zorder=5)

        ax.set_yticks(ys); ax.set_yticklabels(labs)
        ax.set_xlim(0, 1.06); ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
        ax.xaxis.grid(True, zorder=0); ax.set_axisbelow(True)
        ax.invert_yaxis()
        title(ax, head, sub)

    fig.text(0.5, -0.06, "Method-selection accuracy · bars are Wilson 95% intervals",
             ha="center", fontsize=8.5, color=INK_3)
    fig.savefig(FIGS / out)
    plt.close(fig)


# ---------------------------------------------------------------- figure 2

def fig_risk_coverage(df: pd.DataFrame, name: str, out: str = "fig2_risk_coverage.png") -> None:
    """Selective accuracy against coverage -- the safety result.

    A system that abstains only when it should sits top-right. One that answers
    everything sits far right and low; one that abstains indiscriminately drifts
    left without gaining accuracy.
    """
    fig, ax = plt.subplots(figsize=(6.4, 4.2))

    points = []
    for s in ORDER:
        g = df[df.system == s]
        if g.empty:
            continue
        answered = g[~g.chose_abstention]
        cov = float((~g.chose_abstention).mean())
        acc = float(answered.selection_correct.mean()) if len(answered) else float("nan")
        points.append((s, cov, acc))

    # Systems that answer everything pile up on the right edge, so their labels
    # go left and are staggered vertically; anything with headroom labels below.
    at_edge = sorted([p for p in points if p[1] > 0.95], key=lambda p: -p[2])
    for s, cov, acc in points:
        ax.scatter([cov], [acc], s=190, color=SERIES[s], zorder=4,
                   edgecolors=SURFACE, linewidths=2)
        text = f"{LABEL[s]}\n{acc:.0%} at {cov:.0%} coverage"
        if (s, cov, acc) in at_edge:
            rank = at_edge.index((s, cov, acc))
            ax.annotate(text, (cov, acc), textcoords="offset points",
                        xytext=(-18, 22 if rank == 0 else -30), ha="right",
                        fontsize=8.5, color=INK, linespacing=1.5)
        else:
            ax.annotate(text, (cov, acc), textcoords="offset points",
                        xytext=(0, -34), ha="center",
                        fontsize=8.5, color=INK, linespacing=1.5)

    ax.set_xlabel("Coverage — share of cases the system chose to answer")
    ax.set_ylabel("Selective accuracy — accuracy among those")
    ax.set_xlim(0.48, 1.06); ax.set_ylim(0.28, 1.16)
    ax.set_xticks([0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xticklabels(["60%", "70%", "80%", "90%", "100%"])
    ax.set_yticks([0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["40%", "60%", "80%", "100%"])
    ax.grid(True, zorder=0); ax.set_axisbelow(True)
    title(ax, "Risk–coverage", f"{name} · top-right is better")
    fig.savefig(FIGS / out)
    plt.close(fig)


# ---------------------------------------------------------------- figure 3

def fig_failures(df: pd.DataFrame, name: str, out: str = "fig3_failures.png") -> None:
    """Where each system fails, by stage of the error taxonomy."""
    f = df[df.failure_stage.notna()]
    if f.empty:
        return
    stages = list(f.failure_stage.value_counts().index)
    fig, ax = plt.subplots(figsize=(7.4, 3.1))

    left = {s: 0 for s in ORDER}
    hatch = [None, "///", "...", "\\\\\\"]
    for j, stage in enumerate(stages):
        ys, widths, cols = [], [], []
        for i, s in enumerate(ORDER):
            n = int(((f.system == s) & (f.failure_stage == stage)).sum())
            ys.append(i); widths.append(n); cols.append(SERIES[s])
        bars = ax.barh(ys, widths, left=[left[s] for s in ORDER], height=0.5,
                       color=cols, zorder=3, edgecolor=SURFACE, linewidth=2,
                       hatch=hatch[j % len(hatch)], alpha=1.0)
        for i, s in enumerate(ORDER):
            n = int(((f.system == s) & (f.failure_stage == stage)).sum())
            if n:
                # A hatched segment is busy behind white text, so the value sits
                # on a small solid plate rather than fighting the texture.
                ax.text(left[s] + n / 2, i, str(n), va="center", ha="center",
                        fontsize=8.5, color="#ffffff", fontweight="600", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.22", facecolor=cols[i],
                                  edgecolor="none"))
            left[s] += n

    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels([LABEL[s] for s in ORDER])
    ax.invert_yaxis()
    ax.set_xlabel("Failed runs")
    ax.xaxis.grid(True, zorder=0); ax.set_axisbelow(True)
    # Texture carries the stage, colour carries the system -- neither alone.
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=INK_3, edgecolor=SURFACE,
                             hatch=hatch[j % len(hatch)])
               for j in range(len(stages))]
    # Below the axes: inside the plot it sat on top of the longest bar.
    ax.legend(handles, [s.replace("_", " ") for s in stages],
              frameon=False, fontsize=8, ncol=len(stages),
              loc="upper center", bbox_to_anchor=(0.5, -0.28),
              labelcolor=INK_2, handlelength=1.6, columnspacing=1.6)
    title(ax, "Where each system fails", f"{name} · stage of the error taxonomy")
    fig.savefig(FIGS / out)
    plt.close(fig)


# ---------------------------------------------------------------- figure 4

def fig_abstention(live: pd.DataFrame, offline: pd.DataFrame) -> None:
    """Abstention recall -- the sharpest separation between the systems."""
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    sets = [("Claude Opus 5, dev", live), ("Offline policy, held out", offline)]
    width, gap = 0.34, 0.06
    for gi, (gname, df) in enumerate(sets):
        if df.empty:
            continue
        for i, s in enumerate(ORDER):
            g = df[(df.system == s) & df.gold_is_abstention]
            if g.empty:
                continue
            v = float(g.chose_abstention.mean())
            x = i + (gi - 0.5) * (width + gap)
            ax.bar([x], [v], width=width, color=SERIES[s], zorder=3,
                   edgecolor=SURFACE, linewidth=2,
                   hatch=None if gi == 0 else "///")
            ax.text(x, v + 0.035, f"{v:.0%}", ha="center", va="bottom",
                    fontsize=8.5, color=INK, fontweight="600")

    ax.set_xticks(range(len(ORDER)))
    ax.set_xticklabels([LABEL[s] for s in ORDER])
    ax.set_ylim(0, 1.22); ax.set_yticks([0, 0.5, 1.0])
    ax.set_yticklabels(["0", "50%", "100%"])
    ax.set_ylabel("Abstention recall")
    ax.yaxis.grid(True, zorder=0); ax.set_axisbelow(True)
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=INK_3, edgecolor=SURFACE,
                             hatch=h) for h in (None, "///")]
    ax.legend(handles, [s[0] for s in sets], frameon=False, fontsize=8,
              loc="upper left", labelcolor=INK_2)
    title(ax, "Recognising an invalid design",
          "share of design-hazard cases the system declined to model")
    fig.savefig(FIGS / "fig4_abstention.png")
    plt.close(fig)


def main() -> int:
    FIGS.mkdir(parents=True, exist_ok=True)
    live = load("dev_claude-opus-5_high")
    offline = load("heldout_rulebased_expert")
    naive = load("heldout_rulebased_naive")

    fig_accuracy(live, offline)
    fig_risk_coverage(offline if not offline.empty else live,
                      "Offline policy, held-out set")
    fig_failures(naive if not naive.empty else offline,
                 "Naive policy, held-out set")
    fig_abstention(live, offline)

    # The held-out live run, once it exists, supports a comparison the first
    # four figures cannot: a real model and the deterministic policy on the
    # same split.  Figure 1 puts a development-set run beside a held-out one,
    # which is the best available until this run happens and the weaker
    # comparison afterwards.
    best = best_live_heldout(RESULTS)
    if best is not None:
        held = load(best[0].name[: -len("_scores.jsonl")])
        model = best[0].name.split("heldout_")[1].split("_scores")[0]
        if not held.empty:
            fig_accuracy(held, offline,
                         heads=(f"{model} — held-out set",
                                "Offline policy — held-out set"),
                         out="fig5_heldout_accuracy.png")
            fig_risk_coverage(held, f"{model}, held-out set",
                              out="fig6_heldout_risk_coverage.png")
            fig_failures(held, f"{model}, held-out set",
                         out="fig7_heldout_failures.png")

    for p in sorted(FIGS.glob("*.png")):
        print(f"  {p.name:26s} {p.stat().st_size/1024:6.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
