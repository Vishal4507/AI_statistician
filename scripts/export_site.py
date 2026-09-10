"""Export a static, dependency-free bundle for the results explorer.

Netlify (and any static host) cannot run this project's Python: SciPy,
statsmodels, NumPy and pandas total ~321 MB against a 250 MB Lambda ceiling,
and reimplementing the statistics in JavaScript would destroy the premise that
validated libraries perform every numerical operation.

What a static host CAN do is serve everything the system has already computed.
This exports the benchmark, the scored runs, the traces and the rendered reports
as JSON so the explorer is a real artefact rather than a screenshot.
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aistat.env import load_dotenv
load_dotenv()          # credentials are project-local, not in a shell profile
warnings.filterwarnings("ignore")

import pandas as pd

BENCH = ROOT / "benchmark"
RESULTS = ROOT / "results"
SITE = ROOT / "site"
DATA = SITE / "data"

MAX_PREVIEW_ROWS = 8


def load_runs(name: str) -> list[dict]:
    p = RESULTS / f"{name}.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def load_scores(name: str) -> pd.DataFrame:
    p = RESULTS / f"{name}_scores.jsonl"
    if not p.exists():
        return pd.DataFrame()
    return pd.DataFrame([json.loads(l) for l in p.read_text().splitlines() if l.strip()])


def export_cases() -> list[dict]:
    """One entry per benchmark case: question, design card, gold, data preview."""
    out = []
    for split in ("dev", "heldout"):
        for d in sorted((BENCH / split).iterdir()):
            if not d.is_dir():
                continue
            gold = json.loads((BENCH / "gold" / d.name / "gold.json").read_text())
            man = json.loads((d / "case_manifest.json").read_text())
            card = json.loads((d / "design_card.json").read_text())
            q = (d / "question.txt").read_text()
            df = pd.read_csv(d / "data.csv")
            out.append({
                "case_id": d.name, "split": split,
                "origin": man["origin"], "family": man["family"],
                "question": q.split("\n\nAnalysis objective:")[0].strip(),
                "objective": q.split("Analysis objective:")[-1].strip(),
                "design_card": card,
                "variable_roles": man["variable_roles"],
                "n_rows": int(len(df)), "columns": [str(c) for c in df.columns],
                "preview": df.head(MAX_PREVIEW_ROWS).astype(str).to_dict("records"),
                "gold_method": gold["primary_method"],
                "accepted_methods": gold["accepted_methods"],
                "abstain_reason": gold.get("abstain_reason"),
                "required_checks": gold.get("required_checks", []),
                "rationale": gold.get("rationale", ""),
                "source": man.get("source"), "source_doi": man.get("source_doi"),
            })
    return out


def export_runs(name: str, label: str) -> dict:
    """Scored runs plus one full rendered report per (case, system)."""
    runs = load_runs(name)
    scores = load_scores(name)
    if not runs or scores.empty:
        return {}

    by_key = {}
    for r in runs:
        key = f"{r['case_id']}|{r['system']}"
        if key not in by_key and r.get("rendered"):
            # Captures recorded before the reference pattern was widened can
            # contain a template that was emitted verbatim. They are kept as
            # evidence of the defect rather than deleted, and flagged so the
            # explorer can say what they are instead of looking broken.
            residue = any("{{" in str(v) or "UNRESOLVED" in str(v)
                          for v in (r.get("rendered") or {}).values())
            by_key[key] = {
                "pre_fix_residue": residue,
                "case_id": r["case_id"], "system": r["system"],
                "method": r.get("method"),
                "abstain_reason": r.get("abstain_reason"),
                "rendered": r.get("rendered", {}),
                "trace": r.get("trace_signature", []),
                "n_tool_calls": r.get("n_tool_calls", 0),
                "revised": r.get("revised", False),
                "rejected": (r.get("selection") or {}).get("rejected_alternatives", {}),
                "verification": {
                    k: v for k, v in (r.get("verification") or {}).items()
                    if k != "findings"},
                "provenance_values": r.get("metadata", {}).get(
                    "n_provenance_values", 0),
            }

    per_system = []
    for s, g in scores.groupby("system"):
        ab = g[g.gold_is_abstention]
        per_system.append({
            "system": s, "n": int(len(g)),
            "accuracy": float(g.selection_correct.mean()),
            "abstention_recall": float(ab.chose_abstention.mean()) if len(ab) else None,
            "unsafe_rate": float(g.unsafe_selection.mean()),
            "assumption_coverage": float(g.assumption_coverage.dropna().mean()),
            "mean_tool_calls": float(g.n_tool_calls.mean()),
            "provenance_rejections": int(g.provenance_rejections.sum()),
        })

    failures = Counter(
        (r["system"], r["failure_stage"])
        for r in scores.to_dict("records") if r.get("failure_stage"))

    return {
        "label": label, "n_runs": int(len(scores)),
        "n_cases": int(scores.case_id.nunique()),
        "per_system": per_system,
        "failures": [{"system": s, "stage": st, "n": n}
                     for (s, st), n in sorted(failures.items())],
        "reports": list(by_key.values()),
        "per_case": scores.groupby(["case_id", "system"])
                          .selection_correct.mean().unstack().fillna(-1)
                          .reset_index().to_dict("records"),
    }


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)

    cases = export_cases()
    (DATA / "cases.json").write_text(json.dumps(cases, separators=(",", ":")))

    bundles = {}
    for name, label in [("heldout_rulebased_expert", "Held-out, expert policy"),
                        ("heldout_rulebased_naive", "Held-out, naive policy"),
                        ("dev_claude-opus-5_high", "Development, Claude Opus 5")]:
        b = export_runs(name, label)
        if b:
            bundles[name] = b
    (DATA / "runs.json").write_text(json.dumps(bundles, separators=(",", ":")))

    manifest = json.loads((ROOT / "data" / "raw" / "MANIFEST.json").read_text()) \
        if (ROOT / "data" / "raw" / "MANIFEST.json").exists() else {}
    audit = json.loads((ROOT / "reports" / "label_audit.json").read_text()) \
        if (ROOT / "reports" / "label_audit.json").exists() else {}

    (DATA / "meta.json").write_text(json.dumps({
        "n_cases": len(cases),
        "n_supported": sum(1 for c in cases if c["gold_method"] != "abstain"),
        "n_abstention": sum(1 for c in cases if c["gold_method"] == "abstain"),
        "n_dev": sum(1 for c in cases if c["split"] == "dev"),
        "n_heldout": sum(1 for c in cases if c["split"] == "heldout"),
        "methods": sorted({c["gold_method"] for c in cases}),
        "sources": manifest,
        "label_audit": {k: v for k, v in audit.items() if k != "disagreements"},
    }, indent=2))

    total = sum(p.stat().st_size for p in DATA.glob("*.json"))
    print(f"exported to {DATA.relative_to(ROOT)}/")
    for p in sorted(DATA.glob("*.json")):
        print(f"  {p.name:14s} {p.stat().st_size/1024:8.1f} KB")
    print(f"  {'total':14s} {total/1024:8.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
