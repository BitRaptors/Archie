"""Tests for archie.standalone.update_check — npm update-check + JUST_UPGRADED.

Loads the standalone module by path. Its config import falls back to the
sibling config.py (the `archie` package import trips on pydantic and is
caught), so no heavy package import is triggered.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
_SPEC = importlib.util.spec_from_file_location(
    "_archie_update_check", _STANDALONE / "update_check.py"
)
_update_check = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_update_check"] = _update_check
_SPEC.loader.exec_module(_update_check)


def test_mark_upgraded_uses_explicit_old_version(tmp_path, monkeypatch):
    """Regression: the installer overwrites ~/.archie/version with the NEW
    version before calling mark-upgraded, so the old version must be passed
    explicitly — otherwise from == to and JUST_UPGRADED reads "X -> X".
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    uc = _update_check

    # Simulate post-install state: the marker already holds the NEW version.
    archie = tmp_path / ".archie"
    archie.mkdir(parents=True)
    (archie / "version").write_text("3.3.0")

    uc.mark_upgraded("3.3.0", "3.2.0")

    payload = json.loads((archie / "just-upgraded.json").read_text())
    assert payload["from"] == "3.2.0"
    assert payload["to"] == "3.3.0"
    assert payload["from"] != payload["to"]


def test_mark_upgraded_fallback_reads_marker(tmp_path, monkeypatch):
    """Backward compat: older installers call mark-upgraded with no old arg —
    fall back to reading the version marker on disk.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    uc = _update_check

    archie = tmp_path / ".archie"
    archie.mkdir(parents=True)
    (archie / "version").write_text("3.1.0")

    uc.mark_upgraded("3.3.0")

    payload = json.loads((archie / "just-upgraded.json").read_text())
    assert payload["from"] == "3.1.0"
    assert payload["to"] == "3.3.0"


def test_semver_newer():
    uc = _update_check
    assert uc._newer("3.3.0", "3.2.0")
    assert uc._newer("3.2.1", "3.2.0")
    assert uc._newer("10.0.0", "9.9.9")
    assert not uc._newer("3.2.0", "3.2.0")
    assert not uc._newer("3.1.0", "3.2.0")


def test_snooze_ladder_escalates_and_caps(tmp_path, monkeypatch):
    """Snooze escalates 24h -> 48h -> 168h and caps at the longest entry."""
    monkeypatch.setenv("HOME", str(tmp_path))
    uc = _update_check

    archie = tmp_path / ".archie"
    archie.mkdir(parents=True)
    # snooze() reads the latest cached version to scope the snooze.
    (archie / "update-check.json").write_text(
        json.dumps({"latest": "9.9.9", "fetched_at": 0})
    )

    assert uc.snooze()["hours"] == 24
    assert uc.snooze()["hours"] == 48
    assert uc.snooze()["hours"] == 168
    assert uc.snooze()["hours"] == 168  # capped at the longest rung


def test_check_emits_just_upgraded_then_consumes_it(tmp_path, monkeypatch):
    """check() surfaces JUST_UPGRADED once with distinct from/to, then the
    marker is consumed so it never repeats. Network is stubbed out.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    uc = _update_check
    monkeypatch.setattr(uc, "_fetch_latest_from_registry", lambda: None)

    archie = tmp_path / ".archie"
    archie.mkdir(parents=True)
    (archie / "version").write_text("3.3.0")
    uc.mark_upgraded("3.3.0", "3.2.0")

    assert uc.check() == "JUST_UPGRADED 3.2.0 3.3.0"
    assert uc.check() == ""  # marker consumed; no cache + stubbed network -> empty


def test_check_silent_when_update_check_disabled(tmp_path, monkeypatch):
    """With update_check disabled, check() is a no-op even with a pending marker."""
    monkeypatch.setenv("HOME", str(tmp_path))
    uc = _update_check

    archie = tmp_path / ".archie"
    archie.mkdir(parents=True)
    (archie / "version").write_text("3.3.0")
    uc.mark_upgraded("3.3.0", "3.2.0")
    uc.disable()

    assert uc.check() == ""
