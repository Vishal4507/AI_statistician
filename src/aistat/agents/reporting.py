"""Report composition under the provenance contract (review finding F-A4).

Every number in these blocks is a ``{{ref}}`` into the ResultStore.  Nothing
here formats a value; the renderer substitutes at the end.  This module doubles
as the worked example the live prompt shows the model.
"""
from __future__ import annotations

from typing import Any

from aistat.schemas.core import ABSTAIN

_ESTIMATE_LABEL = {
    "student_t": "mean difference", "welch_t": "mean difference",
    "mann_whitney": "Hodges-Lehmann location shift",
    "one_way_anova": "largest group mean difference",
    "welch_anova": "largest group mean difference",
    "kruskal_wallis": "largest group median difference",
    "chi_square": "Cramer's V", "fisher_exact": "odds ratio",
    "pearson": "Pearson correlation", "spearman": "Spearman correlation",
}


def _has(store, ref: str) -> bool:
    return ref in store


def compose_report(ctx: dict[str, Any]) -> dict:
    store = ctx["store"]
    sel = ctx["selection"]
    method = sel["method"]
    task = ctx["task"]
    case_id = ctx["case_id"]
    card = ctx["card"]
    rid = ctx.get("result_call_id")
    diag = ctx.get("diagnostic_refs", {})

    outcome = task.outcome or task.var1 or "the outcome"
    group = task.group or "the groups"
    unit = card.get("observational_unit", "observation")
    population = card.get("intended_population", "the sampled population")
    randomized = card.get("randomized") is True

    problem = (
        f"The question asks about {outcome}"
        + (f" across {group}" if task.group else "")
        + f". The observational unit is one {unit}, and the intended population is "
        f"{population}. The estimand is the "
        f"{_ESTIMATE_LABEL.get(method, 'model-implied association')}."
    )

    # --- data audit -------------------------------------------------------
    audit_bits = []
    if diag.get("n_rows"):
        audit_bits.append(f"The analysis table holds {{{{{diag['n_rows']}}}}} rows")
    if diag.get("total_n"):
        audit_bits.append(f"with {{{{{diag['total_n']}}}}} usable observations")
    if diag.get("min_group_n"):
        audit_bits.append(
            f"and group sizes from {{{{{diag['min_group_n']}}}}} to "
            f"{{{{{diag['max_group_n']}}}}}")
    audit = ". ".join([", ".join(audit_bits)]) if audit_bits else \
        "The analysis table was inspected for missingness, duplicates and repeated identifiers"
    audit += "."
    if card.get("repeated_id_column"):
        audit += (f" The design card names {card['repeated_id_column']} as a repeated "
                  "identifier, so rows are not independent.")
    elif card.get("time_column"):
        audit += (f" The design card names {card['time_column']} as a time index, so "
                  "rows are ordered in time.")
    else:
        audit += " The design card reports independent observations with no pairing or clustering."

    # --- abstention path --------------------------------------------------
    if method == ABSTAIN:
        reason = sel.get("abstain_reason") or "design_validity"
        decision = (
            f"No method in the supported library is valid for this design, so the "
            f"correct decision is to abstain. Reason: {reason.replace('_', ' ')}. "
            + str(sel.get("_rationale", ""))
        )
        return {
            "case_id": case_id,
            "problem_statement": {"text": problem},
            "data_audit": {"text": audit},
            "method_decision": {"text": decision},
            "results": {"text": ("No estimate is reported. Producing one would "
                                 "require an assumption the design does not support.")},
            "interpretation": {"text": (
                "The substantive question cannot be answered from these data with "
                "the available methods. A design-appropriate model would be needed "
                "before any claim about " + outcome + " is warranted.")},
            "limitations": {"text": (
                "The supported library covers independent-sample comparisons, "
                "categorical and continuous association, and generalised linear "
                "models. It does not cover the structure present here.")},
            "selection": {k: v for k, v in sel.items() if not k.startswith("_")},
            "trace_ids": ctx.get("evidence_refs", [])[:8],
        }

    # --- executed path ----------------------------------------------------
    decision = f"Selected method: {method.replace('_', ' ')}. {sel.get('_rationale', '')}"
    for alt, why in (sel.get("rejected_alternatives") or {}).items():
        decision += f" {alt.replace('_', ' ').title()} was rejected because {why}."

    res_bits: list[str] = []
    if rid:
        if _has(store, f"{rid}.estimate"):
            res_bits.append(
                f"The {_ESTIMATE_LABEL.get(method, 'estimate')} is "
                f"{{{{{rid}.estimate}}}}")
        if _has(store, f"{rid}.ci_low") and _has(store, f"{rid}.ci_high"):
            res_bits.append(
                f"with a 95% confidence interval of [{{{{{rid}.ci_low}}}}, "
                f"{{{{{rid}.ci_high}}}}]")
        if _has(store, f"{rid}.effect_size.value"):
            res_bits.append(
                f"The standardised effect size is {{{{{rid}.effect_size.value}}}}"
                + (f", 95% CI [{{{{{rid}.effect_size.ci_low}}}}, "
                   f"{{{{{rid}.effect_size.ci_high}}}}]"
                   if _has(store, f"{rid}.effect_size.ci_low") else ""))
        if _has(store, f"{rid}.p_value"):
            res_bits.append(f"The p-value is {{{{{rid}.p_value}}}}")
        # Model-specific diagnostics.
        for key, phrase in (
            ("pearson_dispersion", "Conditional Pearson dispersion is {}"),
            ("r_squared", "The model explains a proportion {} of variance"),
            ("auc", "Discrimination measured by AUC is {}"),
            ("max_vif", "The largest variance inflation factor is {}"),
            ("breusch_pagan_p", "The Breusch-Pagan p-value is {}"),
            ("nb_alpha", "The estimated dispersion parameter alpha is {}"),
            ("events_per_parameter", "There are {} events per parameter"),
        ):
            if _has(store, f"{rid}.{key}"):
                res_bits.append(phrase.format(f"{{{{{rid}.{key}}}}}"))
        if _has(store, f"{rid}.coefficients[1].estimate"):
            res_bits.append(
                f"The leading predictor coefficient is "
                f"{{{{{rid}.coefficients[1].estimate}}}}, 95% CI "
                f"[{{{{{rid}.coefficients[1].ci_low}}}}, "
                f"{{{{{rid}.coefficients[1].ci_high}}}}]")
    results = ". ".join(res_bits) + "." if res_bits else \
        "The selected method executed and returned an estimate."

    # Magnitude first, then evidence (blueprint section 7).
    verb = "association" if method in ("pearson", "spearman", "chi_square",
                                       "fisher_exact") else "difference"
    interp = (
        f"In practical terms, the estimated {verb} between {group} in {outcome} has "
        f"magnitude {{{{{rid}.estimate}}}}" if rid and _has(store, f"{rid}.estimate")
        else f"The estimated {verb} is reported above")
    interp += (
        ", and the confidence interval indicates the range consistent with these data. "
        if rid and _has(store, f"{rid}.ci_low") else ". ")
    interp += (
        "Because the groups were randomised, a causal reading is supported."
        if randomized else
        "These are observational groups, so the finding describes an association "
        "and does not establish that changing one variable would change the other.")
    if method in ("mann_whitney", "kruskal_wallis"):
        interp += (" The rank test describes stochastic ordering rather than a "
                   "difference in medians.")

    limits = [
        f"The estimate applies to {population} and to the {unit} as the unit of analysis."
    ]
    if not randomized:
        limits.append("Assignment was not randomised, so unmeasured differences "
                      "between groups cannot be excluded.")
    if rid and _has(store, f"{rid}.heteroscedasticity_flag"):
        limits.append("Residual variance is not constant across fitted values, which "
                      "widens the practical uncertainty around individual predictions.")
    if rid and _has(store, f"{rid}.collinearity_concern"):
        limits.append("Predictors are correlated, so individual coefficients are less "
                      "stable than the model fit as a whole.")

    return {
        "case_id": case_id,
        "problem_statement": {"text": problem},
        "data_audit": {"text": audit},
        "method_decision": {"text": decision},
        "results": {"text": results},
        "interpretation": {"text": interp},
        "limitations": {"text": " ".join(limits)},
        "selection": {k: v for k, v in sel.items() if not k.startswith("_")},
        "trace_ids": ctx.get("evidence_refs", [])[:8],
    }
