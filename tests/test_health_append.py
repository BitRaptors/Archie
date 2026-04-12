"""Tests for --append-history flag in measure_health.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

MEASURE_HEALTH = str(Path(__file__).resolve().parent.parent / "archie" / "standalone" / "measure_health.py")

SAMPLE_HEALTH = {
    "erosion": 0.12,
    "gini": 0.45,
    "top20_share": 0.67,
    "verbosity": 0.03,
    "total_loc": 5000,
    "total_functions": 100,
    "high_cc_functions": 5,
    "duplicate_lines": 150,
}


def _run(repo: Path, extra_args: list[str] | None = None):
    """Run measure_health.py with --append-history on the given repo dir."""
    args = [sys.executable, MEASURE_HEALTH, str(repo), "--append-history"]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(args, capture_output=True, text=True)


def test_creates_history_entry(tmp_path: Path):
    """Creates health_history.json with one entry from health.json."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "health.json").write_text(json.dumps(SAMPLE_HEALTH))

    result = _run(tmp_path)

    assert result.returncode == 0
    history = json.loads((archie / "health_history.json").read_text())
    assert isinstance(history, list)
    assert len(history) == 1
    entry = history[0]
    assert entry["erosion"] == 0.12
    assert entry["gini"] == 0.45
    assert entry["top20_share"] == 0.67
    assert entry["verbosity"] == 0.03
    assert entry["total_loc"] == 5000
    assert entry["scan_type"] == "deep"
    assert "timestamp" in entry

    # stdout should be valid JSON
    stdout_entry = json.loads(result.stdout)
    assert stdout_entry["erosion"] == 0.12


def test_appends_to_existing_history(tmp_path: Path):
    """Appends to existing history without replacing previous entries."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "health.json").write_text(json.dumps(SAMPLE_HEALTH))

    existing = [{"timestamp": "2025-01-01T00:00:00+00:00", "erosion": 0.5, "gini": 0.3,
                 "top20_share": 0.6, "verbosity": 0.01, "total_loc": 3000, "scan_type": "fast"}]
    (archie / "health_history.json").write_text(json.dumps(existing))

    result = _run(tmp_path, ["--scan-type", "fast"])

    assert result.returncode == 0
    history = json.loads((archie / "health_history.json").read_text())
    assert len(history) == 2
    assert history[0]["erosion"] == 0.5  # old entry preserved
    assert history[1]["erosion"] == 0.12  # new entry appended
    assert history[1]["scan_type"] == "fast"


def test_handles_dict_format(tmp_path: Path):
    """Handles {"history": [...]} dict format and writes back as plain list."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "health.json").write_text(json.dumps(SAMPLE_HEALTH))

    dict_format = {"history": [
        {"timestamp": "2025-01-01T00:00:00+00:00", "erosion": 0.3, "gini": 0.2,
         "top20_share": 0.5, "verbosity": 0.02, "total_loc": 2000, "scan_type": "deep"}
    ]}
    (archie / "health_history.json").write_text(json.dumps(dict_format))

    result = _run(tmp_path)

    assert result.returncode == 0
    history = json.loads((archie / "health_history.json").read_text())
    assert isinstance(history, list)  # written back as plain list
    assert len(history) == 2
    assert history[0]["erosion"] == 0.3


def test_fails_if_health_json_missing(tmp_path: Path):
    """Exits with error if health.json doesn't exist."""
    archie = tmp_path / ".archie"
    archie.mkdir()

    result = _run(tmp_path)

    assert result.returncode == 1
    assert "not found" in result.stderr.lower()
