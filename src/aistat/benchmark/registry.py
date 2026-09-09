"""Declarative case registry (review finding F-B1).

A case is a row of generator parameters, not a hand-authored folder.  The
builder turns each entry into the six-file package of blueprint section 4.2.

Composition (amended per review finding F-A3 -- the blueprint's 8 abstention
cases were too few to measure):

    synthetic   40 supported +  8 abstention  = 48
    public      12 supported +  4 hazard      = 16
    ---------------------------------------------
    total       52 supported + 12 abstention  = 64
    split       16 development / 48 held out

Leakage control (blueprint section 4.4): questions never name a method, and
the gold rationale never appears in any agent-visible field.
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------
# Question templates -- deliberately method-free
# --------------------------------------------------------------------------

Q = {
    "two_group": "Do {g1} and {g2} differ in {outcome}? Report the size of any difference.",
    "two_group_shift": "Is {outcome} systematically higher in one of {g1} or {g2}? "
                       "The distribution is known to be skewed and we care about "
                       "the overall shift, not the average.",
    "multi_group": "Does average {outcome} differ across the {k} segments? If so, "
                   "how large is the spread between them?",
    "multi_group_shift": "Do the {k} segments differ in {outcome}? The measure is "
                         "known to be heavily skewed.",
    "categorical": "Is there an association between {v1} and {v2}?",
    "association": "How strongly are {x} and {y} related, and what is the form of "
                   "that relationship?",
    "ols": "Which of the available predictors are related to {outcome}, and by how much?",
    "logistic": "Which predictors are associated with the odds of {outcome}, "
                "and how strong is each association?",
    "count": "What explains variation in the number of {outcome}? Quantify the "
             "association with each predictor.",
    "count_exposure": "What explains variation in the number of {outcome}? Note "
                      "that observation windows differ in length across units.",
    "abstain": "Analyse whether {what}. Use whatever approach the data supports.",
}


def _c(cid: str, family: str, split: str, question: str, objective: str,
       params: dict[str, Any], seed: int, roles: dict[str, str],
       notes: str = "") -> dict:
    return {"case_id": cid, "family": family, "origin": "synthetic",
            "split": split, "question": question, "objective": objective,
            "params": params, "seed": seed, "variable_roles": roles,
            "notes": notes}


# --------------------------------------------------------------------------
# Synthetic supported cases (40)
# --------------------------------------------------------------------------

SYNTHETIC: list[dict] = []
_s = 1000

def _add(cid, family, split, question, objective, params, roles, notes=""):
    global _s
    _s += 7
    SYNTHETIC.append(_c(cid, family, split, question, objective, params, _s, roles, notes))


# ---- student_t (3): equal variance, balanced, normal, mean estimand ----
for i, (split, n) in enumerate([("dev", 60), ("heldout", 45), ("heldout", 80)]):
    _add(f"syn_student_t_{i+1}", "two_group", split,
         Q["two_group"].format(g1="control", g2="treatment", outcome="response score"),
         "compare two independent groups on a continuous outcome",
         {"shape": "normal", "var_ratio": 1.0, "n1": n, "n2": n, "effect": 0.55,
          "estimand": "mean_difference", "outcome": "response_score", "group": "arm",
          "randomized": i == 2},
         {"response_score": "outcome", "arm": "group"},
         "equal variance, balanced")

# ---- welch_t (4): unequal variance and/or imbalance ----
for i, (split, vr, n1, n2) in enumerate(
        [("dev", 4.0, 30, 80), ("heldout", 5.5, 25, 95), ("heldout", 3.0, 50, 50),
         ("heldout", 1.0, 22, 110)]):
    _add(f"syn_welch_t_{i+1}", "two_group", "dev" if split == "dev" else "heldout",
         Q["two_group"].format(g1="plan A", g2="plan B", outcome="monthly spend"),
         "compare two independent groups on a continuous outcome",
         {"shape": "normal", "var_ratio": vr, "n1": n1, "n2": n2, "effect": 0.6,
          "estimand": "mean_difference", "outcome": "monthly_spend", "group": "plan"},
         {"monthly_spend": "outcome", "plan": "group"},
         f"variance ratio {vr}, n {n1}/{n2}")

# ---- mann_whitney (3): skew + distributional-shift estimand ----
for i, (split, shape, cont) in enumerate(
        [("dev", "lognormal", 0.0), ("heldout", "gamma", 0.0), ("heldout", "lognormal", 0.08)]):
    _add(f"syn_mann_whitney_{i+1}", "two_group", split,
         Q["two_group_shift"].format(g1="cohort one", g2="cohort two",
                                     outcome="session duration"),
         "compare the distributions of two independent groups",
         {"shape": shape, "var_ratio": 1.4, "n1": 55, "n2": 62, "effect": 0.5,
          "estimand": "distributional_shift", "contaminate": cont,
          "outcome": "session_duration", "group": "cohort"},
         {"session_duration": "outcome", "cohort": "group"},
         f"{shape} shape, shift estimand")

# ---- one_way_anova (2) ----
for i, (split, k) in enumerate([("dev", 3), ("heldout", 4)]):
    _add(f"syn_anova_{i+1}", "multi_group", split,
         Q["multi_group"].format(k=k, outcome="satisfaction score"),
         "compare three or more independent groups",
         {"k": k, "shape": "normal", "var_ratios": [1.0] * k, "ns": [55] * k,
          "outcome": "satisfaction_score", "group": "segment"},
         {"satisfaction_score": "outcome", "segment": "group"},
         "homogeneous variance, balanced")

# ---- welch_anova (3) ----
for i, (split, vrs, ns) in enumerate(
        [("dev", [1.0, 4.0, 9.0], [40, 55, 30]),
         ("heldout", [1.0, 6.0, 2.0], [60, 25, 70]),
         ("heldout", [1.0, 3.5, 8.0, 2.0], [35, 45, 30, 60])]):
    _add(f"syn_welch_anova_{i+1}", "multi_group", split,
         Q["multi_group"].format(k=len(vrs), outcome="handling time"),
         "compare three or more independent groups",
         {"k": len(vrs), "shape": "normal", "var_ratios": vrs, "ns": ns,
          "outcome": "handling_time", "group": "tier"},
         {"handling_time": "outcome", "tier": "group"},
         "heteroscedastic and unbalanced")

# ---- kruskal_wallis (2) ----
for i, (split, k) in enumerate([("dev", 3), ("heldout", 4)]):
    _add(f"syn_kruskal_{i+1}", "multi_group", split,
         Q["multi_group_shift"].format(k=k, outcome="claim amount"),
         "compare the distributions of three or more independent groups",
         {"k": k, "shape": "lognormal", "var_ratios": [1.0] * k, "ns": [48] * k,
          "outcome": "claim_amount", "group": "region"},
         {"claim_amount": "outcome", "region": "group"},
         "skewed groups")

# ---- chi_square (3) ----
for i, (split, shape, n) in enumerate(
        [("dev", (2, 3), 420), ("heldout", (3, 3), 600), ("heldout", (2, 4), 500)]):
    _add(f"syn_chi_square_{i+1}", "categorical", split,
         Q["categorical"].format(v1="acquisition channel", v2="enquiry outcome"),
         "test association between two categorical variables",
         {"n": n, "shape": list(shape), "strength": 0.22, "sparse": False,
          "var1": "channel", "var2": "enquiry_outcome"},
         {"channel": "variable", "enquiry_outcome": "variable"},
         f"{shape[0]}x{shape[1]}, adequate expected counts")

# ---- fisher_exact (2) ----
for i, split in enumerate(["dev", "heldout"]):
    _add(f"syn_fisher_{i+1}", "categorical", split,
         Q["categorical"].format(v1="site", v2="adverse event"),
         "test association between two categorical variables",
         {"n": 26, "shape": [2, 2], "strength": 0.34, "sparse": True,
          "var1": "site", "var2": "adverse_event"},
         {"site": "variable", "adverse_event": "variable"},
         "sparse 2x2")

# ---- pearson (3) ----
for i, (split, rho, n) in enumerate(
        [("dev", 0.62, 140), ("heldout", 0.45, 90), ("heldout", 0.7, 200)]):
    _add(f"syn_pearson_{i+1}", "association", split,
         Q["association"].format(x="advertising spend", y="weekly revenue"),
         "quantify association between two continuous variables",
         {"n": n, "form": "linear", "rho": rho, "x": "advertising_spend",
          "y": "weekly_revenue"},
         {"advertising_spend": "variable", "weekly_revenue": "variable"},
         "linear, no dominant points")

# ---- spearman (3) ----
for i, (split, form, ordl, cont) in enumerate(
        [("dev", "monotone_nonlinear", 0, 0.0),
         ("heldout", "linear", 5, 0.0),
         ("heldout", "linear", 0, 0.07)]):
    _add(f"syn_spearman_{i+1}", "association", split,
         Q["association"].format(x="tenure months", y="engagement rating"),
         "quantify association between two variables",
         {"n": 130, "form": form, "rho": 0.6, "ordinal_levels": ordl,
          "contaminate": cont, "x": "tenure_months", "y": "engagement_rating"},
         {"tenure_months": "variable", "engagement_rating": "variable"},
         f"form={form} ordinal={ordl} contaminate={cont}")

# ---- ols (4) ----
for i, (split, het, coll) in enumerate(
        [("dev", False, False), ("heldout", True, False),
         ("heldout", False, True), ("heldout", True, True)]):
    _add(f"syn_ols_{i+1}", "regression", split,
         Q["ols"].format(outcome="delivery cost"),
         "model a continuous outcome from several predictors",
         {"kind": "ols", "n": 260, "betas": [1.5, -0.8], "noise": 1.0,
          "heteroscedastic": het, "collinear": coll, "outcome": "delivery_cost"},
         {"delivery_cost": "outcome", "predictor_a": "predictor",
          "predictor_b": "predictor"},
         f"het={het} collinear={coll}")

# ---- logistic (3) ----
for i, (split, n, sep) in enumerate(
        [("dev", 300, False), ("heldout", 180, False), ("heldout", 220, False)]):
    _add(f"syn_logistic_{i+1}", "regression", split,
         Q["logistic"].format(outcome="conversion"),
         "model a binary outcome from several predictors",
         {"kind": "logistic", "n": n, "betas": [1.2, -0.6], "separation": sep,
          "outcome": "converted"},
         {"converted": "outcome", "predictor_a": "predictor",
          "predictor_b": "predictor"},
         "binary outcome from logit link")

# ---- poisson (2) ----
for i, (split, exp_) in enumerate([("dev", False), ("heldout", True)]):
    _add(f"syn_poisson_{i+1}", "count_model", split,
         (Q["count_exposure"] if exp_ else Q["count"]).format(outcome="support tickets"),
         "model a count outcome",
         {"n": 320, "overdispersed": False, "with_exposure": exp_,
          "outcome": "support_tickets"},
         {"support_tickets": "outcome", "predictor_a": "predictor",
          **({"observation_days": "exposure"} if exp_ else {})},
         f"equidispersed, exposure={exp_}")

# ---- negative_binomial (3) ----
for i, (split, exp_) in enumerate([("dev", False), ("heldout", True), ("heldout", False)]):
    _add(f"syn_negbin_{i+1}", "count_model", split,
         (Q["count_exposure"] if exp_ else Q["count"]).format(outcome="incidents"),
         "model a count outcome",
         {"n": 300, "overdispersed": True, "with_exposure": exp_,
          "outcome": "incidents"},
         {"incidents": "outcome", "predictor_a": "predictor",
          **({"observation_days": "exposure"} if exp_ else {})},
         f"overdispersed, exposure={exp_}")

# --------------------------------------------------------------------------
# Synthetic abstention cases (8)
# --------------------------------------------------------------------------

_ABSTAIN = [
    ("repeated_measures", "dev", "the condition changes the measured value",
     {"value": "outcome", "subject_id": "repeated_id", "condition": "group"}),
    ("repeated_measures", "heldout", "the intervention shifts the recorded value",
     {"value": "outcome", "subject_id": "repeated_id", "condition": "group"}),
    ("serial_dependence", "dev", "temperature is related to the hourly measure",
     {"value": "outcome", "temperature": "predictor", "hour_index": "time"}),
    ("zero_inflated", "heldout", "the predictor explains the number of claims",
     {"claim_count": "outcome", "predictor_a": "predictor"}),
    ("censored", "heldout", "the two groups differ in follow-up duration",
     {"followup_days": "outcome", "group": "group", "was_censored": "indicator"}),
    ("clustered", "heldout", "the enhanced arm improves the measured value",
     {"value": "outcome", "arm": "group", "clinic_id": "cluster"}),
    ("paired", "heldout", "values change between the two timepoints",
     {"value": "outcome", "timepoint": "group", "participant_id": "repeated_id"}),
    ("missing_design_facts", "heldout", "the two arms differ",
     {"value": "outcome", "arm": "group", "reading_id": "identifier"}),
]
for i, (kind, split, what, roles) in enumerate(_ABSTAIN):
    _add(f"syn_abstain_{kind}_{i+1}", "abstention", split,
         Q["abstain"].format(what=what),
         "determine whether a valid analysis is possible and, if so, perform it",
         {"kind": kind, "n": 200}, roles, f"abstention: {kind}")


# --------------------------------------------------------------------------
# Public cases (16) -- built from UCI sources by benchmark/public.py
# --------------------------------------------------------------------------

PUBLIC: list[dict] = [
    # Bank Marketing (UCI 222) -- 4 cases
    {"case_id": "pub_bank_1", "dataset": "bank_marketing", "split": "dev",
     "recipe": "chi_square", "vars": {"var1": "contact", "var2": "y"},
     "question": "Is there an association between contact method and whether the "
                 "client subscribed to a term deposit?",
     "objective": "test association between two categorical variables",
     "expected": "chi_square", "n_sample": 4000},
    {"case_id": "pub_bank_2", "dataset": "bank_marketing", "split": "heldout",
     "recipe": "logistic", "vars": {"outcome": "y",
                                    "predictors": ["duration", "campaign", "age"]},
     "question": "Which call characteristics are associated with the odds that a "
                 "client subscribes to a term deposit?",
     "objective": "model a binary outcome from several predictors",
     "expected": "logistic", "n_sample": 4000},
    {"case_id": "pub_bank_3", "dataset": "bank_marketing", "split": "heldout",
     "recipe": "two_group", "vars": {"outcome": "duration", "group": "y"},
     "question": "Do subscribers and non-subscribers differ in call duration? "
                 "Call duration is known to be strongly right-skewed.",
     "objective": "compare the distributions of two independent groups",
     "expected": "mann_whitney", "n_sample": 3000},
    {"case_id": "pub_bank_4", "dataset": "bank_marketing", "split": "heldout",
     "recipe": "two_group_mean", "vars": {"outcome": "age", "group": "y"},
     "question": "Do subscribers and non-subscribers differ in average age?",
     "objective": "compare two independent groups on a continuous outcome",
     "expected": "welch_t", "n_sample": 4000},

    # Online Shoppers (UCI 468) -- 4 cases
    {"case_id": "pub_shoppers_1", "dataset": "online_shoppers", "split": "dev",
     "recipe": "two_group_mean", "vars": {"outcome": "ProductRelated_Duration",
                                          "group": "Revenue"},
     "question": "Do sessions that ended in a purchase differ from those that did "
                 "not in time spent on product pages?",
     "objective": "compare two independent groups on a continuous outcome",
     "expected": "mann_whitney", "n_sample": 4000},
    {"case_id": "pub_shoppers_2", "dataset": "online_shoppers", "split": "heldout",
     "recipe": "chi_square", "vars": {"var1": "VisitorType", "var2": "Revenue"},
     "question": "Is visitor type associated with whether a session generates revenue?",
     "objective": "test association between two categorical variables",
     "expected": "chi_square", "n_sample": 6000},
    {"case_id": "pub_shoppers_3", "dataset": "online_shoppers", "split": "heldout",
     "recipe": "association", "vars": {"x": "BounceRates", "y": "ExitRates"},
     "question": "How strongly are bounce rates and exit rates related, and what "
                 "form does that relationship take?",
     "objective": "quantify association between two continuous variables",
     "expected": "pearson", "n_sample": 4000},
    {"case_id": "pub_shoppers_4", "dataset": "online_shoppers", "split": "heldout",
     "recipe": "logistic", "vars": {"outcome": "Revenue",
                                    "predictors": ["PageValues", "BounceRates"]},
     "question": "Which session metrics are associated with the odds that a session "
                 "generates revenue?",
     "objective": "model a binary outcome from several predictors",
     "expected": "logistic", "n_sample": 5000},

    # Student Performance (UCI 320) -- 4 cases
    {"case_id": "pub_student_1", "dataset": "student_performance", "split": "dev",
     "recipe": "two_group_mean", "vars": {"outcome": "G3", "group": "sex"},
     "question": "Do male and female students differ in final grade?",
     "objective": "compare two independent groups on a continuous outcome",
     "expected": "welch_t", "n_sample": 0},
    {"case_id": "pub_student_2", "dataset": "student_performance", "split": "heldout",
     "recipe": "multi_group", "vars": {"outcome": "G3", "group": "Mjob"},
     "question": "Does final grade differ across mother's occupation categories?",
     "objective": "compare three or more independent groups",
     "expected": "welch_anova", "n_sample": 0},
    {"case_id": "pub_student_3", "dataset": "student_performance", "split": "heldout",
     "recipe": "association", "vars": {"x": "studytime", "y": "G3"},
     "question": "How is weekly study time related to final grade? Study time is "
                 "recorded on a four-point ordered scale.",
     "objective": "quantify association between two variables",
     "expected": "spearman", "n_sample": 0},
    {"case_id": "pub_student_4", "dataset": "student_performance", "split": "heldout",
     "recipe": "ols", "vars": {"outcome": "G3",
                               "predictors": ["absences", "studytime", "failures"]},
     "question": "Which school-related factors are related to final grade, and by "
                 "how much?",
     "objective": "model a continuous outcome from several predictors",
     "expected": "ols", "n_sample": 0},

    # Seoul Bike (UCI 560) -- 4 deliberate design-hazard cases (blueprint 4.4)
    {"case_id": "pub_bike_1", "dataset": "seoul_bike", "split": "dev",
     "recipe": "hazard_count", "vars": {"outcome": "Rented Bike Count",
                                        "predictors": ["Temperature"]},
     "question": "What explains variation in the number of bikes rented?",
     "objective": "model a count outcome",
     "expected": "abstain", "abstain_reason": "serial_dependence", "n_sample": 2000},
    {"case_id": "pub_bike_2", "dataset": "seoul_bike", "split": "heldout",
     "recipe": "hazard_assoc", "vars": {"x": "Temperature",
                                        "y": "Rented Bike Count"},
     "question": "How strongly is temperature related to bike rental volume?",
     "objective": "quantify association between two continuous variables",
     "expected": "abstain", "abstain_reason": "serial_dependence", "n_sample": 2000},
    {"case_id": "pub_bike_3", "dataset": "seoul_bike", "split": "heldout",
     "recipe": "hazard_group", "vars": {"outcome": "Rented Bike Count",
                                        "group": "Seasons"},
     "question": "Does rental volume differ across seasons?",
     "objective": "compare three or more independent groups",
     "expected": "abstain", "abstain_reason": "serial_dependence", "n_sample": 2400},
    {"case_id": "pub_bike_4", "dataset": "seoul_bike", "split": "heldout",
     "recipe": "hazard_group2", "vars": {"outcome": "Rented Bike Count",
                                         "group": "Holiday"},
     "question": "Do holidays differ from non-holidays in rental volume?",
     "objective": "compare two independent groups on a continuous outcome",
     "expected": "abstain", "abstain_reason": "serial_dependence", "n_sample": 2000},
]


# --------------------------------------------------------------------------
# Split assignment
# --------------------------------------------------------------------------
#
# The blueprint asks for 16 development cases (12 synthetic + 4 public) AND for
# "each method [to appear] in both partitions".  Those two requirements are
# arithmetically incompatible: 12 synthetic development slots cannot cover 14
# methods plus abstention.  We keep the split sizes, which protect the held-out
# estimate, and cover all seven *families* plus the hardest within-family
# contrasts instead.  The four methods below are therefore held-out only, which
# means no prompt was ever tuned against them -- a limitation to disclose, and
# incidentally a cleaner generalisation test.

DEV_SYNTHETIC = {
    "syn_student_t_1",       # student vs welch contrast
    "syn_welch_t_1",         # unequal variance + imbalance
    "syn_mann_whitney_1",    # skew + shift estimand
    "syn_welch_anova_1",     # heteroscedastic multi-group
    "syn_kruskal_1",         # skewed multi-group
    "syn_chi_square_1",      # adequate expected counts
    "syn_fisher_1",          # sparse 2x2
    "syn_spearman_1",        # monotone nonlinear
    "syn_ols_1",             # linear model
    "syn_negbin_1",          # overdispersion
    "syn_abstain_repeated_measures_1",
    "syn_abstain_serial_dependence_3",
}

HELDOUT_ONLY_METHODS = ("one_way_anova", "pearson", "logistic", "poisson")
"""Methods with no development representation -- see the note above."""


def _apply_split(specs: list[dict]) -> list[dict]:
    for s in specs:
        if s["origin"] == "synthetic":
            s["split"] = "dev" if s["case_id"] in DEV_SYNTHETIC else "heldout"
    return specs


def all_specs() -> list[dict]:
    return _apply_split(
        [dict(s) for s in SYNTHETIC]
        + [dict(p, origin="public", family="public") for p in PUBLIC]
    )


def summary() -> dict:
    specs = all_specs()
    syn = [s for s in specs if s["origin"] == "synthetic"]
    pub = [s for s in specs if s["origin"] == "public"]
    return {
        "total": len(specs),
        "synthetic": len(syn), "public": len(pub),
        "dev": sum(s["split"] == "dev" for s in specs),
        "heldout": sum(s["split"] == "heldout" for s in specs),
        "synthetic_abstention": sum(s["family"] == "abstention" for s in syn),
        "public_abstention": sum(s.get("expected") == "abstain" for s in pub),
    }
