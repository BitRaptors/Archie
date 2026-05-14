"""Tests for archie.standalone.telemetry_sync — endpoint resolution.

Loaded by path (its config import falls back to the sibling config.py, so no
pydantic / package import is triggered). These tests cover the
ARCHIE_TELEMETRY_ENDPOINT override that keeps test runs off production.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "_archie_telemetry_sync",
    Path(__file__).resolve().parent.parent / "archie" / "standalone" / "telemetry_sync.py",
)
_telemetry_sync = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_telemetry_sync"] = _telemetry_sync
_SPEC.loader.exec_module(_telemetry_sync)


def test_endpoint_defaults_to_production(monkeypatch):
    """With no override, _endpoint() returns the hardcoded production URL."""
    monkeypatch.delenv("ARCHIE_TELEMETRY_ENDPOINT", raising=False)
    ts = _telemetry_sync
    assert ts._endpoint() == ts.ENDPOINT_URL
    assert ts._endpoint().startswith("https://")


def test_endpoint_env_override_respected(monkeypatch):
    """ARCHIE_TELEMETRY_ENDPOINT redirects uploads — this is what keeps a test
    run (or a verification script) from ever POSTing to production."""
    ts = _telemetry_sync
    monkeypatch.setenv("ARCHIE_TELEMETRY_ENDPOINT", "http://localhost:9999/stub")
    assert ts._endpoint() == "http://localhost:9999/stub"


def test_status_reports_resolved_endpoint(tmp_path, monkeypatch):
    """status() surfaces the override so an operator can confirm where events go."""
    ts = _telemetry_sync
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARCHIE_TELEMETRY_ENDPOINT", "http://localhost:9999/stub")
    assert ts.status()["endpoint"] == "http://localhost:9999/stub"
