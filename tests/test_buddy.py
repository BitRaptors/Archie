"""Tests for archie buddy."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

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
