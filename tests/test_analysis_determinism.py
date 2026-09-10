"""The same results file must always produce the same numbers.

`majority_by_case` collapsed repetitions with `max(set(methods), key=...)`.
Set iteration order depends on PYTHONHASHSEED, so a tie was resolved
differently in every process.  With two repetitions each disagreement between
runs is a 1-1 tie, and on the held-out evaluation that alone moved McNemar's
p-value between 0.016 and 0.125 -- straddling 0.05 -- on identical data.

A capstone whose conclusions change when the reader re-runs the analysis has
no conclusions, so determinism is pinned here rather than assumed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from aistat.evaluation.analysis import majority_by_case, pairwise_comparisons

ROOT = Path(__file__).resolve().parent.parent


def _frame(rows):
    cols = ["system", "case_id", "rep", "chosen_method", "selection_correct",
            "gold_is_abstention", "chose_abstention", "unsafe_selection"]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows])


def test_a_tie_goes_to_the_earliest_repetition():
    """Two reps, two different methods: the rule must be stated, not emergent."""
    df = _frame([
        ("C_protocol", "c1", 0, "welch_t", True, False, False, False),
        ("C_protocol", "c1", 1, "student_t", False, False, False, False),
    ])
    row = majority_by_case(df).iloc[0]
    assert row.majority_method == "welch_t"
    assert bool(row.majority_correct) is True
    assert row.rep_agreement == 0.5
    assert not bool(row.unanimous)


def test_tie_break_ignores_row_order_in_the_file():
    """Runs are written in completion order, which a thread pool won't repeat."""
    forward = _frame([
        ("C_protocol", "c1", 0, "welch_t", True, False, False, False),
        ("C_protocol", "c1", 1, "student_t", False, False, False, False),
    ])
    shuffled = forward.iloc[::-1].reset_index(drop=True)
    assert (majority_by_case(forward).majority_method.iloc[0]
            == majority_by_case(shuffled).majority_method.iloc[0] == "welch_t")


def test_a_real_majority_still_wins():
    df = _frame([
        ("C_protocol", "c1", 0, "welch_t", True, False, False, False),
        ("C_protocol", "c1", 1, "student_t", False, False, False, False),
        ("C_protocol", "c1", 2, "student_t", False, False, False, False),
    ])
    row = majority_by_case(df).iloc[0]
    assert row.majority_method == "student_t"
    assert bool(row.majority_correct) is False


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_identical_output_under_any_hash_seed(seed):
    """The regression itself: run the analysis in a fresh interpreter."""
    scores = ROOT / "results" / "heldout_rulebased_expert_scores.jsonl"
    if not scores.exists():
        pytest.skip("no results to analyse in this checkout")
    code = (
        "import sys; sys.path.insert(0, 'src');"
        "from aistat.evaluation.analysis import majority_by_case,"
        " pairwise_comparisons;"
        "from aistat.evaluation.runner import load_scores;"
        "pw = pairwise_comparisons(majority_by_case("
        "load_scores('heldout_rulebased_expert')));"
        "print(pw.to_csv(index=False))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True,
                         env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr
    test_identical_output_under_any_hash_seed.seen = getattr(
        test_identical_output_under_any_hash_seed, "seen", None) or out.stdout
    assert out.stdout == test_identical_output_under_any_hash_seed.seen
