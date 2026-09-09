"""Diagnostic tools (blueprint section 5.2, tools 1-5).

These supply *evidence*, never decisions.  Blueprint section 2: "Normality tests
are evidence, not switches."  Each function therefore returns the raw material
for a judgement -- group sizes, variance ratios, skew, influence, Q-Q behaviour --
and deliberately does not return a recommended method.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _clean(a) -> np.ndarray:
    a = np.asarray(a, float)
    return a[np.isfinite(a)]


def _suggest_scale(s: pd.Series) -> str:
    """Suggest a measurement scale.  A suggestion, not an assertion."""
    nn = s.dropna()
    if nn.empty:
        return "unknown"
    if nn.dtype == bool or set(nn.unique()) <= {0, 1}:
        return "binary"
    if not pd.api.types.is_numeric_dtype(nn):
        return "binary" if nn.nunique() == 2 else "nominal"
    if pd.api.types.is_integer_dtype(nn) or (nn % 1 == 0).all():
        if (nn >= 0).all() and nn.nunique() > 2:
            return "count" if nn.max() > 10 or nn.nunique() > 10 else "ordinal"
        return "ordinal"
    return "continuous"


# --------------------------------------------------------------------------


def inspect_dataset(df: pd.DataFrame) -> dict:
    """Schema, missingness, duplicates, repeated IDs, and time-order candidates.

    The repeated-ID and monotonic-column scans exist to surface design hazards
    the design card may have omitted -- blueprint section 11's first risk.
    """
    n = len(df)
    cols = {}
    for name in df.columns:
        s = df[name]
        entry = {
            "dtype": str(s.dtype),
            "suggested_scale": _suggest_scale(s),
            "n_missing": int(s.isna().sum()),
            "pct_missing": float(s.isna().mean() * 100),
            "n_unique": int(s.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(s) and s.notna().any():
            v = _clean(s)
            if v.size:
                entry.update(
                    min=float(v.min()), max=float(v.max()),
                    mean=float(v.mean()),
                    is_monotonic=bool(pd.Series(v).is_monotonic_increasing),
                    n_zeros=int((v == 0).sum()),
                    pct_zeros=float((v == 0).mean() * 100),
                )
        else:
            entry["levels"] = [str(x) for x in s.dropna().unique()[:12]]
        cols[name] = entry

    # Repeated identifiers: a low-cardinality non-numeric column whose values
    # recur is a candidate repeated-measures key.
    repeated: list[dict] = []
    for name in df.columns:
        s = df[name].dropna()
        if s.empty or s.nunique() >= len(s):
            continue
        ratio = s.nunique() / max(len(s), 1)
        if 0 < ratio < 0.9:
            counts = s.value_counts()
            if counts.max() > 1 and s.nunique() > 1:
                repeated.append({
                    "column": name,
                    "n_unique": int(s.nunique()),
                    "max_repeats": int(counts.max()),
                    "mean_repeats": float(counts.mean()),
                    "unique_ratio": float(ratio),
                })
    repeated.sort(key=lambda d: -d["max_repeats"])

    time_like = [
        c for c in df.columns
        if any(k in str(c).lower()
               for k in ("date", "time", "hour", "day", "month", "year",
                         "week", "timestamp", "period", "seq"))
    ]

    return {
        "n_rows": int(n),
        "n_columns": int(df.shape[1]),
        "columns": cols,
        "n_duplicate_rows": int(df.duplicated().sum()),
        "n_complete_rows": int(df.dropna().shape[0]),
        "repeated_id_candidates": repeated[:5],
        "time_column_candidates": time_like,
        "n_repeated_id_candidates": len(repeated),
    }


def summarize_groups(df: pd.DataFrame, outcome: str, group: str) -> dict:
    """Per-group location, spread, shape, and outlier/Q-Q behaviour."""
    out: dict[str, dict] = {}
    for name, sub in df[[outcome, group]].dropna().groupby(group, observed=True):
        v = _clean(sub[outcome])
        if v.size == 0:
            continue
        q1, q3 = np.percentile(v, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        entry = {
            "n": int(v.size),
            "mean": float(v.mean()),
            "sd": float(v.std(ddof=1)) if v.size > 1 else 0.0,
            "median": float(np.median(v)),
            "q1": float(q1), "q3": float(q3), "iqr": float(iqr),
            "min": float(v.min()), "max": float(v.max()),
            "mad": float(stats.median_abs_deviation(v, scale="normal")),
            "skew": float(stats.skew(v)) if v.size > 2 else 0.0,
            "kurtosis": float(stats.kurtosis(v)) if v.size > 3 else 0.0,
            "n_outliers_iqr": int(((v < lo) | (v > hi)).sum()),
            "pct_outliers": float(((v < lo) | (v > hi)).mean() * 100),
        }
        if 3 <= v.size <= 5000:
            w, p = stats.shapiro(v)
            entry["shapiro_w"] = float(w)
            entry["shapiro_p"] = float(p)
        # Q-Q linearity: correlation of sorted data with normal quantiles.
        if v.size >= 3:
            qq = stats.probplot(v, dist="norm")
            entry["qq_correlation"] = float(qq[1][2])
        out[str(name)] = entry

    ns = [g["n"] for g in out.values()]
    sds = [g["sd"] for g in out.values() if g["sd"] > 0]
    return {
        "groups": out,
        "n_groups": len(out),
        "total_n": int(sum(ns)),
        "min_group_n": int(min(ns)) if ns else 0,
        "max_group_n": int(max(ns)) if ns else 0,
        "group_size_ratio": float(max(ns) / min(ns)) if ns and min(ns) else float("nan"),
        "sd_ratio": float(max(sds) / min(sds)) if len(sds) > 1 else 1.0,
        "max_abs_skew": float(max((abs(g["skew"]) for g in out.values()), default=0.0)),
    }


def check_group_assumptions(df: pd.DataFrame, outcome: str, group: str) -> dict:
    """Variance-homogeneity evidence and imbalance.

    Returns Levene *and* Brown-Forsythe (median-centred, robust to non-normality)
    because they disagree exactly when it matters -- skewed data.
    """
    d = df[[outcome, group]].dropna()
    samples = [_clean(s[outcome]) for _, s in d.groupby(group, observed=True)]
    samples = [s for s in samples if s.size > 1]
    if len(samples) < 2:
        return {"error": "fewer than two usable groups", "n_groups": len(samples)}

    lev_s, lev_p = stats.levene(*samples, center="mean")
    bf_s, bf_p = stats.levene(*samples, center="median")
    variances = [float(s.var(ddof=1)) for s in samples]
    ns = [int(s.size) for s in samples]
    pooled = sum((n - 1) * v for n, v in zip(ns, variances)) / (sum(ns) - len(ns))

    return {
        "n_groups": len(samples),
        "group_ns": ns,
        "group_variances": variances,
        "variance_ratio": float(max(variances) / min(variances)) if min(variances) > 0 else float("inf"),
        "pooled_variance": float(pooled),
        "levene_statistic": float(lev_s), "levene_p": float(lev_p),
        "brown_forsythe_statistic": float(bf_s), "brown_forsythe_p": float(bf_p),
        "group_size_ratio": float(max(ns) / min(ns)),
        "balanced": bool(max(ns) / min(ns) < 1.5),
        "min_group_n": int(min(ns)),
        "total_n": int(sum(ns)),
    }


def check_contingency(df: pd.DataFrame, var1: str, var2: str) -> dict:
    """Observed/expected cells and sparsity -- decides chi-square vs Fisher."""
    table = pd.crosstab(df[var1], df[var2])
    obs = table.to_numpy()
    if obs.size == 0 or obs.sum() == 0:
        return {"error": "empty contingency table"}
    chi2, p, dof, exp = stats.chi2_contingency(obs)
    return {
        "n_rows": int(obs.shape[0]), "n_cols": int(obs.shape[1]),
        "is_2x2": bool(obs.shape == (2, 2)),
        "row_labels": [str(x) for x in table.index],
        "col_labels": [str(x) for x in table.columns],
        "observed": obs.tolist(),
        "expected": np.round(exp, 4).tolist(),
        "total_n": int(obs.sum()),
        "min_expected": float(exp.min()),
        "n_cells_expected_lt_5": int((exp < 5).sum()),
        "pct_cells_expected_lt_5": float((exp < 5).mean() * 100),
        "n_structural_zeros": int((obs == 0).sum()),
        "chi2_eligible": bool((exp >= 5).mean() >= 0.8 and exp.min() >= 1),
        "fisher_eligible": bool(obs.shape == (2, 2)),
        "degrees_of_freedom": int(dof),
    }


def check_association(df: pd.DataFrame, x: str, y: str) -> dict:
    """Linearity vs monotonicity, influence, and range restriction."""
    d = df[[x, y]].dropna()
    xv, yv = d[x].to_numpy(float), d[y].to_numpy(float)
    n = len(xv)
    if n < 3:
        return {"error": "fewer than three complete pairs", "n": n}

    pear_r, pear_p = stats.pearsonr(xv, yv)
    spear_r, spear_p = stats.spearmanr(xv, yv)

    # Linearity evidence: does a quadratic term add explanatory power?
    lin = np.polyfit(xv, yv, 1)
    resid_lin = yv - np.polyval(lin, xv)
    ss_lin = float((resid_lin**2).sum())
    ss_quad = ss_lin
    if n > 4:
        quad = np.polyfit(xv, yv, 2)
        ss_quad = float(((yv - np.polyval(quad, xv)) ** 2).sum())
    ss_tot = float(((yv - yv.mean()) ** 2).sum())

    # Influence: leverage from the simple-regression hat diagonal.
    sxx = float(((xv - xv.mean()) ** 2).sum())
    lev = 1.0 / n + (xv - xv.mean()) ** 2 / sxx if sxx > 0 else np.full(n, 1.0 / n)
    high_lev = int((lev > 3 * (2.0 / n)).sum())

    # Leave-one-out stability of Pearson r.
    max_delta = 0.0
    if 4 <= n <= 4000:
        for i in range(n):
            m = np.ones(n, bool); m[i] = False
            if np.std(xv[m]) > 0 and np.std(yv[m]) > 0:
                max_delta = max(max_delta, abs(np.corrcoef(xv[m], yv[m])[0, 1] - pear_r))

    return {
        "n": int(n),
        "pearson_r": float(pear_r), "pearson_p": float(pear_p),
        "spearman_rho": float(spear_r), "spearman_p": float(spear_p),
        "abs_r_difference": float(abs(abs(spear_r) - abs(pear_r))),
        "linear_r_squared": float(1 - ss_lin / ss_tot) if ss_tot else float("nan"),
        "quadratic_r_squared": float(1 - ss_quad / ss_tot) if ss_tot else float("nan"),
        "quadratic_gain": float((ss_lin - ss_quad) / ss_tot) if ss_tot else 0.0,
        "x_unique": int(len(np.unique(xv))), "y_unique": int(len(np.unique(yv))),
        "x_range_ratio": float(np.ptp(xv) / np.std(xv)) if np.std(xv) > 0 else float("nan"),
        "n_high_leverage": high_lev,
        "max_loo_r_change": float(max_delta),
        "x_skew": float(stats.skew(xv)), "y_skew": float(stats.skew(yv)),
        "x_is_monotonic": bool(pd.Series(xv).is_monotonic_increasing),
    }
