"""The statistical decision policy (blueprint section 2).

Encoded once, used two ways: as the routing rules the structured agent's prompt
describes, and as the deterministic offline stand-in in ``RuleBasedClient``.

Decision principles, in the order the blueprint states them:

1. Design validity precedes distribution checks.  Dependence, pairing,
   clustering and time order invalidate every in-scope choice.
2. Normality tests are evidence, not switches.
3. Welch is the default; Student needs an affirmative equal-variance case.
4. Rank tests describe stochastic ordering, not medians.
5. Pearson for linear without dominant points, Spearman for monotone/ordinal.
6. Poisson vs NB is decided from *conditional* dispersion.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from aistat.schemas.core import ABSTAIN


@dataclass
class TaskShape:
    kind: str                       # two_group | multi_group | categorical |
                                    # association | regression_* | unknown
    outcome: str | None = None
    group: str | None = None
    var1: str | None = None
    var2: str | None = None
    predictors: tuple[str, ...] = ()
    exposure: str | None = None
    n_groups: int = 0
    outcome_scale: str = "continuous"


def infer_task(df: pd.DataFrame, roles: dict[str, str]) -> TaskShape:
    """Read the analytical task off the variable roles and the data."""
    outcome = next((c for c, r in roles.items() if r == "outcome" and c in df), None)
    group = next((c for c, r in roles.items() if r == "group" and c in df), None)
    preds = tuple(c for c, r in roles.items() if r == "predictor" and c in df)
    exposure = next((c for c, r in roles.items() if r == "exposure" and c in df), None)
    variables = [c for c, r in roles.items() if r == "variable" and c in df]

    def scale(col: str) -> str:
        s = df[col].dropna()
        if s.nunique() == 2:
            return "binary"                     # two levels is binary either way
        if not pd.api.types.is_numeric_dtype(s):
            return "nominal"
        if pd.api.types.is_integer_dtype(s) and (s >= 0).all() and s.nunique() > 2:
            if s.nunique() <= 8:
                return "ordinal"
            # A bounded, roughly symmetric integer score (a grade, a rating) is
            # not a count.  Counts arise from a rate process and are right
            # skewed; requiring that keeps the ordinal-versus-count trap honest
            # without hard-coding variable names.
            from scipy import stats as _st
            return "count" if float(_st.skew(s.astype(float))) > 0.5 else "ordinal"
        return "continuous"

    if len(variables) >= 2:
        a, b = variables[0], variables[1]
        if scale(a) in ("nominal", "binary") and scale(b) in ("nominal", "binary"):
            return TaskShape("categorical", var1=a, var2=b)
        return TaskShape("association", var1=a, var2=b)

    if outcome and group and not preds:
        k = int(df[group].dropna().nunique())
        return TaskShape("two_group" if k == 2 else "multi_group",
                         outcome=outcome, group=group, n_groups=k,
                         outcome_scale=scale(outcome))
    if outcome and preds:
        sc = scale(outcome)
        kind = {"binary": "regression_binary", "count": "regression_count"} \
            .get(sc, "regression_continuous")
        return TaskShape(kind, outcome=outcome, predictors=preds,
                         exposure=exposure, outcome_scale=sc)
    if outcome and group:
        k = int(df[group].dropna().nunique())
        return TaskShape("two_group" if k == 2 else "multi_group",
                         outcome=outcome, group=group, n_groups=k,
                         outcome_scale=scale(outcome))
    return TaskShape("unknown")


# --------------------------------------------------------------------------
# Step 1 -- design validity (precedes everything)
# --------------------------------------------------------------------------


def design_verdict(card: dict, df: pd.DataFrame, task: TaskShape,
                   inspect: dict | None = None) -> tuple[str | None, str]:
    """Return ``(abstain_reason, explanation)`` or ``(None, "")``."""
    if card.get("pairing") is True:
        return "pairing", ("The design card declares paired observations; the "
                           "library contains only independent-sample methods.")
    if card.get("repeated_id_column"):
        col = card["repeated_id_column"]
        n_rep = df[col].nunique() if col in df else 0
        if col in df and n_rep < len(df):
            return "repeated_measures", (
                f"Column {col} identifies repeated units across the rows, so "
                "observations are not independent. No in-scope method models "
                "subject effects.")
    if card.get("clustering_column"):
        return "clustering", (
            f"Observations are nested within {card['clustering_column']}; "
            "clustering violates the independence assumption of every in-scope method.")
    if card.get("time_column"):
        return "serial_dependence", (
            f"Rows are ordered by {card['time_column']}. Consecutive observations "
            "of the same system are autocorrelated, so independence fails "
            "regardless of how well the variable types fit.")
    if card.get("observational_unit") in (None, "", "unknown") or \
       card.get("sampling_unit") in (None, "", "unknown"):
        return "missing_design_facts", (
            "The design card does not state the observational or sampling unit, "
            "so independence cannot be established. The correct behaviour when a "
            "material design fact is unknown is to ask or abstain.")

    # Data-visible hazards the card does not carry.
    censor_cols = [c for c in df.columns
                   if any(k in str(c).lower() for k in ("censor", "truncat"))]
    if censor_cols:
        return "censoring", (
            f"Column {censor_cols[0]} indicates censored observations; survival "
            "methods are outside the supported library.")

    if task.kind == "regression_count" and task.outcome in df:
        y = df[task.outcome].to_numpy(float)
        if y.mean() > 0:
            expected_zero = float(np.mean(np.exp(-np.maximum(y.mean(), 1e-9))))
            observed_zero = float((y == 0).mean())
            if observed_zero > expected_zero + 0.20 and observed_zero > 0.25:
                return "zero_inflation", (
                    "The observed proportion of zero counts greatly exceeds what a "
                    "Poisson process would produce; a separate structural zero "
                    "process is indicated and neither Poisson nor negative binomial "
                    "is adequate.")
    return None, ""


# --------------------------------------------------------------------------
# Step 2 -- method routing from diagnostic evidence
# --------------------------------------------------------------------------


def route(task: TaskShape, evidence: dict, question: str = "",
          naive: bool = False, slot_ids: dict[str, str] | None = None
          ) -> tuple[str, str, dict[str, str]]:
    """Return ``(method, rationale, rejected_alternatives)``.

    ``slot_ids`` maps an evidence slot to the tool call that produced it, so the
    rationale can cite diagnostics as ``{{ref}}`` templates rather than
    formatted literals.  The provenance contract covers decision prose too --
    not just results.
    """
    rej: dict[str, str] = {}
    q = question.lower()
    ids = slot_ids or {}

    def R(slot: str, key: str, fallback: str = "the observed value") -> str:
        cid = ids.get(slot)
        return f"{{{{{cid}.{key}}}}}" if cid else fallback

    if task.kind == "two_group":
        a = evidence.get("assumptions", {})
        s = evidence.get("summary", {})
        vr = a.get("variance_ratio", 1.0)
        ratio = a.get("group_size_ratio", 1.0)
        skew = s.get("max_abs_skew", 0.0)
        shift = any(w in q for w in ("skew", "shift", "systematically higher",
                                     "overall shift", "distribution"))
        if naive:                                   # p-value used as a switch
            if a.get("levene_p", 1.0) < 0.05:
                return "welch_t", "Levene test rejected equal variances.", rej
            return "student_t", "Levene test did not reject equal variances.", rej
        # Extreme skew is checked BEFORE the variance branch. Under a skew of
        # this magnitude the mean is not a meaningful summary of either group,
        # so a Welch correction to a comparison of means answers the wrong
        # question -- the variance ratio is beside the point. Found by
        # scripts/audit_labels.py on pub_shoppers_1 (skew 5.23).
        if skew > 2.5:
            rej["welch_t"] = ("the outcome is too skewed for a mean difference to "
                              "summarise either group")
            rej["student_t"] = "pronounced skew with influential observations"
            return ("mann_whitney",
                    f"Max absolute skew of {R('summary', 'max_abs_skew')} dominates "
                    "the mean; the rank test targets stochastic ordering.", rej)
        if skew > 1.5 and shift:
            rej["welch_t"] = "estimand is a distributional shift, not a mean difference"
            return ("mann_whitney",
                    f"Max absolute skew of {R('summary', 'max_abs_skew')} with a "
                    "shift estimand; the rank test targets stochastic ordering.", rej)
        if vr >= 2.0 or ratio >= 1.5:
            rej["student_t"] = (
                f"a variance ratio of {R('assumptions', 'variance_ratio')} and a size "
                f"ratio of {R('assumptions', 'group_size_ratio')} give no affirmative "
                "equal-variance justification")
            return ("welch_t",
                    f"Variance ratio {R('assumptions', 'variance_ratio')} with group "
                    f"size ratio {R('assumptions', 'group_size_ratio')}; Welch is the "
                    "default under either condition.", rej)
        rej["mann_whitney"] = "no skew or variance problem requiring a rank test"
        return ("student_t",
                f"Balanced groups with a size ratio of "
                f"{R('assumptions', 'group_size_ratio')} and comparable variances "
                f"(ratio {R('assumptions', 'variance_ratio')}); mean-difference "
                "estimand.", rej)

    if task.kind == "multi_group":
        a = evidence.get("assumptions", {})
        s = evidence.get("summary", {})
        vr = a.get("variance_ratio", 1.0)
        ratio = a.get("group_size_ratio", 1.0)
        skew = s.get("max_abs_skew", 0.0)
        if naive:
            if a.get("levene_p", 1.0) < 0.05:
                return "kruskal_wallis", "Levene rejected; used a rank test.", rej
            return "one_way_anova", "Levene did not reject.", rej
        if skew > 1.5:
            rej["one_way_anova"] = "skewed group distributions"
            return ("kruskal_wallis",
                    f"Max absolute skew of {R('summary', 'max_abs_skew')} across "
                    "groups.", rej)
        if vr >= 2.0 or ratio >= 1.5:
            rej["one_way_anova"] = (
                f"a variance ratio of {R('assumptions', 'variance_ratio')} and a size "
                f"ratio of {R('assumptions', 'group_size_ratio')}")
            return ("welch_anova",
                    f"Heteroscedastic (variance ratio "
                    f"{R('assumptions', 'variance_ratio')}) or unbalanced (size ratio "
                    f"{R('assumptions', 'group_size_ratio')}) groups.", rej)
        rej["welch_anova"] = "variances and group sizes are homogeneous"
        return "one_way_anova", "Homogeneous variances and balanced groups.", rej

    if task.kind == "categorical":
        c = evidence.get("contingency", {})
        if c.get("fisher_eligible") and not c.get("chi2_eligible", True):
            rej["chi_square"] = (
                f"a minimum expected count of {R('contingency', 'min_expected')} fails "
                "the approximation requirement")
            return ("fisher_exact",
                    f"A 2x2 table with {R('contingency', 'n_cells_expected_lt_5')} "
                    "cells below an expected count of 5.", rej)
        rej["fisher_exact"] = "expected counts are adequate and the table may exceed 2x2"
        return ("chi_square",
                f"A table of {R('contingency', 'n_rows')} by "
                f"{R('contingency', 'n_cols')} with a minimum expected count of "
                f"{R('contingency', 'min_expected')}.", rej)

    if task.kind == "association":
        a = evidence.get("association", {})
        pr, sr = abs(a.get("pearson_r", 0.0)), abs(a.get("spearman_rho", 0.0))
        gain = a.get("quadratic_gain", 0.0)
        y_unique = a.get("y_unique", 999)
        x_unique = a.get("x_unique", 999)
        loo = a.get("max_loo_r_change", 0.0)
        if naive:
            return "pearson", "Both variables are numeric.", rej
        # Either variable being coarsely ordinal is enough to prefer ranks.
        if min(x_unique, y_unique) <= 10:
            rej["pearson"] = ("one variable takes only a few ordered values, so the "
                              "product-moment coefficient is not appropriate")
            side = "y_unique" if y_unique <= x_unique else "x_unique"
            return ("spearman",
                    f"An ordered variable with only {R('association', side)} distinct "
                    "levels; rank correlation is the appropriate measure.", rej)
        if gain > 0.03 or sr > pr + 0.08:
            rej["pearson"] = ("relationship is monotone but nonlinear; the "
                              "product-moment coefficient understates it")
            return ("spearman",
                    f"A quadratic term adds {R('association', 'quadratic_gain')} to "
                    f"R-squared, and Spearman "
                    f"({R('association', 'spearman_rho')}) exceeds Pearson "
                    f"({R('association', 'pearson_r')}).", rej)
        if loo > 0.10:
            rej["pearson"] = ("single observations move the coefficient materially "
                              "under leave-one-out")
            return ("spearman",
                    f"Leave-one-out instability of "
                    f"{R('association', 'max_loo_r_change')}.", rej)
        rej["spearman"] = "relationship is approximately linear without dominant points"
        return ("pearson",
                f"Approximately linear (quadratic gain "
                f"{R('association', 'quadratic_gain')}) and stable under "
                f"leave-one-out ({R('association', 'max_loo_r_change')}).", rej)

    if task.kind == "regression_continuous":
        return "ols", "Continuous outcome modelled from several predictors.", rej
    if task.kind == "regression_binary":
        return "logistic", "Binary outcome; odds-ratio estimand.", rej
    if task.kind == "regression_count":
        d = evidence.get("dispersion", {})
        pear = d.get("pearson_dispersion")
        if naive:
            mv = d.get("marginal_var_mean_ratio", 1.0)
            if mv and mv > 1.5:
                return "negative_binomial", "Marginal variance exceeds the mean.", rej
            return "poisson", "Marginal variance is close to the mean.", rej
        if pear is not None and pear > 1.5:
            rej["poisson"] = ("the conditional Pearson dispersion exceeds the Poisson "
                              "mean-variance identity")
            return ("negative_binomial",
                    "Conditional dispersion after fitting Poisson exceeded the "
                    "mean-variance identity.", rej)
        rej["negative_binomial"] = ("conditional dispersion is close to 1, so the extra "
                                    "parameter is not warranted")
        return ("poisson",
                "Conditional Pearson dispersion after fitting is close to one, so the "
                "extra dispersion parameter is not warranted.", rej)

    return ABSTAIN, "The analytical task could not be identified from the inputs.", rej
