"""Run the held-out evaluation (blueprint section 6 step 12).

    python scripts/run_evaluation.py --client rulebased --split heldout --reps 3

With ``--client anthropic`` this is the live 432-run experiment; with
``--client rulebased`` it is the deterministic offline calibration run.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
warnings.filterwarnings("ignore")

from aistat.agents.llm import DEFAULT_EFFORT, DEFAULT_MODEL, api_key_available
from aistat.evaluation.runner import evaluate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", default="rulebased",
                    choices=["rulebased", "rulebased-naive", "anthropic"])
    ap.add_argument("--split", default="heldout", choices=["dev", "heldout"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--systems", nargs="*", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--no-thinking", action="store_true")
    args = ap.parse_args()

    if args.client == "anthropic":
        if not api_key_available():
            print("ANTHROPIC_API_KEY is not set and no credential profile was "
                  "found.\nSet the key, or use --client rulebased for the "
                  "offline calibration run.", file=sys.stderr)
            return 2
        from aistat.agents.llm import AnthropicClient
        def factory():
            return AnthropicClient(model=args.model, effort=args.effort,
                                   thinking=not args.no_thinking)
        default_out = f"heldout_{args.model.replace('.', '-')}"
    else:
        from aistat.agents.rulebased import RuleBasedClient
        policy = "naive" if args.client.endswith("naive") else "expert"
        def factory():
            return RuleBasedClient(policy)
        default_out = f"{args.split}_rulebased_{policy}"

    out = args.out or default_out
    print(f"AI Statistician evaluation\n  client={args.client} split={args.split} "
          f"reps={args.reps} out={out}")
    res = evaluate(factory, split=args.split, reps=args.reps,
                   systems=args.systems, out_name=out, max_workers=args.workers)
    print(f"\n  executed {res['n_run']} runs in "
          f"{res.get('elapsed_seconds', 0):.1f}s, {res.get('n_errors', 0)} errors")
    print(f"  scores -> {res.get('scores_path')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
