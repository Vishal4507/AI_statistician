"""Deterministic offline client implementing the LLMClient protocol.

Two policies:
    ``expert``  follows the full decision protocol (design validity first,
                diagnostics as evidence, conditional dispersion, and so on).
    ``naive``   ignores the design card and uses assumption-test p-values as
                switches -- the failure mode blueprint section 11 names.

Together these give the study a policy ceiling and a floor without an API key.
Neither is an arm of the experiment; they calibrate the harness and the scorers.
"""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

from aistat.agents.llm import LLMResponse, ToolUse
from aistat.agents.policy import design_verdict, infer_task, route
from aistat.schemas.core import ABSTAIN


class RuleBasedClient:
    def __init__(self, policy: str = "expert", respect_design: bool | None = None,
                 skip_diagnostics: bool = False) -> None:
        self.policy = policy
        self.naive = policy == "naive"
        self.respect_design = (not self.naive) if respect_design is None else respect_design
        self.skip_diagnostics = skip_diagnostics or self.naive
        self.name = f"rulebased:{policy}"
        self.total_input = self.total_output = self.total_cache_read = 0
        self.n_calls = 0

    # ----------------------------------------------------------------------

    def complete(self, *, system: str, messages: list[dict],
                 tools: list[dict] | None = None,
                 output_schema: dict | None = None,
                 purpose: str = "", context: Any = None,
                 max_tokens: int = 8000) -> LLMResponse:
        self.n_calls += 1
        ctx = context or {}
        handler = {
            "parse_problem": self._parse_problem,
            "plan_candidates": self._plan,
            "select_method": self._select,
            "write_report": self._report,
            "free_tool_use": self._free_tools,
            "direct_advice": self._direct,
        }.get(purpose)
        if handler is None:
            return LLMResponse(text="{}", structured={})
        out = handler(ctx)
        self.total_input += 1200
        self.total_output += 400
        return out

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _shape(ctx) -> Any:
        return infer_task(ctx["df"], ctx["roles"])

    def _verdict(self, ctx) -> tuple[str | None, str]:
        if not self.respect_design:
            return None, ""
        return design_verdict(ctx["card"], ctx["df"], self._shape(ctx),
                              ctx.get("inspect"))

    # -- phase handlers ----------------------------------------------------

    def _parse_problem(self, ctx) -> LLMResponse:
        t = self._shape(ctx)
        df, card = ctx["df"], ctx["card"]
        scales = {}
        for c, r in ctx["roles"].items():
            if c not in df.columns:
                continue
            s = df[c].dropna()
            if not pd.api.types.is_numeric_dtype(s):
                scales[c] = "binary" if s.nunique() == 2 else "nominal"
            elif s.nunique() == 2:
                scales[c] = "binary"
            elif pd.api.types.is_integer_dtype(s) and (s >= 0).all() and s.nunique() > 8:
                scales[c] = "count"
            elif pd.api.types.is_integer_dtype(s) and s.nunique() <= 8:
                scales[c] = "ordinal"
            else:
                scales[c] = "continuous"

        hazards, missing = [], []
        if self.respect_design:
            if card.get("repeated_id_column"):
                hazards.append("repeated_measures")
            if card.get("time_column"):
                hazards.append("serial_dependence")
            if card.get("pairing"):
                hazards.append("pairing")
            if card.get("clustering_column"):
                hazards.append("clustering")
            if card.get("observational_unit") in (None, "", "unknown"):
                hazards.append("missing_design_facts")
                missing.append("observational unit is not stated")
            if card.get("randomized") is None:
                missing.append("randomised versus observational is not stated")

        estimand = {"two_group": "mean_difference", "multi_group": "mean_difference",
                    "categorical": "association", "association": "association",
                    "regression_continuous": "conditional_mean",
                    "regression_binary": "odds",
                    "regression_count": "rate"}.get(t.kind, "association")
        q = ctx.get("question", "").lower()
        if any(w in q for w in ("skew", "shift", "systematically higher")):
            if t.kind in ("two_group", "multi_group"):
                estimand = "distributional_shift"

        spec = {
            "objective": ctx.get("objective", "analyse the stated question"),
            "outcome": t.outcome or t.var1 or "",
            "predictors": list(t.predictors) or ([t.var2] if t.var2 else []),
            "group_column": t.group,
            "variable_scales": scales,
            "estimand": estimand,
            "population": card.get("intended_population", "unspecified"),
            "observational_unit": card.get("observational_unit") or "unknown",
            "design_hazards": hazards,
            "missing_facts": missing,
        }
        return LLMResponse(text=json.dumps(spec), structured=spec)

    def _plan(self, ctx) -> LLMResponse:
        t = self._shape(ctx)
        reason, _ = self._verdict(ctx)
        if reason:
            plan = {"eligible_methods": [ABSTAIN], "required_diagnostics": [],
                    "rejection_reasons": {}, "ordered_tool_requests": []}
            return LLMResponse(text=json.dumps(plan), structured=plan)

        eligible, diags, reqs = {
            "two_group": (["student_t", "welch_t", "mann_whitney"],
                          ["variance_structure", "skew_and_outliers", "group_sizes"],
                          ["summarize_groups", "check_group_assumptions"]),
            "multi_group": (["one_way_anova", "welch_anova", "kruskal_wallis"],
                            ["variance_balance", "skew_and_outliers", "n_groups"],
                            ["summarize_groups", "check_group_assumptions"]),
            "categorical": (["chi_square", "fisher_exact"],
                            ["expected_cell_counts", "table_dimension"],
                            ["check_contingency"]),
            "association": (["pearson", "spearman"],
                            ["linearity_or_monotonicity", "influential_points", "scale"],
                            ["check_association"]),
            "regression_continuous": (["ols"], ["functional_form", "residual_pattern"], []),
            "regression_binary": (["logistic"],
                                  ["binary_coding", "events_per_parameter", "separation"], []),
            "regression_count": (["poisson", "negative_binomial"],
                                 ["conditional_dispersion", "excess_zeros", "exposure"], []),
        }.get(t.kind, ([ABSTAIN], [], []))
        if self.skip_diagnostics:
            reqs = []
        plan = {"eligible_methods": eligible, "required_diagnostics": diags,
                "rejection_reasons": {}, "ordered_tool_requests": reqs}
        return LLMResponse(text=json.dumps(plan), structured=plan)

    def _select(self, ctx) -> LLMResponse:
        t = self._shape(ctx)
        reason, expl = self._verdict(ctx)
        if reason:
            sel = {"method": ABSTAIN, "abstain_reason": reason,
                   "evidence_refs": ctx.get("evidence_refs", [])[:6],
                   "rejected_alternatives": {}, "confidence": "high",
                   "_rationale": expl}
            return LLMResponse(text=json.dumps(sel), structured=sel)

        method, rationale, rejected = route(
            t, ctx.get("evidence", {}), ctx.get("question", ""), naive=self.naive,
            slot_ids=ctx.get("slot_ids"))
        sel = {"method": method, "abstain_reason": None,
               "evidence_refs": ctx.get("evidence_refs", [])[:6],
               "rejected_alternatives": rejected,
               "confidence": "high" if not self.naive else "moderate",
               "_rationale": rationale}
        return LLMResponse(text=json.dumps(sel), structured=sel)

    def _free_tools(self, ctx) -> LLMResponse:
        """System B behaviour: request whatever looks relevant, then execute."""
        step = ctx.get("step", 0)
        t = self._shape(ctx)
        done = ctx.get("called", [])

        if step == 0:
            return LLMResponse(tool_uses=[ToolUse("tu0", "inspect_dataset", {})],
                               stop_reason="tool_use")
        if step == 1 and t.kind in ("two_group", "multi_group"):
            return LLMResponse(tool_uses=[
                ToolUse("tu1", "summarize_groups",
                        {"outcome": t.outcome, "group": t.group})],
                stop_reason="tool_use")
        if step == 1 and t.kind == "categorical":
            return LLMResponse(tool_uses=[
                ToolUse("tu1", "check_contingency", {"var1": t.var1, "var2": t.var2})],
                stop_reason="tool_use")
        if step == 1 and t.kind == "association":
            return LLMResponse(tool_uses=[
                ToolUse("tu1", "check_association", {"x": t.var1, "y": t.var2})],
                stop_reason="tool_use")

        if not any(c in ("run_group_test", "run_categorical_or_correlation",
                         "fit_regression") for c in done):
            method, _, _ = route(t, ctx.get("evidence", {}), ctx.get("question", ""),
                                 naive=True, slot_ids=ctx.get("slot_ids"))
            if t.kind in ("two_group", "multi_group"):
                tu = ToolUse("tu2", "run_group_test",
                             {"method": method, "outcome": t.outcome, "group": t.group})
            elif t.kind in ("categorical", "association"):
                tu = ToolUse("tu2", "run_categorical_or_correlation",
                             {"method": method, "var1": t.var1, "var2": t.var2})
            else:
                args = {"method": method, "outcome": t.outcome,
                        "predictors": list(t.predictors)}
                if t.exposure:
                    args["exposure"] = t.exposure
                tu = ToolUse("tu2", "fit_regression", args)
            return LLMResponse(tool_uses=[tu], stop_reason="tool_use")

        return LLMResponse(text="analysis complete", stop_reason="end_turn")

    def _direct(self, ctx) -> LLMResponse:
        """System A behaviour: advise from summaries alone, no execution."""
        t = self._shape(ctx)
        method, rationale, rejected = route(
            t, ctx.get("evidence", {}), ctx.get("question", ""), naive=True,
            slot_ids=ctx.get("slot_ids"))
        sel = {"method": method, "abstain_reason": None, "evidence_refs": [],
               "rejected_alternatives": rejected, "confidence": "moderate",
               "_rationale": rationale}
        return LLMResponse(text=json.dumps(sel), structured=sel)

    def _report(self, ctx) -> LLMResponse:
        from aistat.agents.reporting import compose_report
        return LLMResponse(structured=compose_report(ctx),
                           text=json.dumps(compose_report(ctx)))
