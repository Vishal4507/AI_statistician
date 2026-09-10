"""Blinded interpretation scoring (blueprint section 8.3).

    python scripts/score_blinded.py --prepare heldout_claude-opus-5
    # a human scores reports/blinded/scores_blank.csv
    python scripts/score_blinded.py --ingest reports/blinded/scores_blank.csv

The blueprint requires a human scorer blind to system identity, with at least
20% double-scored and agreement reported.  This prepares the packet, seals the
key, and joins them back afterwards.  It cannot do the scoring: that judgement
is the metric.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aistat.env import load_dotenv
load_dotenv()          # credentials are project-local, not in a shell profile
warnings.filterwarnings("ignore")

from aistat.evaluation.blinded import RUBRIC, Session, base_id, ingest

OUT = ROOT / "reports" / "blinded"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", metavar="RUN_NAME",
                    help="build a scoring packet from results/<RUN_NAME>.jsonl")
    ap.add_argument("--ingest", metavar="CSV",
                    help="join completed scores back to the sealed key")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap the number of distinct reports presented")
    ap.add_argument("--double", type=float, default=0.20)
    args = ap.parse_args()

    if args.prepare:
        try:
            session = Session.from_runs(args.prepare, double_fraction=args.double,
                                        limit=args.limit)
        except FileNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 2
        packet, sheet, key = session.write_packet(OUT)
        n_distinct = len({base_id(i.item_id) for i in session.items})
        print(f"Prepared {len(session.items)} presentations of {n_distinct} "
              f"distinct reports")
        if session.excluded:
            print(f"  excluded {len(session.excluded)} report(s) carrying an "
                  "unresolved template -- they cannot be scored fairly and the\n"
                  "  visible placeholder would break the blinding. Listed in "
                  "excluded.json; disclose in the write-up.")
        print()
        print(f"  packet     {packet.relative_to(ROOT)}")
        print(f"  score here {sheet.relative_to(ROOT)}")
        print(f"  sealed key {key.relative_to(ROOT)}  <- do not open until scored")
        print("\n  Rubric:")
        for k, v in RUBRIC.items():
            print(f"    {k}  {v}")
        print(f"\n  {int(args.double * 100)}% are deliberate repeats, shuffled in, "
              "so inter-rater\n  agreement can be computed. Score each occurrence "
              "independently.")
        return 0

    if args.ingest:
        csv = Path(args.ingest)
        key = OUT / "KEY_do_not_open_until_scored.json"
        if not csv.exists() or not key.exists():
            print(f"missing {csv if not csv.exists() else key}", file=sys.stderr)
            return 2
        result = ingest(csv, key)
        print(f"Scored {result['n_scored']} presentations\n")
        print(f"  {'system':14s} {'n':>4s} {'mean':>6s} {'fully supported':>16s} "
              f"{'incorrect':>10s}")
        for r in result["per_system"]:
            print(f"  {str(r['system']):14s} {r['n']:4d} {r['mean']:6.2f} "
                  f"{r['full_support']:16.2f} {r['incorrect']:10.2f}")
        print(f"\n  double-scored: {result['n_double_scored']} reports")
        if result["exact_agreement"] is not None:
            print(f"  exact agreement: {result['exact_agreement']:.3f}")
            print(f"  Cohen's kappa:   {result['cohens_kappa']:.3f}")
        else:
            print("  too few repeats to compute agreement")
        (ROOT / "reports" / "blinded_interpretation.json").write_text(
            json.dumps(result, indent=2, default=str))
        print(f"\n  written to reports/blinded_interpretation.json")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
