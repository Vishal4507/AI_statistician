"""Numerical correctness against independently known values (blueprint 10.4).

Review finding F-B2: the oracle files cannot validate the library that produced
them.  These tests are the actual correctness check -- every expected value here
is either analytically derivable by hand or a published worked example, never a
value this codebase generated.

At least two tests per supported method, plus the edge cases the blueprint
names: ties, sparse cells, separation, exposure and overdispersion.
"""
import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from aistat.tools import effects
from aistat.tools.execution import (fit_regression, run_categorical_or_correlation,
                                    run_group_test)


def _df(y, g, ycol="y", gcol="g"):
    return pd.DataFrame({ycol: y, gcol: g})


# ==========================================================================
# student_t
# ==========================================================================

def test_student_t_hand_computed():
    """Two samples with hand-computable statistics.

    x = [1,2,3,4,5]  mean 3, var 2.5
    y = [2,4,6,8,10] mean 6, var 10
    pooled var = (4*2.5 + 4*10)/8 = 6.25 ; se = sqrt(6.25 * 2/5) = 1.5811388
    t = (3 - 6)/1.5811388 = -1.8973666 on 8 df
    """
    x, y = [1, 2, 3, 4, 5], [2, 4, 6, 8, 10]
    r = run_group_test(_df(x + y, ["a"] * 5 + ["b"] * 5), "student_t", "y", "g")
    assert r["estimate"] == pytest.approx(-3.0)
    assert r["se"] == pytest.approx(1.5811388300841898, rel=1e-9)
    assert r["statistic"] == pytest.approx(-1.8973665961010275, rel=1e-9)
    assert r["df"] == pytest.approx(8.0)
    assert r["p_value"] == pytest.approx(
        2 * stats.t.cdf(-1.8973665961010275, 8), rel=1e-9)


def test_student_t_ci_matches_t_quantile():
    """The interval must be estimate +/- t(.975, df) * se, exactly."""
    rng = np.random.default_rng(0)
    x, y = rng.normal(5, 1, 30), rng.normal(4, 1, 30)
    r = run_group_test(_df(np.r_[x, y], ["a"] * 30 + ["b"] * 30),
                       "student_t", "y", "g")
    crit = stats.t.ppf(0.975, r["df"])
    assert r["ci_low"] == pytest.approx(r["estimate"] - crit * r["se"], rel=1e-10)
    assert r["ci_high"] == pytest.approx(r["estimate"] + crit * r["se"], rel=1e-10)


# ==========================================================================
# welch_t
# ==========================================================================

def test_welch_t_satterthwaite_df_hand_computed():
    """x=[1..5] var 2.5 n 5 ; y=[2,4,6,8,10] var 10 n 5.

    v1 = 2.5/5 = 0.5 ; v2 = 10/5 = 2.0 ; se = sqrt(2.5) = 1.5811388
    df = (0.5+2)^2 / (0.5^2/4 + 2^2/4) = 6.25 / (0.0625 + 1.0) = 5.8823529
    """
    x, y = [1, 2, 3, 4, 5], [2, 4, 6, 8, 10]
    r = run_group_test(_df(x + y, ["a"] * 5 + ["b"] * 5), "welch_t", "y", "g")
    assert r["se"] == pytest.approx(math.sqrt(2.5), rel=1e-12)
    assert r["df"] == pytest.approx(6.25 / 1.0625, rel=1e-9)


def test_welch_t_equals_scipy_unequal_var():
    rng = np.random.default_rng(1)
    x, y = rng.normal(0, 1, 25), rng.normal(0.5, 3, 40)
    r = run_group_test(_df(np.r_[x, y], ["a"] * 25 + ["b"] * 40),
                       "welch_t", "y", "g")
    t_exp, p_exp = stats.ttest_ind(x, y, equal_var=False)
    assert r["statistic"] == pytest.approx(t_exp, rel=1e-12)
    assert r["p_value"] == pytest.approx(p_exp, rel=1e-12)


# ==========================================================================
# mann_whitney
# ==========================================================================

