"""The provenance contract (review finding F-A4).

These tests defend the strongest claim in the project: the model cannot write a
number.  If any of them fail, "every numerical claim maps to a tool output" is
no longer true and the headline must be restated.
"""
import pytest

from aistat.provenance.store import ProvenanceError, ResultStore, flatten, format_value
from aistat.schemas.core import ProseBlock, find_raw_numbers


def test_flatten_indexes_lists_and_drops_non_numerics():
    out = flatten({"p": 0.03, "ci": [1.5, 2.5], "ok": True, "name": "welch",
                   "nested": {"a": 7}})
    assert out == {"p": 0.03, "ci[0]": 1.5, "ci[1]": 2.5, "nested.a": 7.0}


def test_flatten_drops_nan_and_inf():
    assert flatten({"a": float("nan"), "b": float("inf"), "c": 1.0}) == {"c": 1.0}


def test_unknown_reference_raises():
    s = ResultStore()
    s.register("r1.welch_t", {"p_value": 0.03})
    with pytest.raises(ProvenanceError):
        s.render("{{r1.welch_t.fabricated}}")


def test_render_substitutes_registered_values():
    s = ResultStore()
    s.register("r1.welch_t", {"p_value": 0.0312, "estimate": 12.4})
    out = s.render("p={{r1.welch_t.p_value}} d={{r1.welch_t.estimate}}")
    assert "0.0312" in out and "12.4" in out and "{{" not in out


def test_non_strict_render_marks_instead_of_raising():
    s = ResultStore()
    out = s.render("{{missing.ref}}", strict=False)
    assert "UNRESOLVED" in out
    assert s.rejection_count == 1


def test_schema_rejects_raw_decimals_in_prose():
    with pytest.raises(ValueError):
        ProseBlock(text="The p-value was 0.031.")
    with pytest.raises(ValueError):
        ProseBlock(text="We observed 1234 events.")


def test_schema_allows_conventional_constants():
    ProseBlock(text="A 95% confidence interval was used with alpha of 0.05.")
    ProseBlock(text="The table is 2x2 and there are three groups.")


def test_schema_accepts_reference_templates():
    ProseBlock(text="p = {{r1.welch_t.p_value}}, CI [{{r1.welch_t.ci_low}}, "
                    "{{r1.welch_t.ci_high}}].")


def test_find_raw_numbers_ignores_text_inside_references():
    assert find_raw_numbers("{{r1.x.p_0_value}} and {{r12.welch_t.ci[0]}}") == []


def test_unused_diagnostics_are_detectable():
    s = ResultStore()
    cid = s.next_call_id("check")
    s.register(cid, {"variance_ratio": 4.0, "levene_p": 0.001})
    s.render(f"{{{{{cid}.variance_ratio}}}}")
    unused = s.unused_from(cid)
    assert f"{cid}.levene_p" in unused
    assert f"{cid}.variance_ratio" not in unused


def test_call_ids_are_monotonic_and_labelled():
    s = ResultStore()
    assert s.next_call_id("welch_t") == "r1.welch_t"
    assert s.next_call_id("inspect_dataset") == "r2.inspect_dataset"


@pytest.mark.parametrize("value,expected_substring", [
    (0.0000123, "e-05"), (0.5, "0.5"), (1234.5, "1,234.5"), (42.0, "42"),
])
def test_format_value_shapes(value, expected_substring):
    assert expected_substring in format_value(value)


# ==========================================================================
# Qualitative references and corrective retry
# ==========================================================================
#
# The first live pilot lost 3 of 48 System C runs to two recoverable slips:
# a bare number in prose, and a reference to a string field that flatten()
# correctly dropped. Both are now handled rather than fatal.

def test_string_fields_are_citable_alongside_numbers():
    s = ResultStore()
    cid = s.next_call_id("welch_t")
    s.register(cid, {"p_value": 0.03,
                     "effect_size": {"value": 0.52, "interpretation": "medium"}})
    out = s.render(f"d={{{{{cid}.effect_size.value}}}} "
                   f"({{{{{cid}.effect_size.interpretation}}}})")
    assert "0.52" in out and "medium" in out
    assert "{{" not in out


def test_boolean_flags_render_as_words_not_numbers():
    s = ResultStore()
    cid = s.next_call_id("poisson")
    s.register(cid, {"overdispersion_flag": True, "pearson_dispersion": 2.4})
    assert s.render(f"{{{{{cid}.overdispersion_flag}}}}") == "yes"
    # A flag must not leak into the numeric namespace and be cited as a statistic.
    assert f"{cid}.overdispersion_flag" not in s.keys()


def test_citable_is_the_union_and_keys_stays_numeric():
    s = ResultStore()
    cid = s.next_call_id("t")
    s.register(cid, {"p_value": 0.01, "method": "welch_t"})
    assert f"{cid}.method" in s.citable()
    assert f"{cid}.method" not in s.keys()
    assert f"{cid}.p_value" in s.keys()


