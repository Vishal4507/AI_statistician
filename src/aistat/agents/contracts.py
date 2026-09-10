"""Per-decision-point output contracts for the live path.

The state machine calls the model at five points.  Each one needs a JSON schema
so the response parses deterministically, and an instruction saying what to
produce.  Without these the live client returns free text and every structured
field comes back empty -- the drivers run, the API is billed, and the model
contributes nothing.

Schemas are hand-written rather than derived from the Pydantic models: the
structured-output endpoint wants a flat, closed schema, and Pydantic emits
``$defs`` and ``$ref`` for the enums and nested objects.
"""
from __future__ import annotations

from aistat.schemas.core import ABSTAIN, METHODS

_METHOD_ENUM = list(METHODS) + [ABSTAIN]
_HAZARDS = ["repeated_measures", "serial_dependence", "pairing", "clustering",
            "unsupported_outcome", "missing_design_facts"]
_REASONS = ["repeated_measures", "serial_dependence", "zero_inflation",
            "censoring", "pairing", "clustering", "missing_design_facts",
            "out_of_scope_outcome"]
ABSTAIN_REASONS = frozenset(_REASONS)
_SCALES = ["continuous", "binary", "count", "ordinal", "nominal"]
_ESTIMANDS = ["mean_difference", "distributional_shift", "association",
              "conditional_mean", "odds", "rate"]

_S = {"type": "string"}
_SARR = {"type": "array", "items": _S}


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


ANALYSIS_SPEC_SCHEMA = _obj({
    "objective": _S,
    "outcome": _S,
    "predictors": _SARR,
    "group_column": {"type": ["string", "null"]},
    "variable_scales": {
        "type": "array",
        "items": _obj({"column": _S, "scale": {"type": "string", "enum": _SCALES}},
                      ["column", "scale"]),
    },
    "estimand": {"type": "string", "enum": _ESTIMANDS},
    "population": _S,
    "observational_unit": _S,
    "design_hazards": {"type": "array", "items": {"type": "string", "enum": _HAZARDS}},
    "missing_facts": _SARR,
}, ["objective", "outcome", "predictors", "group_column", "variable_scales",
    "estimand", "population", "observational_unit", "design_hazards",
    "missing_facts"])

CANDIDATE_PLAN_SCHEMA = _obj({
    "eligible_methods": {"type": "array",
                         "items": {"type": "string", "enum": _METHOD_ENUM}},
    "required_diagnostics": _SARR,
    "rejection_reasons": {
        "type": "array",
        "items": _obj({"method": _S, "reason": _S}, ["method", "reason"]),
    },
    "ordered_tool_requests": _SARR,
}, ["eligible_methods", "required_diagnostics", "rejection_reasons",
    "ordered_tool_requests"])

SELECTION_SCHEMA = _obj({
    "method": {"type": "string", "enum": _METHOD_ENUM},
    # Nullable, and deliberately WITHOUT an enum: the structured-output
    # validator rejects an enum whose members do not all match a union type
    # ("Enum value 'repeated_measures' does not match declared type
    # ['string','null']").  The allowed set is enforced in normalise() instead.
    "abstain_reason": {"type": ["string", "null"]},
    "rationale": _S,
    "evidence_refs": _SARR,
    "rejected_alternatives": {
        "type": "array",
        "items": _obj({"method": _S, "reason": _S}, ["method", "reason"]),
    },
    "confidence": {"type": "string", "enum": ["high", "moderate", "low"]},
}, ["method", "abstain_reason", "rationale", "evidence_refs",
    "rejected_alternatives", "confidence"])

_BLOCK = _obj({"text": _S}, ["text"])

FINAL_REPORT_SCHEMA = _obj({
    "problem_statement": _BLOCK,
    "data_audit": _BLOCK,
    "method_decision": _BLOCK,
    "results": _BLOCK,
    "interpretation": _BLOCK,
    "limitations": _BLOCK,
}, ["problem_statement", "data_audit", "method_decision", "results",
    "interpretation", "limitations"])


# --------------------------------------------------------------------------
# Per-purpose instructions
# --------------------------------------------------------------------------