def test_mann_whitney_complete_separation_exact_u():
    """Complete separation: every x below every y, so U1 = 0 and U2 = n1*n2."""
    x, y = [1, 2, 3], [10, 11, 12]
    r = run_group_test(_df(x + y, ["a"] * 3 + ["b"] * 3),
                       "mann_whitney", "y", "g")
    assert r["statistic"] == pytest.approx(0.0)
    assert r["prob_superiority"] == pytest.approx(0.0)
    assert r["effect_size"]["value"] == pytest.approx(-1.0)


def test_mann_whitney_ties_are_counted():
    x, y = [1, 2, 2, 3], [2, 3, 3, 4]
    r = run_group_test(_df(x + y, ["a"] * 4 + ["b"] * 4),
                       "mann_whitney", "y", "g")
    # 8 observations, 4 distinct values -> 4 tied positions.
    assert r["n_ties"] == 4
    u_exp, p_exp = stats.mannwhitneyu(x, y, alternative="two-sided")
    assert r["p_value"] == pytest.approx(p_exp, rel=1e-12)


# ==========================================================================
# one_way_anova / welch_anova
# ==========================================================================

def test_one_way_anova_hand_computed_sums_of_squares():
    """Three groups of 3. Grand mean 5.

    a=[1,2,3] mean 2 ; b=[4,5,6] mean 5 ; c=[7,8,9] mean 8
    SS_between = 3*((2-5)^2 + 0 + (8-5)^2) = 3*18 = 54
    SS_within  = 3 * 2 = 6      (each group has SS 2)
    F = (54/2) / (6/6) = 27
    """
    y = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    g = ["a"] * 3 + ["b"] * 3 + ["c"] * 3
    r = run_group_test(_df(y, g), "one_way_anova", "y", "g")
    assert r["ss_between"] == pytest.approx(54.0)
    assert r["ss_within"] == pytest.approx(6.0)
    assert r["statistic"] == pytest.approx(27.0)
    assert r["eta_squared"]["value"] == pytest.approx(54.0 / 60.0)


def test_welch_anova_matches_statsmodels_and_differs_under_heteroscedasticity():
    from statsmodels.stats.oneway import anova_oneway
    rng = np.random.default_rng(2)
    s = [rng.normal(0, 1, 30), rng.normal(0.4, 4, 30), rng.normal(0.8, 1, 30)]
    df = _df(np.concatenate(s), sum(([c] * 30 for c in "abc"), []))
    r = run_group_test(df, "welch_anova", "y", "g")
    exp = anova_oneway(s, use_var="unequal", welch_correction=True)
    assert r["statistic"] == pytest.approx(float(exp.statistic), rel=1e-10)
    ordinary = run_group_test(df, "one_way_anova", "y", "g")
    assert r["statistic"] != pytest.approx(ordinary["statistic"], rel=1e-6)


# ==========================================================================
# kruskal_wallis
# ==========================================================================

def test_kruskal_wallis_perfect_separation():
    y = [1, 2, 3, 10, 11, 12, 20, 21, 22]
    g = ["a"] * 3 + ["b"] * 3 + ["c"] * 3
    r = run_group_test(_df(y, g), "kruskal_wallis", "y", "g")
    h_exp, p_exp = stats.kruskal([1, 2, 3], [10, 11, 12], [20, 21, 22])
    assert r["statistic"] == pytest.approx(h_exp, rel=1e-12)
    assert r["df"] == 2.0
    assert r["effect_size"]["value"] == pytest.approx(h_exp / 8.0, rel=1e-12)


def test_kruskal_wallis_identical_groups_gives_zero_h():
    y = [1, 2, 3] * 3
    g = ["a"] * 3 + ["b"] * 3 + ["c"] * 3
    r = run_group_test(_df(y, g), "kruskal_wallis", "y", "g")
    assert r["statistic"] == pytest.approx(0.0, abs=1e-12)


# ==========================================================================
# chi_square / fisher_exact
# ==========================================================================

