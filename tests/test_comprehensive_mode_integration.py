"""Integration tests for comprehensive depth on the deep-scan pipeline.

Drives the standalone scanner via subprocess (so the CLI flag wiring is
exercised end to end) and the deep-scan-state shell API for depth persistence.
"""
import json
import subprocess
import sys
from pathlib import Path

SCANNER = "archie/standalone/scanner.py"
INTENT = "archie/standalone/intent_layer.py"


def _scan(root, *flags):
    out = subprocess.run(
        [sys.executable, SCANNER, str(root), *flags],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def _readable_paths(scan):
    """Paths the scanner actually read content from (hashed)."""
    return set((scan.get("file_hashes") or {}).keys())


def _make_repo(tmp_path):
    (tmp_path / "app.py").write_text("import os\n")
    (tmp_path / "x.min.js").write_text("var a=1\n")
    (tmp_path / ".archiebulk").write_text("**/*.min.js  generated  bundler\n")
    return tmp_path


def test_default_depth_bans_bulk(tmp_path):
    _make_repo(tmp_path)
    scan = _scan(tmp_path)
    readable = _readable_paths(scan)
    assert "app.py" in readable
    assert "x.min.js" not in readable  # bulk read-ban active in default depth


def test_comprehensive_depth_reads_bulk(tmp_path):
    _make_repo(tmp_path)
    scan = _scan(tmp_path, "--comprehensive")
    readable = _readable_paths(scan)
    assert "app.py" in readable
    assert "x.min.js" in readable  # read-ban lifted in comprehensive depth


def test_ignore_system_universal_both_depths(tmp_path):
    # An ignored file must never be read, regardless of depth.
    (tmp_path / ".archieignore").write_text("secret/\n")
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "s.py").write_text("k = 1\n")
    (tmp_path / "app.py").write_text("b = 2\n")
    for flags in ((), ("--comprehensive",)):
        scan = _scan(tmp_path, *flags)
        readable = _readable_paths(scan)
        tree = {f.get("path") for f in scan.get("file_tree", [])}
        assert "app.py" in readable, flags
        assert "secret/s.py" not in readable, flags
        assert "secret/s.py" not in tree, flags


def test_depth_persists_and_round_trips(tmp_path):
    subprocess.run([sys.executable, INTENT, "deep-scan-state", str(tmp_path), "init"],
                   check=True, capture_output=True)
    subprocess.run(
        [sys.executable, INTENT, "deep-scan-state", str(tmp_path),
         "save-run-context", "--depth", "comprehensive", "--scan-mode", "incremental"],
        check=True, capture_output=True,
    )
    state = json.loads((tmp_path / ".archie" / "deep_scan_state.json").read_text())
    # depth composes with scan_mode (orthogonal axes)
    assert state["run_context"]["depth"] == "comprehensive"
    assert state["run_context"]["scan_mode"] == "incremental"


def test_ignore_matcher_honors_nested_and_glob(tmp_path):
    """Ancestor-dir and glob semantics for full-path callers of is_ignored
    (e.g. a git-log file list, where the file may no longer exist on disk)."""
    import sys
    sys.path.insert(0, "archie/standalone")
    from _common import IgnoreMatcher
    (tmp_path / ".archieignore").write_text("vendor/\n**/generated/\n")
    m = IgnoreMatcher(tmp_path)
    assert not m.is_ignored("src/a.py")
    assert m.is_ignored("vendor/deep/b.py")
    assert m.is_ignored("pkg/generated/x.py")
    assert not m.is_ignored("src/c.py")


def test_report_caps_gate_on_depth(tmp_path):
    """measure_health lifts its report list-caps when run_context.depth
    is comprehensive (read from deep_scan_state.json, no flag needed)."""
    import sys, json
    sys.path.insert(0, "archie/standalone")
    from importlib import import_module
    (tmp_path / ".archie").mkdir()
    state = tmp_path / ".archie" / "deep_scan_state.json"
    m = import_module("measure_health")
    state.write_text(json.dumps({"run_context": {"depth": "comprehensive"}}))
    assert m._is_comprehensive(str(tmp_path)) is True
    state.write_text(json.dumps({"run_context": {"depth": "default"}}))
    assert m._is_comprehensive(str(tmp_path)) is False
