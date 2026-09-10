"""Completed runs must survive an interrupted evaluation.

A held-out evaluation is the one part of this project that costs money and
cannot be re-derived from anything already on disk.  The runner originally
wrote its results in a single append after the final run, which meant that an
interruption at run 287 of 288 discarded all 287.  Worse, `_completed()` reads
those same files to decide what to skip, so the retry would start from zero and
spend the budget a second time on work already done.

These tests pin the fix: results reach disk while the run is still going, and
whatever finished is kept when the run ends early.
"""
from __future__ import annotations

import json

import pytest

from aistat.agents.rulebased import RuleBasedClient
from aistat.evaluation import runner


def _rows(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def test_results_reach_disk_before_the_run_ends(tmp_path, monkeypatch):
    """Observed from inside the run, not inferred from the final state.

    The factory runs once per run, so what it sees on disk is what a crash at
    that moment would have left behind.
    """
    monkeypatch.setattr(runner, "RESULTS", tmp_path)
    monkeypatch.setattr(runner, "FLUSH_EVERY", 4)
    scores = tmp_path / "dur_scores.jsonl"

    persisted = []

    def factory():
        persisted.append(len(_rows(scores)) if scores.exists() else 0)
        return RuleBasedClient("expert")

    cases = runner.list_cases("heldout")[:6]
    runner.evaluate(factory, split="heldout", reps=1, out_name="dur",
                    case_ids=cases, max_workers=1, write_traces=False,
                    progress=False, preflight=False)

    assert max(persisted) >= 4, (
        f"nothing was persisted mid-run (saw {persisted}); a crash would have "
        "discarded every completed run")
    assert len(_rows(scores)) == len(cases) * len(runner.SYSTEMS)


def test_an_interruption_keeps_what_finished(tmp_path, monkeypatch):
    """Ctrl-C at run N keeps runs 1..N-1 instead of throwing them away."""
    monkeypatch.setattr(runner, "RESULTS", tmp_path)
    monkeypatch.setattr(runner, "FLUSH_EVERY", 2)
    scores = tmp_path / "irq_scores.jsonl"

    started = {"n": 0}

    def factory():
        started["n"] += 1
        if started["n"] > 5:
            raise KeyboardInterrupt("simulated Ctrl-C")
        return RuleBasedClient("expert")

    cases = runner.list_cases("heldout")[:8]
    with pytest.raises(KeyboardInterrupt):
        runner.evaluate(factory, split="heldout", reps=1, out_name="irq",
                        case_ids=cases, max_workers=1, write_traces=False,
                        progress=False, preflight=False)

    kept = _rows(scores)
    assert kept, "an interrupted run threw away everything it had completed"
    assert len(kept) >= 4


def test_a_resumed_run_does_not_repeat_completed_work(tmp_path, monkeypatch):
    """The point of persisting early: the retry must not pay twice."""
    monkeypatch.setattr(runner, "RESULTS", tmp_path)
    monkeypatch.setattr(runner, "FLUSH_EVERY", 2)
    cases = runner.list_cases("heldout")[:4]

    first = runner.evaluate(lambda: RuleBasedClient("expert"), split="heldout",
                            reps=1, out_name="res", case_ids=cases,
                            max_workers=1, write_traces=False, progress=False,
                            preflight=False)
    second = runner.evaluate(lambda: RuleBasedClient("expert"), split="heldout",
                             reps=1, out_name="res", case_ids=cases,
                             max_workers=1, write_traces=False, progress=False,
                             preflight=False)
    assert first["n_run"] > 0
    assert second["n_run"] == 0, "resuming re-ran work already recorded"
