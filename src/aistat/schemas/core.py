"""Typed state objects for the AI Statistician.

Implements blueprint section 5.1, with one amendment (review finding F-A4):
FinalReport prose may not contain raw numeric literals.  Every number must
arrive as a ``{{tool_result_ref}}`` template that the ResultStore substitutes.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------
# Controlled vocabularies
# --------------------------------------------------------------------------

METHODS: tuple[str, ...] = (
    "student_t",
    "welch_t",
    "mann_whitney",
    "one_way_anova",
    "welch_anova",
    "kruskal_wallis",
    "chi_square",
    "fisher_exact",
    "pearson",
    "spearman",
    "ols",
    "logistic",
    "poisson",
    "negative_binomial",
)
"""The 14 supported methods (blueprint section 2).  ``abstain`` is a decision,
not a member of this library."""

ABSTAIN = "abstain"


class VarScale(str, Enum):
    CONTINUOUS = "continuous"
    BINARY = "binary"
    COUNT = "count"
    ORDINAL = "ordinal"
    NOMINAL = "nominal"


class Estimand(str, Enum):
    MEAN_DIFFERENCE = "mean_difference"
    DISTRIBUTIONAL_SHIFT = "distributional_shift"
    ASSOCIATION = "association"
    CONDITIONAL_MEAN = "conditional_mean"
    ODDS = "odds"
    RATE = "rate"


class DesignHazard(str, Enum):
    """Design facts that can invalidate every in-scope method."""

    REPEATED_MEASURES = "repeated_measures"
    SERIAL_DEPENDENCE = "serial_dependence"
    PAIRING = "pairing"
    CLUSTERING = "clustering"
    UNSUPPORTED_OUTCOME = "unsupported_outcome"
    MISSING_DESIGN_FACTS = "missing_design_facts"


class AbstainReason(str, Enum):
    REPEATED_MEASURES = "repeated_measures"
    SERIAL_DEPENDENCE = "serial_dependence"
    ZERO_INFLATION = "zero_inflation"
    CENSORING = "censoring"
    PAIRING = "pairing"
    CLUSTERING = "clustering"
    MISSING_DESIGN_FACTS = "missing_design_facts"
    OUT_OF_SCOPE_OUTCOME = "out_of_scope_outcome"


class Confidence(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# --------------------------------------------------------------------------
# Case-side inputs
# --------------------------------------------------------------------------


class DesignCard(BaseModel):
    """Blueprint section 1 'required input change'.

    A CSV cannot reveal whether rows are independent.  This carries the facts
    that decide design validity.  ``None`` means *unknown*, which is itself
    material evidence: an unknown that matters is grounds to abstain.
    """

    observational_unit: str
    sampling_unit: str
    repeated_id_column: str | None = None
    time_column: str | None = None
    pairing: bool | None = None
    clustering_column: str | None = None
    randomized: bool | None = None
    intended_population: str
    known_missingness: str | None = None

    def declared_hazards(self) -> list[DesignHazard]:
        """Hazards readable directly off the card, before any data is touched."""
        out: list[DesignHazard] = []
        if self.repeated_id_column:
            out.append(DesignHazard.REPEATED_MEASURES)
        if self.time_column:
            out.append(DesignHazard.SERIAL_DEPENDENCE)
        if self.pairing:
            out.append(DesignHazard.PAIRING)
        if self.clustering_column:
            out.append(DesignHazard.CLUSTERING)
        if self.pairing is None or self.randomized is None:
            out.append(DesignHazard.MISSING_DESIGN_FACTS)
        return out


class CaseManifest(BaseModel):
    """Non-gold provenance for one case.  Safe to expose to the agent."""

    case_id: str
    family: str
    origin: Literal["synthetic", "public"]
    split: Literal["dev", "heldout"]
    variable_roles: dict[str, str]
    allowed_preprocessing: list[str] = Field(default_factory=list)
    seed: int | None = None
    source: str | None = None
    source_doi: str | None = None
    n_rows: int
    data_sha256: str


class Gold(BaseModel):
    """Answer key.  Never reachable from a prompt (blueprint section 6 step 11)."""

    case_id: str
    primary_method: str
    accepted_methods: list[str]
    required_checks: list[str] = Field(default_factory=list)
    abstain_reason: AbstainReason | None = None
    expected_hazards: list[DesignHazard] = Field(default_factory=list)
    interpretation_constraints: list[str] = Field(default_factory=list)
    rationale: str = ""

    @property
    def is_abstention(self) -> bool:
        return self.primary_method == ABSTAIN

    @field_validator("accepted_methods")
    @classmethod
    def _known(cls, v: list[str]) -> list[str]:
        bad = [m for m in v if m not in METHODS and m != ABSTAIN]
        if bad:
            raise ValueError(f"unknown method(s) in accepted set: {bad}")
        return v


class Oracle(BaseModel):
    """Pinned tool output for numeric-drift detection.

    Review finding F-B2: this is a *regression fixture*, not a correctness
    check -- it is produced by the same library it guards.  Correctness comes
    from tests/test_methods_reference.py, which checks against independently
    published values.
    """

    case_id: str
    values: dict[str, float]
    tolerances: dict[str, float] = Field(default_factory=dict)
    default_rtol: float = 1e-6

    def tolerance_for(self, key: str) -> float:
        return self.tolerances.get(key, self.default_rtol)


# --------------------------------------------------------------------------
# Agent state objects (blueprint section 5.1)
# --------------------------------------------------------------------------


class AnalysisSpec(BaseModel):
    objective: str
    outcome: str
    predictors: list[str] = Field(default_factory=list)
    group_column: str | None = None
    variable_scales: dict[str, VarScale] = Field(default_factory=dict)
    estimand: Estimand
    population: str
    observational_unit: str
    design_hazards: list[DesignHazard] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)


class CandidatePlan(BaseModel):
    eligible_methods: list[str]
    required_diagnostics: list[str] = Field(default_factory=list)
    rejection_reasons: dict[str, str] = Field(default_factory=dict)
    ordered_tool_requests: list[str] = Field(default_factory=list)

    @field_validator("eligible_methods")
    @classmethod
    def _known(cls, v: list[str]) -> list[str]:
        bad = [m for m in v if m not in METHODS and m != ABSTAIN]
        if bad:
            raise ValueError(f"unknown method(s): {bad}")
        return v


class Selection(BaseModel):
    method: str
    abstain_reason: AbstainReason | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    rejected_alternatives: dict[str, str] = Field(default_factory=dict)
    confidence: Confidence = Confidence.MODERATE

    @property
    def is_abstention(self) -> bool:
        return self.method == ABSTAIN

    @field_validator("method")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in METHODS and v != ABSTAIN:
            raise ValueError(f"unknown method: {v}")
        return v


class AnalysisResult(BaseModel):
    tool_name: str
    call_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Final report -- the provenance-enforcing schema
# --------------------------------------------------------------------------

REF_PATTERN = re.compile(r"\{\{([^{}]{1,240})\}\}")
"""A result reference: ``{{r7.welch_t.p_value}}``.

