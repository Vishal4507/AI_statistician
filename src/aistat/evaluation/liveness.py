"""Deciding whether a held-out evaluation actually happened.

This lives in its own module for two reasons.

The first is testability.  The conformance harness executes every check as a
side effect of import -- its decorator calls the function it decorates -- so it
cannot be imported from a test without running the entire suite, including the
check that shells out to pytest.

The second is that the question is asked in two places, the harness and the
report writer, and they must answer it identically.  When they were written
separately they drifted: the report writer looked for one hardcoded model's
filename and announced "not yet run" after a completed evaluation on any other
model.  One definition, two callers.

The rule enforced here: a run counts when it produced results, not when it
produced a file.  The Groq attempt wrote 432 rows and every one was an
authentication error.  A check that asks only whether the file has lines would
report that as a finished held-out evaluation.
"""
from __future__ import annotations

import json
from pathlib import Path

Attempt = tuple[Path, int, int]          # (scores file, n_succeeded, n_total)


def live_heldout_files(results: Path):
    """Yield every held-out scores file produced by a real model.

    Rule-based runs are the offline calibration, not a model, so they are
    excluded however complete they are.
    """
    if not results.is_dir():
        return
    for p in sorted(results.glob("heldout_*_scores.jsonl")):
        if "rulebased" in p.name:
            continue
        rows = [json.loads(line) for line in p.read_text().splitlines()
                if line.strip()]
        if rows:
            yield p, sum(1 for r in rows if produced_a_result(r)), len(rows)


def produced_a_result(row: dict) -> bool:
    """Whether one scored row carries evidence about the systems.

    A run counts when it reached a method decision.  That is deliberately not
    the same as "no error": a report rejected by the provenance contract is a
    real observation -- the system chose a method, ran it, then failed to
    describe it without inventing a number -- whereas a request that returned
    401 or 400 chose nothing and tells us only about the network.

    On the held-out Haiku run this distinguishes 51 contract failures, which
    are results, from the Groq attempt's 432 authentication errors, which are
    not.  Getting it wrong in either direction is costly: treat contract
    failures as lost and the baseline's worst behaviour disappears from the
    numbers; treat auth errors as results and a total outage reads as a
    finished evaluation.
    """
    method = row.get("chosen_method")
    if method is not None:
        return method != "none"
    return not row.get("run_error")


def best_live_heldout(results: Path) -> Attempt | None:
    """The most complete usable held-out run, or None if there isn't one.

    "Usable" means a majority of runs returned a result.  A run that mostly
    failed is a failed run; reporting it as evidence would make every downstream
    claim false.
    """
    best = None
    for path, ok, total in live_heldout_files(results):
        if ok * 2 > total and (best is None or ok > best[1]):
            best = (path, ok, total)
    return best


def failed_attempts(results: Path) -> list[Attempt]:
    """Runs that happened but did not produce a usable result."""
    return [(p, ok, tot) for p, ok, tot in live_heldout_files(results)
            if ok * 2 <= tot]


def failed_attempts_note(results: Path) -> str:
    """A prefix naming failed attempts, empty when there are none.

    "Not run" and "ran and broke" are different facts.  Collapsing the second
    into the first hides the most useful thing the record contains.
    """
    bad = failed_attempts(results)
    if not bad:
        return ""
    return ("ATTEMPTED AND FAILED: "
            + "; ".join(f"{p.name} ({tot - ok}/{tot} runs errored)"
                        for p, ok, tot in bad) + ". ")
