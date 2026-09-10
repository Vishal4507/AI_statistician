"""A run that happened and failed is not a run that happened.

A capstone stands or falls on whether its claims are true, and the cheapest way
to destroy that is to let a file's existence stand in for its contents.  The
Groq attempt wrote 432 rows to a held-out scores file and every single row was
an authentication error.  Under a check that asked only "does the file have
lines?", that failure would have been reported as a completed held-out
evaluation, and every number downstream of it would have been a fiction.

These tests pin the distinction, and pin it in the one place both the
conformance harness and the report writer consult, so the two cannot drift.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aistat.evaluation.liveness import (best_live_heldout, failed_attempts,
                                        failed_attempts_note,
                                        live_heldout_files, produced_a_result)


def _scores(root: Path, name: str, n_ok: int, n_err: int) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    rows = [{"run_id": f"ok{i}", "system": "C_protocol", "case_id": f"c{i}",
             "chosen_method": "welch_t", "selection_correct": True,
             "run_error": None} for i in range(n_ok)]
    # An authentication failure never reaches a decision: chosen_method "none".
    rows += [{"run_id": f"er{i}", "system": "C_protocol", "case_id": f"e{i}",
              "chosen_method": "none", "selection_correct": False,
              "run_error": "AuthenticationError: 401"} for i in range(n_err)]
    p = root / f"{name}_scores.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_all_error_run_is_not_a_result(tmp_path):
    """The exact Groq outcome: 432 rows, 432 errors, zero evidence."""
    _scores(tmp_path, "heldout_groq_gpt-oss-120b", n_ok=0, n_err=432)
    assert best_live_heldout(tmp_path) is None


def test_mostly_failed_run_is_not_a_result(tmp_path):
    _scores(tmp_path, "heldout_somemodel", n_ok=100, n_err=332)
    assert best_live_heldout(tmp_path) is None


def test_successful_run_is_a_result_and_carries_its_counts(tmp_path):
    _scores(tmp_path, "heldout_claude-haiku-4-5", n_ok=280, n_err=8)
    live = best_live_heldout(tmp_path)
    assert live is not None
    path, ok, total = live
    assert path.name == "heldout_claude-haiku-4-5_scores.jsonl"
    assert (ok, total) == (280, 288)


def test_the_most_complete_run_wins(tmp_path):
    """Two usable runs: the one with more results is the one to report."""
    _scores(tmp_path, "heldout_partial", n_ok=150, n_err=10)
    _scores(tmp_path, "heldout_full", n_ok=288, n_err=0)
    path, ok, _ = best_live_heldout(tmp_path)
    assert path.name == "heldout_full_scores.jsonl" and ok == 288


def test_deterministic_policy_runs_never_count_as_live(tmp_path):
    """The rule-based client is the offline calibration, not a model."""
    _scores(tmp_path, "heldout_rulebased_expert", n_ok=432, n_err=0)
    assert best_live_heldout(tmp_path) is None
    assert list(live_heldout_files(tmp_path)) == []


def test_empty_file_is_not_a_result(tmp_path):
    tmp_path.joinpath("heldout_x_scores.jsonl").write_text("")
    assert best_live_heldout(tmp_path) is None


def test_missing_results_directory_is_not_a_result(tmp_path):
    assert best_live_heldout(tmp_path / "nope") is None
    assert failed_attempts_note(tmp_path / "nope") == ""


def test_failed_attempt_is_named_rather_than_silently_dropped(tmp_path):
    """'Not run' and 'ran and broke' are different facts; report the second."""
    _scores(tmp_path, "heldout_groq_gpt-oss-120b", n_ok=0, n_err=432)
    note = failed_attempts_note(tmp_path)
    assert "ATTEMPTED AND FAILED" in note
    assert "heldout_groq_gpt-oss-120b_scores.jsonl" in note
    assert "432/432" in note


def test_successful_run_produces_no_failure_note(tmp_path):
    _scores(tmp_path, "heldout_claude-haiku-4-5", n_ok=288, n_err=0)
    assert failed_attempts(tmp_path) == []
    assert failed_attempts_note(tmp_path) == ""


def test_no_attempt_produces_no_note(tmp_path):
    assert failed_attempts_note(tmp_path) == ""


@pytest.mark.parametrize("n_ok,n_err,usable", [
    (288, 0, True), (145, 143, True), (144, 144, False),
    (143, 145, False), (0, 288, False), (1, 0, True),
])
def test_majority_rule_boundary(tmp_path, n_ok, n_err, usable):
    """A tie is not a majority: half-failed is not good enough to report."""
    _scores(tmp_path, "heldout_m", n_ok=n_ok, n_err=n_err)
    assert (best_live_heldout(tmp_path) is not None) is usable


# ---------------------------------------------------------------------------
# The distinction the whole held-out analysis turns on
# ---------------------------------------------------------------------------

def test_a_rejected_report_is_a_result():
    """It chose a method and ran it; only the write-up failed the contract.

    43 of System A's 96 held-out runs land here.  Counting them as lost would
    delete the baseline's worst behaviour from the headline metric.
    """
    row = {"chosen_method": "mann_whitney", "selection_correct": True,
           "run_error": "report schema rejected: raw numeric literal ['0.001']"}
    assert produced_a_result(row) is True


def test_a_provenance_failure_is_a_result():
    row = {"chosen_method": "welch_t", "selection_correct": True,
           "run_error": "provenance failure: r2.summarize_groups.levene_p"}
    assert produced_a_result(row) is True


def test_an_authentication_failure_is_not_a_result():
    """The Groq outcome: nothing was decided, so nothing was learned."""
    row = {"chosen_method": "none", "selection_correct": False,
           "run_error": "AuthenticationError: 401"}
    assert produced_a_result(row) is False


def test_a_bad_request_is_not_a_result():
    """16 of the development medium-effort runs; a 400 decides nothing."""
    row = {"chosen_method": "none", "selection_correct": False,
           "run_error": "BadRequestError: Error code: 400"}
    assert produced_a_result(row) is False


def test_a_clean_run_is_a_result():
    assert produced_a_result({"chosen_method": "welch_t",
                              "run_error": None}) is True


def test_rows_without_the_column_fall_back_to_the_error_field():
    """Older score files predate `chosen_method`; they must still be readable."""
    assert produced_a_result({"run_error": None}) is True
    assert produced_a_result({"run_error": "AuthenticationError: 401"}) is False


def test_a_run_of_rejected_reports_still_counts_as_an_evaluation(tmp_path):
    """51 contract failures out of 288 is a finding, not a failed run."""
    d = tmp_path
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"run_id": f"r{i}", "system": "A_direct", "case_id": f"c{i}",
             "chosen_method": "welch_t", "selection_correct": True,
             "run_error": ("report schema rejected: raw numeric literal"
                           if i < 51 else None)} for i in range(288)]
    (d / "heldout_claude-haiku-4-5_scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    live = best_live_heldout(d)
    assert live is not None
    _, ok, total = live
    assert (ok, total) == (288, 288), "contract failures were counted as lost"
