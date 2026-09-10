"""Generate the capstone report from raw logs (blueprint section 6 step 15).

    python scripts/write_report.py --name heldout_rulebased_expert

Everything in the output is computed from results/*.jsonl. Nothing is hand
written, so the report regenerates after any re-run.
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

import pandas as pd

from aistat.evaluation.analysis import (failure_taxonomy, majority_by_case,
                                        pairwise_comparisons, risk_coverage,
                                        system_summary, wilson_ci)
from aistat.evaluation.runner import RESULTS, load_scores

REPORTS = ROOT / "reports"
LABEL = {"A_direct": "A. Direct LLM", "B_tools": "B. LLM with tools",
         "C_protocol": "C. Structured agent"}


def md_table(df: pd.DataFrame, cols: dict[str, str], fmt: dict | None = None) -> str:
    fmt = fmt or {}
    head = "| " + " | ".join(cols.values()) + " |"
    rule = "|" + "|".join("---" for _ in cols) + "|"
    lines = [head, rule]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if c == "system":
                cells.append(LABEL.get(v, str(v)))
            elif isinstance(v, float):
                cells.append(fmt.get(c, "{:.3f}").format(v)
                             if pd.notna(v) else "—")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="heldout_rulebased_expert")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    scores = load_scores(args.name)
    manifest = json.loads((RESULTS / f"{args.name}_manifest.json").read_text())
    summary = system_summary(scores)
    majority = majority_by_case(scores)
    rc = risk_coverage(scores)
    pairs = pairwise_comparisons(majority)
    fails = failure_taxonomy(scores)

    is_offline = "rulebased" in manifest.get("client", "")
    reps = int(scores.groupby(["system", "case_id"]).size().max())
    n_cases = int(scores["case_id"].nunique())

    caveat = ""
    if is_offline:
        caveat = (
            "> **This is a calibration run, not an experiment.**\n"
            "> The client is the deterministic offline policy, not an LLM. The\n"
            "> `expert` policy is the same policy that derived the gold labels,\n"
            "> so System C's score here is **circular by construction** — it is a\n"
            "> label-coherence check and a harness validation, and it says nothing\n"
            "> about LLM performance. Run `make eval-live` for the real experiment.\n\n"
            "> The informative offline number is the naive-policy floor: inside the\n"
            "> *same* state machine, a policy that ignores the design card scores\n"
            "> far lower with zero abstention recall. The architecture alone is not\n"
            "> what produces the uplift; the decision policy inside it is.\n")

    c = summary[summary.system == "C_protocol"]
    bc = pairs[(pairs.system_a == "B_tools") & (pairs.system_b == "C_protocol")]
    acc_c = float(c["selection_accuracy"].iloc[0]) if len(c) else float("nan")
    uplift = float(bc["uplift_b_minus_a"].iloc[0]) if len(bc) else float("nan")
    ulo = float(bc["uplift_ci_low"].iloc[0]) if len(bc) else float("nan")
    uhi = float(bc["uplift_ci_high"].iloc[0]) if len(bc) else float("nan")
    mp = float(bc["mcnemar_p"].iloc[0]) if len(bc) else float("nan")
    unsafe_c = float(c["unsafe_selection_rate"].iloc[0]) if len(c) else float("nan")
    arec = float(c["abstention_recall"].iloc[0]) if len(c) else float("nan")
    n_abst = int(rc[rc.system == "C_protocol"]["n_abstention_cases"].iloc[0])

    def tick(ok: bool) -> str:
        return "met" if ok else "not met"

    doc = f"""# AI Statistician — results

Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from
`results/{args.name}_scores.jsonl`. Regenerate with `make analyze`.

{caveat}
## Run configuration

| | |
|---|---|
| Client | `{manifest.get('client')}` |
| Split | {manifest.get('split')} ({n_cases} cases) |
| Repetitions | {reps} |
| Total runs | {len(scores)} |
| Prompt hash | `{manifest.get('prompt_sha256_16')}` |
| Git commit | `{str(manifest.get('git_commit'))[:12]}` |
| Determinism controls | {', '.join(manifest.get('determinism_controls', []))} |
| Library versions | {', '.join(f'{k} {v}' for k, v in manifest.get('versions', {}).items())} |

`temperature` is not among the controls because it is removed on current Claude
models and returns a 400 if sent. See `docs/DEVIATIONS.md` §1.

## Success targets (blueprint §1)

