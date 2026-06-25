"""Tests for the rule calibration harness (the 'smoke alarm test').

A rule may BLOCK a build only if it's precise: it must fire on real violations
and stay quiet on clean code (including near-misses like the pattern sitting in a
comment). Jumpy rules degrade to WARN.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "calibration"))
from precision_recall import evaluate, demo, PRECISION_BAR  # noqa: E402


def test_a_precise_rule_is_block_eligible():
    cases = [{"id": "p1", "label": "positive"}, {"id": "n1", "label": "negative"}]
    m = evaluate(cases, fired={"p1"})  # fired on the real violation, quiet on clean
    assert m["precision"] == 1.0 and m["recall"] == 1.0
    assert m["block_eligible"] is True


def test_a_jumpy_rule_that_false_fires_is_warn_only():
    cases = [{"id": "p1", "label": "positive"},
             {"id": "n1", "label": "negative"}, {"id": "n2", "label": "negative"}]
    m = evaluate(cases, fired={"p1", "n1"})  # also fired on a clean case = false positive
    assert m["fp"] == 1
    assert m["precision"] < PRECISION_BAR
    assert m["block_eligible"] is False


def test_a_rule_that_misses_real_violations_has_low_recall():
    cases = [{"id": "p1", "label": "positive"}, {"id": "p2", "label": "positive"}]
    m = evaluate(cases, fired={"p1"})  # missed p2
    assert m["fn"] == 1
    assert m["recall"] == 0.5


def test_calibrate_demo_catches_the_jumpy_rule():
    # End-to-end through the REAL check_rules: the naive raw-SQL rule catches the
    # real violation but also false-fires on a comment/string -> not block-eligible.
    _rule, _cases, m = demo()
    assert m["recall"] == 1.0          # it does catch the real raw SQL
    assert m["fp"] >= 1                # but it also false-fires
    assert m["block_eligible"] is False
