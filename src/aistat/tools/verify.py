"""Report verification (blueprint section 5.2 tool 9, section 6 step 10).

Under review finding F-A4 numeric fabrication is prevented upstream by the
ResultStore, so this pass is free to do the work it is actually good at:
semantic checks that a schema cannot express.
"""
from __future__ import annotations

import re

from aistat.provenance.store import ResultStore
from aistat.schemas.core import REF_PATTERN, FinalReport, find_raw_numbers

CAUSAL_PATTERNS = [
    r"\bcaus(e|es|ed|ing|al|ation)\b", r"\beffect of\b", r"\bimpact(s|ed)? (on|of)\b",
    r"\bleads? to\b", r"\bled to\b", r"\bresults? in\b", r"\bdrives?\b",
    r"\bproduces?\b", r"\binfluences?\b", r"\bdue to\b", r"\bbecause of\b",
    r"\bmakes? .{0,20}(increase|decrease|rise|fall)\b", r"\bimproves?\b",
    r"\breduces?\b", r"\bincreases? the\b", r"\bdecreases? the\b",
]

HEDGES = [
    r"\bassociat", r"\bcorrelat", r"\brelated\b", r"\bpredict", r"\bobservational\b",
    r"\bnot causal\b", r"\bcannot infer\b", r"\bdoes not establish\b",
    r"\bconditional on\b", r"\bno causal\b",
]

OVERGENERAL = [
    r"\ball (customers|users|students|people|patients)\b",
    r"\bin general,? (customers|users|people)\b",
    r"\balways\b", r"\bnever\b", r"\bproves?\b", r"\bconfirms? that\b",
    r"\bguarantees?\b", r"\bdefinitiv",
]

MEDIAN_CLAIM = [r"\bmedian\b"]


def _hits(text: str, patterns: list[str]) -> list[str]:
    low = text.lower()
    return [m.group(0) for p in patterns for m in re.finditer(p, low)]


def verify_report(report: FinalReport, store: ResultStore,
                  randomized: bool | None, method: str) -> dict:
    """Return a structured verdict.  Never mutates the report."""
    findings: list[dict] = []
    blocks = report.prose_blocks()
    all_text = " ".join(b.text for b in blocks.values())

    # 1. Numeric provenance -----------------------------------------------
    unknown = sorted(r for r in report.referenced() if r not in store)
    for ref in unknown:
        findings.append({"check": "numeric_provenance", "severity": "critical",
                         "detail": f"reference {ref} has no tool result"})
    raw: list[str] = []
    for name, block in blocks.items():
        for lit in find_raw_numbers(block.text):
            raw.append(f"{name}:{lit}")
    for lit in raw:
        findings.append({"check": "numeric_provenance", "severity": "critical",
                         "detail": f"raw numeric literal in prose ({lit})"})

    # 2. Causal language on observational data ----------------------------
    causal = _hits(all_text, CAUSAL_PATTERNS)
    hedged = _hits(all_text, HEDGES)
    if causal and randomized is not True:
        findings.append({
            "check": "causal_language",
            "severity": "major" if not hedged else "minor",
            "detail": f"causal phrasing on non-randomised data: {sorted(set(causal))[:5]}",
        })

    # 3. Overgeneralisation ------------------------------------------------
    over = _hits(all_text, OVERGENERAL)
    if over:
        findings.append({"check": "unsupported_inference", "severity": "major",
                         "detail": f"absolute or overgeneral claims: {sorted(set(over))[:5]}"})

    # 4. Estimand / interpretation consistency ------------------------------
    if method in ("mann_whitney", "kruskal_wallis"):
        if _hits(report.interpretation.text, MEDIAN_CLAIM):
            findings.append({
                "check": "estimand_consistency", "severity": "minor",
                "detail": ("median language for a rank test requires a stated "
                           "shape assumption"),
            })

    # 5. Interval reporting ------------------------------------------------
    if not report.selection.is_abstention:
        cited = report.referenced()
        if not any(("ci_low" in c or "ci_high" in c or "ci[" in c) for c in cited):
            findings.append({"check": "interval_reporting", "severity": "major",
                             "detail": "no confidence interval cited in the report"})
        if not any("effect_size" in c for c in cited):
            findings.append({"check": "effect_size_reporting", "severity": "minor",
                             "detail": "no effect size cited in the report"})

    # 6. Diagnostics computed then ignored ---------------------------------
    flagged = [k for k, v in store.snapshot().items()
               if k.endswith(("_flag", "separation_suspected")) and v]
    for key in flagged:
        if key not in store.used:
            findings.append({"check": "unaddressed_diagnostic", "severity": "major",
                             "detail": f"{key} was raised by a tool but never addressed"})

    # 7. Magnitude before significance -------------------------------------
    interp = report.interpretation.text.lower()
    if "p" in interp and "significant" in interp:
        if not any(w in interp for w in ("difference", "ratio", "magnitude",
                                         "larger", "smaller", "higher", "lower",
                                         "times", "points", "per")):
            findings.append({"check": "magnitude_first", "severity": "minor",
                             "detail": "significance reported without magnitude"})

    sev = {f["severity"] for f in findings}
    return {
        "passed": "critical" not in sev and "major" not in sev,
        "has_critical": "critical" in sev,
        "n_findings": len(findings),
        "n_critical": sum(f["severity"] == "critical" for f in findings),
        "n_major": sum(f["severity"] == "major" for f in findings),
        "n_minor": sum(f["severity"] == "minor" for f in findings),
        "findings": findings,
        "n_refs_cited": len(report.referenced()),
        "n_unknown_refs": len(unknown),
        "provenance_clean": not unknown and not raw,
    }