def test_nearest_suggests_a_real_reference_for_a_near_miss():
    s = ResultStore()
    cid = s.next_call_id("welch_t")
    s.register(cid, {"effect_size": {"value": 0.5, "interpretation": "medium"}})
    near = s.nearest(f"{cid}.effect_size.interpretaton")     # typo
    assert f"{cid}.effect_size.interpretation" in near


def test_unknown_reference_still_raises_after_labels_were_added():
    """Widening what is citable must not weaken the invariant."""
    s = ResultStore()
    s.register("r1.t", {"p_value": 0.03, "method": "welch_t"})
    with pytest.raises(ProvenanceError):
        s.render("{{r1.t.invented_field}}")


def test_report_validator_names_the_exact_violation():
    from aistat.agents.systems import _validate_report
    s = ResultStore()
    s.register("r1.welch_t", {"p_value": 0.03})
    msg = _validate_report({
        "problem_statement": {"text": "fine"},
        "data_audit": {"text": "fine"},
        "method_decision": {"text": "fine"},
        "results": {"text": "p was 0.031 and d was {{r1.welch_t.nonexistent}}"},
        "interpretation": {"text": "fine"},
        "limitations": {"text": "fine"},
    }, s)
    assert msg is not None
    assert "0.031" in msg                      # names the literal
    assert "nonexistent" in msg                # names the bad reference
    assert "results" in msg                    # names the section


def test_report_validator_passes_a_clean_report():
    from aistat.agents.systems import _validate_report
    s = ResultStore()
    s.register("r1.welch_t", {"p_value": 0.03,
                              "effect_size": {"interpretation": "medium"}})
    assert _validate_report({
        "problem_statement": {"text": "A question about two groups."},
        "data_audit": {"text": "Independent observations."},
        "method_decision": {"text": "Welch was selected."},
        "results": {"text": "p = {{r1.welch_t.p_value}}, a "
                            "{{r1.welch_t.effect_size.interpretation}} effect."},
        "interpretation": {"text": "Observational, so association only."},
        "limitations": {"text": "Applies to the sampled population."},
    }, s) is None


# ==========================================================================
# Templates that no pattern matched
# ==========================================================================
#
# Found by the static explorer, not by these tests: 6 of 2,010 rendered report
# sections contained a template emitted verbatim. Two causes, one hole -- a
# reference the pattern could not express silently survived rendering, which is
# worse than failing, because the report looks finished and contains a
# placeholder where a statistic should be.

def test_reference_containing_spaces_resolves():
    """UCI column names contain spaces; the store keys them faithfully."""
    s = ResultStore()
    cid = s.next_call_id("inspect_dataset")
    s.register(cid, {"columns": {"Rented Bike Count": {"mean": 704.6}}})
    key = f"{cid}.columns.Rented Bike Count.mean"
    assert key in s.keys()
    assert "704.6" in s.render(f"Mean {{{{{key}}}}}")


@pytest.mark.parametrize("malformed", [
    "{{r4.welch_t.group_sds[0])}}",     # stray paren the model wrote
    "{{ spaced.ref }}",                 # padded
    "{{totally.invented}}",             # plausible but absent
])
def test_malformed_or_unknown_templates_are_blocked_not_emitted(malformed):
    s = ResultStore()
    s.register("r1.welch_t", {"p_value": 0.03})
    with pytest.raises(ProvenanceError):
        s.render(malformed)


def test_unclosed_template_cannot_survive_rendering():
    s = ResultStore()
    s.register("r1.t", {"p_value": 0.03})
    with pytest.raises(ProvenanceError):
        s.render("p was {{r1.t.p_value and then {{ broken")


def test_non_strict_render_marks_residue_rather_than_emitting_it():
    s = ResultStore()
    out = s.render("value {{unmatchable", strict=False)
    assert "{{" not in out
    assert "UNRESOLVED" in out
    assert s.rejection_count == 1


# Live captures recorded BEFORE the pattern was widened. They are retained as
# evidence of the defect rather than deleted, and cannot be regenerated without
# API credit. Everything the current code produces must be clean.
PRE_FIX_CAPTURES = {"dev_claude-opus-5_high.jsonl",
                    "dev_claude-opus-5_medium.jsonl"}


def test_no_rendered_report_on_disk_contains_a_surviving_template():
    """Guards the whole corpus, not just a constructed example.

    This is the test the constructed cases above could not be: the hole was
    found in real output, by browsing 2,010 rendered sections, after every
    unit test passed.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    checked = bad = 0
    offenders = []
    for f in (root / "results").glob("*.jsonl"):
        if "scores" in f.name or "traces" in f.name:
            continue
        if f.name in PRE_FIX_CAPTURES:
            continue
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            for section, text in (row.get("rendered") or {}).items():
                checked += 1
                if "{{" in str(text) or "UNRESOLVED" in str(text):
                    bad += 1
                    offenders.append(f"{f.name}:{row.get('case_id')}:{section}")
    assert checked > 0, "no rendered reports found to check"
    assert bad == 0, f"{bad} of {checked} kept a template: {offenders[:5]}"
