"""The handoff archive must never carry a credential.

Keys for this project were pasted into a chat window and a terminal, which is
exactly how one ends up in a file nobody thought to check.  A deny-list of
paths is only as good as the memory of whoever wrote it, so the packager also
reads every file it is about to add.  These tests pin both halves.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _packager():
    spec = importlib.util.spec_from_file_location(
        "package_under_test", ROOT / "scripts" / "package.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


pkg = _packager()


@pytest.mark.parametrize("rel", [
    ".env", ".env.local", ".env.production",
    "src/__pycache__/x.pyc", ".git/config", "results/big.zip",
    "node_modules/left-pad/index.js", ".pytest_cache/v/results",
])
def test_excluded_by_name(rel):
    assert pkg.excluded(Path(rel)), f"{rel} would have been packaged"


@pytest.mark.parametrize("rel", [
    ".env.example", "src/aistat/schemas/core.py", "benchmark/gold/x/gold.json",
    "docs/CAPSTONE_REPORT.md", "results/heldout_rulebased_expert_scores.jsonl",
])
def test_kept_by_name(rel):
    assert not pkg.excluded(Path(rel)), f"{rel} would have been dropped"


@pytest.mark.parametrize("secret", [
    "sk-ant-api03-" + "A1b2C3d4E5" * 6,
    "gsk_" + "Qz7Qz7Qz7Qz7Qz7Qz7Qz7Qz7Qz7Qz7Qz7Qz7Qz7Q" + "Jp9r",
    "sk-or-v1-" + "0" * 64,
    "csk-" + "z" * 48,
    "ghp_" + "B" * 36,
])
def test_content_scan_catches_a_key(tmp_path, secret):
    """A key reaching an unexpected file is the case the deny-list misses."""
    f = tmp_path / "debug.log"
    f.write_text(f"2026-09-11 request failed\nAuthorization: Bearer {secret}\n")
    assert pkg.scan(f) is not None, "a credential would have been packaged"


def test_content_scan_passes_ordinary_files(tmp_path):
    f = tmp_path / "notes.md"
    f.write_text("Welch's t-test, p = 0.0031, Hedges' g = 0.82 [0.31, 1.33].\n"
                 "See sk-learn for the reference implementation.\n")
    assert pkg.scan(f) is None


def test_env_example_carries_no_value():
    """The template ships; it must stay a template."""
    example = ROOT / ".env.example"
    if not example.exists():
        pytest.skip("no .env.example in this checkout")
    assert pkg.scan(example) is None
    for line in example.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            _, _, value = line.partition("=")
            assert len(value.strip().strip('"').strip("'")) < 20, (
                f"{line!r} looks like it carries a real value")
