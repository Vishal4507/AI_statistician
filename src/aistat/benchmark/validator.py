"""Automated case validator (blueprint section 4.3).

Checks: required files present, seeds fixed, no target leakage, expected row
counts and hashes, no dev/held-out overlap, and -- the important one -- no gold
field reachable from anything the agent can see.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from aistat.schemas.core import ABSTAIN, METHODS

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmark"

CASE_FILES = ("data.csv", "question.txt", "design_card.json", "case_manifest.json")
GOLD_FILES = ("gold.json", "oracle.json")

# Method names must never appear in an agent-visible file (section 4.4).
_METHOD_WORDS = [
    "student t", "student's t", "welch", "mann-whitney", "mann whitney",
    "anova", "kruskal", "chi-square", "chi square", "fisher", "pearson",
    "spearman", "ols", "ordinary least squares", "logistic regression",
    "poisson", "negative binomial", "abstain",
]


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_case(case_dir: Path, gold_dir: Path) -> list[str]:
    cid = case_dir.name
    errs: list[str] = []

    for f in CASE_FILES:
        if not (case_dir / f).exists():
            errs.append(f"{cid}: missing {f}")
    for f in GOLD_FILES:
        if not (gold_dir / f).exists():
            errs.append(f"{cid}: missing gold/{f}")
    if errs:
        return errs

    df = pd.read_csv(case_dir / "data.csv")
    manifest = json.loads((case_dir / "case_manifest.json").read_text())
    card = json.loads((case_dir / "design_card.json").read_text())
    gold = json.loads((gold_dir / "gold.json").read_text())
    question = (case_dir / "question.txt").read_text()

    # -- integrity ---------------------------------------------------------
    if manifest["n_rows"] != len(df):
        errs.append(f"{cid}: manifest n_rows={manifest['n_rows']} but data has {len(df)}")
    if manifest["data_sha256"] != _sha_file(case_dir / "data.csv"):
        errs.append(f"{cid}: data.csv hash does not match the manifest")
    if len(df) < 20:
        errs.append(f"{cid}: only {len(df)} rows")
    if manifest["origin"] == "synthetic" and manifest.get("seed") is None:
        errs.append(f"{cid}: synthetic case has no fixed seed")

    # -- gold sanity -------------------------------------------------------
    pm = gold["primary_method"]
    if pm not in METHODS and pm != ABSTAIN:
        errs.append(f"{cid}: unknown primary method {pm!r}")
    if pm not in gold["accepted_methods"]:
        errs.append(f"{cid}: primary method missing from the accepted set")
    if pm == ABSTAIN and not gold.get("abstain_reason"):
        errs.append(f"{cid}: abstention case has no reason")
    if pm != ABSTAIN and gold.get("abstain_reason"):
        errs.append(f"{cid}: non-abstention case carries an abstain reason")

    # -- leakage -----------------------------------------------------------
    low_q = question.lower()
    for w in _METHOD_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", low_q):
            errs.append(f"{cid}: question names a method ({w!r})")
    visible = json.dumps(manifest) + json.dumps(card) + question
    for key in ("primary_method", "accepted_methods", "rationale",
                "abstain_reason", "expected_hazards"):
        if key in visible:
            errs.append(f"{cid}: gold field {key!r} leaked into an agent-visible file")
    if gold.get("rationale") and gold["rationale"][:40] in visible:
        errs.append(f"{cid}: gold rationale text leaked into a visible file")

    # -- design card coherence --------------------------------------------
    for col_key in ("repeated_id_column", "time_column", "clustering_column"):
        col = card.get(col_key)
        if col and col not in df.columns:
            errs.append(f"{cid}: design card {col_key}={col!r} is not a data column")
    for col in manifest["variable_roles"]:
        if col not in df.columns:
            errs.append(f"{cid}: manifest role column {col!r} is not in the data")

    # -- target leakage ----------------------------------------------------
    outcome = next((c for c, r in manifest["variable_roles"].items()
                    if r == "outcome"), None)
    if outcome and outcome in df.columns and pd.api.types.is_numeric_dtype(df[outcome]):
        y = df[outcome]
        for c in df.columns:
            if c == outcome or not pd.api.types.is_numeric_dtype(df[c]):
                continue
            if df[c].nunique() < 2 or y.nunique() < 2:
                continue
            r = df[[c, outcome]].dropna().corr().iloc[0, 1]
            if pd.notna(r) and abs(r) > 0.995:
                errs.append(f"{cid}: possible target leakage, corr({c},{outcome})={r:.4f}")
    return errs


def validate_all() -> dict:
    results: dict[str, list[str]] = {}
    dev = {p.name for p in (BENCH / "dev").iterdir() if p.is_dir()}
    held = {p.name for p in (BENCH / "heldout").iterdir() if p.is_dir()}

    overlap = dev & held
    global_errs = [f"OVERLAP: {c} appears in both splits" for c in sorted(overlap)]

    for split, ids in (("dev", dev), ("heldout", held)):
        for cid in sorted(ids):
            e = validate_case(BENCH / split / cid, BENCH / "gold" / cid)
            if e:
                results[cid] = e

    # Gold must not be reachable from a case directory.
    for split in ("dev", "heldout"):
        for p in (BENCH / split).rglob("*"):
            if p.name in GOLD_FILES:
                global_errs.append(f"LEAK: {p.relative_to(BENCH)} sits inside a case dir")

    return {
        "n_dev": len(dev), "n_heldout": len(held), "n_total": len(dev) + len(held),
        "n_cases_with_errors": len(results),
        "n_errors": sum(len(v) for v in results.values()) + len(global_errs),
        "global_errors": global_errs,
        "case_errors": results,
        "passed": not results and not global_errs,
    }
