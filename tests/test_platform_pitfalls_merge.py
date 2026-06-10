# tests/test_platform_pitfalls_merge.py
"""Tests for archie/standalone/finalize.py::merge_platform_pitfalls (pure, no I/O)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "_archie_finalize", _ROOT / "archie" / "standalone" / "finalize.py",
)
_finalize = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_finalize"] = _finalize
_SPEC.loader.exec_module(_finalize)

merge = _finalize.merge_platform_pitfalls

_CATALOG = json.loads((_ROOT / "archie" / "standalone" / "platform_pitfalls.json").read_text())
_SIGNAL = [{"signal": "ios_legacy_xcode_no_folder_sync", "evidence_path": "App.xcodeproj/project.pbxproj"}]


def test_signal_appends_pitfall_with_evidence():
    out = merge([], _SIGNAL, _CATALOG)
    assert len(out) == 1
    assert out[0]["id"] == "pf_ios_pbxproj_registration"
    assert any("App.xcodeproj/project.pbxproj" in e for e in out[0]["evidence"])


def test_dedup_by_id_is_idempotent():
    once = merge([], _SIGNAL, _CATALOG)
    twice = merge(once, _SIGNAL, _CATALOG)
    assert len(twice) == 1


def test_no_signal_leaves_pitfalls_unchanged():
    existing = [{"id": "pf_0001", "problem_statement": "x"}]
    assert merge(existing, [], _CATALOG) == existing


def test_unknown_signal_is_ignored():
    out = merge([], [{"signal": "nope"}], _CATALOG)
    assert out == []
