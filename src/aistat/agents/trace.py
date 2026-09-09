"""Append-only run traces (review section 04).

Every state transition, tool request and tool return is written with a
monotonic sequence number.  Two payoffs beyond debugging: a run replays without
touching the API, and traces of repeated runs of the same case can be diffed to
locate where nondeterminism first enters.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _safe(o: Any) -> Any:
    try:
        json.dumps(o)
        return o
    except (TypeError, ValueError):
        return str(o)


@dataclass
class TraceLog:
    run_id: str
    system: str
    case_id: str
    rep: int = 0
    events: list[dict] = field(default_factory=list)
    _seq: int = 0
    _t0: float = field(default_factory=time.perf_counter)

    def event(self, kind: str, **payload) -> dict:
        self._seq += 1
        e = {"seq": self._seq, "t_ms": round((time.perf_counter() - self._t0) * 1000, 2),
             "kind": kind, **{k: _safe(v) for k, v in payload.items()}}
        self.events.append(e)
        return e

    # Convenience wrappers -------------------------------------------------

    def state(self, name: str, **payload) -> None:
        self.event("state", state=name, **payload)

    def tool(self, call_id: str, name: str, arguments: dict,
             is_error: bool, n_keys: int) -> None:
        self.event("tool_call", call_id=call_id, tool=name, arguments=arguments,
                   is_error=is_error, n_result_keys=n_keys)

    def llm(self, purpose: str, resp) -> None:
        self.event("llm_call", purpose=purpose, stop_reason=resp.stop_reason,
                   input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                   cache_read_tokens=resp.cache_read_tokens,
                   n_tool_uses=len(resp.tool_uses),
                   thinking_chars=len(resp.thinking or ""))

    def error(self, where: str, message: str) -> None:
        self.event("error", where=where, message=message)

    # Analysis -------------------------------------------------------------

    @property
    def signature(self) -> list[str]:
        """Comparable step signature, used to diff repetitions of one case."""
        out = []
        for e in self.events:
            if e["kind"] == "state":
                out.append(f"S:{e['state']}")
            elif e["kind"] == "tool_call":
                m = e["arguments"].get("method") if isinstance(e["arguments"], dict) else None
                out.append(f"T:{e['tool']}" + (f":{m}" if m else ""))
        return out

    def to_jsonl(self) -> str:
        head = {"run_id": self.run_id, "system": self.system,
                "case_id": self.case_id, "rep": self.rep, "kind": "run_header"}
        return "\n".join(json.dumps(e) for e in [head, *self.events])

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(self.to_jsonl() + "\n")


def divergence_point(a: TraceLog, b: TraceLog) -> int | None:
    """First index at which two run signatures differ, or None if identical."""
    sa, sb = a.signature, b.signature
    for i, (x, y) in enumerate(zip(sa, sb)):
        if x != y:
            return i
    return None if len(sa) == len(sb) else min(len(sa), len(sb))