def test_chi_square_hand_computed_2x2():
    """Table [[20,30],[30,20]], n=100, all margins 50.

    Every expected cell is 25.  chi2 = 4 * (5^2/25) = 4.0 on 1 df.
    Cramer's V = sqrt(4/100) = 0.2
    """
    rows = ([("r1", "c1")] * 20 + [("r1", "c2")] * 30 +
            [("r2", "c1")] * 30 + [("r2", "c2")] * 20)
    df = pd.DataFrame(rows, columns=["a", "b"])
    r = run_categorical_or_correlation(df, "chi_square", "a", "b")
    # scipy applies Yates' correction on 2x2 by default.
    chi2_uncorrected = 4.0
    yates = sum((abs(o - 25) - 0.5) ** 2 / 25 for o in (20, 30, 30, 20))
    assert r["statistic"] == pytest.approx(yates, rel=1e-12)
    assert r["min_expected"] == pytest.approx(25.0)
    assert r["df"] == 1
    assert chi2_uncorrected > r["statistic"]        # correction shrinks it


def test_fisher_exact_tea_tasting():
    """Fisher's tea-tasting table [[3,1],[1,3]].

    Two-sided p = 0.4857142857... (17/35), the classic published value.
    """
    rows = ([("r1", "c1")] * 3 + [("r1", "c2")] * 1 +
            [("r2", "c1")] * 1 + [("r2", "c2")] * 3)
    df = pd.DataFrame(rows, columns=["a", "b"])
    r = run_categorical_or_correlation(df, "fisher_exact", "a", "b")
    assert r["p_value"] == pytest.approx(17 / 35, rel=1e-12)
    assert r["estimate"] == pytest.approx(9.0)      # (3*3)/(1*1)


def test_fisher_rejects_non_2x2():
    df = pd.DataFrame({"a": list("aabbcc"), "b": list("xyxyxy")})
    r = run_categorical_or_correlation(df, "fisher_exact", "a", "b")
    assert "error" in r


def test_chi_square_flags_sparse_expected_cells():
    rows = [("r1", "c1")] * 9 + [("r1", "c2")] + [("r2", "c1")] + [("r2", "c2")] * 3
    df = pd.DataFrame(rows, columns=["a", "b"])
    r = run_categorical_or_correlation(df, "chi_square", "a", "b")
    assert r["n_cells_expected_lt_5"] >= 2
    assert r["min_expected"] < 5


# ==========================================================================
# pearson / spearman
# ==========================================================================

def test_pearson_exact_on_hand_data():
    """x=[1,2,3,4,5], y=[2,4,5,4,5].

    Sxy = 6, Sxx = 10, Syy = 6  ->  r = 6/sqrt(60) = 0.7745966692414834
    """
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 4, 5, 4, 5]})
    r = run_categorical_or_correlation(df, "pearson", "x", "y")
    assert r["estimate"] == pytest.approx(6 / math.sqrt(60), rel=1e-12)
    assert r["r_squared"] == pytest.approx(0.6, rel=1e-12)


def test_spearman_perfect_monotone_is_one():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 6],
                       "y": [1, 8, 27, 64, 125, 216]})   # monotone, nonlinear
    r = run_categorical_or_correlation(df, "spearman", "x", "y")
    assert r["estimate"] == pytest.approx(1.0, rel=1e-12)
    p = run_categorical_or_correlation(df, "pearson", "x", "y")
    assert p["estimate"] < 0.98          # the point of preferring ranks here


def test_correlation_ci_brackets_estimate():
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, 80)
    df = pd.DataFrame({"x": x, "y": 0.5 * x + rng.normal(0, 1, 80)})
    for m in ("pearson", "spearman"):
        r = run_categorical_or_correlation(df, m, "x", "y")
        assert r["ci_low"] < r["estimate"] < r["ci_high"]


# ==========================================================================
# ols
# ==========================================================================

def test_ols_exact_recovery_on_noiseless_data():
    # x2 must not be a linear function of x1, or the coefficients are not
    # identified and the "exact recovery" claim is meaningless.
    x1 = np.arange(20, dtype=float)
    x2 = np.array([0., 1, 0, 1, 2, 0, 3, 1, 0, 2,
                   1, 3, 0, 2, 1, 0, 3, 2, 1, 0])
    y = 3.0 + 2.0 * x1 - 5.0 * x2                      # no noise
    df = pd.DataFrame({"predictor_a": x1, "predictor_b": x2, "y": y})
    r = fit_regression(df, "ols", "y", ["predictor_a", "predictor_b"])
    coefs = {c["term"]: c["estimate"] for c in r["coefficients"]}
    assert coefs["const"] == pytest.approx(3.0, abs=1e-8)
    assert coefs["predictor_a"] == pytest.approx(2.0, abs=1e-8)
    assert coefs["predictor_b"] == pytest.approx(-5.0, abs=1e-8)
    assert r["r_squared"] == pytest.approx(1.0, abs=1e-12)


