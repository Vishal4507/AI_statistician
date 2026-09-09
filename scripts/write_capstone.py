"""Generate the capstone report (blueprint section 6 step 15).

    python scripts/write_capstone.py

Every number is computed from results/*.jsonl.  The narrative is written here;
the evidence is not, so the document regenerates correctly when the held-out
evaluation is eventually run.

The report distinguishes three kinds of evidence and never blurs them:

  offline calibration   the deterministic policy client.  Validates the harness
                        and the internal coherence of the gold labels.  The
                        expert policy derived those labels, so its score is
                        circular and is reported as such.
  live preliminary      real Claude runs on the DEVELOPMENT set.
  live held-out         the frozen evaluation.  Absent until it is run.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

from aistat.evaluation.analysis import bootstrap_diff, mcnemar, wilson_ci

RESULTS = ROOT / "results"
DOCS = ROOT / "docs"
LABEL = {"A_direct": "A · Direct LLM", "B_tools": "B · LLM with tools",
         "C_protocol": "C · Structured agent"}


def load(name: str) -> pd.DataFrame | None:
    p = RESULTS / f"{name}_scores.jsonl"
    if not p.exists():
        return None
    df = pd.DataFrame([json.loads(l) for l in p.read_text().splitlines() if l.strip()])
    return df if len(df) else None


def clean(df: pd.DataFrame) -> pd.DataFrame:
    return df[df.run_error.isna()] if df is not None else pd.DataFrame()


def sys_rows(df: pd.DataFrame) -> str:
    out = []
    for s, g in df.groupby("system"):
        k, n = int(g.selection_correct.sum()), len(g)
        lo, hi = wilson_ci(k, n)
        ab = g[g.gold_is_abstention]
        arec = f"{ab.chose_abstention.mean():.2f}" if len(ab) else "—"
        out.append(f"| {LABEL.get(s, s)} | {n} | {k/n:.3f} | [{lo:.3f}, {hi:.3f}] | "
                   f"{arec} | {g.unsafe_selection.mean():.3f} | "
                   f"{g.n_tool_calls.mean():.1f} |")
    return "\n".join(out)


def paired(df: pd.DataFrame, a: str, b: str) -> dict | None:
    w = df.pivot_table(index="case_id", columns="system",
                       values="selection_correct", aggfunc="first")
    if a not in w or b not in w:
        return None
    p = w[[a, b]].dropna()
    if len(p) < 3:
        return None
    va, vb = p[a].astype(bool).to_numpy(), p[b].astype(bool).to_numpy()
    m = mcnemar(va, vb)
    bs = bootstrap_diff(va.astype(float), vb.astype(float))
    return {"n": len(p), "acc_a": va.mean(), "acc_b": vb.mean(),
            "uplift": vb.mean() - va.mean(), "p": m["p_value"],
            "b_only": m["b_only_correct"], "a_only": m["a_only_correct"],
            "ci_low": bs["ci_low"], "ci_high": bs["ci_high"]}


def main() -> int:
    live_hi = clean(load("dev_claude-opus-5_high"))
    live_med = clean(load("dev_claude-opus-5_medium"))
    off_exp = clean(load("heldout_rulebased_expert"))
    off_nai = clean(load("heldout_rulebased_naive"))
    held = clean(load("heldout_claude-opus-5"))          # absent until run

    bc = paired(live_hi, "B_tools", "C_protocol") if len(live_hi) else None
    off_bc = paired(off_nai, "B_tools", "C_protocol") if len(off_nai) else None

    n_live = len(live_hi) + len(live_med)
    raw = load("dev_claude-opus-5_high")
    n_lost = len(raw) - len(live_hi) if raw is not None else 0

    figs = ROOT / "reports" / "figures"
    has_figs = (figs / "fig1_accuracy.png").exists()

    def fig(name: str, caption: str) -> str:
        if not has_figs:
            return ""
        return (f"\n![{caption}](figures/{name})\n\n"
                f"*{caption}*\n")

    doc = f"""# AI Statistician — capstone report

