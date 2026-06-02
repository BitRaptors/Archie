"""Tests for deep-scan-state test-snapshots + --from ledger warnings.

Covers the general checkpoint/restore primitive (snapshot -> mutate -> restore
round-trip, including post-snapshot additions being undone and gitignored
outside files captured) and the check-prereqs ledger/stale-input warnings.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import intent_layer  # noqa: E402


def _setup(tmp_path: Path, *, started_at: str = "2020-01-01T00:00:00+00:00",
           last_completed: int = 2) -> Path:
    a = tmp_path / ".archie"
    (a / "tmp").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (a / "findings.json").write_text(json.dumps(
        {"findings": [{"id": "f_0001", "confirmed_in_scan": 1}]}))
    (a / "deep_scan_state.json").write_text(json.dumps({
        "completed_steps": list(range(1, last_completed + 1)),
        "last_completed": last_completed, "status": "in_progress",
        "started_at": started_at,
    }))
    (a / "blueprint.json").write_text('{"meta":{}}')
    (tmp_path / ".claude" / "hooks" / "pre.sh").write_text("hook-v1\n")
    return tmp_path


def test_snapshot_restore_round_trip(tmp_path):
    root = _setup(tmp_path)
    a = root / ".archie"

    intent_layer.cmd_deep_scan_state(root, "snapshot", None, label="t1")
    assert (a / ".test_snapshots" / "t1" / "manifest.json").exists()

    # Mutate: corrupt the compounding store, add a post-snapshot tmp file,
    # change a captured outside (gitignored) file.
    (a / "findings.json").write_text(json.dumps(
        {"findings": [{"id": "f_0001", "confirmed_in_scan": 7}, {"id": "f_0002"}]}))
    (a / "tmp" / "leftover.json").write_text("junk")
    (root / ".claude" / "hooks" / "pre.sh").write_text("hook-v2\n")

    intent_layer.cmd_deep_scan_state(root, "restore", None, label="t1")

    findings = json.loads((a / "findings.json").read_text())["findings"]
    assert len(findings) == 1 and findings[0]["confirmed_in_scan"] == 1
    assert not (a / "tmp" / "leftover.json").exists()  # post-snapshot add undone
    assert (root / ".claude" / "hooks" / "pre.sh").read_text() == "hook-v1\n"


def test_snapshot_dir_excluded_from_itself(tmp_path):
    # The snapshot dir must never be captured into a snapshot (no recursion).
    root = _setup(tmp_path)
    intent_layer.cmd_deep_scan_state(root, "snapshot", None, label="a")
    intent_layer.cmd_deep_scan_state(root, "snapshot", None, label="b")
    assert not (root / ".archie" / ".test_snapshots" / "b" / "archie" / ".test_snapshots").exists()


def test_list_snapshots(tmp_path, capsys):
    root = _setup(tmp_path)
    intent_layer.cmd_deep_scan_state(root, "snapshot", None, label="alpha")
    capsys.readouterr()
    intent_layer.cmd_deep_scan_state(root, "list-snapshots")
    out = json.loads(capsys.readouterr().out)
    labels = [s["label"] for s in out["snapshots"]]
    assert "alpha" in labels


def test_invalid_label_rejected(tmp_path):
    root = _setup(tmp_path)
    for bad in ["../escape", "a/b", "..", ""]:
        with pytest.raises(SystemExit):
            intent_layer.cmd_deep_scan_state(root, "snapshot", None, label=bad)


def test_restore_missing_snapshot_errors(tmp_path):
    root = _setup(tmp_path)
    with pytest.raises(SystemExit):
        intent_layer.cmd_deep_scan_state(root, "restore", None, label="nope")


def test_check_prereqs_ledger_gap_warning(tmp_path, capsys):
    # last_completed=2, but --from 5 → steps 3-4 never completed: warn, don't block.
    root = _setup(tmp_path, last_completed=2)
    (root / ".archie" / "blueprint_raw.json").write_text("{}")  # step 5 prereq exists
    intent_layer.cmd_deep_scan_state(root, "check-prereqs", 5)
    cap = capsys.readouterr()
    assert json.loads(cap.out)["ok"] is True          # not blocked
    assert "last_completed=2" in cap.err
    assert "never completed" in cap.err


def test_check_prereqs_no_warning_when_contiguous(tmp_path, capsys):
    root = _setup(tmp_path, last_completed=4)
    (root / ".archie" / "blueprint_raw.json").write_text("{}")
    intent_layer.cmd_deep_scan_state(root, "check-prereqs", 5)
    cap = capsys.readouterr()
    assert "never completed" not in cap.err           # 4 == 5-1, no gap


def test_check_prereqs_stale_input_warning(tmp_path, capsys):
    # Prereq artifact older than the run's started_at → stale-input warning.
    root = _setup(tmp_path, started_at=datetime.now(timezone.utc).isoformat(),
                  last_completed=4)
    raw = root / ".archie" / "blueprint_raw.json"
    raw.write_text("{}")
    os.utime(raw, (0, 0))  # 1970 — well before started_at
    intent_layer.cmd_deep_scan_state(root, "check-prereqs", 5)
    cap = capsys.readouterr()
    assert "stale input" in cap.err
    assert "blueprint_raw.json" in cap.err
