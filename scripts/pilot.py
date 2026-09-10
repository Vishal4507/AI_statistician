"""Two-tier development pilot (review finding F-A2).

MUST be run before the prompts are frozen and before any held-out contact.

The purpose is to answer one question with data rather than hope: does the
tool-enabled baseline leave enough headroom for the protocol to show measurable
uplift on this model tier? If System B already scores near ceiling on the
development set, a 10-point uplift target cannot be met, and you would otherwise
discover that in week 5 with a frozen benchmark and no time to react.

    python scripts/pilot.py --tiers claude-opus-5 claude-haiku-4-5

Outputs a headroom table and a recommendation. The tier you choose here is
recorded in reports/pilot_decision.json and must not be revisited after the
held-out run begins.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aistat.env import load_dotenv
load_dotenv()          # credentials are project-local, not in a shell profile
warnings.filterwarnings("ignore")

from aistat.agents.llm import api_key_available
from aistat.evaluation.analysis import system_summary, wilson_ci
from aistat.evaluation.runner import evaluate, load_scores

REPORTS = ROOT / "reports"
HEADROOM_FLOOR = 0.10       # the blueprint's uplift target


PRICE = {"claude-opus-5": (5.0, 25.0), "claude-fable-5": (10.0, 50.0),
         "claude-sonnet-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0)}
N_HELDOUT_RUNS = 144            # 48 held-out cases x 3 repetitions, per system


def _run_config(model: str, effort: str, reps: int, workers: int) -> str:
    from aistat.agents.llm import AnthropicClient
    name = f"dev_{model.replace('.', '-')}_{effort}"
    evaluate(lambda: AnthropicClient(model=model, effort=effort),
             split="dev", reps=reps, out_name=name, max_workers=workers)
    return name


def _project_cost(scores, model: str) -> float:
    """Extrapolate the full held-out cost from a development run."""
    pin, pout = PRICE.get(model, (5.0, 25.0))
    n_dev_runs = max(len(scores), 1)
    per_run_in = scores["input_tokens"].sum() / n_dev_runs
    per_run_out = scores["output_tokens"].sum() / n_dev_runs
    per_run_cache = scores["cache_read_tokens"].sum() / n_dev_runs
    n_systems = scores["system"].nunique() or 3
    total_runs = N_HELDOUT_RUNS * n_systems
    billed_in = max(per_run_in - per_run_cache, 0) * total_runs
    return (billed_in / 1e6 * pin
            + per_run_cache * total_runs / 1e6 * pin * 0.1
            + per_run_out * total_runs / 1e6 * pout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", nargs="+", default=["claude-opus-5"])
    ap.add_argument("--efforts", nargs="+", default=["high", "medium"],
                    help="effort levels to sweep; 85%% of cost is output "
                         "tokens, and effort is what drives them")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--offline", action="store_true",
                    help="use the rule-based policies as stand-in tiers")
    ap.add_argument("--budget", type=float, default=None,
                    help="hard spend ceiling in USD for this pilot AND the "
                         "held-out run it informs; configurations that do not "
                         "fit are dropped rather than started")
    ap.add_argument("--yes", action="store_true",
                    help="skip the pre-flight confirmation")
    args = ap.parse_args()

    REPORTS.mkdir(exist_ok=True)
    rows = []

    # ---- pre-flight ------------------------------------------------------
    if not args.offline and api_key_available():
        from aistat.evaluation.budget import estimate, plan
        from aistat.evaluation.runner import list_cases

        n_dev = len(list_cases("dev"))
        configs = [(m, e) for m in args.tiers for e in args.efforts]
        keep, dropped = plan(configs, n_cases=n_dev, reps=args.reps,
                             budget_usd=args.budget)

        pilot_cost = sum(est.usd for _, _, est in keep)
        print("Pre-flight estimate\n")
        for m, e, est in keep:
            print(f"  pilot   {est.describe()}")
        for d in dropped:
            print(f"  DROPPED {d}")

        # The pilot exists to inform a held-out run.  Spending the whole budget
        # on the pilot leaves a decision and no experiment -- state that plainly
        # rather than discovering it afterwards.
        n_held = len(list_cases("heldout"))
        cheapest_full = min(
            (estimate(m, e, n_cases=n_held, reps=3) for m, e, _ in keep or
             [(t, f, None) for t in args.tiers for f in args.efforts]),
            key=lambda x: x.usd)
        print(f"\n  pilot subtotal            ${pilot_cost:,.2f}")
        print(f"  cheapest held-out run     ${cheapest_full.usd:,.2f}  "
              f"({cheapest_full.model} @ {cheapest_full.effort}, "
              f"{cheapest_full.n_runs} runs)")
        print(f"  total to a finished result ${pilot_cost + cheapest_full.usd:,.2f}")

        if args.budget is not None:
            total = pilot_cost + cheapest_full.usd
            if total > args.budget:
                print(f"\n  WARNING: a ${args.budget:,.2f} budget does not cover "
                      f"both the pilot and the held-out run it informs.")
                print(f"  Consider a narrower sweep -- e.g. "
                      f"--tiers claude-haiku-4-5 -- which leaves enough to "
                      f"actually run the experiment.")
                if not args.yes:
                    print("\n  Re-run with --yes to proceed anyway.")
                    return 3

        if not keep:
            print("\n  Nothing affordable within the budget. Nothing was run.")
            return 3
        args.tiers = sorted({m for m, _, _ in keep})
        args.efforts = sorted({e for _, e, _ in keep})

    if args.offline or not api_key_available():
        if not args.offline:
            print("No API key found; running the offline stand-in instead.\n"
                  "The real pilot needs ANTHROPIC_API_KEY.\n", file=sys.stderr)
        from aistat.agents.rulebased import RuleBasedClient
        for label, policy in [("policy-expert", "expert"), ("policy-naive", "naive")]:
            name = f"dev_{policy}"
            evaluate(lambda p=policy: RuleBasedClient(p), split="dev",
                     reps=1, out_name=name, max_workers=args.workers)
            rows.append(((label, "n/a"), load_scores(name)))
    else:
        for model in args.tiers:
            for effort in args.efforts:
                print(f"\n--- {model} @ effort={effort} ---")
                name = _run_config(model, effort, args.reps, args.workers)
                rows.append(((model, effort), load_scores(name)))

    print(f"\n{'model':20s} {'effort':8s} {'A':>6s} {'B':>6s} {'C':>6s} "
          f"{'head(B)':>8s} {'C-B':>7s} {'$ heldout':>10s}  verdict")
    print("-" * 92)

    table = []
    for (model, effort), scores in rows:
        summ = system_summary(scores).set_index("system")["selection_accuracy"]
        a = float(summ.get("A_direct", float("nan")))
        b = float(summ.get("B_tools", float("nan")))
        c = float(summ.get("C_protocol", float("nan")))
        headroom = 1.0 - b
        uplift = c - b
        cost = _project_cost(scores, model) if effort != "n/a" else float("nan")
        ok = headroom >= HEADROOM_FLOOR
        verdict = "usable" if ok else "AT CEILING -- uplift not measurable"
        print(f"{model:20s} {effort:8s} {a:6.3f} {b:6.3f} {c:6.3f} "
              f"{headroom:8.3f} {uplift:7.3f} {cost:10,.2f}  {verdict}")
        table.append({"tier": model, "effort": effort, "acc_A": a, "acc_B": b,
                      "acc_C": c, "headroom_above_B": headroom,
                      "uplift_C_minus_B": uplift,
                      "projected_heldout_cost_usd": cost,
                      "n_dev_runs": len(scores),
                      "usable_for_headline": ok})

    usable = [t for t in table if t["usable_for_headline"]
              and t["acc_C"] == t["acc_C"]]
    chosen = None
    if usable:
        best = max(usable, key=lambda t: t["acc_C"])
        n = max(best["n_dev_runs"] // 3, 1)          # dev runs per system
        # Cheapest configuration whose System C accuracy is not distinguishable
        # from the best, using non-overlapping Wilson intervals as the test.
        # Cheap-but-equal beats expensive-and-equal; cheap-and-worse does not.
        blo, _ = wilson_ci(int(round(best["acc_C"] * n)), n)
        affordable = []
        for t in usable:
            _, thi = wilson_ci(int(round(t["acc_C"] * n)), n)
            if thi >= blo:                            # intervals overlap
                affordable.append(t)
        chosen = min(affordable or [best],
                     key=lambda t: t["projected_heldout_cost_usd"])
        saving = best["projected_heldout_cost_usd"] - chosen["projected_heldout_cost_usd"]
        rec = (f"Run the headline experiment on {chosen['tier']} at effort="
               f"{chosen['effort']}: projected "
               f"${chosen['projected_heldout_cost_usd']:,.2f}, headroom "
               f"{chosen['headroom_above_B']:.3f}, uplift "
               f"{chosen['uplift_C_minus_B']:+.3f}.")
        if saving > 1:
            rec += (f" That is ${saving:,.2f} cheaper than the most accurate "
                    f"configuration ({best['tier']} @ {best['effort']}), whose "
                    "development accuracy it is not statistically "
                    "distinguishable from.")
        if len(affordable) > 1:
            rec += (" Keep a second configuration as a confirmatory arm and "
                    "report uplift as a function of model strength.")
    else:
        rec = ("Every configuration is at ceiling on the development set. Do NOT "
               "report a single uplift number. Either add harder cases, or "
               "reframe the contribution around abstention recall and "
               "unsupported-inference rate, which do not saturate.")

    print(f"\n  {rec}\n")
    out = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
           "headroom_floor": HEADROOM_FLOOR, "configurations": table,
           "chosen_tier": chosen["tier"] if chosen else None,
           "chosen_effort": chosen["effort"] if chosen else None,
           "projected_cost_usd": chosen["projected_heldout_cost_usd"]
           if chosen else None,
           "recommendation": rec,
           "note": ("Decided on the development set before any held-out contact. "
                    "Must not be revisited after the held-out run begins.")}
    (REPORTS / "pilot_decision.json").write_text(json.dumps(out, indent=2))
    print(f"  recorded -> {REPORTS / 'pilot_decision.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