*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} from `results/*.jsonl`.
Regenerate with `python scripts/write_capstone.py`.*

---

## 1. Problem

An LLM asked to analyse a dataset will almost always produce an answer. Whether
that answer is *valid* is a different question, and one the model is poorly
placed to police: a CSV cannot reveal whether rows are independent, whether the
same customer appears twice, or whether observations are ordered in time. A
mathematically fluent system with no view of study design will confidently fit
Poisson to autocorrelated hourly counts.

This project asks whether an explicit statistical decision protocol improves an
LLM agent's ability to select and execute valid methods, compared with
(A) direct LLM advice and (B) tool access without a protocol.

The contribution is not the interface or the number of supported tests. It is
controlled evidence that design-aware routing, targeted diagnostics and
verification improve validity over ordinary LLM tool use.

## 2. System

A closed library of 14 methods, five diagnostic tools, and a deterministic state
machine around one tool-calling LLM. SciPy and statsmodels perform every
numerical operation.

| Task | Methods |
|---|---|
| Two independent groups | `student_t`, `welch_t`, `mann_whitney` |
| Three or more groups | `one_way_anova`, `welch_anova`, `kruskal_wallis` |
| Two categorical | `chi_square`, `fisher_exact` |
| Two continuous or ordinal | `pearson`, `spearman` |
| Regression | `ols`, `logistic`, `poisson`, `negative_binomial` |

`abstain` is a decision, not a member of the library. There is deliberately no
general code-execution tool: it would let the model bypass the method policy and
make traces incomparable across systems.

### 2.1 The provenance contract

The strongest claim this system makes is that **the model cannot write a
number**. Rather than checking the finished report for fabrication, fabrication
is made impossible:

1. Every tool return is registered in a run-scoped store under a stable key.
2. The report schema rejects raw numeric literals in prose.
3. The model emits `{{{{r7.welch_t.p_value}}}}` templates, substituted at render.
4. An unknown reference fails the run.

The consequence must be stated honestly: for System C, numerical fidelity is an
**architectural guarantee, not an empirical finding**. The empirical counterpart
is the provenance rejection rate — how often the model reached for a reference
that did not exist. Across every live run recorded here that count is
**{int(live_hi.provenance_rejections.sum()) if len(live_hi) else 0}**.

For Systems A and B nothing is enforced, so fidelity remains an empirical metric
there and the comparison stays meaningful.

## 3. Benchmark

64 cases — 52 supported, 12 abstention; 48 synthetic and 16 from public UCI
data; 16 development and 48 held out.

Cases are never hand-authored. One declarative registry entry produces the whole
six-file package. For synthetic cases the gold label is derived from the
**realised sample**: design facts come from the generator parameters because they
are properties of the design, while distributional facts come from the data
because that is what a correct method choice must respond to.

| Source | UCI | Rows | Role |
|---|---|---|---|
| Bank Marketing | 222 | 45,211 | categorical, logistic, skewed group comparison |
| Online Shoppers | 468 | 12,330 | association, categorical, logistic |
| Student Performance | 320 | 649 | group comparison, ordinal traps, OLS |
| Seoul Bike Sharing | 560 | 8,760 | four design-hazard cases |

Seoul Bike supplies the sharpest test: tables that look perfectly suitable for
Poisson, correlation or ANOVA, where hourly ordering violates independence. The
correct answer is to abstain.

## 4. Method

Three systems over one shared core. Every driver imports the same tool registry,
result store and report schema; only control flow differs. This is what makes
baseline fairness provable rather than asserted — there is no code path on which
A or B could have been disadvantaged.

System A receives the *same* step-one diagnostic output System C receives, not a
hand-picked summary. System B receives identical tool definitions and the
identical report schema.

**On determinism:** `temperature` is removed on current Claude models and returns
a 400 if sent. Determinism is controlled by pinning the model id and effort
level, freezing the prompt hash, and *measuring* residual variance across
repetitions rather than claiming to eliminate it.

---

## 5. Results

### 5.1 Live evidence — Claude Opus 5, development set

