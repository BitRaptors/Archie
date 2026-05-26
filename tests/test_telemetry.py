"""Tests for archie.standalone.telemetry — per-run timing output.

Imports the standalone module by path to avoid the heavy
`archie/__init__.py` (which pulls in pydantic via engine.scan).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "_archie_telemetry",
    Path(__file__).resolve().parent.parent / "archie" / "standalone" / "telemetry.py",
)
_telemetry = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_telemetry"] = _telemetry
_SPEC.loader.exec_module(_telemetry)


def test_telemetry_writes_file(tmp_path):
    from tests.test_telemetry import _telemetry as telemetry

    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "scan.json").write_text(
        json.dumps({"statistics": {"source_files": 100, "total_loc": 5000, "directories": 42}})
    )

    steps = [
        {"name": "scan", "started_at": "2026-04-17T10:00:00Z", "completed_at": "2026-04-17T10:00:30Z"},
        {"name": "gather", "started_at": "2026-04-17T10:00:30Z", "completed_at": "2026-04-17T10:05:00Z"},
    ]
    telemetry.write_telemetry(str(tmp_path), "scan", steps)

    files = list((archie / "telemetry").glob("scan_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["command"] == "scan"
    assert data["project"]["source_files"] == 100
    assert data["project"]["total_loc"] == 5000
    assert data["project"]["directories"] == 42
    assert len(data["steps"]) == 2
    assert data["steps"][0]["seconds"] == 30
    assert data["steps"][1]["seconds"] == 270
    assert data["total_seconds"] > 0


def test_telemetry_handles_missing_scan_json(tmp_path):
    from tests.test_telemetry import _telemetry as telemetry

    archie = tmp_path / ".archie"
    archie.mkdir()
    # No scan.json
    steps = [{"name": "scan", "started_at": "2026-04-17T10:00:00Z", "completed_at": "2026-04-17T10:00:30Z"}]
    telemetry.write_telemetry(str(tmp_path), "scan", steps)
    files = list((archie / "telemetry").glob("scan_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["project"]["source_files"] == 0  # graceful fallback
    assert data["project"]["total_loc"] == 0
    assert data["project"]["directories"] == 0


def test_telemetry_handles_partial_steps(tmp_path):
    """Steps with missing completed_at should get seconds=0, not crash."""
    from tests.test_telemetry import _telemetry as telemetry

    archie = tmp_path / ".archie"
    archie.mkdir()
    steps = [
        {"name": "scan", "started_at": "2026-04-17T10:00:00Z", "completed_at": "2026-04-17T10:00:30Z"},
        {"name": "gather", "started_at": "2026-04-17T10:00:30Z"},  # no completed_at
    ]
    telemetry.write_telemetry(str(tmp_path), "scan", steps)
    files = list((archie / "telemetry").glob("scan_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert len(data["steps"]) == 2
    assert data["steps"][0]["seconds"] == 30
    assert data["steps"][1]["seconds"] == 0


def test_telemetry_preserves_extra_step_fields(tmp_path):
    """Extra fields like 'model' or 'folders_processed' pass through."""
    from tests.test_telemetry import _telemetry as telemetry

    archie = tmp_path / ".archie"
    archie.mkdir()
    steps = [
        {
            "name": "synthesis",
            "started_at": "2026-04-17T10:00:00Z",
            "completed_at": "2026-04-17T10:01:00Z",
            "model": "opus",
        },
        {
            "name": "intent_layer",
            "started_at": "2026-04-17T10:01:00Z",
            "completed_at": "2026-04-17T10:02:00Z",
            "folders_processed": 15,
        },
    ]
    telemetry.write_telemetry(str(tmp_path), "deep-scan", steps)
    files = list((archie / "telemetry").glob("deep-scan_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["steps"][0]["model"] == "opus"
    assert data["steps"][1]["folders_processed"] == 15


def test_telemetry_started_completed_at_from_steps(tmp_path):
    """Top-level started_at / completed_at derived from first/last step."""
    from tests.test_telemetry import _telemetry as telemetry

    archie = tmp_path / ".archie"
    archie.mkdir()
    steps = [
        {"name": "scan", "started_at": "2026-04-17T10:00:00Z", "completed_at": "2026-04-17T10:00:30Z"},
        {"name": "render", "started_at": "2026-04-17T10:00:30Z", "completed_at": "2026-04-17T10:05:00Z"},
    ]
    telemetry.write_telemetry(str(tmp_path), "scan", steps)
    files = list((archie / "telemetry").glob("scan_*.json"))
    data = json.loads(files[0].read_text())
    assert data["started_at"] == "2026-04-17T10:00:00Z"
    assert data["completed_at"] == "2026-04-17T10:05:00Z"
    assert data["total_seconds"] == 300


def test_telemetry_empty_steps(tmp_path):
    """Empty steps list should not crash."""
    from tests.test_telemetry import _telemetry as telemetry

    archie = tmp_path / ".archie"
    archie.mkdir()
    telemetry.write_telemetry(str(tmp_path), "scan", [])
    files = list((archie / "telemetry").glob("scan_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["steps"] == []
    assert data["total_seconds"] == 0


def test_legacy_write_fires_telemetry_sync(tmp_path, monkeypatch):
    """Regression: legacy --command/--timing-file path still works for telemetry uploads.
    It must fire the anonymous-telemetry upload, not just write the local file —
    otherwise runs taking this path are never reported.
    """
    from tests.test_telemetry import _telemetry as telemetry

    calls = []
    monkeypatch.setattr(
        telemetry, "_fire_telemetry_sync", lambda root, out: calls.append((root, out))
    )

    (tmp_path / ".archie").mkdir()
    timing = tmp_path / "timing.json"
    timing.write_text(
        json.dumps(
            [{"name": "scan", "started_at": "2026-04-17T10:00:00Z", "completed_at": "2026-04-17T10:00:30Z"}]
        )
    )
    telemetry._legacy_write([str(tmp_path), "--command", "scan", "--timing-file", str(timing)])

    assert len(calls) == 1, "_legacy_write must fire the telemetry sync exactly once"
    root, out = calls[0]
    assert Path(root) == tmp_path.resolve()
    assert out.name.startswith("scan_") and out.exists()


def test_write_from_disk_fires_telemetry_sync(tmp_path, monkeypatch):
    """Regression: the deep-scan disk-persisted writer fires the upload too,
    so both telemetry code paths stay consistent.
    """
    from tests.test_telemetry import _telemetry as telemetry

    calls = []
    monkeypatch.setattr(
        telemetry, "_fire_telemetry_sync", lambda root, out: calls.append((root, out))
    )

    telem_dir = tmp_path / ".archie" / "telemetry"
    telem_dir.mkdir(parents=True)
    (telem_dir / "_current_run.json").write_text(
        json.dumps(
            {
                "command": "deep-scan",
                "steps": [
                    {"name": "scan", "started_at": "2026-04-17T10:00:00Z", "completed_at": "2026-04-17T10:00:30Z"}
                ],
            }
        )
    )
    out = telemetry.write_from_disk(tmp_path)

    assert out is not None
    assert len(calls) == 1, "write_from_disk must fire the telemetry sync exactly once"
    assert calls[0][1] == out
