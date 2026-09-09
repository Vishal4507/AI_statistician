"""Schema and malformed-input tests (blueprint section 10.4)."""
import pytest
from pydantic import ValidationError

from aistat.schemas.core import (AnalysisSpec, CandidatePlan, DesignCard, Gold,
                                 Selection)


def test_design_card_reads_hazards_off_the_card():
    card = DesignCard(observational_unit="measurement", sampling_unit="subject",
                      repeated_id_column="subject_id", time_column=None,
                      pairing=True, clustering_column=None, randomized=False,
                      intended_population="enrolled subjects")
    h = [x.value for x in card.declared_hazards()]
    assert "repeated_measures" in h and "pairing" in h


def test_missing_design_facts_is_itself_a_hazard():
    card = DesignCard(observational_unit="unknown", sampling_unit="unknown",
                      pairing=None, randomized=None,
                      intended_population="unspecified")
    assert "missing_design_facts" in [x.value for x in card.declared_hazards()]


def test_gold_rejects_unknown_methods():
    with pytest.raises(ValidationError):
        Gold(case_id="x", primary_method="welch_t",
             accepted_methods=["welch_t", "mixed_effects"])


def test_gold_requires_primary_in_accepted_set_is_caller_enforced():
    g = Gold(case_id="x", primary_method="welch_t", accepted_methods=["welch_t"])
    assert g.primary_method in g.accepted_methods


def test_selection_rejects_unknown_method():
    with pytest.raises(ValidationError):
        Selection(method="mixed_effects")


def test_selection_accepts_abstain():
    s = Selection(method="abstain", abstain_reason="repeated_measures")
    assert s.is_abstention


def test_candidate_plan_rejects_unknown_method():
    with pytest.raises(ValidationError):
        CandidatePlan(eligible_methods=["welch_t", "survival"])


def test_analysis_spec_rejects_bad_estimand():
    with pytest.raises(ValidationError):
        AnalysisSpec(objective="o", outcome="y", estimand="vibes",
                     population="p", observational_unit="u")
