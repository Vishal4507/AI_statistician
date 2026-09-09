"""Blinded interpretation scoring (blueprint section 8.2 metric 5, section 8.3).

The blueprint requires a 0-2 rubric applied by a human scorer who is blind to
system identity, with at least 20% of reports double-scored and inter-rater
agreement reported.  No API key substitutes for that: it is a judgement about
whether prose is supported by evidence, and the programmatic proxy in
``scorers.py`` covers only the mechanically checkable half.

This module supplies the instrument.  It shuffles reports, strips every cue to
which system produced them, presents one at a time, and records scores against
a sealed key that is only joined back after scoring is complete.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"

RUBRIC = {
    0: "Incorrect -- the interpretation misstates the estimand, the direction, "
       "or the strength of evidence.",
    1: "Partly correct -- broadly right but overreaches, omits a material "
       "limitation, or states significance without magnitude.",
    2: "Fully supported -- every substantive claim follows from the reported "
       "result and the stated design.",
}

# Phrases that would reveal which system produced a report.  Ordered longest
# first so a compound tell ("System C, the structured agent") is replaced once
# rather than twice -- doubled substitutions leave ungrammatical text, which is
# itself a cue about which reports were edited.
_TELLS = [
    (re.compile(r"\bSystems? [ABC](,? the (structured agent|direct LLM|"
                r"tool-enabled baseline))?", re.I), "the analysis"),
    (re.compile(r"\b(A_direct|B_tools|C_protocol)\b"), "the analysis"),
    (re.compile(r"\bthe (structured agent|direct LLM|tool-enabled baseline)\b",
                re.I), "the analysis"),
    (re.compile(r"\bstructured agent\b", re.I), "analysis"),
    (re.compile(r"\bdirect LLM\b", re.I), "analysis"),
    (re.compile(r"\bno method was executed, so no\b", re.I), "No"),
    (re.compile(r"\bno method was executed\b", re.I),
     "no estimate is reported"),
    (re.compile(r"[^.]*\bthe recommendation above is advisory\b[^.]*\.\s*",
                re.I), ""),
    (re.compile(r"\bunconstrained tool use\b", re.I), "the analysis"),
    (re.compile(r"\bone permitted revision\b", re.I), "a revision"),
]

# Applied after substitution to repair the seams.
_TIDY = [
    (re.compile(r"\bthe the\b", re.I), "the"),
    (re.compile(r"\ba the\b", re.I), "the"),
    (re.compile(r"\bthe analysis, the analysis\b", re.I), "the analysis"),
    (re.compile(r"\s+,"), ","),
    (re.compile(r",\s*,"), ","),
    (re.compile(r"\s{2,}"), " "),
    (re.compile(r"\s+\."), "."),
    # An appositive comma left dangling when the phrase it set off was removed.
    (re.compile(r",\s+(selected|chose|abstained|reported|fitted|executed)\b"),
     r" \1"),
]

SECTIONS = ("problem_statement", "data_audit", "method_decision", "results",
            "interpretation", "limitations")

REPEAT_SUFFIX = "-r2"
"""Marks the second presentation of a double-scored report.

