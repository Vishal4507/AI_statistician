"""Benchmark integrity (blueprint sections 4.3 and 10.4)."""
import json
from pathlib import Path

import pytest

from aistat.benchmark.registry import all_specs, summary
from aistat.benchmark.validator import BENCH, validate_all
from aistat.schemas.core import ABSTAIN, METHODS


def test_composition_matches_the_plan():
    s = summary()
    assert s["total"] == 64
    assert s["dev"] == 16 and s["heldout"] == 48
    assert s["synthetic"] == 48 and s["public"] == 16
    # Review finding F-A3: abstention raised from 8 to 12 so the metric is
    # measurable rather than a threshold on six cases.
    assert s["synthetic_abstention"] + s["public_abstention"] == 12


def test_case_ids_are_unique():
    ids = [c["case_id"] for c in all_specs()]
    assert len(ids) == len(set(ids))


def test_all_cases_validate():
    r = validate_all()
    assert r["passed"], json.dumps(
        {"global": r["global_errors"], "cases": r["case_errors"]}, indent=2)[:3000]


def test_every_method_appears_in_the_benchmark():
    seen = {json.loads((BENCH / "gold" / d.name / "gold.json").read_text())["primary_method"]
            for d in (BENCH / "gold").iterdir() if d.is_dir()}
    missing = set(METHODS) - seen
    assert not missing, f"methods with no case: {sorted(missing)}"
    assert ABSTAIN in seen


def test_dev_and_heldout_do_not_overlap():
    dev = {p.name for p in (BENCH / "dev").iterdir() if p.is_dir()}
    held = {p.name for p in (BENCH / "heldout").iterdir() if p.is_dir()}
    assert not (dev & held)


def test_gold_is_not_reachable_from_a_case_directory():
    for split in ("dev", "heldout"):
        for p in (BENCH / split).rglob("*"):
            assert p.name not in ("gold.json", "oracle.json")


def test_questions_never_name_a_method():
    for split in ("dev", "heldout"):
        for d in (BENCH / split).iterdir():
            if not d.is_dir():
                continue
            q = (d / "question.txt").read_text().lower()
            for word in ("welch", "mann-whitney", "anova", "kruskal", "fisher",
                         "spearman", "pearson", "chi-square", "poisson",
                         "negative binomial", "logistic regression"):
                assert word not in q, f"{d.name} question names {word!r}"


def test_public_labels_are_supported_by_their_data():
    from aistat.benchmark.public import build_case, validate_label
    from aistat.benchmark.registry import PUBLIC
    problems = {}
    for spec in PUBLIC:
        df, _, gold = build_case(spec)
        if gold["primary_method"] != ABSTAIN:
            p = validate_label(spec, df, gold)
            if p:
                problems[spec["case_id"]] = p
    assert not problems, problems


def test_oracles_exist_for_every_non_abstention_case():
    for d in (BENCH / "gold").iterdir():
        if not d.is_dir():
            continue
        gold = json.loads((d / "gold.json").read_text())
        oracle = json.loads((d / "oracle.json").read_text())
        if gold["primary_method"] == ABSTAIN:
            continue
        assert oracle.get("values"), f"{d.name} has an empty oracle"
        assert "error" not in oracle, f"{d.name} oracle errored: {oracle.get('error')}"
