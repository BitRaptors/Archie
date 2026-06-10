# tests/test_finalize_platform_pitfall.py
"""finalize() seeds the iOS pbxproj pitfall from scan.json signals (no AI needed)."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "_archie_finalize_int", _ROOT / "archie" / "standalone" / "finalize.py",
)
_finalize = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_finalize_int"] = _finalize
_SPEC.loader.exec_module(_finalize)


def _setup(tmp_path, signals):
    archie = tmp_path / ".archie"
    archie.mkdir(parents=True)
    (archie / "blueprint_raw.json").write_text(json.dumps({"pitfalls": []}))
    (archie / "scan.json").write_text(json.dumps({"platform_pitfall_signals": signals}))
    shutil.copyfile(
        _ROOT / "archie" / "standalone" / "platform_pitfalls.json",
        archie / "platform_pitfalls.json",
    )
    return archie


def test_finalize_seeds_pitfall_when_signal_present(tmp_path):
    archie = _setup(tmp_path, [{"signal": "ios_legacy_xcode_no_folder_sync",
                                "evidence_path": "App.xcodeproj/project.pbxproj"}])
    _finalize.finalize(tmp_path, agent_files=None)
    bp = json.loads((archie / "blueprint.json").read_text())
    ids = [p.get("id") for p in bp.get("pitfalls", [])]
    assert "pf_ios_pbxproj_registration" in ids


def test_finalize_no_signal_no_seed(tmp_path):
    archie = _setup(tmp_path, [])
    _finalize.finalize(tmp_path, agent_files=None)
    bp = json.loads((archie / "blueprint.json").read_text())
    assert bp.get("pitfalls", []) == []
