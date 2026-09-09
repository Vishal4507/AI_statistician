"""Effect sizes with confidence intervals (review finding F-B5).

Blueprint section 2 requires an effect size and interval on every method's
output, but SciPy and statsmodels do not supply most of these.  This module is
the missing layer.  Every function is checked against an independently
published value in tests/test_effects_reference.py.

References
----------
Hedges & Olkin (1985)      -- bias correction J, noncentral-t intervals
Kerby (2014)               -- rank-biserial as the simple difference of proportions
Kelley & Preacher (2012)   -- effect size definitions and interval logic
Fisher (1921)              -- z transform for correlation intervals
Haldane (1956)/Anscombe    -- 0.5 continuity correction for zero cells
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy import optimize, stats


@dataclass
class EffectSize:
    name: str
    value: float
    ci_low: float
    ci_high: float
    interpretation: str = ""
    conf_level: float = 0.95

    def to_dict(self) -> dict:
        return asdict(self)


def _magnitude(v: float, small: float, medium: float, large: float) -> str:
    a = abs(v)
    if a < small:
        return "negligible"
    if a < medium:
        return "small"
    if a < large:
        return "medium"
    return "large"


# --------------------------------------------------------------------------
# Standardised mean difference
# --------------------------------------------------------------------------


def hedges_g(x: np.ndarray, y: np.ndarray, conf: float = 0.95) -> EffectSize:
    """Hedges' g with a noncentral-t confidence interval.

    The interval is exact rather than the common normal approximation: it
    inverts the noncentral t distribution, finding the noncentrality parameters
    that place the observed t at the tail quantiles.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    n1, n2 = len(x), len(y)
    df = n1 + n2 - 2
    s_pooled = math.sqrt(
        ((n1 - 1) * x.var(ddof=1) + (n2 - 1) * y.var(ddof=1)) / df
    )
    if s_pooled == 0:
        return EffectSize("hedges_g", 0.0, 0.0, 0.0, "negligible", conf)

    d = (x.mean() - y.mean()) / s_pooled
    J = 1.0 - 3.0 / (4.0 * df - 1.0)          # small-sample bias correction
    g = d * J

    # Noncentral-t interval on the noncentrality parameter, rescaled to d.
    scale = math.sqrt(n1 * n2 / (n1 + n2))
    t_obs = d * scale
    alpha = 1.0 - conf

    def _solve(target: float, lo: float, hi: float) -> float:
        f = lambda ncp: stats.nct.cdf(t_obs, df, ncp) - target
        try:
            return optimize.brentq(f, lo, hi, xtol=1e-8)
        except (ValueError, RuntimeError):
            return float("nan")

    span = 10.0 + abs(t_obs) * 2.0
    ncp_hi = _solve(alpha / 2.0, t_obs - span, t_obs + span)
    ncp_lo = _solve(1.0 - alpha / 2.0, t_obs - span, t_obs + span)

    lo, hi = ncp_lo / scale * J, ncp_hi / scale * J
    if not (math.isfinite(lo) and math.isfinite(hi)):     # fall back to normal
        se = math.sqrt((n1 + n2) / (n1 * n2) + g**2 / (2 * df))
        z = stats.norm.ppf(1 - alpha / 2)
        lo, hi = g - z * se, g + z * se

    return EffectSize("hedges_g", g, min(lo, hi), max(lo, hi),
                      _magnitude(g, 0.2, 0.5, 0.8), conf)


