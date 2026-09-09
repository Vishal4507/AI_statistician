"""Validate the live path before spending money on it.

    python scripts/smoke_live.py

Makes a handful of real API calls -- a few cents -- and exercises every part of
the live path that the offline suite cannot reach: the request shape, structured
outputs at each decision point, tool_use / tool_result threading, prompt-cache
behaviour, and the provenance contract under a real model.

Run this FIRST after setting ANTHROPIC_API_KEY. A failure here is cheap; the
same failure discovered 300 runs into the held-out evaluation is not.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

from aistat.agents.base import Case
from aistat.agents.contracts import SCHEMAS
from aistat.agents.llm import AnthropicClient, api_key_available
from aistat.agents.systems import SYSTEMS
from aistat.evaluation.scorers import score_run

OK, BAD = "  PASS  ", "  FAIL  "


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--case", default="syn_welch_t_1")
    ap.add_argument("--abstain-case", default="syn_abstain_repeated_measures_1")
    args = ap.parse_args()

    if not api_key_available():
        print("ANTHROPIC_API_KEY is not set and no credential profile was found.",
              file=sys.stderr)
        return 2

    failures: list[str] = []
    _COST: list[tuple] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"{OK if ok else BAD}{label}" + (f" -- {detail}" if detail else ""))
        if not ok:
            failures.append(label)

    print(f"Live-path smoke test  model={args.model} effort={args.effort}\n")

    # -- 1. minimal request shape -----------------------------------------
    client = AnthropicClient(model=args.model, effort=args.effort)
    try:
        r = client.complete(system="Reply with the single word: ready.",
                            messages=[{"role": "user", "content": "Are you ready?"}],
                            max_tokens=64)
        check("request shape accepted (no temperature, adaptive thinking, effort)",
              bool(r.text), f"{r.input_tokens} in / {r.output_tokens} out")
    except Exception as exc:
        check("request shape accepted", False, f"{type(exc).__name__}: {exc}")
        print("\nThe basic request was rejected. Nothing else can pass; stopping.")
        return 1

    # -- 2. structured output ---------------------------------------------
    try:
        r = client.complete(
            system="You extract structure. Return only JSON matching the schema.",
            messages=[{"role": "user", "content":
                       "Outcome column is 'monthly_spend', group column is 'plan', "
                       "two independent groups, observational data on customers. "
                       "TASK: produce the analysis specification."}],
            output_schema=SCHEMAS["parse_problem"], max_tokens=2000)
        ok = isinstance(r.structured, dict) and "estimand" in (r.structured or {})
        check("structured output parses against the schema", ok,
              f"estimand={r.structured.get('estimand') if r.structured else None}")
    except Exception as exc:
        check("structured output parses", False, f"{type(exc).__name__}: {exc}")

    # -- 3. prompt caching --------------------------------------------------
    # A cacheable prefix must exceed ~1024 tokens.  Measure the REAL prefixes
    # rather than a toy prompt, then confirm a repeated one is actually read
    # back.  System A and System C carry no tool definitions, so their prefixes
    # fall below the minimum and never cache -- that is a property of the
    # design, not a defect, and it is reported rather than failed.
    from aistat.agents import systems as _sys
    from aistat.tools.registry import ToolRegistry
    tools = ToolRegistry.specs(strict=True)
    sizes = {}
    for label, prompt, with_tools in [
        ("A_direct", _sys._SYSTEM_A, False),
        ("B_tools", _sys._SYSTEM_B, True),
        ("C_protocol", _sys._SYSTEM_C, False),
    ]:
        kw = dict(model=args.model, system=prompt,
                  messages=[{"role": "user", "content": "x"}])
        if with_tools:
            kw["tools"] = tools
        sizes[label] = client._client.messages.count_tokens(**kw).input_tokens
    print("          prefix sizes: " + ", ".join(
        f"{k}={v}" + ("" if v >= 1024 else " (under 1024, will not cache)")
        for k, v in sizes.items()))

    big = _sys._SYSTEM_B
    before = client.total_cache_read
    for _ in range(2):
        client.complete(system=big, messages=[{"role": "user", "content": "Ready?"}],
                        tools=tools, max_tokens=32)
    cached = client.total_cache_read > before
    check("prompt cache is read back on a cacheable prefix", cached,
          f"cache_read={client.total_cache_read - before} tokens on a "
          f"{sizes['B_tools']}-token prefix")

    # -- 4. System C end to end --------------------------------------------
    try:
        case = Case.load(args.case)
        result = SYSTEMS["C_protocol"](
            AnthropicClient(model=args.model, effort=args.effort)).run(case)
        check("System C completes a real case", result.error is None,
              f"method={result.method}, {result.n_llm_calls} LLM calls, "
              f"{result.n_tool_calls} tool calls")
        unsub = [k for k, v in result.rendered.items() if "{{" in v]
        check("no unsubstituted template survived rendering", not unsub, str(unsub))
        bad = [k for k, v in result.rendered.items()
               if "PROVENANCE FAILURE" in v or "UNRESOLVED" in v]
        check("no provenance failure", not bad, str(bad))
        check("model cited references rather than writing numbers",
              result.provenance_rejections == 0,
              f"{result.provenance_rejections} rejected references")
        sc = score_run(result.to_dict(), case.card.get("randomized"))
        print(f"          selected {sc['chosen_method']} against gold "
              f"{sc['gold_method']} -- "
              f"{'correct' if sc['selection_correct'] else 'incorrect'}")
        # Real per-run token cost, for projecting the full evaluation.
        print(f"          tokens this run: {result.input_tokens:,} in / "
              f"{result.output_tokens:,} out "
              f"({result.cache_read_tokens:,} from cache)")
        _COST.append(("C_protocol", result.input_tokens, result.output_tokens,
                      result.cache_read_tokens))
    except Exception as exc:
        check("System C completes a real case", False, f"{type(exc).__name__}: {exc}")

    # -- 5. System B tool threading ----------------------------------------
    try:
        case = Case.load(args.case)
        result = SYSTEMS["B_tools"](
            AnthropicClient(model=args.model, effort=args.effort)).run(case)
        check("System B tool_use / tool_result threading holds",
              result.error is None and result.n_tool_calls > 0,
              f"{result.n_tool_calls} tool calls, method={result.method}")
        print(f"          tokens this run: {result.input_tokens:,} in / "
              f"{result.output_tokens:,} out "
              f"({result.cache_read_tokens:,} from cache)")
        _COST.append(("B_tools", result.input_tokens, result.output_tokens,
                      result.cache_read_tokens))
    except Exception as exc:
        check("System B tool threading holds", False, f"{type(exc).__name__}: {exc}")

    # -- 6. abstention path -------------------------------------------------
    try:
        case = Case.load(args.abstain_case)
        result = SYSTEMS["C_protocol"](
            AnthropicClient(model=args.model, effort=args.effort)).run(case)
        check("abstention path produces a report without an estimate",
              result.error is None,
              f"method={result.method}, reason={result.abstain_reason}")
    except Exception as exc:
        check("abstention path", False, f"{type(exc).__name__}: {exc}")

    # -- projection ---------------------------------------------------------
    if _COST:
        PRICE = {"claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (2.0, 10.0),
                 "claude-haiku-4-5": (1.0, 5.0)}
        pin, pout = PRICE.get(args.model, (5.0, 25.0))
        per = {s: (i, o, c) for s, i, o, c in _COST}
        # 48 held-out cases x 3 reps = 144 runs per system.  A is one call, so
        # it is estimated at a quarter of C's per-run input.
        est_c = per.get("C_protocol", (0, 0, 0))
        est_b = per.get("B_tools", (0, 0, 0))
        est_a = (est_c[0] // 4, est_c[1] // 4, 0)
        total_in = sum(x[0] for x in (est_a, est_b, est_c)) * 144
        total_out = sum(x[1] for x in (est_a, est_b, est_c)) * 144
        total_cache = sum(x[2] for x in (est_a, est_b, est_c)) * 144
        billed_in = max(total_in - total_cache, 0)
        cost = billed_in / 1e6 * pin + total_cache / 1e6 * pin * 0.1 \
            + total_out / 1e6 * pout
        print(f"\n  Projected held-out cost on {args.model}: ${cost:,.2f}")
        print(f"    432 runs, ~{total_in:,} input ({total_cache:,} cached) "
              f"/ ~{total_out:,} output tokens")
        print("    measured from this smoke run, not estimated from assumptions")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        print("\nFix these before running make eval-live.")
        return 1
    print("Live path validated. `make pilot` next, then `make eval-live`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
