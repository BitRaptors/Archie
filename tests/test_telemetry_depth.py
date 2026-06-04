"""Telemetry records deep-scan depth under `meta` (command-specific extras),
so runs can be compared (default vs comprehensive) without a sparse column."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "archie/standalone")
import telemetry_sync


def _event(run_extra):
    run = {"command": "deep-scan", "cli": "claude", "total_seconds": 100,
           "steps": [{"step": 1, "key": "scan", "name": "Scanner", "seconds": 100}]}
    run.update(run_extra)
    return telemetry_sync._build_event(Path(tempfile.mkdtemp()), run, source="test")


def test_meta_depth_comprehensive_forwarded():
    assert _event({"meta": {"depth": "comprehensive"}})["meta"] == {"depth": "comprehensive"}

def test_meta_depth_default_forwarded():
    assert _event({"meta": {"depth": "default"}})["meta"] == {"depth": "default"}

def test_meta_absent_is_none():
    assert _event({})["meta"] is None

def test_meta_non_dict_is_none():
    assert _event({"meta": "garbage"})["meta"] is None
