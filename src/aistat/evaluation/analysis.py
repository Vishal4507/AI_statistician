"""Result analysis (blueprint section 8.3).

Case-level bootstrap intervals on paired differences, McNemar for the paired
B-versus-C comparison, per-case majority decisions with run-to-run variability,
and the risk-coverage curve added by review finding F-A3.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def majority_by_case(scores: pd.DataFrame) -> pd.DataFrame:
    """Per (system, case) majority decision plus repetition agreement."""
    rows = []
    for (sysname, case), g in scores.groupby(["system", "case_id"]):
        methods = g["chosen_method"].tolist()
        top = max(set(methods), key=methods.count)
        rows.append({
            "system": sysname, "case_id": case,
            "majority_method": top,
            "majority_correct": bool(g.loc[g["chosen_method"] == top,
                                           "selection_correct"].iloc[0]),
            "mean_correct": float(g["selection_correct"].mean()),
            "n_reps": len(g),
            "rep_agreement": methods.count(top) / len(methods),
            "unanimous": len(set(methods)) == 1,
            "gold_is_abstention": bool(g["gold_is_abstention"].iloc[0]),
            "chose_abstention": bool(g["chose_abstention"].mode().iloc[0]),
            "unsafe_selection": bool(g["unsafe_selection"].mean() > 0.5),
        })
    return pd.DataFrame(rows)


def bootstrap_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 10000,
                   seed: int = 0, conf: float = 0.95) -> dict:
    """Case-level bootstrap CI on a paired accuracy difference (b - a)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.size != b.size or a.size == 0:
        return {"diff": float("nan"), "ci_low": float("nan"),
                "ci_high": float("nan"), "n": int(a.size)}
    rng = np.random.default_rng(seed)
    n = a.size
    idx = rng.integers(0, n, size=(n_boot, n))
    diffs = b[idx].mean(axis=1) - a[idx].mean(axis=1)
    lo, hi = np.percentile(diffs, [(1 - conf) / 2 * 100, (1 + conf) / 2 * 100])
    return {"diff": float(b.mean() - a.mean()), "ci_low": float(lo),
            "ci_high": float(hi), "n": int(n),
            "p_boot_two_sided": float(2 * min((diffs <= 0).mean(),
                                              (diffs >= 0).mean()))}


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict:
    """Exact McNemar on paired correct/incorrect outcomes."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    n01 = int((~a & b).sum())      # a wrong, b right
    n10 = int((a & ~b).sum())      # a right, b wrong
    n = n01 + n10
    p = float(stats.binomtest(n01, n, 0.5).pvalue) if n else 1.0
    return {"b_only_correct": n01, "a_only_correct": n10,
            "n_discordant": n, "p_value": p,
            "odds_ratio": (n01 / n10) if n10 else float("inf") if n01 else float("nan")}


def risk_coverage(scores: pd.DataFrame) -> pd.DataFrame:
    """Selective accuracy against abstention rate (review finding F-A3).

    Coverage is the share of cases the system chose to answer.  Selective
    accuracy is accuracy among those.  A system that abstains only when it
    should will show high accuracy at high coverage.
    """
    rows = []
    for sysname, g in scores.groupby("system"):
        answered = g[~g["chose_abstention"]]
        supported = g[~g["gold_is_abstention"]]
        abst_gold = g[g["gold_is_abstention"]]
        rows.append({
            "system": sysname,
            "n_runs": len(g),
            "coverage": float((~g["chose_abstention"]).mean()),
            "selective_accuracy": float(answered["selection_correct"].mean())
            if len(answered) else float("nan"),
            "overall_accuracy": float(g["selection_correct"].mean()),
            "accuracy_on_supported": float(supported["selection_correct"].mean())
            if len(supported) else float("nan"),
            "abstention_recall": float(abst_gold["chose_abstention"].mean())
            if len(abst_gold) else float("nan"),
            "n_abstention_cases": int(len(abst_gold)),
            "unsafe_selection_rate": float(g["unsafe_selection"].mean()),
            "over_abstention_rate": float(supported["chose_abstention"].mean())
            if len(supported) else float("nan"),
        })
    return pd.DataFrame(rows).sort_values("system").reset_index(drop=True)


def wilson_ci(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Wilson interval -- correct near 0 and 1, where abstention recall lives."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    p = k / n
    den = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return (float(max(0.0, centre - half)), float(min(1.0, centre + half)))


def system_summary(scores: pd.DataFrame) -> pd.DataFrame:
    """One row per system: every headline metric with an interval where apt."""
    rows = []
    for sysname, g in scores.groupby("system"):
        n = len(g)
        k = int(g["selection_correct"].sum())
        lo, hi = wilson_ci(k, n)
        abst = g[g["gold_is_abstention"]]
        arec = int(abst["chose_abstention"].sum())
        alo, ahi = wilson_ci(arec, len(abst)) if len(abst) else (np.nan, np.nan)
        rows.append({
            "system": sysname, "n_runs": n,
            "selection_accuracy": k / n,
            "acc_ci_low": lo, "acc_ci_high": hi,
            "exact_match_rate": float(g["selection_exact"].mean()),
            "abstention_recall": arec / len(abst) if len(abst) else np.nan,
            "abst_ci_low": alo, "abst_ci_high": ahi,
            "unsafe_selection_rate": float(g["unsafe_selection"].mean()),
            "assumption_coverage": float(g["assumption_coverage"].dropna().mean()),
            "unsupported_inference_rate": float(
                g["unsupported_inference_rate"].dropna().mean()),
            "numeric_fidelity": float(g["numeric_fidelity"].dropna().mean())
            if g["numeric_fidelity"].notna().any() else np.nan,
            "provenance_rejections": int(g["provenance_rejections"].sum()),
            "verification_pass_rate": float(g["verification_passed"].dropna().mean())
            if g["verification_passed"].notna().any() else np.nan,
            "mean_tool_calls": float(g["n_tool_calls"].mean()),
            "mean_llm_calls": float(g["n_llm_calls"].mean()),
            "mean_latency_ms": float(g["latency_ms"].mean()),
            "total_input_tokens": int(g["input_tokens"].sum()),
            "total_output_tokens": int(g["output_tokens"].sum()),
            "revision_rate": float(g["revised"].mean()),
            "n_errors": int(g["run_error"].notna().sum()),
        })
    return pd.DataFrame(rows).sort_values("system").reset_index(drop=True)


def pairwise_comparisons(majority: pd.DataFrame,
                         systems: list[str] | None = None) -> pd.DataFrame:
    """Paired bootstrap and McNemar for every ordered system pair."""
    systems = systems or sorted(majority["system"].unique())
    wide = majority.pivot(index="case_id", columns="system",
                          values="majority_correct").dropna()
    rows = []
    for i, a in enumerate(systems):
        for b in systems[i + 1:]:
            if a not in wide or b not in wide:
                continue
            va, vb = wide[a].to_numpy(bool), wide[b].to_numpy(bool)
            boot = bootstrap_diff(va.astype(float), vb.astype(float))
            mc = mcnemar(va, vb)
            rows.append({
                "system_a": a, "system_b": b, "n_cases": len(wide),
                "acc_a": float(va.mean()), "acc_b": float(vb.mean()),
                "uplift_b_minus_a": boot["diff"],
                "uplift_ci_low": boot["ci_low"], "uplift_ci_high": boot["ci_high"],
                "bootstrap_p": boot["p_boot_two_sided"],
                "mcnemar_p": mc["p_value"],
                "b_only_correct": mc["b_only_correct"],
                "a_only_correct": mc["a_only_correct"],
            })
    return pd.DataFrame(rows)


def failure_taxonomy(scores: pd.DataFrame) -> pd.DataFrame:
    """Failure counts by stage and system (blueprint section 8.4)."""
    f = scores[scores["failure_stage"].notna()]
    if f.empty:
        return pd.DataFrame(columns=["system", "failure_stage", "n"])
    return (f.groupby(["system", "failure_stage"]).size()
            .reset_index(name="n").sort_values(["system", "n"],
                                               ascending=[True, False]))
