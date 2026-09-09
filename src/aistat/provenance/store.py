"""Run-scoped numeric provenance (review finding F-A4).

The blueprint's ``verify_report`` *detects* fabricated numbers after the model
has written them.  This module *prevents* them: every tool return is registered
here under a stable key, the report schema forbids raw numeric literals, and
the model can only emit ``{{ref}}`` templates that this store substitutes.

An unknown reference is a hard error, not a warning.  The consequence, which
the write-up must state honestly: numerical fidelity for System C is an
architectural guarantee rather than an empirical finding.  The empirical number
is ``rejection_count`` -- how often the model reached for a reference that did
not exist.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from aistat.schemas.core import REF_PATTERN


class ProvenanceError(ValueError):
    """Raised when a report references a value no tool produced."""

    def __init__(self, ref: str, known: int) -> None:
        super().__init__(
            f"unknown result reference {ref!r} "
            f"({known} registered values); no tool produced it"
        )
        self.ref = ref


def flatten(payload: Any, prefix: str = "") -> dict[str, float]:
    """Flatten a tool payload into dotted numeric keys.

    Only finite numbers survive -- NaN and booleans are not statistics.  Lists
    are indexed: ``coefficients[0].estimate``.
    """
    out: dict[str, float] = {}
    if isinstance(payload, dict):
        for k, v in payload.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(payload, (list, tuple)):
        for i, v in enumerate(payload):
            out.update(flatten(v, f"{prefix}[{i}]"))
    elif isinstance(payload, bool):
        pass  # a flag is not a statistic
    elif isinstance(payload, (int, float)):
        if math.isfinite(payload):
            out[prefix] = float(payload)
    return out


def flatten_labels(payload: Any, prefix: str = "") -> dict[str, str]:
    """Flatten the *qualitative* tool output -- short strings and flags.

    A model that writes "the effect size is {{...value}}, which is
    {{...interpretation}}" is writing well, and both halves came from the same
    tool.  Registering labels alongside numbers makes that legal without
    weakening anything: the numeric invariant is unchanged, and a label is
    still provenanced to a tool result rather than invented.
    """
    out: dict[str, str] = {}
    if isinstance(payload, dict):
        for k, v in payload.items():
            out.update(flatten_labels(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(payload, (list, tuple)):
        for i, v in enumerate(payload):
            out.update(flatten_labels(v, f"{prefix}[{i}]"))
    elif isinstance(payload, bool):
        out[prefix] = "yes" if payload else "no"
    elif isinstance(payload, str) and 0 < len(payload) <= 200:
        out[prefix] = payload
    return out


def format_value(v: float) -> str:
    """Render a statistic for a report.

    Significance-aware: p-values below the display floor become ``< 0.001``
    rather than a misleading ``0.000``.
    """
    a = abs(v)
    if v == int(v) and a < 1e15:
        return f"{int(v):,}"
    if a != 0 and a < 1e-3:
        return f"{v:.2e}"
    if a < 1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if a < 1000:
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return f"{v:,.2f}"


@dataclass
class ResultStore:
    """Every tool return lands here before the model sees it."""

    _values: dict[str, float] = field(default_factory=dict)
    _labels: dict[str, str] = field(default_factory=dict)
    _payloads: dict[str, dict] = field(default_factory=dict)
    _used: set[str] = field(default_factory=set)
    _rejected: list[str] = field(default_factory=list)
    _counter: int = 0

    # -- registration ------------------------------------------------------

    def next_call_id(self, tool_name: str) -> str:
        self._counter += 1
        return f"r{self._counter}.{tool_name}"

    def register(self, call_id: str, payload: dict) -> dict:
        """Record a tool return.  Returns the payload unchanged for chaining."""
        self._payloads[call_id] = payload
        for key, val in flatten(payload).items():
            self._values[f"{call_id}.{key}"] = val
        for key, text in flatten_labels(payload).items():
            self._labels[f"{call_id}.{key}"] = text
        return payload

    # -- lookup ------------------------------------------------------------

    def __contains__(self, ref: str) -> bool:
        return ref in self._values or ref in self._labels

    def __len__(self) -> int:
        return len(self._values)

    def get(self, ref: str) -> float:
        if ref not in self._values:
            raise ProvenanceError(ref, len(self._values))
        self._used.add(ref)
        return self._values[ref]

    def keys(self) -> list[str]:
        """Numeric references only -- the statistics."""
        return sorted(self._values)

    def label_keys(self) -> list[str]:
        """Qualitative references -- interpretations, method names, flags."""
        return sorted(self._labels)

    def citable(self) -> list[str]:
        """Everything a report may reference."""
        return sorted(set(self._values) | set(self._labels))

    def keys_for(self, call_id: str) -> list[str]:
        return sorted(k for k in self._values if k.startswith(call_id + "."))

    def payload(self, call_id: str) -> dict | None:
        return self._payloads.get(call_id)

    # -- rendering ---------------------------------------------------------

    def render(self, text: str, strict: bool = True) -> str:
        """Substitute every ``{{ref}}`` with its registered value.

        With ``strict``, an unknown reference raises.  With ``strict=False``
        it is recorded in ``rejected`` and left visibly marked, which is how
        the scorer measures provenance failures for the unconstrained systems
        without aborting their runs.
        """

        def sub(m):
            ref = m.group(1)
            if ref in self._values:
                self._used.add(ref)
                return format_value(self._values[ref])
            if ref in self._labels:
                self._used.add(ref)
                return self._labels[ref]
            self._rejected.append(ref)
            if strict:
                raise ProvenanceError(ref, len(self._values) + len(self._labels))
            return f"[UNRESOLVED:{ref}]"

        out = REF_PATTERN.sub(sub, text)

        # A template that matched no pattern would otherwise be emitted verbatim.
        # That is worse than failing: the report looks finished and contains a
        # placeholder where a statistic should be. Catch any residue explicitly.
        if "{{" in out or "}}" in out:
            residue = re.search(r"\{\{.{0,80}|.{0,80}\}\}", out)
            frag = residue.group(0) if residue else out[:80]
            self._rejected.append(frag)
            if strict:
                raise ProvenanceError(frag, len(self._values) + len(self._labels))
            out = out.replace("{{", "[UNRESOLVED:").replace("}}", "]")
        return out

    # -- audit -------------------------------------------------------------

    @property
    def used(self) -> set[str]:
        return set(self._used)

    @property
    def rejected(self) -> list[str]:
        return list(self._rejected)

    @property
    def rejection_count(self) -> int:
        return len(self._rejected)

    def unused_from(self, call_id: str) -> list[str]:
        """Registered values from a call that the report never cited.

        A diagnostic that was computed and then ignored is exactly the failure
        mode the interpretation guardrails in blueprint section 7 exist to catch.
        """
        return [k for k in self.keys_for(call_id) if k not in self._used]

    def snapshot(self) -> dict[str, float]:
        return dict(self._values)

    def nearest(self, ref: str, n: int = 6) -> list[str]:
        """References most similar to a bad one, for a corrective retry."""
        import difflib
        return difflib.get_close_matches(ref, self.citable(), n=n, cutoff=0.5)
