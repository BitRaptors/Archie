"""Tests for archie buddy."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import buddy


def _make_archie_dir(tmp: Path, *, blueprint: bool = True, scan_age_hours: float = 0,
                     violations: int = 0) -> Path:
    """Create a minimal .archie/ directory for testing."""
    archie = tmp / ".archie"
    archie.mkdir(exist_ok=True)
    if blueprint:
        (archie / "blueprint.json").write_text(json.dumps({"meta": {"version": 1}}))
    if scan_age_hours >= 0:
        report = archie / "scan_report.md"
        report.write_text(f"# Scan Report\nViolations found: {violations}\n")
        # Backdate the file modification time
        age_seconds = scan_age_hours * 3600
        mtime = time.time() - age_seconds
        import os
        os.utime(report, (mtime, mtime))
    return tmp


def test_hp_full_health():
    """Blueprint exists, fresh scan, 0 violations → 100 HP."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=0, violations=0)
        hp, _ = buddy.calculate_hp(tmp_path)
        assert hp == 100


def test_hp_no_blueprint():
    """No blueprint → 0 HP, unborn mood."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=False, scan_age_hours=-1, violations=0)
        hp, mood = buddy.calculate_hp(tmp_path)
        assert hp == 0
        assert mood == "unborn"


def test_hp_stale_scan():
    """Blueprint exists, scan 8 days old, 0 violations → 60 HP."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=8*24, violations=0)
        hp, _ = buddy.calculate_hp(tmp_path)
        assert hp == 60  # 30 (blueprint) + 0 (stale scan) + 30 (0 violations)


def test_hp_many_violations():
    """Blueprint, fresh scan, 25 violations → 70 HP."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=0, violations=25)
        hp, _ = buddy.calculate_hp(tmp_path)
        assert hp == 70  # 30 (blueprint) + 40 (fresh) + 0 (>20 violations)


def test_hp_medium_state():
    """Blueprint, 2-day scan, 5 violations → moderate HP."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=48, violations=5)
        hp, _ = buddy.calculate_hp(tmp_path)
        assert hp == 75  # 30 (blueprint) + 30 (1-3 day bucket, <72h) + 15 (4-7 violations)


def test_mood_confident():
    assert buddy.mood_from_hp(95) == "confident"
    assert buddy.mood_from_hp(80) == "confident"

def test_mood_skeptical():
    assert buddy.mood_from_hp(79) == "skeptical"
    assert buddy.mood_from_hp(50) == "skeptical"

def test_mood_sick():
    assert buddy.mood_from_hp(49) == "sick"
    assert buddy.mood_from_hp(20) == "sick"

def test_mood_dead():
    assert buddy.mood_from_hp(19) == "dead"
    assert buddy.mood_from_hp(0) == "dead"

def test_get_message_returns_string():
    """Each mood should produce a non-empty string message."""
    for mood in ("confident", "skeptical", "sick", "dead", "unborn"):
        msg = buddy.get_message(mood)
        assert isinstance(msg, str)
        assert len(msg) > 0

def test_eyes_for_mood():
    assert buddy.eyes_for_mood("confident") == ("◕", "◕")
    assert buddy.eyes_for_mood("skeptical") == ("¬", "¬")
    assert buddy.eyes_for_mood("sick") == ("◔", "◔")
    assert buddy.eyes_for_mood("dead") == ("×", "×")
    assert buddy.eyes_for_mood("unborn") == ("·", "·")


def test_render_full_contains_ghost():
    """Full render should contain the ghost body characters."""
    output = buddy.render_full(hp=75, mood="skeptical", violations=5,
                               scan_age_text="2 napja", streak=3)
    assert "▄███████▄" in output
    assert "▀█▄▀" in output
    assert "¬" in output  # skeptical eyes
    assert "HP:" in output
    assert "75" in output


def test_render_compact_one_block():
    """Compact render should be shorter than full render."""
    full = buddy.render_full(hp=90, mood="confident", violations=0,
                             scan_age_text="ma", streak=1)
    compact = buddy.render_compact(hp=90, mood="confident")
    assert len(compact) < len(full)
    assert "▄███████▄" in compact
    assert "◕" in compact


def test_render_full_unborn():
    """Unborn render shows special message, no HP bar."""
    output = buddy.render_full(hp=0, mood="unborn", violations=0,
                               scan_age_text="soha", streak=0)
    assert "·" in output  # unborn eyes


def test_load_state_missing_file():
    """Missing buddy.json returns default state."""
    with tempfile.TemporaryDirectory() as tmp:
        state = buddy.load_state(Path(tmp) / ".archie")
        assert state["streak"] == 0
        assert state["total_scans"] == 0
        assert state["best_hp"] == 0
        assert state["achievements"] == []


def test_save_and_load_state():
    """State round-trips through JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        archie = Path(tmp) / ".archie"
        archie.mkdir()
        state = buddy.default_state()
        state["streak"] = 5
        state["best_hp"] = 90
        buddy.save_state(archie, state)

        loaded = buddy.load_state(archie)
        assert loaded["streak"] == 5
        assert loaded["best_hp"] == 90


def test_update_state_tracks_best_hp():
    """update_state should record new best HP."""
    state = buddy.default_state()
    state["best_hp"] = 50
    updated = buddy.update_state(state, hp=80)
    assert updated["best_hp"] == 80


def test_update_state_keeps_best_hp():
    """update_state should not lower best HP."""
    state = buddy.default_state()
    state["best_hp"] = 95
    updated = buddy.update_state(state, hp=60)
    assert updated["best_hp"] == 95


def test_achievement_first_scan():
    """First interaction unlocks first_scan achievement."""
    state = buddy.default_state()
    updated = buddy.update_state(state, hp=50)
    assert "first_scan" in updated["achievements"]


def test_achievement_comeback():
    """HP jumping from <20 to >=80 unlocks comeback."""
    state = buddy.default_state()
    state["last_hp"] = 15
    updated = buddy.update_state(state, hp=85)
    assert "comeback" in updated["achievements"]


def test_cli_full_view():
    """Running buddy.py on a project with .archie/ produces full ASCII output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=0, violations=2)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "archie" / "standalone" / "buddy.py"), str(tmp_path)],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "▄███████▄" in result.stdout
        assert "HP:" in result.stdout
        assert "Mood:" in result.stdout


def test_cli_compact_view():
    """Running buddy.py --compact produces shorter output without Mood: line."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=0, violations=0)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "archie" / "standalone" / "buddy.py"), str(tmp_path), "--compact"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "▄███████▄" in result.stdout
        assert "Mood:" not in result.stdout


def test_cli_no_archie_dir():
    """Running on a project with no .archie/ still returns 0 and shows unborn."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "archie" / "standalone" / "buddy.py"), tmp],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "·" in result.stdout  # unborn eyes
