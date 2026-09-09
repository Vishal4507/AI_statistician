"""Shared machinery for all three systems (review section 04).

Everything except control flow lives here.  That is what makes baseline
fairness provable rather than asserted: the three drivers import the same tool
registry, the same result store and the same report schema, so there is no code
path on which System A or B could have been disadvantaged.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from aistat.agents.policy import TaskShape, infer_task
from aistat.agents.trace import TraceLog
from aistat.provenance.store import ProvenanceError, ResultStore
from aistat.schemas.core import ABSTAIN, FinalReport
from aistat.tools.registry import ToolRegistry
from aistat.tools.verify import verify_report

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmark"


@dataclass
class Case:
    case_id: str
    split: str
    df: pd.DataFrame
    question: str
    objective: str
    card: dict
    manifest: dict

    @property
    def roles(self) -> dict[str, str]:
        return self.manifest["variable_roles"]

    @classmethod
    def load(cls, case_id: str, split: str | None = None) -> "Case":
        for s in ([split] if split else ["dev", "heldout"]):
            d = BENCH / s / case_id
            if d.exists():
                q = (d / "question.txt").read_text()
                question = q.split("\n\nAnalysis objective:")[0].strip()
                objective = q.split("Analysis objective:")[-1].strip() \
                    if "Analysis objective:" in q else ""
                return cls(case_id, s, pd.read_csv(d / "data.csv"), question,
                           objective, json.loads((d / "design_card.json").read_text()),
                           json.loads((d / "case_manifest.json").read_text()))
        raise FileNotFoundError(f"case {case_id} not found")


@dataclass
class RunResult:
    run_id: str
    system: str
    case_id: str
    rep: int
    method: str
    abstain_reason: str | None
    report: dict | None
    rendered: dict[str, str]
    selection: dict
    verification: dict
    trace: TraceLog
    executed_methods: list[str]
    n_tool_calls: int
    n_diagnostic_calls: int
    n_llm_calls: int
    provenance_rejections: int
    revised: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "trace"}
        d["trace_signature"] = self.trace.signature
        d["n_trace_events"] = len(self.trace.events)
        return d


class DriverBase:
    """Common context assembly, report finalisation and provenance accounting."""

    system_name = "base"

    def __init__(self, client, *, strict_provenance: bool = True) -> None:
        self.client = client
        self.strict_provenance = strict_provenance

    # -- setup -------------------------------------------------------------

    def _new_run(self, case: Case, rep: int):
        run_id = f"{self.system_name}-{case.case_id}-r{rep}-{uuid.uuid4().hex[:8]}"
        store = ResultStore()
        registry = ToolRegistry(case.df, store)
        trace = TraceLog(run_id, self.system_name, case.case_id, rep)
        return run_id, store, registry, trace

    @staticmethod
    def _task(case: Case) -> TaskShape:
        return infer_task(case.df, case.roles)

    def _ctx(self, case: Case, store, registry, **extra) -> dict[str, Any]:
        return {
            "df": case.df, "roles": case.roles, "card": case.card,
            "question": case.question, "objective": case.objective,
            "case_id": case.case_id, "store": store, "registry": registry,
            "task": self._task(case), **extra,
        }

    # -- finalisation ------------------------------------------------------

    def _finalise(self, *, case: Case, run_id: str, rep: int, store: ResultStore,
                  registry: ToolRegistry, trace: TraceLog, report_dict: dict | None,
                  selection: dict, t0: float, revised: bool = False,
                  error: str | None = None, n_llm: int = 0,
                  metadata: dict | None = None) -> RunResult:
        rendered: dict[str, str] = {}
        verification: dict = {}
        report_obj: FinalReport | None = None

        if report_dict is not None and error is None:
            try:
                report_obj = FinalReport.model_validate(report_dict)
            except Exception as exc:
                error = f"report schema rejected: {exc}"
                trace.error("report_schema", str(exc))

        if report_obj is not None:
            for name, block in report_obj.prose_blocks().items():
                try:
                    rendered[name] = store.render(block.text,
                                                  strict=self.strict_provenance)
                except ProvenanceError as exc:
                    trace.error("provenance", str(exc))
                    rendered[name] = f"[PROVENANCE FAILURE: {exc.ref}]"
                    error = error or f"provenance failure: {exc.ref}"
            verification = verify_report(
                report_obj, store, case.card.get("randomized"),
                selection.get("method", ""))
            trace.event("verification", **{k: v for k, v in verification.items()
                                           if k != "findings"})

        usage = (getattr(self.client, "total_input", 0),
                 getattr(self.client, "total_output", 0),
                 getattr(self.client, "total_cache_read", 0))

        return RunResult(
            run_id=run_id, system=self.system_name, case_id=case.case_id, rep=rep,
            method=selection.get("method", "none"),
            abstain_reason=selection.get("abstain_reason"),
            report=report_dict, rendered=rendered, selection=selection,
            verification=verification, trace=trace,
            executed_methods=registry.executed_methods,
            n_tool_calls=len(registry.calls),
            n_diagnostic_calls=registry.n_diagnostic_calls,
            n_llm_calls=n_llm, provenance_rejections=store.rejection_count,
            revised=revised, latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            input_tokens=usage[0], output_tokens=usage[1], cache_read_tokens=usage[2],
            error=error,
            metadata={**(metadata or {}),
                      "provenance_keys": store.keys(),
                      "n_provenance_values": len(store),
                      "refs_used": sorted(store.used)},
        )

    # -- shared evidence gathering ----------------------------------------

    @staticmethod
    def _gather_evidence(registry: ToolRegistry, task: TaskShape,
                         trace: TraceLog) -> tuple[dict, dict, dict[str, str]]:
        """Run the diagnostics material to *this* task shape.

        Blueprint section 7: request only diagnostics that can change the method
        or the interpretation.  A generic checklist encourages ritual testing.
        """
        evidence: dict[str, dict] = {}
        refs: dict[str, str] = {}
        slot_ids: dict[str, str] = {}

        tc = registry.call("inspect_dataset")
        trace.tool(tc.call_id, tc.name, tc.arguments, tc.is_error,
                   len(tc.payload) if isinstance(tc.payload, dict) else 0)
        if not tc.is_error:
            evidence["inspect"] = tc.payload
            refs["n_rows"] = f"{tc.call_id}.n_rows"
            slot_ids["inspect"] = tc.call_id

        if task.kind in ("two_group", "multi_group"):
            for tool, key in (("summarize_groups", "summary"),
                              ("check_group_assumptions", "assumptions")):
                tc = registry.call(tool, {"outcome": task.outcome, "group": task.group})
                trace.tool(tc.call_id, tc.name, tc.arguments, tc.is_error,
                           len(tc.payload))
                if not tc.is_error:
                    evidence[key] = tc.payload
                    slot_ids[key] = tc.call_id
                    if key == "summary":
                        refs.update(total_n=f"{tc.call_id}.total_n",
                                    min_group_n=f"{tc.call_id}.min_group_n",
                                    max_group_n=f"{tc.call_id}.max_group_n")
        elif task.kind == "categorical":
            tc = registry.call("check_contingency",
                               {"var1": task.var1, "var2": task.var2})
            trace.tool(tc.call_id, tc.name, tc.arguments, tc.is_error, len(tc.payload))
            if not tc.is_error:
                evidence["contingency"] = tc.payload
                refs["total_n"] = f"{tc.call_id}.total_n"
                slot_ids["contingency"] = tc.call_id
        elif task.kind == "association":
            tc = registry.call("check_association", {"x": task.var1, "y": task.var2})
            trace.tool(tc.call_id, tc.name, tc.arguments, tc.is_error, len(tc.payload))
            if not tc.is_error:
                evidence["association"] = tc.payload
                refs["total_n"] = f"{tc.call_id}.n"
                slot_ids["association"] = tc.call_id
        return evidence, refs, slot_ids

    @staticmethod
    def _execute(registry: ToolRegistry, method: str, task: TaskShape,
                 trace: TraceLog):
        if task.kind in ("two_group", "multi_group"):
            args = {"method": method, "outcome": task.outcome, "group": task.group}
            tool = "run_group_test"
        elif task.kind in ("categorical", "association"):
            args = {"method": method, "var1": task.var1, "var2": task.var2}
            tool = "run_categorical_or_correlation"
        else:
            args = {"method": method, "outcome": task.outcome,
                    "predictors": list(task.predictors)}
            if task.exposure:
                args["exposure"] = task.exposure
            tool = "fit_regression"
        tc = registry.call(tool, args)
        trace.tool(tc.call_id, tc.name, tc.arguments, tc.is_error,
                   len(tc.payload) if isinstance(tc.payload, dict) else 0)
        return tc