Item ids are hex, so a suffix of "b" collides with originals that legitimately
end in b -- and stripping it would silently mis-pair scores and corrupt the
agreement statistic. A hyphen cannot occur in hex.
"""


def base_id(item_id: str) -> str:
    """The original id behind a presentation, repeat or not."""
    return item_id.split(REPEAT_SUFFIX)[0]


def blind(text: str) -> str:
    """Remove identifying phrasing without altering substantive content.

    Substitution is followed by a tidy pass: a scorer who can spot which
    reports were edited is no longer blind, so the output must read as though
    it were written that way.
    """
    for pattern, replacement in _TELLS:
        text = pattern.sub(replacement, text)
    for pattern, replacement in _TIDY:
        text = pattern.sub(replacement, text)
    return text.strip()


@dataclass
class Item:
    """One report presented for scoring, with its origin sealed."""

    item_id: str
    case_id: str
    system: str          # sealed -- never shown to the scorer
    run_id: str
    sections: dict[str, str]

    def presented(self) -> str:
        titles = {"problem_statement": "Problem statement",
                  "data_audit": "Data audit", "method_decision": "Method decision",
                  "results": "Results", "interpretation": "Interpretation",
                  "limitations": "Limitations"}
        out = [f"REPORT {self.item_id}", ""]
        for key in SECTIONS:
            if self.sections.get(key):
                out += [f"## {titles[key]}", blind(self.sections[key]), ""]
        return "\n".join(out)


@dataclass
class Session:
    """A blinded scoring session over one run set."""

    items: list[Item] = field(default_factory=list)
    double_fraction: float = 0.20
    seed: int = 20260909
    excluded: list[dict] = field(default_factory=list)
    """Reports withheld from scoring, with the reason. Belongs in the write-up."""

    @classmethod
    def from_runs(cls, run_name: str, *, double_fraction: float = 0.20,
                  seed: int = 20260909, limit: int | None = None) -> "Session":
        path = RESULTS / f"{run_name}.jsonl"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found -- run an evaluation before scoring")

        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        rows = [r for r in rows if not r.get("error") and r.get("rendered")]

        # A report carrying an unresolved template cannot be scored fairly: the
        # statistic the interpretation rests on is simply absent, so a low score
        # would record a harness defect rather than a judgement about the prose.
        # The visible {{...}} is also a cue, which would end the blinding.
        # Excluded, counted, and reported rather than silently dropped.
        def _unrenderable(r: dict) -> bool:
            return any("{{" in str(v) or "UNRESOLVED" in str(v)
                       for v in (r.get("rendered") or {}).values())

        excluded = [r for r in rows if _unrenderable(r)]
        rows = [r for r in rows if not _unrenderable(r)]

        items = []
        for r in rows:
            # A stable, opaque id: the scorer cannot infer origin from ordering,
            # and the same report gets the same id across sessions.
            h = hashlib.sha256(r["run_id"].encode()).hexdigest()[:8]
            items.append(Item(item_id=f"R{h}", case_id=r["case_id"],
                              system=r["system"], run_id=r["run_id"],
                              sections={k: str(v) for k, v in
                                        (r.get("rendered") or {}).items()}))

        rng = random.Random(seed)
        rng.shuffle(items)
        if limit:
            items = items[:limit]

        # Double-scored subset, drawn before presentation so the scorer cannot
        # tell which items are repeats.
        n_double = max(1, int(len(items) * double_fraction))
        repeats = rng.sample(items, min(n_double, len(items)))
        for item in repeats:
            items.append(Item(item_id=item.item_id + REPEAT_SUFFIX,
                              case_id=item.case_id, system=item.system,
                              run_id=item.run_id, sections=item.sections))
        rng.shuffle(items)
        return cls(items=items, double_fraction=double_fraction, seed=seed,
                   excluded=[{"run_id": r.get("run_id"),
                              "case_id": r.get("case_id"),
                              "system": r.get("system"),
                              "reason": "unresolved template in the rendered report"}
                             for r in excluded])

    # -- export / import ---------------------------------------------------

    def write_packet(self, out_dir: Path) -> tuple[Path, Path, Path]:
        """Write the scoring packet, the blank score sheet, and the sealed key."""
        out_dir.mkdir(parents=True, exist_ok=True)

        packet = [
            "# Blinded interpretation scoring",
            "",
            "Score each report 0-2 on whether its **interpretation and limitations**",
            "are supported by the result it reports. Do not score writing quality,",
            "and do not try to work out which system produced it.",
            "",
            "| Score | Meaning |",
            "|---|---|",
        ] + [f"| {k} | {v} |" for k, v in RUBRIC.items()] + [
            "",
            "Some reports appear twice, deliberately. Score each occurrence on its",
            "own; do not try to remember or match them.",
            "",
            "Record scores in `scores_blank.csv`, then run:",
            "",
            "    python scripts/score_blinded.py --ingest reports/blinded/scores_blank.csv",
            "",
            "---",
            "",
        ]
        for item in self.items:
            packet.append(item.presented())
            packet.append("-" * 72)
            packet.append("")

        packet_path = out_dir / "packet.md"
        packet_path.write_text("\n".join(packet))

        sheet = ["item_id,score,notes"] + [f"{i.item_id},," for i in self.items]
        sheet_path = out_dir / "scores_blank.csv"
        sheet_path.write_text("\n".join(sheet) + "\n")

        key = {i.item_id: {"system": i.system, "case_id": i.case_id,
                           "run_id": i.run_id} for i in self.items}
        key_path = out_dir / "KEY_do_not_open_until_scored.json"
        key_path.write_text(json.dumps(key, indent=2))

        if self.excluded:
            (out_dir / "excluded.json").write_text(
                json.dumps(self.excluded, indent=2))

        return packet_path, sheet_path, key_path


def ingest(scores_csv: Path, key_json: Path) -> dict:
    """Join completed scores to the sealed key and compute agreement."""
    import pandas as pd

    scores = pd.read_csv(scores_csv)
    scores = scores[scores["score"].notna()]
    if scores.empty:
        raise ValueError("no scores recorded in the sheet")
    scores["score"] = scores["score"].astype(int)
    key = json.loads(key_json.read_text())

    scores["system"] = scores["item_id"].map(lambda i: key.get(i, {}).get("system"))
    scores["case_id"] = scores["item_id"].map(lambda i: key.get(i, {}).get("case_id"))
    scores["base_id"] = scores["item_id"].map(base_id)

    per_system = (scores.groupby("system")["score"]
                  .agg(n="size", mean="mean", full_support=lambda s: (s == 2).mean(),
                       incorrect=lambda s: (s == 0).mean())
                  .reset_index())

    # Agreement on the double-scored subset.
    dupes = scores[scores.duplicated("base_id", keep=False)]
    agreement = exact = None
    if len(dupes) >= 4:
        paired = dupes.groupby("base_id")["score"].agg(list)
        paired = paired[paired.map(len) == 2]
        if len(paired):
            a = [p[0] for p in paired]
            b = [p[1] for p in paired]
            exact = sum(x == y for x, y in zip(a, b)) / len(a)
            # Cohen's kappa on a 3-point ordinal scale.
            import numpy as np
            cats = [0, 1, 2]
            obs = exact
            pa = np.array([sum(1 for x in a if x == c) / len(a) for c in cats])
            pb = np.array([sum(1 for x in b if x == c) / len(b) for c in cats])
            pe = float((pa * pb).sum())
            agreement = (obs - pe) / (1 - pe) if pe < 1 else 1.0

    return {
        "n_scored": int(len(scores)),
        "per_system": per_system.to_dict("records"),
        "n_double_scored": int(len(dupes) // 2),
        "exact_agreement": exact,
        "cohens_kappa": agreement,
    }
