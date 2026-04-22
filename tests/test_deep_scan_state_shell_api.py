"""Tests for the shell-friendly save-run-context action + inspect --list.

These close the gap where the deep-scan Resume Prelude used inline
`python3 -c` blocks to parse deep_scan_state.json. The prelude now uses
`intent_layer.py inspect --query` (nested keys, plus `--list` for arrays)
and `intent_layer.py deep-scan-state save-run-context` (flags + stdin for
workspaces).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"


def _run(*args: str, stdin: str = "", cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run intent_layer.py as a subprocess — exercises the real CLI layout."""
    cmd = [sys.executable, str(_STANDALONE / "intent_layer.py"), *args]
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def _seed(tmp_path: Path) -> None:
    (tmp_path / ".archie").mkdir(parents=True, exist_ok=True)
    _run("deep-scan-state", str(tmp_path), "init")


# ---------------------------------------------------------------------------
# inspect --query nested + --list
# ---------------------------------------------------------------------------


def test_inspect_nested_query_on_saved_run_context(tmp_path):
    _seed(tmp_path)
    _run(
        "deep-scan-state", str(tmp_path), "save-run-context",
        "--scope", "whole",
        "--intent-layer", "yes",
        "--scan-mode", "full",
        "--project-root", str(tmp_path),
        "--monorepo-type", "pnpm",
        "--start-step", "1",
        "--workspaces-from-stdin",
        stdin="apps/web\napps/api\n",
    )

    r = _run(
        "inspect", str(tmp_path), "deep_scan_state.json",
        "--query", ".run_context.scope",
    )
    assert r.returncode == 0
    assert r.stdout.strip() == "whole"


def test_inspect_missing_key_prints_null(tmp_path):
    _seed(tmp_path)
    r = _run(
        "inspect", str(tmp_path), "deep_scan_state.json",
        "--query", ".run_context.scope",
    )
    assert r.stdout.strip() == "null"


def test_inspect_list_prints_each_element_on_own_line(tmp_path):
    _seed(tmp_path)
    _run(
        "deep-scan-state", str(tmp_path), "save-run-context",
        "--project-root", str(tmp_path),
        "--workspaces-from-stdin",
        stdin="apps/web\napps/api\npackages/core\n",
    )
    r = _run(
        "inspect", str(tmp_path), "deep_scan_state.json",
        "--query", ".run_context.workspaces",
        "--list",
    )
    assert r.returncode == 0
    assert r.stdout.splitlines() == ["apps/web", "apps/api", "packages/core"]


def test_inspect_list_on_missing_key_prints_null(tmp_path):
    _seed(tmp_path)
    r = _run(
        "inspect", str(tmp_path), "deep_scan_state.json",
        "--query", ".run_context.workspaces",
        "--list",
    )
    assert r.stdout.strip() == "null"


# ---------------------------------------------------------------------------
# save-run-context (the flag-based API that replaces inline python JSON building)
# ---------------------------------------------------------------------------


def test_save_run_context_persists_all_fields(tmp_path):
    _seed(tmp_path)
    _run(
        "deep-scan-state", str(tmp_path), "save-run-context",
        "--scope", "hybrid",
        "--intent-layer", "no",
        "--scan-mode", "incremental",
        "--project-root", str(tmp_path),
        "--monorepo-type", "turborepo",
        "--start-step", "3",
        "--workspaces-from-stdin",
        stdin="a/b\nc/d\n",
    )
    state = json.loads((tmp_path / ".archie" / "deep_scan_state.json").read_text())
    rc = state.get("run_context") or {}
    assert rc["scope"] == "hybrid"
    assert rc["intent_layer"] == "no"
    assert rc["scan_mode"] == "incremental"
    assert rc["project_root"] == str(tmp_path)
    assert rc["monorepo_type"] == "turborepo"
    assert rc["start_step"] == 3
    assert rc["workspaces"] == ["a/b", "c/d"]


def test_save_run_context_workspaces_skip_empty_lines(tmp_path):
    """Newline-separated stdin with blank lines → list with blanks dropped."""
    _seed(tmp_path)
    _run(
        "deep-scan-state", str(tmp_path), "save-run-context",
        "--project-root", str(tmp_path),
        "--workspaces-from-stdin",
        stdin="apps/web\n\napps/api\n   \npackages/core\n",
    )
    state = json.loads((tmp_path / ".archie" / "deep_scan_state.json").read_text())
    assert state["run_context"]["workspaces"] == ["apps/web", "apps/api", "packages/core"]


def test_save_run_context_partial_flags_merge_with_existing(tmp_path):
    _seed(tmp_path)
    # First save: full set
    _run(
        "deep-scan-state", str(tmp_path), "save-run-context",
        "--scope", "whole", "--intent-layer", "yes",
        "--project-root", str(tmp_path),
    )
    # Second save: only update scan_mode — other fields must remain
    _run(
        "deep-scan-state", str(tmp_path), "save-run-context",
        "--scan-mode", "incremental",
    )
    state = json.loads((tmp_path / ".archie" / "deep_scan_state.json").read_text())
    rc = state["run_context"]
    assert rc["scope"] == "whole"
    assert rc["intent_layer"] == "yes"
    assert rc["scan_mode"] == "incremental"


def test_save_run_context_without_stdin_does_not_overwrite_workspaces(tmp_path):
    _seed(tmp_path)
    _run(
        "deep-scan-state", str(tmp_path), "save-run-context",
        "--project-root", str(tmp_path),
        "--workspaces-from-stdin",
        stdin="apps/web\n",
    )
    _run(
        "deep-scan-state", str(tmp_path), "save-run-context",
        "--scope", "whole",
        # no --workspaces-from-stdin
    )
    state = json.loads((tmp_path / ".archie" / "deep_scan_state.json").read_text())
    assert state["run_context"]["workspaces"] == ["apps/web"]


# ---------------------------------------------------------------------------
# telemetry steps-count
# ---------------------------------------------------------------------------


_TELEMETRY = _STANDALONE / "telemetry.py"


def _run_telemetry(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_TELEMETRY), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def test_telemetry_steps_count_empty_is_zero(tmp_path):
    (tmp_path / ".archie").mkdir()
    r = _run_telemetry("steps-count", str(tmp_path))
    assert r.returncode == 0
    assert r.stdout.strip() == "0"


def test_telemetry_steps_count_after_mark(tmp_path):
    (tmp_path / ".archie").mkdir()
    _run_telemetry("mark", str(tmp_path), "deep-scan", "step_one")
    _run_telemetry("mark", str(tmp_path), "deep-scan", "step_two")
    r = _run_telemetry("steps-count", str(tmp_path))
    assert r.stdout.strip() == "2"
