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
