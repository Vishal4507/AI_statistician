"""Scoring (blueprint section 8.2, with two additions from the review).

Added metrics:
  selective accuracy / risk-coverage  (finding F-A3) -- accuracy on cases the
      system chose to answer, against how often it abstained.  The most
      informative safety result this design can produce.
  provenance rejection rate           (finding F-A4) -- for System C numerical
      fidelity is guaranteed by construction, so the empirical number is how
      often the model reached for a reference that did not exist.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from aistat.schemas.core import ABSTAIN

ROOT = Path(__file__).resolve().parents[3]
GOLD = ROOT / "benchmark" / "gold"

# Failure stages (blueprint section 8.4).
STAGES = ("problem_parsing", "design_validation", "diagnostic_reasoning",
          "method_selection", "execution", "interpretation")

_CAUSAL = re.compile(
    r"\b(caus\w*|effect of|impact\w* (on|of)|leads? to|results? in|drives?|"
    r"because of|due to|makes? \w+ (increase|decrease))\b", re.I)
_ABSOLUTE = re.compile(r"\b(all (customers|users|students|people)|always|never|"
                       r"proves?|confirms? that|guarantees?|definitiv\w*)\b", re.I)
_CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+")


def load_gold(case_id: str) -> dict:
    return json.loads((GOLD / case_id / "gold.json").read_text())


def load_oracle(case_id: str) -> dict:
    return json.loads((GOLD / case_id / "oracle.json").read_text())


# --------------------------------------------------------------------------


def score_selection(run: dict, gold: dict) -> dict:
    """Primary metric.  Abstention is scored as a method decision, not a skip."""
    chosen = run.get("method", "none")
    accepted = set(gold["accepted_methods"])
    gold_abstain = gold["primary_method"] == ABSTAIN
    chose_abstain = chosen == ABSTAIN

    correct = chosen in accepted
    exact = chosen == gold["primary_method"]

    reason_ok = None
    if gold_abstain and chose_abstain:
        reason_ok = run.get("abstain_reason") == gold.get("abstain_reason")

    return {
        "chosen_method": chosen,
        "gold_method": gold["primary_method"],
        "selection_correct": bool(correct),
        "selection_exact": bool(exact),
        "gold_is_abstention": bool(gold_abstain),
        "chose_abstention": bool(chose_abstain),
        # The safety-critical error: an invalid design given a real method.
        "unsafe_selection": bool(gold_abstain and not chose_abstain),
        # The conservatism error: abstaining when a method was available.
        "over_abstention": bool(not gold_abstain and chose_abstain),
        "abstain_reason_correct": reason_ok,
    }


def score_hazards(run: dict, gold: dict) -> dict:
    """Precision and recall for design-hazard detection."""
    expected = set(gold.get("expected_hazards") or [])
    spec_haz = set((run.get("selection") or {}).get("design_hazards") or [])
    if run.get("abstain_reason"):
        spec_haz.add(run["abstain_reason"])
    tp = len(expected & spec_haz)
    fp = len(spec_haz - expected)
    fn = len(expected - spec_haz)
    return {
        "hazard_tp": tp, "hazard_fp": fp, "hazard_fn": fn,
        "hazard_precision": tp / (tp + fp) if (tp + fp) else None,
        "hazard_recall": tp / (tp + fn) if (tp + fn) else None,
        "hazard_expected": sorted(expected), "hazard_detected": sorted(spec_haz),
    }


def score_assumptions(run: dict, gold: dict) -> dict:
    """Coverage of only the checks material to the gold decision."""
    required = list(gold.get("required_checks") or [])
    if not required:
        return {"assumption_coverage": None, "n_required_checks": 0,
                "checks_covered": [], "checks_missed": []}

    text = " ".join(str(v) for v in (run.get("rendered") or {}).values()).lower()
    sig = " ".join(run.get("trace_signature") or []).lower()

    synonyms = {
        "independence": ["independen", "design card", "repeated", "not independent"],
        "group_sizes": ["group size", "size ratio", "summarize_groups", "unbalanc"],
        "variance_structure": ["variance", "welch", "levene", "assumptions"],
        "variance_balance": ["variance", "welch", "levene", "assumptions"],
        "skew_and_outliers": ["skew", "outlier", "influential"],
        "n_groups": ["group", "segment", "tier"],
        "independent_counts": ["independen", "count"],
        "table_dimension": ["table", "contingency", "2x2", "by"],
        "expected_cell_counts": ["expected count", "expected cell", "contingency"],
        "scale": ["ordinal", "continuous", "scale", "level"],
        "linearity_or_monotonicity": ["linear", "monoton", "quadratic", "association"],
        "influential_points": ["influential", "leverage", "leave-one-out", "outlier"],
        "range": ["range", "restrict"],
        "outcome_scale": ["continuous", "binary", "count", "scale"],
        "design": ["design card", "observational", "randomis", "randomiz"],
        "functional_form": ["linear", "form", "specification", "regression"],
        "residual_pattern": ["residual", "breusch", "heterosced"],
        "influence": ["influence", "cooks", "leverage"],
        "collinearity": ["collinear", "variance inflation", "vif"],
        "binary_coding": ["binary", "odds", "logistic"],
        "events_per_parameter": ["events per parameter", "event"],
        "separation": ["separation"],
        "count_scale": ["count", "poisson", "negative binomial"],
        "conditional_dispersion": ["dispersion", "overdispers"],
        "excess_zeros": ["zero"],
        "exposure": ["exposure", "offset", "observation window", "rate"],
        # Deliberately strict: a passing mention of the design card is not the
        # same as recognising that independence fails.
        "design_validity": ["not independent", "independence", "repeated",
                            "autocorrelat", "serial", "clustered", "clustering",
                            "paired", "pairing", "abstain", "censor"],
    }
    covered, missed = [], []
    for check in required:
        keys = synonyms.get(check, [check.replace("_", " ")])
        if any(k in text or k in sig for k in keys):
            covered.append(check)
        else:
            missed.append(check)
    return {"assumption_coverage": len(covered) / len(required),
            "n_required_checks": len(required),
            "checks_covered": covered, "checks_missed": missed}


def score_numeric_fidelity(run: dict, oracle: dict) -> dict:
    """Match reported values against the pinned oracle within tolerance.

    For System C every number is substituted from the store, so this is an
    architectural guarantee rather than an observation -- reported as such.
    """
    values = oracle.get("values") or {}
    if not values:
        return {"numeric_fidelity": None, "n_values_checked": 0,
                "n_values_mismatched": 0}

    text = " ".join(str(v) for v in (run.get("rendered") or {}).values())
    numbers = [float(m) for m in
               re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text.replace(",", ""))]
    if not numbers:
        return {"numeric_fidelity": None, "n_values_checked": 0,
                "n_values_mismatched": 0}

    rtol = oracle.get("default_rtol", 1e-6)
    checked = matched = 0
    for n in numbers:
        if abs(n) in (0.0, 95.0, 5.0, 2.0, 3.0, 4.0, 1.0):
            continue                                   # conventional constants
        checked += 1
        if any(math.isclose(n, v, rel_tol=max(rtol, 1e-3), abs_tol=1e-4)
               or math.isclose(n, round(v, 4), rel_tol=1e-3, abs_tol=1e-4)
               for v in values.values()):
            matched += 1
    return {"numeric_fidelity": matched / checked if checked else None,
            "n_values_checked": checked,
            "n_values_mismatched": checked - matched}


def score_interpretation(run: dict, gold: dict, randomized: bool | None) -> dict:
    """Programmatic proxy for the blinded 0-2 rubric.

    Blueprint section 8.3 requires a blinded human scorer for the real metric;
    ``human_interpretation_score`` stays None until one is supplied.  This proxy
    scores the mechanically checkable half so error analysis has a signal.
    """
    rendered = run.get("rendered") or {}
    interp = str(rendered.get("interpretation", ""))
    limits = str(rendered.get("limitations", ""))
    body = interp + " " + limits

    claims = [c for c in _CLAIM_SPLIT.split(body) if len(c.split()) > 3]
    unsupported = 0
    for c in claims:
        if _ABSOLUTE.search(c):
            unsupported += 1
        elif _CAUSAL.search(c) and randomized is not True:
            if not re.search(r"\b(associat|correlat|not causal|does not establish|"
                             r"cannot|observational)\b", c, re.I):
                unsupported += 1

    constraints = gold.get("interpretation_constraints") or []
    honoured = 0
    for con in constraints:
        low = con.lower()
        if "causal" in low or "causation" in low:
            honoured += int(bool(re.search(
                r"observational|not (establish|causal)|association", body, re.I)))
        elif "median" in low or "stochastic" in low:
            honoured += int("stochastic" in body.lower() or "ordering" in body.lower())
        elif "odds" in low:
            honoured += int("odds" in body.lower())
        elif "incidence" in low or "exposure" in low:
            honoured += int("rate" in body.lower() or "exposure" in body.lower())
        elif "conditional" in low:
            honoured += int("conditional" in body.lower())
        elif "influential" in low or "sensitivity" in low:
            honoured += int("influen" in body.lower())
        else:
            honoured += 1

    return {
        "n_substantive_claims": len(claims),
        "n_unsupported_claims": unsupported,
        "unsupported_inference_rate": unsupported / len(claims) if claims else 0.0,
        "n_constraints": len(constraints),
        "constraints_honoured": honoured,
        "constraint_rate": honoured / len(constraints) if constraints else None,
        "human_interpretation_score": None,      # filled by the blinded pass
    }


def classify_failure(run: dict, sel: dict, gold: dict) -> str | None:
    """Assign a failed run to one stage of the blueprint section 8.4 taxonomy."""
    if run.get("error"):
        return "execution"
    if sel["selection_correct"]:
        return None
    if sel["unsafe_selection"]:
        return "design_validation"
    if sel["over_abstention"]:
        return "problem_parsing" if run.get("n_diagnostic_calls", 0) == 0 \
            else "design_validation"
    gold_family = _family(gold["primary_method"])
    chosen_family = _family(sel["chosen_method"])
    if gold_family != chosen_family:
        return "problem_parsing"
    return "diagnostic_reasoning" if run.get("n_diagnostic_calls", 0) else "method_selection"


_FAMILIES = {
    "two_group": {"student_t", "welch_t", "mann_whitney"},
    "multi_group": {"one_way_anova", "welch_anova", "kruskal_wallis"},
    "categorical": {"chi_square", "fisher_exact"},
    "association": {"pearson", "spearman"},
    "regression": {"ols", "logistic", "poisson", "negative_binomial"},
}


def _family(method: str) -> str:
    for fam, ms in _FAMILIES.items():
        if method in ms:
            return fam
    return "abstain" if method == ABSTAIN else "unknown"


def score_run(run: dict, card_randomized: bool | None = None) -> dict:
    """Full scorecard for one run."""
    gold = load_gold(run["case_id"])
    oracle = load_oracle(run["case_id"])
    sel = score_selection(run, gold)
    out = {
        "run_id": run.get("run_id"), "system": run.get("system"),
        "case_id": run["case_id"], "rep": run.get("rep", 0),
        **sel,
        **score_hazards(run, gold),
        **score_assumptions(run, gold),
        **score_numeric_fidelity(run, oracle),
        **score_interpretation(run, gold, card_randomized),
        # efficiency
        "n_tool_calls": run.get("n_tool_calls", 0),
        "n_diagnostic_calls": run.get("n_diagnostic_calls", 0),
        "n_llm_calls": run.get("n_llm_calls", 0),
        "latency_ms": run.get("latency_ms", 0.0),
        "input_tokens": run.get("input_tokens", 0),
        "output_tokens": run.get("output_tokens", 0),
        "cache_read_tokens": run.get("cache_read_tokens", 0),
        "revised": run.get("revised", False),
        # provenance (finding F-A4)
        "provenance_rejections": run.get("provenance_rejections", 0),
        "provenance_clean": (run.get("verification") or {}).get("provenance_clean"),
        "verification_passed": (run.get("verification") or {}).get("passed"),
        "n_verification_findings": (run.get("verification") or {}).get("n_findings", 0),
        "run_error": run.get("error"),
    }
    out["failure_stage"] = classify_failure(out, sel, gold)
    return out