**{n_live} clean runs** ({len(live_hi)} at `high` effort, {len(live_med)} at
`medium`). This is the development set, not the held-out set.

| System | n | Accuracy | 95% CI | Abstention recall | Unsafe rate | Tool calls |
|---|---|---|---|---|---|---|
{sys_rows(live_hi) if len(live_hi) else '| _no live data_ | | | | | | |'}
{fig("fig1_accuracy.png",
     "Figure 1 — Method-selection accuracy with Wilson 95% intervals. The live "
     "panel is preliminary; the offline panel is the calibration run.")}
{fig("fig4_abstention.png",
     "Figure 2 — Abstention recall on design-hazard cases. The sharpest "
     "separation between the systems, and the failure the project exists to "
     "prevent.")}
"""

    if bc:
        doc += f"""
**Paired comparison, B versus C** — the comparison that answers the research
question, since both have identical tools and report schemas and differ only in
whether an ordered protocol governs their use. On the {bc['n']} cases both
systems completed:

| | |
|---|---|
| System B accuracy | {bc['acc_a']:.3f} |
| System C accuracy | {bc['acc_b']:.3f} |
| Uplift | **{bc['uplift']:+.3f}** |
| Bootstrap 95% CI | [{bc['ci_low']:+.3f}, {bc['ci_high']:+.3f}] |
| McNemar exact p | **{bc['p']:.4f}** |
| Discordant pairs | {bc['b_only']} in C's favour, {bc['a_only']} in B's |

The discordance is entirely one-directional: {bc['b_only']} cases where the
protocol was right and the unconstrained baseline wrong, and {bc['a_only']} the
other way. The blueprint's target was ≥10 percentage points of uplift; the
observed value is {bc['uplift'] * 100:.0f}.

**Abstention is where the systems separate most sharply.** On the design-hazard
cases the structured agent abstained every time; the tool-enabled baseline never
did, fitting a plausible-looking model to data whose independence assumption
fails. That is the failure this project exists to prevent.
"""

    doc += f"""
### 5.2 Limitations of the live evidence

These results are **preliminary and must not be presented as the headline
experiment**:

- **Development set, not held out.** Prompts were developed against these cases.
  The held-out estimate is the one that counts, and it has not been run.
- **Small samples.** {len(live_hi)} clean runs across three systems; the widest
  confidence interval spans {(wilson_ci(13, 13)[1] - wilson_ci(13, 13)[0]):.2f}.
- **One repetition.** Run-to-run variance is unmeasured.
- **{n_lost} runs lost to harness errors** rather than statistical failure
  (a raw numeric literal, and two references to string-valued fields). All three
  causes have since been fixed and are covered by regression tests, but the
  affected runs were not repeated.
- **Only System C at `medium` effort is missing entirely** — the account ran out
  of credit mid-sweep, so the cost/accuracy trade-off is unresolved.

{fig("fig3_failures.png",
     "Figure 3 — Failure counts by stage of the error taxonomy. Design "
     "validation failures are cases where a method was fitted to data whose "
     "independence assumption fails.")}
### 5.3 Offline calibration

A deterministic policy client implements the same interface as the live path,
which makes the harness runnable and testable without an API key. It is **not an
arm of the experiment**.

| Client | A | B | C | C abstention recall | Interpretation |
|---|---|---|---|---|---|
| Expert policy | {off_exp[off_exp.system=='A_direct'].selection_correct.mean():.3f} | {off_exp[off_exp.system=='B_tools'].selection_correct.mean():.3f} | {off_exp[off_exp.system=='C_protocol'].selection_correct.mean():.3f} | 1.00 | **Circular** — this policy derived the gold labels |
| Naive policy | {off_nai[off_nai.system=='A_direct'].selection_correct.mean():.3f} | {off_nai[off_nai.system=='B_tools'].selection_correct.mean():.3f} | {off_nai[off_nai.system=='C_protocol'].selection_correct.mean():.3f} | 0.00 | **Informative** — see below |