Deliberately permissive. Real store keys contain characters a tight pattern
would exclude -- a UCI column named "Rented Bike Count" produces the legitimate
key ``r1.inspect_dataset.columns.Rented Bike Count.mean``. Under a narrower
pattern that template matched nothing and was emitted verbatim into the report,
which is the one outcome the provenance contract must never allow.

Anything of the form ``{{...}}`` is therefore treated as a *claim* to be a
reference. If it resolves, it is substituted; if it does not, it is a
provenance failure. Nothing passes through unexamined.
"""

# A bare number in prose.  Deliberately permissive about what is *allowed*:
# small integers read as counts of groups/variables ("three groups", "2x2")
# are unavoidable in natural writing, so we only reject decimals and large
# integers -- the shapes a statistic actually takes.
_RAW_NUMBER = re.compile(
    r"""
    (?<![\w.{}/-])          # not already inside a token or a ref
    -?
    (?:
        \d+\.\d+            # any decimal
      | \d{3,}              # 3+ digit integer
      | \d+[eE][-+]?\d+     # scientific notation
    )
    (?![\w}])
    """,
    re.VERBOSE,
)

_ALLOWED_LITERALS = {"95", "0.05", "1.96", "2x2", "99", "90"}
"""Conventional constants that are not results: the confidence level, the
alpha threshold, the normal quantile, the table dimension."""


def find_raw_numbers(text: str) -> list[str]:
    """Return raw numeric literals in prose that did not come from a tool."""
    stripped = REF_PATTERN.sub(" ", text)
    return [m.group(0) for m in _RAW_NUMBER.finditer(stripped)
            if m.group(0) not in _ALLOWED_LITERALS]


class ProseBlock(BaseModel):
    """Report prose.  Numbers may only appear as ``{{ref}}`` templates."""

    text: str

    @field_validator("text")
    @classmethod
    def _no_raw_numbers(cls, v: str) -> str:
        bad = find_raw_numbers(v)
        if bad:
            raise ValueError(
                "raw numeric literal(s) in report prose: "
                f"{bad}. Every number must be a {{{{tool.result.ref}}}} "
                "template -- see ResultStore."
            )
        return v


class FinalReport(BaseModel):
    """Blueprint section 7 'standard final report structure'."""

    case_id: str
    problem_statement: ProseBlock
    data_audit: ProseBlock
    method_decision: ProseBlock
    results: ProseBlock
    interpretation: ProseBlock
    limitations: ProseBlock
    selection: Selection
    trace_ids: list[str] = Field(default_factory=list)

    def prose_blocks(self) -> dict[str, ProseBlock]:
        return {
            "problem_statement": self.problem_statement,
            "data_audit": self.data_audit,
            "method_decision": self.method_decision,
            "results": self.results,
            "interpretation": self.interpretation,
            "limitations": self.limitations,
        }

    def referenced(self) -> set[str]:
        refs: set[str] = set()
        for block in self.prose_blocks().values():
            refs.update(m.group(1) for m in REF_PATTERN.finditer(block.text))
        return refs