def test_ols_detects_heteroscedasticity():
    rng = np.random.default_rng(4)
    n = 400
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)                           # independent
    y = 1 + x1 + rng.normal(0, 1, n) * (1 + 3 * np.abs(x1))
    df = pd.DataFrame({"predictor_a": x1, "predictor_b": x2, "y": y})
    r = fit_regression(df, "ols", "y", ["predictor_a", "predictor_b"])
    # sd proportional to |x1| is invisible to Breusch-Pagan and obvious to
    # White; the flag must fire on either.
    assert r["heteroscedasticity_flag"] is True
    assert r["white_p"] < 0.05
    assert r["breusch_pagan_p"] > 0.05      # documents the blind spot


def test_ols_detects_collinearity():
    rng = np.random.default_rng(14)
    n = 400
    x1 = rng.normal(0, 1, n)
    x2 = x1 + 0.15 * rng.normal(0, 1, n)               # r ~ 0.99, VIF >> 10
    y = 1 + x1 + rng.normal(0, 1, n)
    df = pd.DataFrame({"predictor_a": x1, "predictor_b": x2, "y": y})
    r = fit_regression(df, "ols", "y", ["predictor_a", "predictor_b"])
    assert r["max_vif"] > 10
    assert r["collinearity_concern"] is True


# ==========================================================================
# logistic
# ==========================================================================

def test_logistic_recovers_known_odds_ratio():
    rng = np.random.default_rng(5)
    n = 6000
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    p = 1 / (1 + np.exp(-(0.2 + 1.0 * x1)))
    y = (rng.random(n) < p).astype(int)
    df = pd.DataFrame({"predictor_a": x1, "predictor_b": x2, "y": y})
    r = fit_regression(df, "logistic", "y", ["predictor_a", "predictor_b"])
    coefs = {c["term"]: c for c in r["coefficients"]}
    a = coefs["predictor_a"]
    assert a["odds_ratio"] == pytest.approx(math.e, rel=0.12)
    # The interval must bracket its own estimate and exclude "no effect".
    assert a["odds_ratio_ci_low"] < a["odds_ratio"] < a["odds_ratio_ci_high"]
    assert a["odds_ratio_ci_low"] > 1.0
    assert coefs["predictor_b"]["odds_ratio_ci_low"] < 1.0 < \
        coefs["predictor_b"]["odds_ratio_ci_high"]     # true effect is zero
    assert 0.5 < r["auc"] <= 1.0


def test_logistic_flags_separation():
    x1 = np.linspace(-3, 3, 60)
    df = pd.DataFrame({"predictor_a": x1, "predictor_b": np.zeros(60),
                       "y": (x1 > 0).astype(int)})
    r = fit_regression(df, "logistic", "y", ["predictor_a"])
    assert r.get("separation_suspected") is True or "error" in r


def test_logistic_rejects_non_binary_outcome():
    df = pd.DataFrame({"predictor_a": range(30), "y": list(range(30))})
    r = fit_regression(df, "logistic", "y", ["predictor_a"])
    assert "error" in r


# ==========================================================================
# poisson / negative_binomial
# ==========================================================================

def test_poisson_recovers_known_irr_and_reports_unit_dispersion():
    rng = np.random.default_rng(6)
    n = 8000
    x1 = rng.normal(0, 1, n)
    y = rng.poisson(np.exp(1.0 + 0.5 * x1))
    df = pd.DataFrame({"predictor_a": x1, "y": y})
    r = fit_regression(df, "poisson", "y", ["predictor_a"])
    coefs = {c["term"]: c for c in r["coefficients"]}
    assert coefs["predictor_a"]["irr"] == pytest.approx(math.exp(0.5), rel=0.06)
    assert r["pearson_dispersion"] == pytest.approx(1.0, abs=0.15)
    assert r["overdispersion_flag"] is False


