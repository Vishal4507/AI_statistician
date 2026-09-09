"""The tool surface (blueprint section 5.2).

Nine typed tools with strict JSON schemas.  Deliberately no ``run_python``:
unrestricted execution would let the model bypass the method policy and would
make traces incomparable across the three systems.

Every dispatch registers its return in the ResultStore before the model sees
it, which is what makes ``{{ref}}`` substitution possible downstream.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from aistat.provenance.store import ResultStore
from aistat.tools import diagnostics, execution
from aistat.schemas.core import METHODS

GROUP_METHODS = ("student_t", "welch_t", "mann_whitney",
                 "one_way_anova", "welch_anova", "kruskal_wallis")
CATCORR_METHODS = ("chi_square", "fisher_exact", "pearson", "spearman")
REGRESSION_METHODS = ("ols", "logistic", "poisson", "negative_binomial")


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


_STR = {"type": "string"}


TOOL_SPECS: list[dict] = [
    {
        "name": "inspect_dataset",
        "description": ("Schema, variable-type suggestions, row count, unique "
                        "values, missingness, duplicates, repeated-ID candidates, "
                        "time-column candidates, and range checks. Call this first."),
        "input_schema": _schema({}, []),
    },
    {
        "name": "summarize_groups",
        "description": ("Per-group n, mean, SD, median, IQR, skew, robust spread, "
                        "outlier counts and Q-Q correlation."),
        "input_schema": _schema(
            {"outcome": _STR, "group": _STR}, ["outcome", "group"]),
    },
    {
        "name": "check_group_assumptions",
        "description": ("Variance ratio, Levene and Brown-Forsythe evidence, "
                        "group imbalance. Evidence for a judgement, not a switch."),
        "input_schema": _schema(
            {"outcome": _STR, "group": _STR}, ["outcome", "group"]),
    },
    {
        "name": "check_contingency",
        "description": ("Observed and expected cell counts, sparse-cell counts, "
                        "table dimension, chi-square and Fisher eligibility."),
        "input_schema": _schema(
            {"var1": _STR, "var2": _STR}, ["var1", "var2"]),
    },
    {
        "name": "check_association",
        "description": ("Linearity versus monotonicity evidence, leverage, "
                        "leave-one-out stability of r, range restriction."),
        "input_schema": _schema({"x": _STR, "y": _STR}, ["x", "y"]),
    },
    {
        "name": "run_group_test",
        "description": ("Execute one of the six group-comparison methods with "
                        "effect size and confidence interval."),
        "input_schema": _schema(
            {"method": {"type": "string", "enum": list(GROUP_METHODS)},
             "outcome": _STR, "group": _STR},
            ["method", "outcome", "group"]),
    },
    {
        "name": "run_categorical_or_correlation",
        "description": "Execute chi-square, Fisher exact, Pearson, or Spearman.",
        "input_schema": _schema(
            {"method": {"type": "string", "enum": list(CATCORR_METHODS)},
             "var1": _STR, "var2": _STR},
            ["method", "var1", "var2"]),
    },
    {
        "name": "fit_regression",
        "description": ("Fit OLS, logistic, Poisson, or negative binomial and "
                        "return a coefficient table with model diagnostics."),
        "input_schema": _schema(
            {"method": {"type": "string", "enum": list(REGRESSION_METHODS)},
             "outcome": _STR,
             "predictors": {"type": "array", "items": _STR},
             "exposure": {"type": ["string", "null"]}},
            ["method", "outcome", "predictors"]),
    },
]

DIAGNOSTIC_TOOLS = {"inspect_dataset", "summarize_groups",
                    "check_group_assumptions", "check_contingency",
                    "check_association"}
EXECUTION_TOOLS = {"run_group_test", "run_categorical_or_correlation",
                   "fit_regression"}


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict
    payload: dict
    is_error: bool = False


class ToolRegistry:
    """Dispatches tool calls against one case's data, recording provenance."""

    def __init__(self, df: pd.DataFrame, store: ResultStore) -> None:
        self.df = df
        self.store = store
        self.calls: list[ToolCall] = []
        self._impl: dict[str, Callable[..., dict]] = {
            "inspect_dataset": lambda: diagnostics.inspect_dataset(self.df),
            "summarize_groups": lambda outcome, group:
                diagnostics.summarize_groups(self.df, outcome, group),
            "check_group_assumptions": lambda outcome, group:
                diagnostics.check_group_assumptions(self.df, outcome, group),
            "check_contingency": lambda var1, var2:
                diagnostics.check_contingency(self.df, var1, var2),
            "check_association": lambda x, y:
                diagnostics.check_association(self.df, x, y),
            "run_group_test": lambda method, outcome, group:
                execution.run_group_test(self.df, method, outcome, group),
            "run_categorical_or_correlation": lambda method, var1, var2:
                execution.run_categorical_or_correlation(self.df, method, var1, var2),
            "fit_regression": lambda method, outcome, predictors, exposure=None:
                execution.fit_regression(self.df, method, outcome, predictors, exposure),
        }

    # -- introspection -----------------------------------------------------

    @staticmethod
    def specs(strict: bool = True) -> list[dict]:
        """Anthropic tool definitions.  ``strict`` guarantees input validation."""
        out = []
        for s in TOOL_SPECS:
            spec = {"name": s["name"], "description": s["description"],
                    "input_schema": s["input_schema"]}
            if strict:
                spec["strict"] = True
            out.append(spec)
        return out

    @property
    def executed_methods(self) -> list[str]:
        return [c.arguments.get("method") for c in self.calls
                if c.name in EXECUTION_TOOLS and not c.is_error
                and c.arguments.get("method")]

    @property
    def n_diagnostic_calls(self) -> int:
        return sum(c.name in DIAGNOSTIC_TOOLS for c in self.calls)

    @property
    def n_execution_calls(self) -> int:
        return sum(c.name in EXECUTION_TOOLS for c in self.calls)

    # -- dispatch ----------------------------------------------------------

    def call(self, name: str, arguments: dict | None = None) -> ToolCall:
        arguments = dict(arguments or {})
        if name not in self._impl:
            tc = ToolCall("", name, arguments,
                          {"error": f"unknown tool {name!r}"}, True)
            self.calls.append(tc)
            return tc

        label = arguments.get("method", name) if name in EXECUTION_TOOLS else name
        call_id = self.store.next_call_id(label)
        try:
            payload = self._impl[name](**arguments)
            is_error = isinstance(payload, dict) and "error" in payload
        except TypeError as exc:
            payload, is_error = {"error": f"bad arguments: {exc}"}, True
        except Exception as exc:                     # tool failure is data
            payload, is_error = {"error": f"{type(exc).__name__}: {exc}"}, True

        if not is_error:
            self.store.register(call_id, payload)
        tc = ToolCall(call_id, name, arguments, payload, is_error)
        self.calls.append(tc)
        return tc