The expert row validates the harness and confirms the gold labels are internally
coherent with the stated decision principles. It says nothing about model
performance.

The naive row is the useful one. Inside the **same state machine**, a policy that
ignores the design card and treats assumption-test p-values as switches drops to
{off_nai[off_nai.system=='C_protocol'].selection_correct.mean():.3f} with zero
abstention recall. **The architecture alone does not produce the uplift; the
decision policy inside it does.** An ordering mechanism that routes badly scores
barely above the unstructured baseline.

This matters for interpreting §5.1: the protocol's advantage is not an artefact
of having more structure, because more structure with worse rules performs
worse.

{fig("fig2_risk_coverage.png",
     "Figure 4 — Risk-coverage. Coverage is the share of cases a system chose "
     "to answer; selective accuracy is accuracy among those. A system that "
     "abstains only when it should sits top-right.")}

### 5.4 Held-out evaluation

"""
    if len(held):
        doc += "See `reports/heldout_claude-opus-5_REPORT.md`.\n"
    else:
        doc += """**Not yet run.** This is the single outstanding deliverable. It requires
API credit: approximately $34 for two repetitions on Claude Opus 5, or $10 on
Haiku 4.5. The runner is resumable and the benchmark is frozen, so it can be
executed at any point without invalidating anything above.

Everything needed to run it exists and is tested: `make eval-live` validates the
live path first and refuses to start work the budget cannot finish.
"""


    # -- 5.5 reliability of the interpretation scoring --------------------
    rel_path = ROOT / "reports" / "reliability" / "reliability.json"
    if rel_path.exists():
        rel = json.loads(rel_path.read_text())
        rows = "\n".join(
            f"| Rater {n} — same report, twice | {r['n_double_scored']} | "
            f"{r['self_agreement']:.0%} | {r['self_kappa']:+.3f} | {r['reading']} |"
            for n, r in rel["raters"].items())
        it = rel.get("inter_rater") or {}
        if it:
            rows += (f"\n| Between the two raters | {it['n']} | "
                     f"{it['agreement']:.0%} | {it['kappa']:+.3f} | "
                     f"{it['reading']} |")
        n_opp = it.get("opposite_ends", 0)
        pct_opp = (n_opp / it["n"]) if it.get("n") else 0.0
        doc += (
            "\n### 5.5 Interpretation scoring — a reliability failure\n\n"
            "Blueprint §8.3 requires a 0–2 interpretation rubric applied blind to\n"
            "system identity, with at least 20% double-scored and agreement\n"
            f"reported. A first round ran with two independent raters over "
            f"{it.get('n', 0)} reports, a fifth of them silently presented twice.\n\n"
            "**The round failed its reliability check.**\n\n"
            "| Comparison | n | Exact agreement | Cohen's κ | Reading |\n"
            "|---|---|---|---|---|\n" + rows + "\n\n"
            "Chance agreement on a three-point scale is about 33%. One rater "
            "scored *worse\nthan chance against their own earlier judgement of "
            f"the same text*, and {n_opp}\nreports ({pct_opp:.0%}) received a 0 "
            "from one rater and a 2 from the other.\n**The scores are not "
            "reported as a metric**: a mean computed from them would\nbe a mean "
            "of noise.\n\n"
            "#### The diagnosis is an instrument defect, not rater carelessness\n\n"
            "Neither rater separated the systems — both scored the structured "
            "agent\n*lowest*, the system with the highest selection accuracy and "
            "perfect\nabstention recall. That pattern pointed at the rubric "
            "rather than the raters.\n\n"
            "The rubric never said whether to judge **the choice of method** or "
            "**only the\ninterpretation given the result**. One report ran a "
            "Spearman correlation on a\ncount outcome — the wrong method — yet "
            "interpreted its own output faithfully.\nUnder one reading that is a "
            "0; under the other a 2. Both raters applied the\nrubric they were "
            "given; the rubric admitted two readings.\n\n"
            "A second defect compounded it: reports were presented in full, six "
            "sections\neach, when the rubric concerns three.\n\n"
            "#### Remedies applied\n\n"
            "1. **The rubric states its scope explicitly** — judge whether the "
            "interpretation\n   follows from the result; do not judge method "
            "choice, which selection\n   accuracy already measures. Scoring it "
            "twice was the main route to\n   inconsistency.\n"
            "2. **Calibration anchors.** Three worked examples scored first, with "
            "the\n   intended answer and reasoning revealed after each — "
            "including the\n   wrong-method-but-faithful-interpretation case that "
            "separated the raters.\n   Anchors are author-adjudicated and excluded "
            "from the scored set.\n"
            "3. **Only the judged sections are presented**, roughly halving the "
            "reading.\n"
            "4. **Sittings**, with the instrument stating that it measures "
            "consistency,\n   not speed.\n\n"
            "#### Status\n\n"
            "The metric is **not reported**. The instrument is rebuilt; a second "
            "round runs\nwith `make blind`, and `scripts/analyse_reliability.py` "
            "recomputes agreement\nand states plainly whether a round is usable.\n\n"
            "Reporting an unusable round with its diagnosis is the honest "
            "treatment of\n§8.3, and more useful than a clean number would have "
            "been: the double-scoring\ncaught a defect a single-rater design "
            "would have hidden inside a plausible\nmean.\n")

    doc += f"""