INSTRUCTIONS = {
    "parse_problem": (
        "Identify the analytical task. Name the outcome, any grouping column, any "
        "predictors, the measurement scale of each relevant variable, the estimand, "
        "the population and the observational unit. Read the design card carefully "
        "and list every design hazard it implies, plus any material fact it leaves "
        "unstated. Do not choose a method yet."
    ),
    "plan_candidates": (
        "Given the problem specification, list only the methods from the supported "
        "library that could be valid for this design, and the diagnostics that could "
        "actually change the choice between them. If the design invalidates every "
        "supported method, the eligible list is exactly [\"abstain\"] and no "
        "diagnostics are needed. Do not request diagnostics that cannot change the "
        "decision."
    ),
    "select_method": (
        "Using the diagnostic evidence supplied above, choose one method or abstain. "
        "Design validity comes first: if dependence, pairing, clustering or time "
        "order is present, abstain regardless of how well the variable types fit. "
        "Otherwise weigh group sizes, spread, skew and influence together -- an "
        "assumption test's p-value is evidence, not a switch. State why each "
        "seriously considered alternative was rejected.\n\n"
        "If you abstain, `abstain_reason` must be exactly one of: "
        + ", ".join(_REASONS) + ". Otherwise set it to null.\n\n"
        "In `rationale` and in every rejection reason, cite diagnostic values as "
        "{{reference}} templates taken from the evidence keys listed above. Never "
        "write a numeral."
    ),
    "write_report": (
        "Write the final report in six sections.\n\n"
        "CRITICAL: you may not write any number anywhere. Every statistic, interval, "
        "effect size, count and proportion must appear as a {{reference}} template "
        "drawn from the available result references listed above -- for example "
        "{{r3.welch_t.p_value}}. A reference that was not listed will fail the run, "
        "so copy names exactly and never construct a variant of one. Qualitative "
        "values from the tools (effect-size interpretations, method names, "
        "diagnostic flags) are citable the same way. Conventional constants "
        "(95, 0.05, 2x2) may be written as words or digits.\n\n"
        "Lead the interpretation with magnitude, then statistical evidence. Do not "
        "use causal language unless the design card says assignment was randomised. "
        "State only limitations that follow from the observed design, the diagnostics "
        "or the excluded scope."
    ),
    "direct_advice": (
        "You have no tools and cannot execute anything. From the question, the design "
        "card and the summary statistics above, recommend the single most appropriate "
        "method, or abstain if no supported method is valid for this design. Explain "
        "the reasoning and name the alternatives you rejected."
    ),
}

SCHEMAS = {
    "parse_problem": ANALYSIS_SPEC_SCHEMA,
    "plan_candidates": CANDIDATE_PLAN_SCHEMA,
    "select_method": SELECTION_SCHEMA,
    "direct_advice": SELECTION_SCHEMA,
    "write_report": FINAL_REPORT_SCHEMA,
}


# --------------------------------------------------------------------------
# Normalisation: schema-friendly shapes back into what the drivers consume
# --------------------------------------------------------------------------
#
# Structured outputs dislike open-ended maps, so pairs travel as arrays of
# {key, value} objects.  These helpers put them back into dicts.

def _pairs(items, key: str, val: str) -> dict[str, str]:
    """Normalise a pair collection to a map.

    Structured outputs deliver these as an array of {key, value} objects; the
    offline client produces the map directly. An earlier version handled only
    the array, so a map was silently emptied -- which cost the section 12
    demonstration its "clear rejection of ordinary ANOVA" without any error.
    """
    if isinstance(items, dict):
        return {str(k): str(v) for k, v in items.items()}
    out: dict[str, str] = {}
    for it in items or []:
        if isinstance(it, dict) and key in it:
            out[str(it[key])] = str(it.get(val, ""))
    return out


def normalise(purpose: str, payload: dict | None) -> dict | None:
    """Convert a live structured response into the driver's internal shape."""
    if not payload:
        return payload
    p = dict(payload)

    if purpose == "parse_problem":
        p["variable_scales"] = _pairs(p.get("variable_scales"), "column", "scale")
    elif purpose == "plan_candidates":
        p["rejection_reasons"] = _pairs(p.get("rejection_reasons"), "method", "reason")
    elif purpose in ("select_method", "direct_advice"):
        p["rejected_alternatives"] = _pairs(p.get("rejected_alternatives"),
                                            "method", "reason")
        p["_rationale"] = p.pop("rationale", "")
        if p.get("method") != ABSTAIN:
            p["abstain_reason"] = None
        else:
            # Enforced here rather than in the schema -- see the note on the
            # abstain_reason property above.
            reason = p.get("abstain_reason")
            if reason not in ABSTAIN_REASONS:
                p["abstain_reason"] = "missing_design_facts"
                p["_reason_coerced_from"] = reason
    elif purpose == "write_report":
        pass                       # blocks are already the right shape
    return p