def test_poisson_offset_changes_estimates_when_exposure_varies():
    rng = np.random.default_rng(7)
    n = 3000
    x1 = rng.normal(0, 1, n)
    exposure = rng.uniform(0.5, 5.0, n)
    y = rng.poisson(np.exp(0.5 + 0.4 * x1) * exposure)
    df = pd.DataFrame({"predictor_a": x1, "obs_days": exposure, "y": y})
    with_exp = fit_regression(df, "poisson", "y", ["predictor_a"], exposure="obs_days")
    without = fit_regression(df, "poisson", "y", ["predictor_a"])
    c_with = {c["term"]: c["irr"] for c in with_exp["coefficients"]}
    assert with_exp["exposure"] == "obs_days"
    assert c_with["predictor_a"] == pytest.approx(math.exp(0.4), rel=0.08)
    # Ignoring exposure biases the intercept badly.
    i_with = {c["term"]: c["estimate"] for c in with_exp["coefficients"]}["const"]
    i_without = {c["term"]: c["estimate"] for c in without["coefficients"]}["const"]
    assert abs(i_with - 0.5) < abs(i_without - 0.5)


def test_negative_binomial_beats_poisson_on_overdispersed_counts():
    rng = np.random.default_rng(8)
    n = 3000
    x1 = rng.normal(0, 1, n)
    mu = np.exp(1.0 + 0.5 * x1)
    r_shape = 1.5
    y = rng.negative_binomial(r_shape, r_shape / (r_shape + mu))
    df = pd.DataFrame({"predictor_a": x1, "y": y})
    pois = fit_regression(df, "poisson", "y", ["predictor_a"])
    nb = fit_regression(df, "negative_binomial", "y", ["predictor_a"])
    assert pois["pearson_dispersion"] > 1.5
    assert pois["overdispersion_flag"] is True
    assert nb["aic"] < pois["aic"]                  # NB fits materially better
    assert nb["nb_alpha"] == pytest.approx(1 / r_shape, rel=0.35)


def test_count_model_rejects_non_integer_outcome():
    df = pd.DataFrame({"predictor_a": np.arange(30.0), "y": np.arange(30) + 0.5})
    assert "error" in fit_regression(df, "poisson", "y", ["predictor_a"])


# ==========================================================================
# Effect sizes
# ==========================================================================

def test_hedges_g_bias_correction_and_direction():
    """d = (10-8)/2 = 1.0 exactly; J = 1 - 3/(4*38-1) = 1 - 3/151."""
    rng = np.random.default_rng(9)
    x = rng.normal(0, 1, 20); x = (x - x.mean()) / x.std(ddof=1) * 2 + 10
    y = rng.normal(0, 1, 20); y = (y - y.mean()) / y.std(ddof=1) * 2 + 8
    g = effects.hedges_g(x, y)
    J = 1 - 3 / (4 * 38 - 1)
    assert g.value == pytest.approx(1.0 * J, rel=1e-6)
    assert g.ci_low < g.value < g.ci_high


def test_cramers_v_upper_bound_and_hand_value():
    # chi2=4, n=100, 2x2 -> V = sqrt(4/100) = 0.2
    v = effects.cramers_v(4.0, 100, 2, 2)
    assert v.value == pytest.approx(0.2, rel=1e-12)
    # Perfect association in a 2x2: chi2 = n -> V = 1
    assert effects.cramers_v(100.0, 100, 2, 2).value == pytest.approx(1.0)


def test_odds_ratio_haldane_correction_on_zero_cell():
    t = np.array([[10, 0], [5, 15]])
    r = effects.odds_ratio_2x2(t)
    assert math.isfinite(r.value) and r.value > 1
    assert r.ci_low < r.value < r.ci_high


def test_rank_biserial_bounds():
    x, y = np.array([1., 2, 3]), np.array([4., 5, 6])
    assert effects.rank_biserial(x, y, 0.0).value == pytest.approx(-1.0)
    assert effects.rank_biserial(x, y, 9.0).value == pytest.approx(1.0)


def test_omega_squared_is_below_eta_squared():
    w = effects.omega_squared(54.0, 60.0, 2, 1.0)
    e = effects.eta_squared(54.0, 60.0)
    assert w.value < e.value