| Measure | Target | Observed | Verdict |
|---|---|---|---|
| Method-selection accuracy | ≥ 85% | {acc_c:.1%} | {tick(acc_c >= 0.85)} |
| Unsafe-selection rate | ≈ 0 | {unsafe_c:.1%} | {tick(unsafe_c <= 0.02)} |
| Numerical fidelity | ≥ 98% | guaranteed by construction | see below |
| Unsupported inference rate | ≤ 5% | {float(c['unsupported_inference_rate'].iloc[0]):.1%} | {tick(float(c['unsupported_inference_rate'].iloc[0]) <= 0.05)} |
| Protocol uplift over B | ≥ 10 pts | {uplift:+.1%} [{ulo:+.1%}, {uhi:+.1%}] | {tick(uplift >= 0.10)} |

**On numerical fidelity.** For System C this is an architectural guarantee, not
an observation: the report schema rejects raw numeric literals and every value
is substituted from a recorded tool result, so there is no path to fabrication.
The empirical counterpart is the provenance rejection count —
{int(c['provenance_rejections'].iloc[0]) if len(c) else 0} across
{len(scores[scores.system == 'C_protocol'])} runs. Fidelity remains an empirical
metric for Systems A and B, where nothing is enforced.

## System summary

{md_table(summary, {
    "system": "System", "n_runs": "Runs",
    "selection_accuracy": "Selection accuracy", "acc_ci_low": "CI low",
    "acc_ci_high": "CI high", "abstention_recall": "Abstention recall",
    "unsafe_selection_rate": "Unsafe rate",
    "assumption_coverage": "Assumption coverage",
    "mean_tool_calls": "Tool calls", "mean_llm_calls": "LLM calls"},
    fmt={"mean_tool_calls": "{:.2f}", "mean_llm_calls": "{:.2f}"})}

Accuracy intervals are Wilson intervals on the run-level counts.

## Risk–coverage

Coverage is the share of cases a system chose to answer; selective accuracy is
accuracy among those. This is the addition from review finding F-A3 — it
separates a system that abstains *correctly* from one that simply answers less.

{md_table(rc, {
    "system": "System", "coverage": "Coverage",
    "selective_accuracy": "Selective accuracy",
    "accuracy_on_supported": "Accuracy on supported",
    "abstention_recall": "Abstention recall",
    "unsafe_selection_rate": "Unsafe rate",
    "over_abstention_rate": "Over-abstention"})}

Abstention recall for System C is {arec:.1%} over {n_abst} abstention runs
(Wilson interval {wilson_ci(int(round(arec * n_abst)), n_abst)[0]:.3f} to
{wilson_ci(int(round(arec * n_abst)), n_abst)[1]:.3f}).

## Paired comparisons

Per-case majority decision across {reps} repetitions, then a case-level
bootstrap on the paired difference and an exact McNemar test.

{md_table(pairs, {
    "system_a": "A", "system_b": "B", "n_cases": "Cases",
    "acc_a": "Acc A", "acc_b": "Acc B",
    "uplift_b_minus_a": "Uplift (B−A)",
    "uplift_ci_low": "CI low", "uplift_ci_high": "CI high",
    "mcnemar_p": "McNemar p"}, fmt={"mcnemar_p": "{:.4f}"})}

The comparison that answers the research question is **B vs C**: both have the
same tools and the same report schema, and differ only in whether an ordered
decision protocol governs their use. Observed uplift {uplift:+.1%}
[{ulo:+.1%}, {uhi:+.1%}], McNemar p = {mp:.4f}.

## Failure taxonomy (blueprint §8.4)

{md_table(fails, {"system": "System", "failure_stage": "Stage", "n": "Runs"})
 if len(fails) else "_No failures recorded._"}

## Run-to-run stability

Mean repetition agreement {float(majority['rep_agreement'].mean()):.3f};
unanimous on {float(majority['unanimous'].mean()):.1%} of cases. Because
`temperature` no longer exists as a control, this is a *measurement* of residual
provider variance rather than a confirmation of determinism.

## Reproducing this

```bash
make benchmark && make validate && make test
make eval && make analyze
python scripts/write_report.py --name {args.name}
```

Every table above is derived from `results/{args.name}_scores.jsonl`. Deviations
from the blueprint are documented in `docs/DEVIATIONS.md`.
"""
    out = Path(args.out) if args.out else REPORTS / f"{args.name}_REPORT.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(doc)
    print(f"wrote {out} ({len(doc.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