def cohens_d_welch(x: np.ndarray, y: np.ndarray, conf: float = 0.95) -> EffectSize:
    """Standardised difference using the average (not pooled) variance.

    Appropriate when variances differ -- pooling assumes what Welch rejects.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    n1, n2 = len(x), len(y)
    s_av = math.sqrt((x.var(ddof=1) + y.var(ddof=1)) / 2.0)
    if s_av == 0:
        return EffectSize("cohens_d_av", 0.0, 0.0, 0.0, "negligible", conf)
    d = (x.mean() - y.mean()) / s_av
    se = math.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2 - 2)))
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    return EffectSize("cohens_d_av", d, d - z * se, d + z * se,
                      _magnitude(d, 0.2, 0.5, 0.8), conf)


# --------------------------------------------------------------------------
# Rank-based
# --------------------------------------------------------------------------


def rank_biserial(x: np.ndarray, y: np.ndarray, u_statistic: float,
                  conf: float = 0.95) -> EffectSize:
    """Rank-biserial correlation for Mann-Whitney U (Kerby 2014).

    Interpreted as stochastic superiority: ``f = U/(n1*n2)`` is the probability
    that a random draw from x exceeds a random draw from y, and r = 2f - 1.
    This is NOT a statement about medians -- blueprint section 7's guardrail.
    """
    n1, n2 = len(x), len(y)
    f = u_statistic / (n1 * n2)
    r = 2.0 * f - 1.0
    # Interval via Fisher z on the rank correlation.
    n = n1 + n2
    if n > 3 and abs(r) < 1:
        z = math.atanh(r)
        se = 1.0 / math.sqrt(n - 3)
        crit = stats.norm.ppf(1 - (1 - conf) / 2)
        lo, hi = math.tanh(z - crit * se), math.tanh(z + crit * se)
    else:
        lo, hi = float("nan"), float("nan")
    return EffectSize("rank_biserial", r, lo, hi,
                      _magnitude(r, 0.1, 0.3, 0.5), conf)


def epsilon_squared_kw(h_statistic: float, n: int) -> EffectSize:
    """Epsilon-squared for Kruskal-Wallis: H / (n - 1)."""
    eps2 = h_statistic / (n - 1) if n > 1 else float("nan")
    eps2 = min(max(eps2, 0.0), 1.0)
    return EffectSize("epsilon_squared", eps2, float("nan"), float("nan"),
                      _magnitude(eps2, 0.01, 0.06, 0.14))


# --------------------------------------------------------------------------
# ANOVA
# --------------------------------------------------------------------------


def omega_squared(ss_between: float, ss_total: float, df_between: int,
                  ms_within: float) -> EffectSize:
    """Omega-squared -- the less biased alternative to eta-squared."""
    num = ss_between - df_between * ms_within
    den = ss_total + ms_within
    w2 = num / den if den != 0 else float("nan")
    w2 = max(w2, 0.0)
    return EffectSize("omega_squared", w2, float("nan"), float("nan"),
                      _magnitude(w2, 0.01, 0.06, 0.14))


def eta_squared(ss_between: float, ss_total: float) -> EffectSize:
    e2 = ss_between / ss_total if ss_total != 0 else float("nan")
    return EffectSize("eta_squared", e2, float("nan"), float("nan"),
                      _magnitude(e2, 0.01, 0.06, 0.14))


# --------------------------------------------------------------------------
# Categorical
# --------------------------------------------------------------------------


def cramers_v(chi2: float, n: int, r: int, c: int,
              conf: float = 0.95) -> EffectSize:
    """Cramer's V with a noncentral chi-square interval."""
    k = min(r - 1, c - 1)
    if k <= 0 or n <= 0:
        return EffectSize("cramers_v", float("nan"), float("nan"),
                          float("nan"), "", conf)
    v = math.sqrt(chi2 / (n * k))
    df = (r - 1) * (c - 1)
    alpha = 1 - conf

    def _ncp(target: float) -> float:
        f = lambda lam: stats.ncx2.cdf(chi2, df, lam) - target
        try:
            return optimize.brentq(f, 1e-9, max(chi2 * 4, 100.0), xtol=1e-8)
        except (ValueError, RuntimeError):
            return 0.0

    lam_hi = _ncp(alpha / 2)
    lam_lo = _ncp(1 - alpha / 2) if stats.ncx2.cdf(chi2, df, 1e-9) > 1 - alpha / 2 else 0.0
    lo = math.sqrt(max(lam_lo, 0.0) / (n * k))
    hi = math.sqrt(max(lam_hi, 0.0) / (n * k))
    return EffectSize("cramers_v", v, min(lo, hi), max(lo, hi),
                      _magnitude(v, 0.1, 0.3, 0.5), conf)


def odds_ratio_2x2(table: np.ndarray, conf: float = 0.95) -> EffectSize:
    """Odds ratio with a Woolf log interval and Haldane-Anscombe correction."""
    t = np.asarray(table, float)
    if (t == 0).any():
        t = t + 0.5              # Haldane-Anscombe
    a, b, c, d = t[0, 0], t[0, 1], t[1, 0], t[1, 1]
    or_ = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    lo, hi = math.exp(math.log(or_) - z * se), math.exp(math.log(or_) + z * se)
    return EffectSize("odds_ratio", or_, lo, hi,
                      _magnitude(math.log(or_), 0.2, 0.7, 1.5), conf)


# --------------------------------------------------------------------------
# Correlation
# --------------------------------------------------------------------------


def correlation_ci(r: float, n: int, kind: str = "pearson",
                   conf: float = 0.95) -> EffectSize:
    """Fisher z interval.  Spearman uses the Bonett-Wright variance inflation."""
    if n <= 3 or abs(r) >= 1:
        return EffectSize(f"{kind}_r", r, float("nan"), float("nan"),
                          _magnitude(r, 0.1, 0.3, 0.5), conf)
    z = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    if kind == "spearman":
        se *= math.sqrt(1.0 + r**2 / 2.0)     # Bonett & Wright (2000)
    crit = stats.norm.ppf(1 - (1 - conf) / 2)
    return EffectSize(f"{kind}_r", r, math.tanh(z - crit * se),
                      math.tanh(z + crit * se),
                      _magnitude(r, 0.1, 0.3, 0.5), conf)


# --------------------------------------------------------------------------
# Regression
# --------------------------------------------------------------------------


def ratio_ci(coef: float, se: float, conf: float = 0.95,
             name: str = "ratio") -> EffectSize:
    """Exponentiated coefficient interval -- odds ratios and incidence-rate ratios."""
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    return EffectSize(name, math.exp(coef), math.exp(coef - z * se),
                      math.exp(coef + z * se),
                      _magnitude(coef, 0.1, 0.4, 1.0), conf)
