"""Case-package builder (blueprint section 4.2).

One registry entry in, one six-file package out.  Gold and oracle files are
written to a separate tree that the application never reads (section 6 step 11).

    benchmark/dev/<case_id>/      data.csv question.txt design_card.json
    benchmark/heldout/<case_id>/  case_manifest.json
    benchmark/gold/<case_id>/     gold.json oracle.json
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from aistat.benchmark import public, registry
from aistat.benchmark.generators import GENERATORS
from aistat.provenance.store import ResultStore
from aistat.tools.registry import ToolRegistry

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmark"

# Which tool call produces the oracle for each gold method.
_ORACLE_CALL = {
    **{m: "run_group_test" for m in
       ("student_t", "welch_t", "mann_whitney", "one_way_anova",
        "welch_anova", "kruskal_wallis")},
    **{m: "run_categorical_or_correlation" for m in
       ("chi_square", "fisher_exact", "pearson", "spearman")},
    **{m: "fit_regression" for m in ("ols", "logistic", "poisson", "negative_binomial")},
}


def _sha_file(path: Path) -> str:
    """Hash the written bytes, not the in-memory frame -- a CSV round-trip
    changes dtype formatting, so only the file itself is a stable identity."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _roles_for_public(spec: dict, df: pd.DataFrame) -> dict[str, str]:
    v, roles = spec["vars"], {}
    for key, role in (("outcome", "outcome"), ("group", "group"),
                      ("var1", "variable"), ("var2", "variable"),
                      ("x", "variable"), ("y", "variable")):
        if key in v and v[key] in df.columns:
            roles[v[key]] = role
    for pcol in v.get("predictors", []):
        if pcol in df.columns:
            roles[pcol] = "predictor"
    for c in df.columns:
        roles.setdefault(c, "context")
    return roles


def _oracle(df: pd.DataFrame, gold: dict, spec: dict) -> dict:
    """Pinned tool output for the gold method (regression fixture, not a check)."""
    method = gold["primary_method"]
    if method == "abstain":
        return {"values": {}, "note": "abstention case: no reference computation"}

    store = ResultStore()
    reg = ToolRegistry(df, store)
    tool = _ORACLE_CALL[method]
    v = spec.get("vars") or {}
    roles = spec.get("variable_roles") or {}

    def _role(name: str) -> str | None:
        for col, r in roles.items():
            if r == name and col in df.columns:
                return col
        return None

    if tool == "run_group_test":
        outcome = v.get("outcome") or _role("outcome")
        group = v.get("group") or _role("group")
        args = {"method": method, "outcome": outcome, "group": group}
    elif tool == "run_categorical_or_correlation":
        if "var1" in v or "x" in v:
            a = v.get("var1") or v.get("x")
            b = v.get("var2") or v.get("y")
        else:
            cols = [c for c, r in roles.items() if r == "variable"]
            a, b = (cols + [None, None])[:2]
        args = {"method": method, "var1": a, "var2": b}
    else:
        outcome = v.get("outcome") or _role("outcome")
        preds = list(v.get("predictors") or
                     [c for c, r in roles.items() if r == "predictor"])
        args = {"method": method, "outcome": outcome, "predictors": preds}
        exp = v.get("exposure") or _role("exposure")
        if exp:
            args["exposure"] = exp

    tc = reg.call(tool, args)
    if tc.is_error:
        return {"values": {}, "error": tc.payload.get("error"), "args": args}
    return {"values": {k.split(".", 2)[-1]: val
                       for k, val in store.snapshot().items()},
            "tool": tool, "args": args}


def build_one(spec: dict, write: bool = True) -> dict:
    """Materialise one case package.  Returns a summary record."""
    cid = spec["case_id"]

    if spec["origin"] == "synthetic":
        gen = GENERATORS[spec["family"]]
        df, card, gold = gen(spec["seed"], **spec["params"])
        roles = spec["variable_roles"]
    else:
        df, card, gold = public.build_case(spec)
        roles = _roles_for_public(spec, df)
        spec = dict(spec, variable_roles=roles, seed=None)

    gold = dict(gold, case_id=cid)
    manifest = {
        "case_id": cid, "family": spec["family"], "origin": spec["origin"],
        "split": spec["split"], "variable_roles": roles,
        "allowed_preprocessing": ["drop rows with missing values in analysis columns"],
        "seed": spec.get("seed"),
        "source": spec.get("dataset"), "source_doi": None,
        "n_rows": int(len(df)), "data_sha256": None,   # filled after the write
    }
    if spec["origin"] == "public":
        import json as _json
        mf = ROOT / "data" / "raw" / "MANIFEST.json"
        if mf.exists():
            meta = _json.loads(mf.read_text()).get(spec.get("dataset"), {})
            manifest["source_doi"] = meta.get("doi")
            manifest["source_url"] = meta.get("url")
            manifest["source_license"] = meta.get("license")

    oracle = {"case_id": cid, **_oracle(df, gold, spec), "default_rtol": 1e-6}

    if write:
        case_dir = BENCH / spec["split"] / cid
        gold_dir = BENCH / "gold" / cid
        case_dir.mkdir(parents=True, exist_ok=True)
        gold_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(case_dir / "data.csv", index=False)
        manifest["data_sha256"] = _sha_file(case_dir / "data.csv")
        (case_dir / "question.txt").write_text(
            f"{spec['question']}\n\nAnalysis objective: {spec['objective']}\n")
        (case_dir / "design_card.json").write_text(json.dumps(card, indent=2))
        (case_dir / "case_manifest.json").write_text(json.dumps(manifest, indent=2))
        (gold_dir / "gold.json").write_text(json.dumps(gold, indent=2))
        (gold_dir / "oracle.json").write_text(json.dumps(oracle, indent=2))

    return {"case_id": cid, "split": spec["split"], "origin": spec["origin"],
            "family": spec["family"], "primary_method": gold["primary_method"],
            "accepted": gold["accepted_methods"], "n_rows": len(df),
            "n_oracle_values": len(oracle.get("values", {})),
            "oracle_error": oracle.get("error")}


def build_all(write: bool = True) -> list[dict]:
    return [build_one(s, write) for s in registry.all_specs()]
