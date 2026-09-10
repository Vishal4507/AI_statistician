"""Independent label audit (blueprint section 4.3).

The blueprint requires a second reviewer on every gold label.  A solo build
cannot meet that, and quietly skipping it would undermine every accuracy number
in the report.  This is the substitute, and its weakness is stated plainly:

  1. 48 of 64 labels are construction-derived -- they follow mechanically from
     generator parameters and realised sample statistics, so they are not
     opinions and do not need a second opinion.
  2. The 16 public labels ARE judgements. Each is re-derived here from the case
     package alone, independently of the label, and disagreements are reported.
  3. This is NOT independent review: the same author wrote both the labelling
     logic and this audit. It catches internal inconsistency, not shared
     misconception. Disclose it as such.

    python scripts/audit_labels.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aistat.env import load_dotenv
load_dotenv()          # credentials are project-local, not in a shell profile
warnings.filterwarnings("ignore")

import pandas as pd

from aistat.agents.policy import design_verdict, infer_task, route
from aistat.schemas.core import ABSTAIN
from aistat.tools import diagnostics
from aistat.tools.registry import ToolRegistry
from aistat.provenance.store import ResultStore

BENCH = ROOT / "benchmark"


def rederive(case_dir: Path) -> tuple[str, str]:
    """Derive a method from the case package alone, without seeing the gold."""
    df = pd.read_csv(case_dir / "data.csv")
    card = json.loads((case_dir / "design_card.json").read_text())
    man = json.loads((case_dir / "case_manifest.json").read_text())
    question = (case_dir / "question.txt").read_text()

    task = infer_task(df, man["variable_roles"])
    reason, _ = design_verdict(card, df, task)
    if reason:
        return ABSTAIN, reason

    store = ResultStore()
    reg = ToolRegistry(df, store)
    evidence, slot_ids = {}, {}
    if task.kind in ("two_group", "multi_group"):
        for tool, slot in (("summarize_groups", "summary"),
                           ("check_group_assumptions", "assumptions")):
            tc = reg.call(tool, {"outcome": task.outcome, "group": task.group})
            if not tc.is_error:
                evidence[slot] = tc.payload; slot_ids[slot] = tc.call_id
    elif task.kind == "categorical":
        tc = reg.call("check_contingency", {"var1": task.var1, "var2": task.var2})
        if not tc.is_error:
            evidence["contingency"] = tc.payload; slot_ids["contingency"] = tc.call_id
    elif task.kind == "association":
        tc = reg.call("check_association", {"x": task.var1, "y": task.var2})
        if not tc.is_error:
            evidence["association"] = tc.payload; slot_ids["association"] = tc.call_id
    elif task.kind == "regression_count":
        tc = reg.call("fit_regression", {"method": "poisson", "outcome": task.outcome,
                                         "predictors": list(task.predictors),
                                         "exposure": task.exposure})
        if not tc.is_error:
            evidence["dispersion"] = tc.payload

    method, _, _ = route(task, evidence, question, slot_ids=slot_ids)
    return method, ""


def main() -> int:
    rows = []
    for split in ("dev", "heldout"):
        for d in sorted((BENCH / split).iterdir()):
            if not d.is_dir():
                continue
            gold = json.loads((BENCH / "gold" / d.name / "gold.json").read_text())
            man = json.loads((d / "case_manifest.json").read_text())
            try:
                derived, reason = rederive(d)
            except Exception as exc:
                derived, reason = f"ERROR:{type(exc).__name__}", str(exc)[:80]
            accepted = set(gold["accepted_methods"])
            rows.append({
                "case_id": d.name, "origin": man["origin"], "split": split,
                "gold": gold["primary_method"], "accepted": sorted(accepted),
                "audit": derived,
                "agrees": derived in accepted,
                "reason_matches": (reason == (gold.get("abstain_reason") or ""))
                if derived == ABSTAIN else None,
            })

    df = pd.DataFrame(rows)
    print("Independent label audit\n")
    for origin, g in df.groupby("origin"):
        n_ok = int(g.agrees.sum())
        print(f"  {origin:10s} {n_ok}/{len(g)} agree with the accepted set "
              f"({n_ok/len(g):.1%})")

    dis = df[~df.agrees]
    if len(dis):
        print(f"\n  {len(dis)} disagreement(s):\n")
        for _, r in dis.iterrows():
            print(f"    {r.case_id:32s} gold={r.gold:18s} audit={r.audit}")
            print(f"      accepted set: {r.accepted}")
    else:
        print("\n  No disagreements.")

    ab = df[df.gold == ABSTAIN]
    if len(ab):
        rm = ab.reason_matches.dropna()
        print(f"\n  abstention reasons matched: {int(rm.sum())}/{len(rm)}")

    out = ROOT / "reports" / "label_audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "n_cases": len(df),
        "n_agree": int(df.agrees.sum()),
        "agreement_rate": float(df.agrees.mean()),
        "by_origin": {k: float(g.agrees.mean()) for k, g in df.groupby("origin")},
        "disagreements": dis.to_dict("records"),
        "caveat": ("Not independent review -- the same author wrote both the "
                   "labelling logic and this audit. Catches internal "
                   "inconsistency, not shared misconception."),
    }, indent=2, default=str))
    print(f"\n  written to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
