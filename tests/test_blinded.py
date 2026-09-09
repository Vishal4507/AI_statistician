"""Blinded interpretation scoring (blueprint section 8.3).

The metric this supports requires a human. These tests defend the property that
makes the human's judgement worth anything: that they cannot tell which system
wrote what.
"""
import csv
import json

import pytest

from aistat.evaluation.blinded import RUBRIC, Item, Session, blind, ingest


def test_rubric_is_the_three_point_scale_the_blueprint_specifies():
    assert set(RUBRIC) == {0, 1, 2}


@pytest.mark.parametrize("text", [
    "System C, the structured agent, selected Welch.",
    "System A, the direct LLM, reported no estimate.",
    "Selected during unconstrained tool use.",
    "C_protocol chose to abstain.",
])
def test_system_identity_is_removed(text):
    out = blind(text)
    for tell in ("System A", "System B", "System C", "A_direct", "B_tools",
                 "C_protocol", "structured agent", "direct LLM",
                 "unconstrained tool use"):
        assert tell.lower() not in out.lower(), f"{tell!r} survived in {out!r}"


def test_blinding_leaves_grammatical_text():
    """A scorer who can spot which reports were edited is no longer blind."""
    out = blind("System C, the structured agent, selected Welch.")
    assert "the the" not in out
    assert " ," not in out
    assert ", selected" not in out
    assert out.endswith(".")


def test_blinding_does_not_touch_substantive_content():
    text = "The mean difference is 12.4, 95% CI [1.2, 23.7], p = 0.031."
    assert blind(text) == text


def test_item_presentation_contains_no_identity():
    item = Item("R00000001", "case_x", "C_protocol", "run_1", {
        "interpretation": "System C found an association.",
        "limitations": "Observational.",
    })
    shown = item.presented()
    assert "C_protocol" not in shown
    assert "System C" not in shown
    assert "association" in shown          # content survives


def test_session_shuffles_and_adds_double_scored_repeats(tmp_path):
    session = Session.from_runs("heldout_rulebased_expert", double_fraction=0.2, limit=10)
    from aistat.evaluation.blinded import REPEAT_SUFFIX, base_id
    ids = [i.item_id for i in session.items]
    assert len(ids) > 10                        # repeats were added
    repeats = [i for i in ids if i.endswith(REPEAT_SUFFIX)]
    assert repeats, "no double-scored items"
    for r in repeats:
        assert base_id(r) in ids, "a repeat has no original"


def test_repeat_suffix_cannot_collide_with_a_hex_item_id():
    """Item ids are hex; a suffix of 'b' would mangle originals ending in b."""
    from aistat.evaluation.blinded import REPEAT_SUFFIX, base_id
    # The suffix needs at least one character hex cannot produce, so it can
    # never be mistaken for part of an id.
    assert any(c not in "0123456789abcdef" for c in REPEAT_SUFFIX)
    assert base_id("Rabbbbbbb") == "Rabbbbbbb"          # original survives
    assert base_id("Rabbbbbbb" + REPEAT_SUFFIX) == "Rabbbbbbb"


def test_packet_key_and_sheet_round_trip(tmp_path):
    # Enough items that the double-scored subset supports an agreement
    # statistic -- ingest needs at least two complete pairs.
    session = Session.from_runs("heldout_rulebased_expert", limit=40)
    packet, sheet, key = session.write_packet(tmp_path)

    text = packet.read_text()
    for tell in ("System A", "System B", "System C", "A_direct", "B_tools",
                 "C_protocol"):
        assert tell not in text, f"{tell!r} leaked into the packet"

    # The key holds the identities the packet must not.
    keydata = json.loads(key.read_text())
    assert {v["system"] for v in keydata.values()} <= {
        "A_direct", "B_tools", "C_protocol"}

    rows = list(csv.DictReader(sheet.open()))
    assert {r["item_id"] for r in rows} == set(keydata)

    # Score everything 2 and confirm the join reconstructs per-system results.
    with sheet.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item_id", "score", "notes"])
        w.writeheader()
        for r in rows:
            w.writerow({"item_id": r["item_id"], "score": 2, "notes": ""})

    result = ingest(sheet, key)
    assert result["n_scored"] == len(rows)
    assert all(r["mean"] == 2.0 for r in result["per_system"])
    assert result["exact_agreement"] == 1.0     # identical scores agree


def test_ingest_rejects_an_unscored_sheet(tmp_path):
    session = Session.from_runs("heldout_rulebased_expert", limit=4)
    _, sheet, key = session.write_packet(tmp_path)
    with pytest.raises(ValueError):
        ingest(sheet, key)


def test_missing_run_set_fails_clearly():
    with pytest.raises(FileNotFoundError):
        Session.from_runs("a_run_that_was_never_executed")
