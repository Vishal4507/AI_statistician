"""Public-data case construction (blueprint section 4.4).

Twelve supported cases from Bank Marketing, Online Shoppers and Student
Performance, plus four Seoul Bike design-hazard cases where the table looks
suitable for a common method but hourly ordering violates independence.

These are the sixteen cases that genuinely need adjudication (review finding
F-B1): the label is proposed from design reasoning, then *checked against the
realised data* by ``validate_label``.  A label that the data contradicts is
reported rather than silently kept.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from aistat.tools import diagnostics

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"

# Design cards per source (blueprint section 3.1 'Planned use').
CARDS = {
    "bank_marketing": {
        "observational_unit": "client contact", "sampling_unit": "client contact",
        "repeated_id_column": None, "time_column": None, "pairing": False,
        "clustering_column": None, "randomized": False,
        "intended_population": "clients contacted in the marketing campaign",
        "known_missingness": "'unknown' is used as a category level in several fields",
    },
    "online_shoppers": {
        "observational_unit": "browsing session", "sampling_unit": "browsing session",
        "repeated_id_column": None, "time_column": None, "pairing": False,
        "clustering_column": None, "randomized": False,
        "intended_population": "sessions on the retailer's site over one year",
        "known_missingness": "source states each session belongs to a different user",
    },
    "student_performance": {
        "observational_unit": "student", "sampling_unit": "student",
        "repeated_id_column": None, "time_column": None, "pairing": False,
        "clustering_column": None, "randomized": False,
        "intended_population": "Portuguese-course students at two schools",
        "known_missingness": None,
    },
    "seoul_bike": {
        "observational_unit": "hourly observation", "sampling_unit": "hourly observation",
        "repeated_id_column": None, "time_column": "Date_Hour", "pairing": False,
        "clustering_column": None, "randomized": False,
        "intended_population": "hourly rental demand in Seoul over one year",
        "known_missingness": None,
    },
}

_ABSTAIN_RATIONALE = (
    "Rows are consecutive hourly observations of the same city system. Rental "
    "counts are strongly autocorrelated, so every in-scope method's independence "
    "assumption fails regardless of how well the variable types fit."
)


def load_raw(dataset: str) -> pd.DataFrame:
    path = RAW / f"{dataset}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing -- run scripts/acquire_data.py first")
    return pd.read_csv(path, low_memory=False)


def build_case(spec: dict) -> tuple[pd.DataFrame, dict, dict]:
    """Return ``(dataframe, design_card, gold)`` for one public case."""
    ds = spec["dataset"]
    raw = load_raw(ds)
    v = spec["vars"]
    seed = abs(hash(spec["case_id"])) % (2**31)

    if ds == "seoul_bike":
        raw = raw.copy()
        raw["Date_Hour"] = raw["Date"].astype(str) + "T" + raw["Hour"].astype(str)
        # Contiguous block, preserving order -- the hazard is the ordering itself.
        n = spec.get("n_sample") or len(raw)
        raw = raw.iloc[:n].reset_index(drop=True)
        cols = ["Date_Hour", "Hour", "Seasons", "Holiday", "Temperature",
                "Humidity", "Rainfall", "Rented Bike Count"]
        df = raw[[c for c in cols if c in raw.columns]].copy()
        gold = {
            "primary_method": "abstain", "accepted_methods": ["abstain"],
            "required_checks": ["design_validity", "independence"],
            "abstain_reason": spec["abstain_reason"],
            "expected_hazards": ["serial_dependence"],
            "interpretation_constraints": ["no in-scope method models serial dependence"],
            "rationale": _ABSTAIN_RATIONALE,
        }
        return df, dict(CARDS[ds]), gold

    keep: list[str] = []
    for key in ("outcome", "group", "var1", "var2", "x", "y"):
        if key in v:
            keep.append(v[key])
    keep += list(v.get("predictors", []))
    keep = [c for c in dict.fromkeys(keep) if c in raw.columns]
    df = raw[keep].dropna().copy()

    n = spec.get("n_sample") or 0
    if n and len(df) > n:
        df = df.sample(n=n, random_state=seed).reset_index(drop=True)

    # Cast booleans to readable labels so the agent sees a real categorical.
    for c in df.columns:
        if df[c].dtype == bool:
            df[c] = df[c].map({True: "yes", False: "no"})

    gold = _derive_gold(spec, df)
    return df, dict(CARDS[ds]), gold


def _derive_gold(spec: dict, df: pd.DataFrame) -> dict:
    """Proposed label plus the data-based rationale that supports it."""
    expected = spec["expected"]
    v = spec["vars"]
    accepted = [expected]
    checks = ["independence"]
    rationale = ""
    constraints = ["observational data: association, not causation"]

    if spec["recipe"] in ("two_group", "two_group_mean"):
        a = diagnostics.check_group_assumptions(df, v["outcome"], v["group"])
        s_ = diagnostics.summarize_groups(df, v["outcome"], v["group"])
        checks += ["group_sizes", "variance_structure", "skew_and_outliers"]
        rationale = (f"variance ratio {a.get('variance_ratio', float('nan')):.2f}, "
                     f"group sizes {a.get('group_ns')}, "
                     f"max |skew| {s_.get('max_abs_skew', float('nan')):.2f}")
        if expected == "mann_whitney":
            accepted = ["mann_whitney"]
            constraints.append("describe stochastic ordering, not medians")
        else:
            accepted = ["welch_t"]
            # Blueprint section 2: Student requires an affirmative equal-variance
            # justification. When variances, group sizes and skew are all mild,
            # that justification exists and both choices are defensible -- an
            # ambiguous case does not get a brittle label (section 4.3).
            vr = a.get("variance_ratio", 99.0)
            gr = a.get("group_size_ratio", 99.0)
            sk = s_.get("max_abs_skew", 99.0)
            if vr < 1.5 and gr < 1.5 and sk < 1.5:
                accepted = ["welch_t", "student_t"]
                rationale += " (mild on all three axes: Student is affirmatively "
                rationale += "justified and Welch remains defensible)"
    elif spec["recipe"] == "multi_group":
        a = diagnostics.check_group_assumptions(df, v["outcome"], v["group"])
        sm = diagnostics.summarize_groups(df, v["outcome"], v["group"])
        checks += ["n_groups", "variance_balance", "skew_and_outliers"]
        skew = sm.get("max_abs_skew", 0.0)
        rationale = (f"{a.get('n_groups')} groups, variance ratio "
                     f"{a.get('variance_ratio', float('nan')):.2f}, sizes "
                     f"{a.get('group_ns')}, max |skew| {skew:.2f}")
        # Material skew alongside imbalance makes the rank test equally
        # defensible; an ambiguous case does not get a brittle label
        # (blueprint section 4.3).
        accepted = ["welch_anova"] + (["kruskal_wallis"] if skew > 1.4 else [])
        if skew > 1.4:
            constraints.append("if a rank test is used, describe stochastic ordering")
    elif spec["recipe"] == "chi_square":
        c = diagnostics.check_contingency(df, v["var1"], v["var2"])
        checks += ["independent_counts", "expected_cell_counts", "table_dimension"]
        rationale = (f"{c.get('n_rows')}x{c.get('n_cols')} table, min expected "
                     f"{c.get('min_expected', float('nan')):.1f}, "
                     f"{c.get('n_cells_expected_lt_5')} cells below 5")
        constraints.append("association, not individual risk")
    elif spec["recipe"] == "association":
        a = diagnostics.check_association(df, v["x"], v["y"])
        checks += ["scale", "linearity_or_monotonicity", "influential_points"]
        rationale = (f"Pearson {a.get('pearson_r', float('nan')):.3f} vs Spearman "
                     f"{a.get('spearman_rho', float('nan')):.3f}, quadratic gain "
                     f"{a.get('quadratic_gain', float('nan')):.3f}, "
                     f"{a.get('n_high_leverage')} high-leverage points")
        # Influence makes the product-moment choice arguable; accept both
        # rather than impose a brittle label (blueprint section 4.3).
        if expected == "pearson" and a.get("n_high_leverage", 0) > 0.02 * len(df):
            accepted = ["pearson", "spearman"]
            constraints.append("report sensitivity to influential points")
    elif spec["recipe"] == "logistic":
        checks += ["binary_coding", "events_per_parameter", "separation", "collinearity"]
        constraints.append("report odds ratios, not probability changes")
    elif spec["recipe"] == "ols":
        checks += ["functional_form", "residual_pattern", "influence", "collinearity"]
        constraints.append("coefficients are conditional on included variables")

    return {"primary_method": expected, "accepted_methods": accepted,
            "required_checks": checks, "abstain_reason": None,
            "expected_hazards": [], "interpretation_constraints": constraints,
            "rationale": rationale}


def validate_label(spec: dict, df: pd.DataFrame, gold: dict) -> list[str]:
    """Check a proposed public label against the realised data.

    Returns a list of contradictions.  Empty means the data supports the label.
    """
    problems: list[str] = []
    v, exp = spec["vars"], gold["primary_method"]

    if spec["recipe"] in ("two_group", "two_group_mean"):
        a = diagnostics.check_group_assumptions(df, v["outcome"], v["group"])
        s = diagnostics.summarize_groups(df, v["outcome"], v["group"])
        vr, skew = a.get("variance_ratio", 1.0), s.get("max_abs_skew", 0.0)
        if exp == "welch_t" and skew > 2.0:
            problems.append(f"label welch_t but max|skew|={skew:.2f} favours a rank test")
        if exp == "mann_whitney" and skew < 1.0:
            problems.append(f"label mann_whitney but max|skew|={skew:.2f} is mild")
        if exp == "student_t" and vr > 2.0:
            problems.append(f"label student_t but variance ratio={vr:.2f}")
    elif spec["recipe"] == "multi_group":
        a = diagnostics.check_group_assumptions(df, v["outcome"], v["group"])
        if exp == "welch_anova" and a.get("variance_ratio", 1.0) < 1.5 and a.get("balanced"):
            problems.append("label welch_anova but variances and sizes look homogeneous")
    elif spec["recipe"] == "chi_square":
        c = diagnostics.check_contingency(df, v["var1"], v["var2"])
        if exp == "chi_square" and not c.get("chi2_eligible", True):
            problems.append(f"label chi_square but min expected={c.get('min_expected'):.1f}")
    elif spec["recipe"] == "association":
        a = diagnostics.check_association(df, v["x"], v["y"])
        pr, sr = abs(a.get("pearson_r", 0)), abs(a.get("spearman_rho", 0))
        if exp == "spearman" and sr < pr - 0.02 and a.get("quadratic_gain", 0) < 0.01:
            problems.append(f"label spearman but Pearson({pr:.3f}) >= Spearman({sr:.3f}) "
                            "and the relationship looks linear")
        if exp == "pearson" and sr > pr + 0.08:
            problems.append(f"label pearson but Spearman({sr:.3f}) clearly exceeds "
                            f"Pearson({pr:.3f})")
    elif spec["recipe"] == "logistic":
        yv = df[v["outcome"]]
        if yv.nunique() != 2:
            problems.append(f"label logistic but outcome has {yv.nunique()} levels")
    return problems
