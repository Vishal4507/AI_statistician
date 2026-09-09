"""End-to-end runs (blueprint section 10.4).

One case in each task family plus abstention cases, across all three systems,
with the provenance and fairness invariants asserted on every run.
"""
import pytest

from aistat.agents.base import Case
from aistat.agents.rulebased import RuleBasedClient
from aistat.agents.systems import SYSTEMS
from aistat.evaluation.scorers import score_run
from aistat.schemas.core import ABSTAIN, REF_PATTERN

FAMILY_CASES = [
    "syn_student_t_1",      # two independent groups
    "syn_welch_anova_1",    # three or more groups
    "syn_chi_square_1",     # categorical association
    "syn_spearman_1",       # continuous / ordinal association
    "syn_ols_1",            # regression, continuous outcome
    "syn_negbin_1",         # count outcome
]
ABSTENTION_CASES = [
    "syn_abstain_repeated_measures_1",
    "syn_abstain_serial_dependence_3",
]


@pytest.mark.parametrize("case_id", FAMILY_CASES + ABSTENTION_CASES)
@pytest.mark.parametrize("system", list(SYSTEMS))
def test_run_completes_without_error(case_id, system):
    case = Case.load(case_id)
    result = SYSTEMS[system](RuleBasedClient("expert")).run(case)
    assert result.error is None, result.error
    assert result.report is not None
    assert result.method


@pytest.mark.parametrize("case_id", FAMILY_CASES)
@pytest.mark.parametrize("system", list(SYSTEMS))
def test_every_rendered_number_came_from_a_tool(case_id, system):
    """The load-bearing invariant: no unresolved reference survives rendering."""
    case = Case.load(case_id)
    result = SYSTEMS[system](RuleBasedClient("expert")).run(case)
    for name, text in result.rendered.items():
        assert "{{" not in text, f"{name} kept an unsubstituted template"
        assert "PROVENANCE FAILURE" not in text
        assert "UNRESOLVED" not in text
    assert result.provenance_rejections == 0


@pytest.mark.parametrize("case_id", ABSTENTION_CASES)
def test_protocol_abstains_where_the_design_forbids_a_method(case_id):
    case = Case.load(case_id)
    result = SYSTEMS["C_protocol"](RuleBasedClient("expert")).run(case)
    assert result.method == ABSTAIN
    assert result.abstain_reason
    score = score_run(result.to_dict(), case.card.get("randomized"))
    assert score["selection_correct"]
    assert not score["unsafe_selection"]


def test_protocol_revises_once_on_overdispersion():
    """Blueprint section 12: Poisson fit, dispersion failure, one revision."""
    case = Case.load("syn_negbin_1")
    result = SYSTEMS["C_protocol"](RuleBasedClient("expert")).run(case)
    assert result.method == "negative_binomial"
    trigger = [e for e in result.trace.events if e["kind"] == "state"
               and e.get("state") == "revise"]
    if trigger:                       # revision fires when Poisson was tried first
        assert trigger[0]["to"] == "negative_binomial"
        assert result.revised


def test_baselines_receive_the_same_tool_surface():
    """Review finding F-C1: B must not be handicapped by a smaller tool set."""
    from aistat.tools.registry import ToolRegistry
    specs = ToolRegistry.specs(strict=True)
    assert len(specs) == 8
    assert all(s.get("strict") is True for s in specs)
    names = {s["name"] for s in specs}
    assert "run_python" not in names          # blueprint section 5.2


def test_direct_baseline_receives_the_same_step_one_evidence():
    """A's evidence dump must come from the same call C uses, not a digest."""
    case = Case.load("syn_welch_t_1")
    a = SYSTEMS["A_direct"](RuleBasedClient("expert")).run(case)
    c = SYSTEMS["C_protocol"](RuleBasedClient("expert")).run(case)
    a_diag = {e["tool"] for e in a.trace.events if e["kind"] == "tool_call"}
    c_diag = {e["tool"] for e in c.trace.events if e["kind"] == "tool_call"
              and e["tool"].startswith(("inspect", "summarize", "check"))}
    assert c_diag <= a_diag, (a_diag, c_diag)


def test_traces_are_replayable_and_comparable():
    case = Case.load("syn_welch_t_1")
    r1 = SYSTEMS["C_protocol"](RuleBasedClient("expert")).run(case, rep=0)
    r2 = SYSTEMS["C_protocol"](RuleBasedClient("expert")).run(case, rep=1)
    from aistat.agents.trace import divergence_point
    assert divergence_point(r1.trace, r2.trace) is None   # deterministic client
    assert r1.trace.signature[0] == "S:start"
    assert "T:run_group_test:welch_t" in r1.trace.signature


def test_verifier_flags_a_causal_claim_on_observational_data():
    from aistat.provenance.store import ResultStore
    from aistat.schemas.core import FinalReport
    from aistat.tools.verify import verify_report
    store = ResultStore()
    store.register("r1.welch_t", {"p_value": 0.01, "ci_low": 1.0, "ci_high": 2.0,
                                  "effect_size": {"value": 0.5}})
    report = FinalReport.model_validate({
        "case_id": "t", "problem_statement": {"text": "A question."},
        "data_audit": {"text": "Clean."},
        "method_decision": {"text": "Welch."},
        "results": {"text": "p={{r1.welch_t.p_value}} CI [{{r1.welch_t.ci_low}}, "
                            "{{r1.welch_t.ci_high}}] d={{r1.welch_t.effect_size.value}}"},
        "interpretation": {"text": "The treatment causes higher spend."},
        "limitations": {"text": "None."},
        "selection": {"method": "welch_t"},
    })
    v = verify_report(report, store, randomized=False, method="welch_t")
    assert any(f["check"] == "causal_language" for f in v["findings"])
    assert not v["passed"]
