"""Pre-flight cost estimation and a hard budget guard.

Written after the first pilot ran out of credit mid-sweep and produced 112
runs of unusable output: three of four configurations failed with
"credit balance is too low", and the pilot then recommended the only
configuration that had survived.  A recommendation derived from a billing
failure is worse than no recommendation, because it looks like a finding.

This module refuses to start work it cannot afford to finish.
"""
from __future__ import annotations

from dataclasses import dataclass

# USD per million tokens, (input, output).
PRICE: dict[str, tuple[float, float]] = {
    "claude-fable-5":    (10.0, 50.0),
    "claude-opus-5":     (5.0, 25.0),
    "claude-opus-4-8":   (5.0, 25.0),
    "claude-sonnet-5":   (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5":  (1.0, 5.0),
}
DEFAULT_PRICE = (5.0, 25.0)

# Mean tokens per run, measured from the first live pilot on Opus 5 at high
# effort (44 completed runs).  Used only for the pre-flight estimate; actuals
# are recorded per run and the projection is refreshed from them afterwards.
MEASURED: dict[str, tuple[int, int, int]] = {
    # system      input   output  cache_read
    "A_direct":   (2411,  1837,   0),
    "B_tools":    (6468,  2152,   6820),
    "C_protocol": (7041,  8048,   0),
}

# Lower effort reduces thinking, which is where the output tokens go.  Scaling
# factors from the same pilot: medium cut A by 29% and B by 24%.  C was never
# measured at medium, so it is assumed to behave like the others -- flagged in
# the estimate as an assumption rather than a measurement.
EFFORT_OUTPUT_SCALE = {"low": 0.45, "medium": 0.72, "high": 1.0,
                       "xhigh": 1.4, "max": 2.0}


@dataclass
class Estimate:
    model: str
    effort: str
    n_cases: int
    reps: int
    systems: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    cache_tokens: int
    usd: float
    assumed_c_scaling: bool

    @property
    def n_runs(self) -> int:
        return self.n_cases * self.reps * len(self.systems)

    def describe(self) -> str:
        note = "  (C at non-high effort is assumed, not measured)" \
            if self.assumed_c_scaling else ""
        return (f"{self.model} @ {self.effort}: {self.n_runs} runs, "
                f"~{self.input_tokens:,} in / {self.output_tokens:,} out "
                f"-> ${self.usd:,.2f}{note}")


def estimate(model: str, effort: str = "high", *, n_cases: int,
             reps: int = 1,
             systems: tuple[str, ...] = ("A_direct", "B_tools", "C_protocol")
             ) -> Estimate:
    pin, pout = PRICE.get(model, DEFAULT_PRICE)
    scale = EFFORT_OUTPUT_SCALE.get(effort, 1.0)
    n = n_cases * reps

    tin = tout = tcache = 0
    for sysname in systems:
        i, o, c = MEASURED.get(sysname, (5000, 3000, 0))
        tin += i * n
        tout += int(o * scale) * n
        tcache += c * n

    billed_in = max(tin - tcache, 0)
    usd = (billed_in / 1e6 * pin
           + tcache / 1e6 * pin * 0.1
           + tout / 1e6 * pout)
    return Estimate(model, effort, n_cases, reps, systems, tin, tout, tcache,
                    usd, assumed_c_scaling=(effort != "high"))


class BudgetExceeded(RuntimeError):
    """Raised before any API call when a plan cannot be afforded."""


@dataclass
class Budget:
    """A spend ceiling enforced across a sequence of configurations."""

    limit_usd: float
    spent_usd: float = 0.0
    reserve_fraction: float = 0.15
    """Held back so a mid-run overshoot cannot exhaust the balance -- the
    failure mode that ruined the first pilot."""

    @property
    def usable(self) -> float:
        return self.limit_usd * (1 - self.reserve_fraction)

    @property
    def remaining(self) -> float:
        return self.usable - self.spent_usd

    def can_afford(self, est: Estimate) -> bool:
        return est.usd <= self.remaining

    def check(self, est: Estimate) -> None:
        if not self.can_afford(est):
            raise BudgetExceeded(
                f"{est.describe()}\n"
                f"  needs ${est.usd:,.2f} but only ${self.remaining:,.2f} of the "
                f"${self.limit_usd:,.2f} budget remains "
                f"(${self.limit_usd * self.reserve_fraction:,.2f} held in reserve).\n"
                f"  Refusing to start work that cannot be finished -- a "
                f"half-completed configuration produces unusable results.")

    def commit(self, est: Estimate) -> None:
        self.spent_usd += est.usd

    def record_actual(self, usd: float) -> None:
        """Replace an estimate with what was really spent, once known."""
        self.spent_usd = usd


def plan(configs: list[tuple[str, str]], *, n_cases: int, reps: int,
         budget_usd: float | None) -> tuple[list[tuple[str, str, Estimate]], list[str]]:
    """Return the affordable configurations and the reasons any were dropped."""
    ests = [(m, e, estimate(m, e, n_cases=n_cases, reps=reps))
            for m, e in configs]
    if budget_usd is None:
        return ests, []

    budget = Budget(budget_usd)
    keep, dropped = [], []
    # Cheapest first, so a tight budget buys the most configurations rather
    # than spending everything on the first expensive one.
    for m, e, est in sorted(ests, key=lambda t: t[2].usd):
        if budget.can_afford(est):
            budget.commit(est)
            keep.append((m, e, est))
        else:
            dropped.append(f"{m} @ {e} (${est.usd:,.2f}, "
                           f"${budget.remaining:,.2f} left)")
    return keep, dropped
