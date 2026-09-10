"""Evaluation runner (blueprint section 6 step 12).

Resumable and concurrent by design (review section 04): 432 runs at roughly a
minute each is about seven hours sequentially, and the full set will be run more
than once.  Results are appended as JSONL and keyed on
``(system, case_id, rep)`` so a re-invocation skips completed work.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aistat.agents.base import Case
from aistat.agents.systems import SYSTEMS
from aistat.evaluation.scorers import score_run

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
BENCH = ROOT / "benchmark"


def list_cases(split: str) -> list[str]:
    d = BENCH / split
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "not-a-git-repo"


def _prompt_hash() -> str:
    import hashlib
    from aistat.agents import systems
    blob = "".join(getattr(systems, n) for n in
                   ("_SYSTEM_A", "_SYSTEM_B", "_SYSTEM_C", "_SHARED_POLICY"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def run_manifest(client_name: str, split: str, reps: int,
                 systems: list[str]) -> dict:
    """Everything needed to reproduce a run (blueprint section 10.3)."""
    import numpy, pandas, scipy, statsmodels
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "client": client_name,
        "split": split, "reps": reps, "systems": systems,
        "git_commit": _git_commit(),
        "prompt_sha256_16": _prompt_hash(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "versions": {"numpy": numpy.__version__, "pandas": pandas.__version__,
                     "scipy": scipy.__version__,
                     "statsmodels": statsmodels.__version__},
        # Review finding F-A1: temperature is removed on current models, so
        # determinism is controlled by pinning, not by a sampling parameter.
        "determinism_controls": ["pinned model id", "fixed effort",
                                 "frozen prompt hash", "n repetitions"],
    }


@dataclass
class RunKey:
    system: str
    case_id: str
    rep: int

    @property
    def id(self) -> str:
        return f"{self.system}|{self.case_id}|{self.rep}"


def _completed(path: Path) -> set[str]:
    """Runs that need not be repeated.

    A run that errored is NOT complete. Counting it as done meant that after a
    401 wiped out an entire evaluation, the retry skipped all 432 -- the resume
    logic turning a transient failure into a permanent one.
    """
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
            if r.get("error"):
                continue
            done.add(f"{r['system']}|{r['case_id']}|{r.get('rep', 0)}")
        except Exception:
            continue
    return done


def verify_credentials(client_factory) -> tuple[bool, str]:
    """One trivial call before committing to hundreds.

    A 401 discovered at run 432 costs the whole evaluation and looks like a
    harness failure; the same 401 on call one costs a second and names itself.
    """
    try:
        client = client_factory()
        r = client.complete(system="Reply with the single word: ok.",
                            messages=[{"role": "user", "content": "ping"}],
                            max_tokens=8)
        return True, (f"{getattr(client, 'name', 'client')} responded "
                      f"({r.input_tokens} in / {r.output_tokens} out)")
    except Exception as exc:
        msg = str(exc)
        hint = ""
        low = msg.lower()
        if "401" in msg or "invalid api key" in low or "authentication" in low:
            hint = ("  The credential was rejected. Check for a truncated "
                    "paste, surrounding quotes, or a stray newline; Groq keys "
                    "begin 'gsk_'.")
        elif "429" in msg or "rate" in low:
            hint = "  Rate limited. Lower --workers and try again."
        elif "connect" in low or "refused" in low:
            hint = "  Endpoint unreachable. Is the local server running?"
        return False, f"{type(exc).__name__}: {msg[:220]}" + ("\n" + hint if hint else "")


def evaluate(client_factory, *, split: str = "heldout", reps: int = 3,
             systems: list[str] | None = None, out_name: str = "runs",
             max_workers: int = 4, case_ids: list[str] | None = None,
             write_traces: bool = True, progress: bool = True,
             preflight: bool = True) -> dict:
    """Run every (system, case, rep) combination that is not already recorded."""
    systems = systems or list(SYSTEMS)
    cases = case_ids or list_cases(split)
    RESULTS.mkdir(parents=True, exist_ok=True)

    if preflight:
        ok, detail = verify_credentials(client_factory)
        if progress:
            print(f"  pre-flight: {'OK' if ok else 'FAILED'} -- {detail}")
        if not ok:
            return {"n_run": 0, "n_errors": 0, "preflight_failed": True,
                    "detail": detail}

    runs_path = RESULTS / f"{out_name}.jsonl"
    scores_path = RESULTS / f"{out_name}_scores.jsonl"
    trace_path = RESULTS / f"{out_name}_traces.jsonl"
    manifest_path = RESULTS / f"{out_name}_manifest.json"

    done = _completed(runs_path)
    todo = [RunKey(s, c, r) for s in systems for c in cases for r in range(reps)
            if RunKey(s, c, r).id not in done]

    manifest = run_manifest(getattr(client_factory(), "name", "unknown"),
                            split, reps, systems)
    manifest.update(n_cases=len(cases), n_planned=len(systems) * len(cases) * reps,
                    n_already_done=len(done), n_to_run=len(todo))
    manifest_path.write_text(json.dumps(manifest, indent=2))

    if progress:
        print(f"  {len(todo)} runs to execute "
              f"({len(done)} already recorded), {max_workers} workers")
    if not todo:
        return {"n_run": 0, "n_skipped": len(done), "manifest": manifest}

    t0 = time.perf_counter()
    lock_runs, lock_scores, lock_traces = [], [], []
    errors = 0

    def _one(key: RunKey) -> tuple[dict, dict, str] | None:
        try:
            case = Case.load(key.case_id, split)
            driver = SYSTEMS[key.system](client_factory())
            result = driver.run(case, rep=key.rep)
            rd = result.to_dict()
            sc = score_run(rd, case.card.get("randomized"))
            return rd, sc, result.trace.to_jsonl()
        except Exception as exc:                     # a crash is a datum
            rd = {"run_id": f"ERR-{key.id}", "system": key.system,
                  "case_id": key.case_id, "rep": key.rep, "method": "none",
                  "error": f"{type(exc).__name__}: {exc}", "rendered": {},
                  "selection": {}, "verification": {}, "trace_signature": []}
            try:
                sc = score_run(rd, None)
            except Exception:
                sc = {"run_id": rd["run_id"], "system": key.system,
                      "case_id": key.case_id, "rep": key.rep,
                      "run_error": rd["error"], "selection_correct": False}
            return rd, sc, ""

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_one, k): k for k in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            out = fut.result()
            if out is None:
                continue
            rd, sc, tr = out
            if rd.get("error"):
                errors += 1
            lock_runs.append(json.dumps(rd, default=str))
            lock_scores.append(json.dumps(sc, default=str))
            if write_traces and tr:
                lock_traces.append(tr)
            if progress and (i % 25 == 0 or i == len(todo)):
                el = time.perf_counter() - t0
                print(f"    {i}/{len(todo)}  {el:5.1f}s  "
                      f"({i / max(el, 1e-9):.1f}/s)  errors={errors}")

    with runs_path.open("a") as f:
        f.write("\n".join(lock_runs) + "\n")
    with scores_path.open("a") as f:
        f.write("\n".join(lock_scores) + "\n")
    if lock_traces:
        with trace_path.open("a") as f:
            f.write("\n".join(lock_traces) + "\n")

    elapsed = time.perf_counter() - t0
    manifest.update(n_executed=len(lock_runs), n_errors=errors,
                    elapsed_seconds=round(elapsed, 1))
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return {"n_run": len(lock_runs), "n_errors": errors,
            "elapsed_seconds": elapsed, "manifest": manifest,
            "runs_path": str(runs_path), "scores_path": str(scores_path)}


def load_scores(out_name: str = "runs"):
    import pandas as pd
    p = RESULTS / f"{out_name}_scores.jsonl"
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.DataFrame([json.loads(l) for l in p.read_text().splitlines() if l.strip()])
