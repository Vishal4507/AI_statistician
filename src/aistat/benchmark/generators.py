"""Synthetic case generators (blueprint section 4.1).

Review finding F-B1: gold labels are *derived from the generating parameters*,
never assigned by post-hoc judgement.  If a generator was asked for unequal
variances with unbalanced n, then Welch is correct by construction and the
accepted set follows mechanically.  This is what makes 48 of the 64 labels
defensible without a second human reviewer.

Each generator returns ``(dataframe, design_card_dict, gold_dict)``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import skew as stats_skew

from aistat.schemas.core import ABSTAIN

# --------------------------------------------------------------------------
# Design-card helpers
# --------------------------------------------------------------------------


def _card(unit: str, population: str, *, repeated: str | None = None,
          time: str | None = None, pairing: bool = False,
          clustering: str | None = None, randomized: bool = False) -> dict:
    return {
        "observational_unit": unit, "sampling_unit": unit,
        "repeated_id_column": repeated, "time_column": time,
        "pairing": pairing, "clustering_column": clustering,
        "randomized": randomized, "intended_population": population,
        "known_missingness": None,
    }


def _gold(primary: str, accepted: list[str], checks: list[str],
          rationale: str, *, reason: str | None = None,
          hazards: list[str] | None = None,
          constraints: list[str] | None = None) -> dict:
    return {
        "primary_method": primary,
        "accepted_methods": accepted,
        "required_checks": checks,
        "abstain_reason": reason,
        "expected_hazards": hazards or [],
        "interpretation_constraints": constraints or [],
        "rationale": rationale,
    }


# ==========================================================================
# Family 1 -- two independent groups, continuous outcome
# ==========================================================================


def two_group(seed: int, *, shape: str = "normal", var_ratio: float = 1.0,
              n1: int = 60, n2: int = 60, effect: float = 0.5,
              estimand: str = "mean_difference", contaminate: float = 0.0,
              outcome: str = "value", group: str = "arm",
              labels: tuple[str, str] = ("control", "treatment"),
              unit: str = "participant",
              population: str = "enrolled participants",
              randomized: bool = False) -> tuple[pd.DataFrame, dict, dict]:
    rng = np.random.default_rng(seed)
    sd1 = 1.0
    sd2 = float(np.sqrt(var_ratio))

    if shape == "normal":
        a = rng.normal(0.0, sd1, n1)
        b = rng.normal(effect, sd2, n2)
    elif shape == "lognormal":                       # right-skewed
        a = rng.lognormal(0.0, 0.75, n1)
        b = rng.lognormal(effect * 0.75, 0.75 * sd2, n2)
    elif shape == "gamma":
        # Shape 1.2 gives a population skew near 1.8; shape 2 is too symmetric
        # to be a genuine rank-test case.
        a = rng.gamma(1.2, 1.0, n1)
        b = rng.gamma(1.2, 1.0 + effect, n2)
    else:
        raise ValueError(f"unknown shape {shape!r}")

    if contaminate > 0:                              # influential outliers
        k = max(1, int(contaminate * n2))
        idx = rng.choice(n2, k, replace=False)
        b[idx] += rng.normal(6.0, 1.0, k) * sd2

    df = pd.DataFrame({
        outcome: np.r_[a, b],
        group: [labels[0]] * n1 + [labels[1]] * n2,
    }).sample(frac=1.0, random_state=seed).reset_index(drop=True)

    # Gold is derived from the REALISED sample, not the requested parameters.
    # Design facts (independence, randomisation) come from the parameters
    # because they are properties of the design; distributional facts come from
    # the data because that is what a correct method choice must respond to.
    # See review finding F-B1: mechanically defensible, but honest about
    # sampling variation.
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    realized_vr = max(va, vb) / min(va, vb) if min(va, vb) > 0 else float("inf")
    realized_skew = max(abs(float(stats_skew(a))), abs(float(stats_skew(b))))
    imbalanced = max(n1, n2) / min(n1, n2) >= 1.5
    unequal = realized_vr >= 2.0
    skewed = realized_skew > 1.5 or contaminate > 0

    checks = ["independence", "group_sizes", "variance_structure", "skew_and_outliers"]

    if estimand == "distributional_shift" and skewed:
        g = _gold("mann_whitney", ["mann_whitney"], checks,
                  f"Realised max |skew| {realized_skew:.2f} with a distributional-"
                  "shift estimand; the rank test targets stochastic ordering.",
                  constraints=["describe stochastic ordering, not medians, "
                               "unless shapes match"])
    elif unequal or imbalanced:
        acc = ["welch_t"] + (["mann_whitney"] if skewed else [])
        g = _gold("welch_t", acc, checks,
                  f"Realised variance ratio {realized_vr:.2f} with n {n1}/{n2}; "
                  "Welch is the default without an affirmative equal-variance "
                  "justification.")
    elif skewed:
        g = _gold("welch_t", ["welch_t", "mann_whitney"], checks,
                  f"Realised skew {realized_skew:.2f} but the estimand is a mean "
                  "difference; Welch is robust and Mann-Whitney is defensible.")
    else:
        g = _gold("student_t", ["student_t", "welch_t"], checks,
                  f"Realised variance ratio {realized_vr:.2f} with balanced groups "
                  "and a mean-difference estimand; Student is justified and Welch "
                  "is never wrong.")

    if not randomized:
        g["interpretation_constraints"].append("observational groups: no causal claim")
    return df, _card(unit, population, randomized=randomized), g


# ==========================================================================
# Family 2 -- three or more independent groups
# ==========================================================================


def multi_group(seed: int, *, k: int = 3, shape: str = "normal",
                var_ratios: list[float] | None = None,
                ns: list[int] | None = None, effects: list[float] | None = None,
                outcome: str = "value", group: str = "segment",
                unit: str = "customer", population: str = "active customers",
                randomized: bool = False) -> tuple[pd.DataFrame, dict, dict]:
    rng = np.random.default_rng(seed)
    ns = ns or [50] * k
    var_ratios = var_ratios or [1.0] * k
    effects = effects or [0.0, 0.45, 0.9, 1.3][:k]
    names = [f"tier_{chr(97 + i)}" for i in range(k)]

    vals, labs = [], []
    for i in range(k):
        sd = float(np.sqrt(var_ratios[i]))
        if shape == "normal":
            v = rng.normal(effects[i], sd, ns[i])
        else:
            v = rng.lognormal(effects[i] * 0.7, 0.7 * sd, ns[i])
        vals.append(v); labs += [names[i]] * ns[i]

    df = pd.DataFrame({outcome: np.concatenate(vals), group: labs}) \
        .sample(frac=1.0, random_state=seed).reset_index(drop=True)

    # Realised-sample derivation, as in two_group above.
    rv = [float(np.var(v, ddof=1)) for v in vals]
    realized_vr = max(rv) / min(rv) if min(rv) > 0 else float("inf")
    realized_skew = max(abs(float(stats_skew(v))) for v in vals)
    unequal = realized_vr >= 2.0
    imbalanced = max(ns) / min(ns) >= 1.5
    skewed = realized_skew > 1.5
    checks = ["independence", "n_groups", "variance_balance", "skew_and_outliers"]

    if skewed:
        acc = ["kruskal_wallis"] + (["welch_anova"] if unequal or imbalanced else [])
        g = _gold("kruskal_wallis", acc, checks,
                  f"Realised max |skew| {realized_skew:.2f} across groups; omnibus "
                  "rank test.",
                  constraints=["stochastic dominance, not median equality"])
    elif unequal or imbalanced:
        g = _gold("welch_anova", ["welch_anova"], checks,
                  f"Realised variance ratio {realized_vr:.2f} across {k} groups "
                  f"with n {ns}; Welch ANOVA.")
    else:
        g = _gold("one_way_anova", ["one_way_anova", "welch_anova"], checks,
                  f"Realised variance ratio {realized_vr:.2f} with balanced groups; "
                  "ordinary ANOVA is justified and Welch remains defensible.")
    if not randomized:
        g["interpretation_constraints"].append("observational groups: no causal claim")
    return df, _card(unit, population, randomized=randomized), g


# ==========================================================================
# Family 3 -- categorical association
# ==========================================================================


def categorical(seed: int, *, n: int = 400, shape: tuple[int, int] = (2, 3),
                strength: float = 0.25, sparse: bool = False,
                var1: str = "channel", var2: str = "outcome",
                unit: str = "enquiry", population: str = "inbound enquiries"
                ) -> tuple[pd.DataFrame, dict, dict]:
    rng = np.random.default_rng(seed)
    r, c = shape
    if sparse:
        n = min(n, 28)                              # forces low expected counts
        r = c = 2
    row_lab = [f"{var1}_{i+1}" for i in range(r)]
    col_lab = [f"{var2}_{j+1}" for j in range(c)]

    base = np.full((r, c), 1.0 / c)
    for i in range(r):                              # tilt each row
        base[i] = np.roll(base[i], i)
        base[i, i % c] += strength
        base[i] = np.clip(base[i], 0.02, None); base[i] /= base[i].sum()

    rows = rng.choice(r, n, p=np.full(r, 1.0 / r))
    cols = np.array([rng.choice(c, p=base[i]) for i in rows])
    df = pd.DataFrame({var1: [row_lab[i] for i in rows],
                       var2: [col_lab[j] for j in cols]})

    checks = ["independent_counts", "table_dimension", "expected_cell_counts"]
    if sparse:
        g = _gold("fisher_exact", ["fisher_exact"], checks,
                  f"2x2 table with n={n}; expected counts fall below 5, so the "
                  "chi-square approximation is not eligible.",
                  constraints=["association only, not individual risk"])
    else:
        g = _gold("chi_square", ["chi_square"], checks,
                  f"{r}x{c} table with adequate expected counts.",
                  constraints=["association only, not individual risk or causation"])
    return df, _card(unit, population), g


# ==========================================================================
# Family 4 -- continuous / ordinal association
# ==========================================================================


def association(seed: int, *, n: int = 120, form: str = "linear",
                rho: float = 0.6, contaminate: float = 0.0,
                ordinal_levels: int = 0, x: str = "x_measure",
                y: str = "y_measure", unit: str = "record",
                population: str = "sampled records"
                ) -> tuple[pd.DataFrame, dict, dict]:
    rng = np.random.default_rng(seed)
    xv = rng.normal(0.0, 1.0, n)

    if form == "linear":
        yv = rho * xv + np.sqrt(max(1 - rho**2, 0.01)) * rng.normal(0, 1, n)
    elif form == "monotone_nonlinear":
        yv = np.exp(1.6 * xv) + rng.normal(0, 0.4, n)      # monotone, curved
    elif form == "restricted":
        keep = np.abs(xv) < 0.6                            # range restriction
        xv = xv[keep]; n = len(xv)
        yv = rho * xv + np.sqrt(max(1 - rho**2, 0.01)) * rng.normal(0, 1, n)
    else:
        raise ValueError(form)

    if contaminate > 0:
        k = max(2, int(contaminate * n))
        idx = rng.choice(n, k, replace=False)
        xv[idx] += rng.normal(5.0, 0.6, k)
        yv[idx] -= rng.normal(5.0, 0.6, k)                 # high-leverage points

    if ordinal_levels:
        yv = pd.qcut(yv, ordinal_levels, labels=False, duplicates="drop") \
             .astype(float) + 1.0

    df = pd.DataFrame({x: xv, y: yv})
    checks = ["scale", "linearity_or_monotonicity", "influential_points", "range"]

    if ordinal_levels:
        g = _gold("spearman", ["spearman"], checks,
                  f"Outcome is ordinal with {ordinal_levels} levels; rank "
                  "correlation is the appropriate measure.",
                  constraints=["monotone association only"])
    elif form == "monotone_nonlinear":
        g = _gold("spearman", ["spearman"], checks,
                  "Relationship is monotone but distinctly nonlinear; Pearson "
                  "would understate a strong monotone association.",
                  constraints=["monotone, not linear, association"])
    elif contaminate > 0:
        g = _gold("spearman", ["spearman"], checks,
                  "Influential contaminating points dominate the product-moment "
                  "correlation; the rank measure is stable.",
                  constraints=["report influence sensitivity"])
    else:
        g = _gold("pearson", ["pearson", "spearman"], checks,
                  "Roughly linear relationship without dominant points; Pearson "
                  "is appropriate and Spearman is defensible.",
                  constraints=["association, not causation"])
    return df, _card(unit, population), g


# ==========================================================================
# Family 5 -- regression with a known data-generating process
# ==========================================================================


def regression(seed: int, *, kind: str = "ols", n: int = 250,
               betas: list[float] | None = None, noise: float = 1.0,
               heteroscedastic: bool = False, collinear: bool = False,
               separation: bool = False, outcome: str = "outcome",
               unit: str = "observation", population: str = "sampled units"
               ) -> tuple[pd.DataFrame, dict, dict]:
    rng = np.random.default_rng(seed)
    betas = betas or [1.5, -0.8]
    x1 = rng.normal(0, 1, n)
    x2 = (0.95 * x1 + 0.1 * rng.normal(0, 1, n)) if collinear else rng.normal(0, 1, n)
    lin = 0.5 + betas[0] * x1 + betas[1] * x2
    cols = {"predictor_a": x1, "predictor_b": x2}
    checks = ["outcome_scale", "design", "functional_form"]

    if kind == "ols":
        scale = noise * (1 + 1.4 * np.abs(x1)) if heteroscedastic else noise
        cols[outcome] = lin + rng.normal(0, 1, n) * scale
        checks += ["residual_pattern", "influence", "collinearity"]
        g = _gold("ols", ["ols"], checks,
                  f"Continuous outcome generated by a linear model with betas "
                  f"{betas}" + (", heteroscedastic errors" if heteroscedastic else "")
                  + (", collinear predictors" if collinear else "") + ".",
                  constraints=["coefficients are conditional on included variables"])
    elif kind == "logistic":
        if separation:
            cols[outcome] = (x1 > 0).astype(int)          # perfectly separable
        else:
            cols[outcome] = (rng.random(n) < 1 / (1 + np.exp(-lin))).astype(int)
        checks += ["binary_coding", "events_per_parameter", "separation", "collinearity"]
        g = _gold("logistic", ["logistic"], checks,
                  "Binary outcome generated through a logit link"
                  + (" with complete separation" if separation else "") + ".",
                  constraints=["report odds ratios, not probability changes"])
    else:
        raise ValueError(kind)

    df = pd.DataFrame(cols)
    return df, _card(unit, population), g


def count_model(seed: int, *, n: int = 300, overdispersed: bool = False,
                with_exposure: bool = False, beta: float = 0.45,
                intercept: float = 0.8, outcome: str = "events",
                unit: str = "site", population: str = "monitored sites"
                ) -> tuple[pd.DataFrame, dict, dict]:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, n)
    cols = {"predictor_a": x1}
    log_mu = intercept + beta * x1

    if with_exposure:
        exposure = rng.uniform(0.5, 4.0, n)
        cols["observation_days"] = exposure
        log_mu = log_mu + np.log(exposure)

    mu = np.exp(log_mu)
    if overdispersed:
        r = 1.6                                        # NB2 shape
        y = rng.negative_binomial(r, r / (r + mu))
    else:
        y = rng.poisson(mu)
    cols[outcome] = y
    df = pd.DataFrame(cols)

    checks = ["count_scale", "independence", "conditional_dispersion", "excess_zeros"]
    if with_exposure:
        checks.append("exposure")
    if overdispersed:
        g = _gold("negative_binomial", ["negative_binomial"], checks,
                  "Counts generated from a negative-binomial process; conditional "
                  "dispersion exceeds the Poisson mean-variance identity.",
                  constraints=["report incidence-rate ratios and the exposure basis"])
    else:
        g = _gold("poisson", ["poisson", "negative_binomial"], checks,
                  "Equidispersed counts from a log-link Poisson process; NB "
                  "converges to Poisson and remains defensible.",
                  constraints=["report incidence-rate ratios"])
    return df, _card(unit, population), g


# ==========================================================================
# Family 6 -- abstention (correct answer is outside the 14-method library)
# ==========================================================================


def abstention(seed: int, *, kind: str, n: int = 200,
               outcome: str = "value") -> tuple[pd.DataFrame, dict, dict]:
    rng = np.random.default_rng(seed)
    checks = ["design_validity"]

    if kind == "repeated_measures":
        n_subj, n_rep = n // 4, 4
        subj = np.repeat([f"S{i:03d}" for i in range(n_subj)], n_rep)
        re = np.repeat(rng.normal(0, 1.4, n_subj), n_rep)
        cond = np.tile(["before", "after"], n_subj * n_rep // 2)
        val = re + np.where(cond == "after", 0.6, 0.0) + rng.normal(0, 0.6, n_subj * n_rep)
        df = pd.DataFrame({"subject_id": subj, "condition": cond, outcome: val})
        card = _card("measurement", "enrolled subjects", repeated="subject_id")
        g = _gold(ABSTAIN, [ABSTAIN], checks,
                  "Each subject contributes four measurements; observations are "
                  "not independent and no in-scope method models subject effects.",
                  reason="repeated_measures", hazards=["repeated_measures"])

    elif kind == "serial_dependence":
        e = rng.normal(0, 1, n); s = np.zeros(n)
        for t in range(1, n):
            s[t] = 0.85 * s[t - 1] + e[t]              # AR(1)
        df = pd.DataFrame({
            "hour_index": np.arange(n),
            "temperature": 15 + 0.02 * np.arange(n) + rng.normal(0, 2, n),
            outcome: 20 + 4 * s,
        })
        card = _card("hourly observation", "monitored period", time="hour_index")
        g = _gold(ABSTAIN, [ABSTAIN], checks,
                  "Strong AR(1) serial dependence; the library contains no "
                  "time-series model and independence is violated.",
                  reason="serial_dependence", hazards=["serial_dependence"])

    elif kind == "zero_inflated":
        x1 = rng.normal(0, 1, n)
        mu = np.exp(0.9 + 0.4 * x1)
        y = rng.poisson(mu)
        y[rng.random(n) < 0.45] = 0                    # structural zeros
        df = pd.DataFrame({"predictor_a": x1, "claim_count": y})
        card = _card("policy", "policyholders")
        g = _gold(ABSTAIN, [ABSTAIN], checks,
                  "Zero inflation from a separate structural process; neither "
                  "Poisson nor negative binomial is adequate.",
                  reason="zero_inflation")

    elif kind == "censored":
        true = rng.exponential(20.0, n)
        cap = 30.0
        df = pd.DataFrame({
            "group": rng.choice(["a", "b"], n),
            "followup_days": np.minimum(true, cap),
            "was_censored": (true > cap).astype(int),
        })
        card = _card("subject", "followed cohort")
        g = _gold(ABSTAIN, [ABSTAIN], checks,
                  f"{int((true > cap).mean() * 100)}% of durations are right-censored; "
                  "survival methods are outside the supported library.",
                  reason="censoring", hazards=["unsupported_outcome"])

    elif kind == "clustered":
        n_clust = 20
        cl = np.repeat([f"clinic_{i}" for i in range(n_clust)], n // n_clust)
        re = np.repeat(rng.normal(0, 1.5, n_clust), n // n_clust)
        arm = np.tile(["usual", "enhanced"], len(cl) // 2)
        val = re + np.where(arm == "enhanced", 0.5, 0) + rng.normal(0, 0.7, len(cl))
        df = pd.DataFrame({"clinic_id": cl, "arm": arm, outcome: val})
        card = _card("patient", "clinic patients", clustering="clinic_id")
        g = _gold(ABSTAIN, [ABSTAIN], checks,
                  "Patients are nested in clinics with substantial between-clinic "
                  "variance; clustering violates independence.",
                  reason="clustering", hazards=["clustering"])

    elif kind == "missing_design_facts":
        a = rng.normal(0, 1, n // 2); b = rng.normal(0.5, 1, n // 2)
        df = pd.DataFrame({outcome: np.r_[a, b],
                           "reading_id": [f"R{i:04d}" for i in range(n)],
                           "arm": ["a"] * (n // 2) + ["b"] * (n // 2)})
        card = _card("unknown", "unspecified")
        card.update(observational_unit="unknown", sampling_unit="unknown",
                    pairing=None, randomized=None)
        g = _gold(ABSTAIN, [ABSTAIN], checks,
                  "The design card does not state the observational unit or "
                  "whether readings repeat; independence cannot be established.",
                  reason="missing_design_facts", hazards=["missing_design_facts"])

    elif kind == "paired":
        base = rng.normal(50, 8, n // 2)
        df = pd.DataFrame({
            "participant_id": np.repeat([f"P{i:03d}" for i in range(n // 2)], 2),
            "timepoint": np.tile(["pre", "post"], n // 2),
            outcome: np.ravel(np.c_[base, base + rng.normal(3, 2, n // 2)]),
        })
        card = _card("measurement", "enrolled participants",
                     repeated="participant_id", pairing=True)
        g = _gold(ABSTAIN, [ABSTAIN], checks,
                  "Pre/post measurements on the same participant are paired; "
                  "the library contains only independent-sample methods.",
                  reason="pairing", hazards=["pairing", "repeated_measures"])
    else:
        raise ValueError(f"unknown abstention kind {kind!r}")

    return df, card, g


GENERATORS = {
    "two_group": two_group,
    "multi_group": multi_group,
    "categorical": categorical,
    "association": association,
    "regression": regression,
    "count_model": count_model,
    "abstention": abstention,
}
