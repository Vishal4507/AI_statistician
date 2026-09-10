"""Rebuild every result table from raw logs (blueprint section 10.3).

    python scripts/analyze.py --name heldout_rulebased_expert

Definition of done requires the tables to regenerate from the JSONL with one
command.  This is that command.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aistat.env import load_dotenv
load_dotenv()          # credentials are project-local, not in a shell profile
warnings.filterwarnings("ignore")

import pandas as pd

from aistat.evaluation.analysis import (failure_taxonomy, majority_by_case,
                                        pairwise_comparisons, risk_coverage,
                                        system_summary)
from aistat.evaluation.liveness import best_live_heldout
from aistat.evaluation.runner import RESULTS, load_scores

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def fmt(df: pd.DataFrame, floatfmt: str = "%.3f") -> str:
    return df.to_string(index=False, float_format=lambda x: floatfmt % x)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="heldout_rulebased_expert")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--live-heldout", action="store_true",
                    help="analyse whichever live held-out run exists, by "
                         "search rather than by name; exits quietly when "
                         "none has been run yet")
    args = ap.parse_args()

    run_name = args.name
    if args.live_heldout:
        # Resolved by search: the file is named for whichever model executed
        # it, so the one thing this must not do is assume.
        best = best_live_heldout(RESULTS)
        if best is None:
            print("no usable live held-out run yet -- nothing to analyse")
            return 0
        run_name = best[0].name[: -len("_scores.jsonl")]
        if not args.quiet:
            print(f"analysing live held-out run: {run_name}")

    scores = load_scores(run_name)
    REPORTS.mkdir(exist_ok=True)

    summary = system_summary(scores)
    majority = majority_by_case(scores)
    rc = risk_coverage(scores)
    pairs = pairwise_comparisons(majority)
    fails = failure_taxonomy(scores)

    out = {
        "n_runs": len(scores),
        "n_cases": int(scores["case_id"].nunique()),
        "n_systems": int(scores["system"].nunique()),
        "reps": int(scores.groupby(["system", "case_id"]).size().max()),
        "system_summary": summary.to_dict("records"),
        "risk_coverage": rc.to_dict("records"),
        "pairwise": pairs.to_dict("records"),
        "failures": fails.to_dict("records"),
        "rep_agreement_mean": float(majority["rep_agreement"].mean()),
        "pct_unanimous": float(majority["unanimous"].mean()),
    }
    (REPORTS / f"{run_name}_results.json").write_text(json.dumps(out, indent=2, default=str))
    for table, df in (("system_summary", summary), ("risk_coverage", rc),
                      ("pairwise", pairs), ("failures", fails),
                      ("majority_by_case", majority)):
        df.to_csv(REPORTS / f"{run_name}_{table}.csv", index=False)

    if not args.quiet:
        cols = ["system", "n_runs", "selection_accuracy", "acc_ci_low", "acc_ci_high",
                "abstention_recall", "unsafe_selection_rate", "assumption_coverage",
                "unsupported_inference_rate", "provenance_rejections",
                "mean_tool_calls", "mean_llm_calls"]
        print("\n=== System summary " + "=" * 60)
        print(fmt(summary[cols]))
        print("\n=== Risk-coverage (review finding F-A3) " + "=" * 39)
        print(fmt(rc[["system", "coverage", "selective_accuracy", "overall_accuracy",
                      "accuracy_on_supported", "abstention_recall",
                      "n_abstention_cases", "unsafe_selection_rate"]]))
        print("\n=== Paired comparisons (majority decision per case) " + "=" * 27)
        print(fmt(pairs[["system_a", "system_b", "n_cases", "acc_a", "acc_b",
                         "uplift_b_minus_a", "uplift_ci_low", "uplift_ci_high",
                         "mcnemar_p"]]))
        print("\n=== Failure taxonomy (blueprint 8.4) " + "=" * 42)
        print(fmt(fails))
        print(f"\n  repetition agreement {out['rep_agreement_mean']:.3f}, "
              f"unanimous on {out['pct_unanimous']:.1%} of cases")
        print(f"  tables -> {REPORTS}/{run_name}_*.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
