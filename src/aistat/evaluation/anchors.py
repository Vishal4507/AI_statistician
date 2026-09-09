"""Calibration anchors for blinded scoring.

The first scoring round returned intra-rater kappa of -0.231 and -0.044 between
two raters: no shared signal. Diagnosis was not carelessness. The rubric did not
say whether to judge the method choice or only the interpretation, so one rater
penalised a report for running the wrong test while the other scored its
interpretation faithfully -- on the same text, legitimately, 0 and 2.

Calibration anchors are the standard remedy for exactly that. Raters score a
handful of worked examples, see the intended answer and the reasoning, and only
then begin. It converts a rubric people read differently into one they have
practised together.

Provenance, to be disclosed: these anchors are author-adjudicated. They are used
to align raters before scoring, never as scores themselves, and the anchor items
are excluded from the scored set so no rater is graded on text they were shown
the answer to.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Anchor:
    case_id: str
    system: str
    score: int
    why: str


ANCHORS: list[Anchor] = [
    Anchor(
        case_id="pub_shoppers_1", system="A_direct", score=0,
        why=("The Results section states plainly that no method was executed and "
             "no estimate exists. The Interpretation then says \"the estimated "
             "difference is reported above\" and describes what a rank test "
             "shows. Both refer to a result that is not there, which fails "
             "question 1. Note what is NOT the reason: the advice itself may be "
             "perfectly sensible. It scores 0 because the interpretation cites "
             "evidence the report does not contain."),
    ),
    Anchor(
        case_id="syn_negbin_1", system="B_tools", score=2,
        why=("This is the anchor that matters most, and the one most likely to "
             "feel wrong. The report runs a Spearman correlation on a case whose "
             "outcome is a count -- the wrong method. Score it 2 anyway. Every "
             "number in the Interpretation appears in the Results, the direction "
             "and magnitude match, there is no causal language, and the "
             "observational limitation is named. The wrong method is already "
             "counted against this system by selection accuracy; penalising it "
             "here as well would count it twice."),
    ),
    Anchor(
        case_id="syn_welch_anova_1", system="C_protocol", score=2,
        why=("Long, and every part of the length earns its place: magnitude "
             "before significance, the effect size given both raw and "
             "bias-corrected, an explicit statement that non-rejection is not "
             "evidence of equality, and a caveat that the outcome scale is not "
             "raw duration. Do not mark it down for hedging -- naming the "
             "limitations the design implies is question 4, and this does it."),
    ),
]


def anchor_for(case_id: str, system: str) -> Anchor | None:
    return next((a for a in ANCHORS
                 if a.case_id == case_id and a.system == system), None)


def anchor_keys() -> set[tuple[str, str]]:
    return {(a.case_id, a.system) for a in ANCHORS}
