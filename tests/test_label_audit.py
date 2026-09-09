"""Label audit (blueprint section 4.3).

A solo build cannot supply the second reviewer the blueprint requires. This is
the substitute, and these tests defend the two things that make it worth
running: that it re-derives labels without seeing them, and that it actually
agrees with the benchmark it audits.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_audit_runs_and_agrees_with_every_label():
    r = subprocess.run([sys.executable, "scripts/audit_labels.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-2000:]

    report = json.loads((ROOT / "reports" / "label_audit.json").read_text())
    assert report["n_cases"] == 64
    assert report["agreement_rate"] == 1.0, (
        f"{len(report['disagreements'])} label(s) the audit disputes: "
        f"{[d['case_id'] for d in report['disagreements']]}")


def test_audit_discloses_that_it_is_not_independent_review():
    """The limitation must travel with the artefact, not just the write-up."""
    report = json.loads((ROOT / "reports" / "label_audit.json").read_text())
    caveat = report["caveat"].lower()
    assert "not independent" in caveat
    assert "same author" in caveat


def test_audit_never_reads_the_gold_file_when_deriving():
    """A re-derivation that peeked at the answer would prove nothing.

    Looks for actual access to the gold tree rather than the word itself -- the
    docstring legitimately says "without seeing the gold".
    """
    src = (ROOT / "scripts" / "audit_labels.py").read_text()
    body = src.split("def rederive")[1].split("def main")[0]
    forbidden = ["gold.json", "primary_method", "accepted_methods",
                 "abstain_reason"]
    for token in forbidden:
        # Strip the docstring before checking, so prose about gold is allowed.
        code = body.split('"""')[-1]
        assert token not in code, f"rederive() touches {token!r}"
