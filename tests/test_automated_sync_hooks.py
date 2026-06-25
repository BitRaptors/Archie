"""Integration tests for the automated-sync hooks (churn-track + stop nudge)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_STANDALONE = _REPO / "archie" / "standalone"
_HOOKS = _REPO / "archie" / "assets" / "hook_scripts"

# Insert the repo root on sys.path so `archie.*` submodule imports work without
# loading archie/__init__.py (which pulls in archie.engine, which needs tomllib,
# only available on Python 3.11+). We pre-register a stub `archie` package so
# relative imports inside manifest_data.py and connectors/codex.py resolve
# correctly while skipping the heavy engine initialisation in __init__.py.
sys.path.insert(0, str(_REPO))
if "archie" not in sys.modules:
    _pkg = types.ModuleType("archie")
    _pkg.__path__ = [str(_REPO / "archie")]  # type: ignore[attr-defined]
    sys.modules["archie"] = _pkg


def _project(tmp_path: Path) -> Path:
    """A minimal installed-project layout: .archie/ with sync.py + blueprint.json."""
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    archie = tmp_path / ".archie"
    archie.mkdir()
    shutil.copy(_STANDALONE / "sync.py", archie / "sync.py")
    (archie / "blueprint.json").write_text("{}")
    return tmp_path


def test_churn_track_hook_updates_counter(tmp_path):
    root = _project(tmp_path)
    envelope = json.dumps({"tool_name": "apply_patch",
                           "tool_input": {"path": "x.ts", "new_string": "a\nb\n"}})
    subprocess.run(["bash", str(_HOOKS / "churn-track.sh")],
                   input=envelope, text=True, cwd=str(root), check=True)
    churn = json.loads((root / ".archie" / "tmp" / "churn.json").read_text())
    assert churn["files"] == ["x.ts"] and churn["edits"] == 1


def test_churn_track_registered_for_both_clis():
    from archie.manifest_data import HOOKS
    entry = [h for h in HOOKS
             if h.script_path.endswith("churn-track.sh")]
    assert len(entry) == 1
    h = entry[0]
    assert h.event == "post-tool-use" and h.tool_match == "Edit|Write|MultiEdit"
    assert h.blocking is False
    # Codex maps the Edit/Write matcher to apply_patch — verify the mapping exists.
    from archie.connectors.codex import _MATCHER_NAME_CODEX
    assert _MATCHER_NAME_CODEX["Edit|Write|MultiEdit"] == "^apply_patch$"


def _run_stop(root: Path, stdin: str = ""):
    return subprocess.run(["bash", str(_HOOKS / "stop.sh")],
                          input=stdin, text=True, capture_output=True, cwd=str(root))


def test_stop_nudges_when_churn_crossed(tmp_path):
    root = _project(tmp_path)
    (root / ".archie" / "config.json").write_text(json.dumps({"churn_threshold_files": 1}))
    tmp = root / ".archie" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "churn.json").write_text(json.dumps({"files": ["a.ts"], "edits": 1, "lines": 5}))
    result = _run_stop(root)
    assert result.returncode == 2
    assert "/archie-sync" in result.stderr


def test_stop_silent_when_nothing_pending(tmp_path):
    root = _project(tmp_path)
    result = _run_stop(root)
    assert result.returncode == 0 and result.stderr.strip() == ""


def test_stop_loop_guard_when_already_continuing(tmp_path):
    """Even with churn crossed, a Stop event carrying stop_hook_active=true must
    NOT re-nudge. Without this guard the exit-2 nudge re-fires on every stop
    attempt until a sync resets churn — an indefinite loop that also defeats the
    'Decline if nothing is worth recording' affordance."""
    root = _project(tmp_path)
    (root / ".archie" / "config.json").write_text(json.dumps({"churn_threshold_files": 1}))
    tmp = root / ".archie" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "churn.json").write_text(json.dumps({"files": ["a.ts"], "edits": 1, "lines": 5}))
    result = _run_stop(root, stdin=json.dumps({"stop_hook_active": True}))
    assert result.returncode == 0
    assert "/archie-sync" not in result.stderr


def test_skill_references_durable_signals():
    skill = (_REPO / "archie" / "assets" / "workflow" / "sync" / "SKILL.md").read_text()
    # Phase 1 must read the captured plans and churn, and consume them on success.
    assert "plan-list" in skill
    assert "churn-status" in skill
    assert "plan-consume" in skill
    assert "churn-reset" in skill
