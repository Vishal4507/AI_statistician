"""Inter-rater reliability for blinded interpretation scoring (blueprint 8.3).

    python scripts/analyse_reliability.py

The blueprint asks for agreement to be reported. It does not say the agreement
has to be good -- and reporting that a scoring round failed its reliability
check, with a diagnosis, is a complete treatment of the requirement. Quietly
reporting the mean score without the agreement statistic would not be.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aistat.env import load_dotenv
load_dotenv()          # credentials are project-local, not in a shell profile

import numpy as np

RELI = ROOT / "reports" / "reliability"
CATS = (0, 1, 2)


def load(path: Path) -> dict[str, int]:
    return {r["item_id"]: int(r["score"])
            for r in csv.DictReader(path.open()) if r["score"].strip()}


def kappa(x: list[int], y: list[int]) -> tuple[float, float]:
    """Cohen's kappa with observed agreement."""
    n = len(x)
    if n == 0:
        return float("nan"), float("nan")
    po = sum(a == b for a, b in zip(x, y)) / n
    px = np.array([x.count(c) / n for c in CATS])
    py = np.array([y.count(c) / n for c in CATS])
    pe = float((px * py).sum())
    return po, ((po - pe) / (1 - pe) if pe < 1 else 1.0)


def interpret(k: float) -> str:
    if k != k:
        return "not computable"
    if k < 0:
        return "worse than chance"
    if k < 0.20:
        return "slight"
    if k < 0.40:
        return "fair"
    if k < 0.60:
        return "moderate"
    if k < 0.80:
        return "substantial"
    return "almost perfect"


def main() -> int:
    sheets = sorted(RELI.glob("round*_rater*.csv"))
    if not sheets:
        print(f"no score sheets in {RELI.relative_to(ROOT)}", file=sys.stderr)
        return 2

    raters = {p.stem.split("_rater")[-1]: load(p) for p in sheets}
    out: dict = {"n_raters": len(raters), "raters": {}}

    print("Blinded interpretation scoring — reliability\n")
    print("Intra-rater (the same report presented twice, unmarked):")
    for name, d in raters.items():
        pairs = [(d[k], d[k[:-3]]) for k in d
                 if k.endswith("-r2") and k[:-3] in d]
        po, k = kappa([a for a, _ in pairs], [b for _, b in pairs])
        print(f"  rater {name}: {len(pairs)} pairs, agreement {po:.0%}, "
              f"kappa {k:+.3f} ({interpret(k)})")
        out["raters"][name] = {"n_double_scored": len(pairs),
                              "self_agreement": po, "self_kappa": k,
                              "reading": interpret(k)}

    names = list(raters)
    if len(names) >= 2:
        a, b = raters[names[0]], raters[names[1]]
        common = [k for k in a if k in b and not k.endswith("-r2")]
        x, y = [a[k] for k in common], [b[k] for k in common]
        po, k = kappa(x, y)
        far = sum(1 for p, q in zip(x, y) if abs(p - q) == 2)
        print(f"\nInter-rater ({names[0]} vs {names[1]}):")
        print(f"  {len(common)} shared reports, agreement {po:.0%}, "
              f"kappa {k:+.3f} ({interpret(k)})")
        print(f"  {far} ({far/len(common):.0%}) scored at opposite ends "
              "of the scale")
        out["inter_rater"] = {"n": len(common), "agreement": po, "kappa": k,
                              "reading": interpret(k), "opposite_ends": far}

    usable = all(r["self_kappa"] > 0.4 for r in out["raters"].values()) and \
        out.get("inter_rater", {}).get("kappa", 0) > 0.4
    out["usable"] = usable
    print(f"\nVerdict: scores are {'usable' if usable else 'NOT usable'} "
          "as the interpretation metric.")
    if not usable:
        print("  Chance agreement on a 3-point scale is about 33%. A round that "
              "does not\n  clear it carries no signal, and reporting a mean "
              "score from it would be\n  reporting noise.")

    (RELI / "reliability.json").write_text(json.dumps(out, indent=2))
    print(f"\n  written to {(RELI / 'reliability.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
