"""Build all 64 case packages and validate them (blueprint sections 4.2, 4.3)."""
from __future__ import annotations

import json
import sys
import warnings
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
warnings.filterwarnings("ignore")

from aistat.benchmark.builder import build_all
from aistat.benchmark.registry import summary
from aistat.benchmark.validator import validate_all


def main() -> int:
    print("Building case packages ...")
    rows = build_all(write=True)
    s = summary()
    print(f"  {len(rows)} cases: {s['synthetic']} synthetic + {s['public']} public")
    print(f"  split: {s['dev']} development / {s['heldout']} held out")
    print(f"  abstention: {s['synthetic_abstention'] + s['public_abstention']}")

    errs = [r for r in rows if r["oracle_error"]]
    if errs:
        print(f"  ORACLE ERRORS: {len(errs)}")
        for e in errs[:5]:
            print(f"    {e['case_id']}: {e['oracle_error']}")

    counts = Counter(r["primary_method"] for r in rows)
    print("\n  method distribution:")
    for m, n in sorted(counts.items()):
        print(f"    {m:20s} {n}")

    print("\nValidating ...")
    v = validate_all()
    if v["passed"]:
        print(f"  all {v['n_total']} cases pass "
              "(files, hashes, seeds, leakage, split integrity)")
        return 0
    print(f"  {v['n_errors']} errors across {v['n_cases_with_errors']} cases")
    print(json.dumps(v["case_errors"], indent=2)[:3000])
    return 1


if __name__ == "__main__":
    sys.exit(main())
