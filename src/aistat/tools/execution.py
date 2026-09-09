"""Execution dispatchers -- the 14 supported methods (blueprint section 2).

Every return carries an estimate, a 95% interval, an effect size, a p-value
where one is meaningful, and method-specific diagnostics.  Standardised so the
scorer can compare across systems and so ResultStore keys are stable.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.oneway import anova_oneway

from aistat.tools import effects


def _clean(a) -> np.ndarray:
    a = np.asarray(a, float)
    return a[np.isfinite(a)]


def _groups(df: pd.DataFrame, outcome: str, group: str):
    d = df[[outcome, group]].dropna()
    keys, samples = [], []
    for name, sub in d.groupby(group, observed=True):
        v = _clean(sub[outcome])
        if v.size:
            keys.append(str(name)); samples.append(v)
    return keys, samples


# ==========================================================================
# Tool 6 -- run_group_test  (6 methods)
# ==========================================================================


def run_group_test(df: pd.DataFrame, method: str, outcome: str, group: str,
                   conf: float = 0.95) -> dict:
    keys, samples = _groups(df, outcome, group)
    if len(samples) < 2:
        return {"error": f"need >=2 groups, found {len(samples)}"}

    base = {
        "method": method, "outcome": outcome, "group": group,
        "group_labels": keys, "group_ns": [int(s.size) for s in samples],
        "group_means": [float(s.mean()) for s in samples],
        "group_sds": [float(s.std(ddof=1)) if s.size > 1 else 0.0 for s in samples],
        "group_medians": [float(np.median(s)) for s in samples],
        "total_n": int(sum(s.size for s in samples)),
        "n_groups": len(samples),
        "conf_level": conf,
    }

    # ---- two-group methods ----
    if method in ("student_t", "welch_t", "mann_whitney"):
        if len(samples) != 2:
            return {"error": f"{method} requires exactly 2 groups, found {len(samples)}"}
        x, y = samples

        if method in ("student_t", "welch_t"):
            equal_var = method == "student_t"
            t, p = stats.ttest_ind(x, y, equal_var=equal_var)
            n1, n2 = x.size, y.size
            diff = float(x.mean() - y.mean())
            if equal_var:
                dfree = n1 + n2 - 2
                sp2 = ((n1 - 1) * x.var(ddof=1) + (n2 - 1) * y.var(ddof=1)) / dfree
                se = float(np.sqrt(sp2 * (1 / n1 + 1 / n2)))
                es = effects.hedges_g(x, y, conf)
            else:
                v1, v2 = x.var(ddof=1) / n1, y.var(ddof=1) / n2
                se = float(np.sqrt(v1 + v2))
                dfree = float((v1 + v2) ** 2 /
                              (v1**2 / (n1 - 1) + v2**2 / (n2 - 1)))
                es = effects.cohens_d_welch(x, y, conf)
            crit = stats.t.ppf(1 - (1 - conf) / 2, dfree)
            base.update(
                estimate=diff, estimate_label="mean_difference",
                se=se, ci_low=diff - crit * se, ci_high=diff + crit * se,
                statistic=float(t), p_value=float(p), df=float(dfree),
                effect_size=es.to_dict(),
                estimand="mean_difference",
            )
            return base

        # Mann-Whitney U
        u, p = stats.mannwhitneyu(x, y, alternative="two-sided")
        es = effects.rank_biserial(x, y, float(u), conf)
        n1, n2 = x.size, y.size
        # Hodges-Lehmann location shift: median of all pairwise differences.
        hl = float(np.median(np.subtract.outer(x, y))) if n1 * n2 <= 4_000_000 else float("nan")
        base.update(
            estimate=hl, estimate_label="hodges_lehmann_shift",
            statistic=float(u), p_value=float(p),
            prob_superiority=float(u / (n1 * n2)),
            effect_size=es.to_dict(),
            n_ties=int(len(x) + len(y) - len(np.unique(np.r_[x, y]))),
            estimand="distributional_shift",
            interpretation_note=("Stochastic ordering, not a median comparison "
                                 "unless shapes match."),
        )
        return base

    # ---- multi-group methods ----
    if method in ("one_way_anova", "welch_anova"):
        grand = np.concatenate(samples)
        ss_between = float(sum(s.size * (s.mean() - grand.mean()) ** 2 for s in samples))
        ss_within = float(sum(((s - s.mean()) ** 2).sum() for s in samples))
        ss_total = ss_between + ss_within
        df_b, df_w = len(samples) - 1, int(grand.size - len(samples))
        ms_w = ss_within / df_w if df_w else float("nan")

        if method == "one_way_anova":
            f, p = stats.f_oneway(*samples)
            df_denom = float(df_w)
        else:
            res = anova_oneway(samples, use_var="unequal", welch_correction=True)
            f, p, df_denom = float(res.statistic), float(res.pvalue), float(res.df[1])

        w2 = effects.omega_squared(ss_between, ss_total, df_b, ms_w)
        e2 = effects.eta_squared(ss_between, ss_total)
        base.update(
            statistic=float(f), p_value=float(p),
            df_between=float(df_b), df_within=df_denom,
            ss_between=ss_between, ss_within=ss_within, ss_total=ss_total,
            ms_within=ms_w,
            effect_size=w2.to_dict(), eta_squared=e2.to_dict(),
            estimate=float(max(b.mean() for b in samples) - min(b.mean() for b in samples)),
            estimate_label="max_group_mean_difference",
            estimand="mean_difference",
            post_hoc_recommended=bool(p < 0.05),
            post_hoc_note=("Games-Howell for unequal variances; Tukey HSD only "
                           "under an affirmative equal-variance justification."),
        )
        return base

    if method == "kruskal_wallis":
        h, p = stats.kruskal(*samples)
        n = int(sum(s.size for s in samples))
        es = effects.epsilon_squared_kw(float(h), n)
        base.update(
            statistic=float(h), p_value=float(p),
            df=float(len(samples) - 1),
            effect_size=es.to_dict(),
            estimate=float(max(np.median(s) for s in samples) -
                           min(np.median(s) for s in samples)),
            estimate_label="max_group_median_difference",
            estimand="distributional_shift",
            mean_ranks=[float(r) for r in
                        [np.mean(stats.rankdata(np.concatenate(samples))
                                 [sum(x.size for x in samples[:i]):
                                  sum(x.size for x in samples[:i + 1])])
                         for i in range(len(samples))]],
            interpretation_note=("Tests stochastic dominance; median language "
                                 "requires similar shapes."),
        )
        return base

    return {"error": f"unknown group method {method!r}"}


# ==========================================================================
# Tool 7 -- run_categorical_or_correlation  (4 methods)
# ==========================================================================


def run_categorical_or_correlation(df: pd.DataFrame, method: str, var1: str,
                                   var2: str, conf: float = 0.95) -> dict:
    base = {"method": method, "var1": var1, "var2": var2, "conf_level": conf}

    if method in ("chi_square", "fisher_exact"):
        table = pd.crosstab(df[var1], df[var2])
        obs = table.to_numpy()
        n = int(obs.sum())
        base.update(
            observed=obs.tolist(), total_n=n,
            row_labels=[str(x) for x in table.index],
            col_labels=[str(x) for x in table.columns],
            n_rows=int(obs.shape[0]), n_cols=int(obs.shape[1]),
        )
        if method == "chi_square":
            chi2, p, dof, exp = stats.chi2_contingency(obs)
            v = effects.cramers_v(float(chi2), n, *obs.shape, conf=conf)
            base.update(
                statistic=float(chi2), p_value=float(p), df=int(dof),
                expected=np.round(exp, 4).tolist(),
                min_expected=float(exp.min()),
                n_cells_expected_lt_5=int((exp < 5).sum()),
                effect_size=v.to_dict(), estimate=v.value,
                estimate_label="cramers_v", estimand="association",
            )
            if obs.shape == (2, 2):
                base["odds_ratio"] = effects.odds_ratio_2x2(obs, conf).to_dict()
        else:
            if obs.shape != (2, 2):
                return {"error": "fisher_exact requires a 2x2 table",
                        "shape": list(obs.shape)}
            or_, p = stats.fisher_exact(obs)
            es = effects.odds_ratio_2x2(obs, conf)
            base.update(
                p_value=float(p), estimate=float(or_),
                estimate_label="odds_ratio", effect_size=es.to_dict(),
                ci_low=es.ci_low, ci_high=es.ci_high, estimand="association",
            )
        base["interpretation_note"] = "Association, not individual risk or causation."
        return base

    if method in ("pearson", "spearman"):
        d = df[[var1, var2]].dropna()
        x, y = d[var1].to_numpy(float), d[var2].to_numpy(float)
        if len(x) < 3:
            return {"error": "fewer than three complete pairs", "n": int(len(x))}
        if method == "pearson":
            r, p = stats.pearsonr(x, y)
            note = "Linear association; sensitive to influential points."
        else:
            r, p = stats.spearmanr(x, y)
            note = "Monotone association on ranks; not necessarily linear."
        es = effects.correlation_ci(float(r), len(x), method, conf)
        base.update(
            n=int(len(x)), estimate=float(r), estimate_label=f"{method}_r",
            statistic=float(r), p_value=float(p),
            ci_low=es.ci_low, ci_high=es.ci_high,
            r_squared=float(r**2), effect_size=es.to_dict(),
            estimand="association", interpretation_note=note,
        )
        return base

    return {"error": f"unknown method {method!r}"}


# ==========================================================================
# Tool 8 -- fit_regression  (4 models)
# ==========================================================================


def _design(df: pd.DataFrame, outcome: str, predictors: list[str],
            extra: list[str] | None = None):
    """Build the model frame.

    ``extra`` columns (an exposure, for instance) are carried through the
    dropna so they stay aligned with the design matrix -- they are needed for
    the offset but must not enter the predictors.
    """
    cols = [outcome] + list(predictors) + [c for c in (extra or [])
                                           if c in df.columns and c not in predictors]
    d = df[cols].dropna()
    y = d[outcome]
    X = pd.get_dummies(d[list(predictors)], drop_first=True, dtype=float)
    X = sm.add_constant(X, has_constant="add")
    return y, X, d


def _coef_table(res, exponentiate: bool, label: str, conf: float) -> list[dict]:
    ci = res.conf_int(alpha=1 - conf)
    rows = []
    for name in res.params.index:
        b, se = float(res.params[name]), float(res.bse[name])
        lo, hi = float(ci.loc[name, 0]), float(ci.loc[name, 1])
        row = {
            "term": str(name), "estimate": b, "se": se,
            "statistic": float(res.tvalues[name]),
            "p_value": float(res.pvalues[name]),
            "ci_low": lo, "ci_high": hi,
        }
        if exponentiate:
            row[label] = float(np.exp(b))
            row[f"{label}_ci_low"] = float(np.exp(lo))
            row[f"{label}_ci_high"] = float(np.exp(hi))
        rows.append(row)
    return rows


def fit_regression(df: pd.DataFrame, method: str, outcome: str,
                   predictors: list[str], exposure: str | None = None,
                   conf: float = 0.95) -> dict:
    y, X, d = _design(df, outcome, predictors,
                      extra=[exposure] if exposure else None)
    n, k = len(y), X.shape[1]
    base = {
        "method": method, "outcome": outcome, "predictors": list(predictors),
        "n_used": int(n), "n_parameters": int(k),
        "n_dropped_missing": int(len(df) - n),
        "terms": [str(c) for c in X.columns], "conf_level": conf,
    }
    # Collinearity: max VIF over non-intercept columns.
    try:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        cols = [i for i, c in enumerate(X.columns) if c != "const"]
        if len(cols) > 1:
            vifs = [float(variance_inflation_factor(X.to_numpy(float), i)) for i in cols]
            base["max_vif"] = float(np.nanmax(vifs))
            base["collinearity_concern"] = bool(np.nanmax(vifs) > 10)
    except Exception:
        pass

    off = None
    if exposure and exposure in d:
        e = d[exposure].to_numpy(float)
        if (e > 0).all():
            off = np.log(e)
            base["exposure"] = exposure

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if method == "ols":
            res = sm.OLS(y.astype(float), X).fit()
            resid = np.asarray(res.resid, float)
            infl = res.get_influence()
            cooks = np.asarray(infl.cooks_distance[0], float)
            # Breusch-Pagan assumes the variance is linear in the regressors, so
            # it has no power against symmetric patterns such as sd proportional
            # to |x|.  White's test includes squares and cross-products and does.
            # Reporting both is the point: one test used as a switch is exactly
            # the mechanical-checking failure mode the policy warns about.
            Xf = X.to_numpy(float)
            bp = sm.stats.diagnostic.het_breuschpagan(resid, Xf)
            try:
                white = sm.stats.diagnostic.het_white(resid, Xf)
            except Exception:
                white = (float("nan"), float("nan"))
            base.update(
                coefficients=_coef_table(res, False, "", conf),
                r_squared=float(res.rsquared),
                adj_r_squared=float(res.rsquared_adj),
                f_statistic=float(res.fvalue), f_p_value=float(res.f_pvalue),
                df_resid=int(res.df_resid), aic=float(res.aic), bic=float(res.bic),
                residual_sd=float(np.std(resid, ddof=k)),
                breusch_pagan_statistic=float(bp[0]), breusch_pagan_p=float(bp[1]),
                white_statistic=float(white[0]), white_p=float(white[1]),
                heteroscedasticity_flag=bool(
                    bp[1] < 0.05
                    or (white[1] == white[1] and white[1] < 0.05)),
                durbin_watson=float(sm.stats.stattools.durbin_watson(resid)),
                n_high_cooks=int((cooks > 4 / n).sum()),
                max_cooks_distance=float(np.nanmax(cooks)),
                resid_skew=float(stats.skew(resid)),
                jarque_bera_p=float(stats.jarque_bera(resid)[1]),
                estimand="conditional_mean",
                interpretation_note=("Coefficients are conditional on the "
                                     "included variables."),
            )
            return base

        if method == "logistic":
            yv = y.to_numpy()
            levels = sorted(pd.unique(yv))
            if len(levels) != 2:
                return {"error": f"logistic requires a binary outcome, found {len(levels)} levels"}
            yb = (yv == levels[-1]).astype(float)
            n_ev = int(yb.sum())
            epp = min(n_ev, n - n_ev) / max(k, 1)
            try:
                res = sm.Logit(yb, X).fit(disp=0)
            except Exception as exc:
                return {"error": f"logistic fit failed: {exc}", "separation_suspected": True}
            pred = np.asarray(res.predict(X), float)
            sep = bool(pred.min() < 1e-6 or pred.max() > 1 - 1e-6 or
                       np.abs(res.params).max() > 15)
            # Hosmer-Lemeshow calibration over deciles of risk.
            hl_p = float("nan")
            try:
                dec = pd.qcut(pred, 10, duplicates="drop", labels=False)
                obs_g = pd.Series(yb).groupby(dec).sum()
                exp_g = pd.Series(pred).groupby(dec).sum()
                ng = pd.Series(yb).groupby(dec).size()
                hl = float((((obs_g - exp_g) ** 2) /
                            (exp_g * (1 - exp_g / ng))).sum())
                hl_p = float(1 - stats.chi2.cdf(hl, max(len(ng) - 2, 1)))
                base["hosmer_lemeshow_statistic"] = hl
            except Exception:
                pass
            base.update(
                reference_level=str(levels[0]), modelled_level=str(levels[-1]),
                coefficients=_coef_table(res, True, "odds_ratio", conf),
                n_events=n_ev, event_rate=float(yb.mean()),
                events_per_parameter=float(epp),
                epp_adequate=bool(epp >= 10),
                separation_suspected=sep,
                pseudo_r_squared=float(res.prsquared),
                log_likelihood=float(res.llf),
                llr_p_value=float(res.llr_pvalue),
                aic=float(res.aic),
                auc=float(_auc(yb, pred)),
                hosmer_lemeshow_p=hl_p,
                estimand="odds",
                interpretation_note=("Report odds ratios; probability changes "
                                     "require explicit computation."),
            )
            return base

        if method in ("poisson", "negative_binomial"):
            yv = y.to_numpy(float)
            if (yv < 0).any() or not np.allclose(yv, np.round(yv)):
                return {"error": "count models require non-negative integers"}
            if method == "poisson":
                res = sm.GLM(yv, X, family=sm.families.Poisson(), offset=off).fit()
                pear = float(res.pearson_chi2 / res.df_resid)
                dev = float(res.deviance / res.df_resid)
                base.update(
                    coefficients=_coef_table(res, True, "irr", conf),
                    pearson_dispersion=pear, deviance_dispersion=dev,
                    overdispersion_flag=bool(pear > 1.5),
                    dispersion_note=("Conditional dispersion; marginal variance "
                                     "alone does not decide Poisson vs NB."),
                )
            else:
                try:
                    nb = sm.NegativeBinomial(yv, X, loglike_method="nb2",
                                             offset=off).fit(disp=0)
                    alpha = float(nb.params.iloc[-1] if hasattr(nb.params, "iloc")
                                  else nb.params[-1])
                    res = sm.GLM(yv, X,
                                 family=sm.families.NegativeBinomial(alpha=alpha),
                                 offset=off).fit()
                except Exception as exc:
                    return {"error": f"negative binomial fit failed: {exc}"}
                base.update(
                    coefficients=_coef_table(res, True, "irr", conf),
                    nb_alpha=alpha,
                    alpha_significant=bool(alpha > 0.05),
                    pearson_dispersion=float(res.pearson_chi2 / res.df_resid),
                    deviance_dispersion=float(res.deviance / res.df_resid),
                )
            mu = np.asarray(res.fittedvalues, float)
            base.update(
                n_zeros=int((yv == 0).sum()),
                pct_zeros=float((yv == 0).mean() * 100),
                expected_pct_zeros=float(np.mean(np.exp(-mu)) * 100),
                excess_zeros_flag=bool((yv == 0).mean() * 100 >
                                       np.mean(np.exp(-mu)) * 100 + 10),
                mean_outcome=float(yv.mean()), var_outcome=float(yv.var(ddof=1)),
                marginal_var_mean_ratio=float(yv.var(ddof=1) / yv.mean())
                if yv.mean() else float("nan"),
                log_likelihood=float(res.llf), aic=float(res.aic),
                df_resid=int(res.df_resid),
                estimand="rate",
                interpretation_note=("Report incidence-rate ratios and the "
                                     "exposure basis."),
            )
            return base

    return {"error": f"unknown regression method {method!r}"}


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    """Rank-based AUC (Mann-Whitney equivalence), no sklearn dependency."""
    pos, neg = p[y == 1], p[y == 0]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    r = stats.rankdata(np.r_[pos, neg])
    return float((r[:pos.size].sum() - pos.size * (pos.size + 1) / 2) /
                 (pos.size * neg.size))