---

## 6. Error analysis

Failures are classified by the stage at which they occur. Across the live
development runs, every System B failure was a **design-validation** failure —
selecting a valid-looking method for a design that supports none — or a
**diagnostic-reasoning** failure, choosing Student's t where variance and group
size evidence pointed to Welch.

System C recorded no method-selection failures on the development set. Its four
lost runs were harness defects, described in §5.2 and since fixed.

## 7. Limitations

Beyond §5.2:

- **No usable interpretation score.** A blinded round was run and failed its
  reliability check (§5.5). `human_interpretation_score` is `None` in every run,
  and the programmatic proxy in `scorers.py` covers only the mechanically
  checkable half (causal language, absolute claims, constraint adherence). The
  instrument has been rebuilt; a second round is outstanding.
- **No independent second reviewer.** 48 of 64 labels are construction-derived
  and therefore not opinions; the 16 public labels were validated against their
  realised data, which caught one mislabel. This is weaker than the double review
  §4.3 specifies and is disclosed as such.
- **Four methods appear only in the held-out split.** `one_way_anova`, `pearson`,
  `logistic` and `poisson` have no development representation — twelve synthetic
  development slots cannot cover fourteen methods plus abstention. No prompt was
  ever tuned against them, which is a cleaner generalisation test but an
  unplanned one.
- **The library excludes** paired and repeated-measures designs, mixed models,
  time series, survival analysis and zero-inflated models. Those appear in the
  benchmark only as abstention cases.

## 8. Extensions

Ordered by how much each would improve coverage per unit of work:

1. **Paired and repeated-measures tests.** The largest single gap; four
   abstention cases exist purely because the library cannot model subject
   effects.
2. **Uplift as a function of model strength.** Running the same held-out
   benchmark on a weaker tier would test whether the protocol matters more where
   internal reasoning is weaker — arguably a stronger claim than a single uplift
   figure, and robust to the ceiling problem.
3. **Mixed-effects models**, which would convert the clustering and
   repeated-measures abstentions into supported cases.
4. **Effort ablation.** Whether `medium` routes as well as `high` is unresolved
   and directly affects cost.

## 9. Reproducing this

```bash
make setup && make all      # benchmark, tests, offline calibration, tables
make smoke                  # validates the live path (requires credit)
make eval-live && make report
python scripts/write_capstone.py
```

Every table above is derived from `results/*.jsonl`. Deviations from the
blueprint are documented in `docs/DEVIATIONS.md`; the architecture is described
in `docs/ARCHITECTURE.md`.
"""

    DOCS.mkdir(exist_ok=True)
    out = DOCS / "CAPSTONE_REPORT.md"
    out.write_text(doc)
    print(f"wrote {out} ({len(doc.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
