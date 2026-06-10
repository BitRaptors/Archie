# tests/test_platform_pitfall_signal.py
"""Tests for archie/standalone/scanner.py::detect_platform_pitfall_signals.

Loaded by path (scanner.py is pure stdlib, not a package import).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "_archie_scanner",
    Path(__file__).resolve().parent.parent / "archie" / "standalone" / "scanner.py",
)
_scanner = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_scanner"] = _scanner
_SPEC.loader.exec_module(_scanner)

detect = _scanner.detect_platform_pitfall_signals

_LEGACY_PBX = "// !$*UTF8*$!\n{ objects = { 54BC /* X.swift in Sources */ = {isa = PBXBuildFile;}; }; }\n"
_SYNC_PBX = _LEGACY_PBX + "\n7A0 = {isa = PBXFileSystemSynchronizedRootGroup;};\n"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_legacy_xcode_emits_signal(tmp_path):
    _write(tmp_path / "App.xcodeproj" / "project.pbxproj", _LEGACY_PBX)
    signals = detect(tmp_path)
    assert signals == [{
        "signal": "ios_legacy_xcode_no_folder_sync",
        "evidence_path": "App.xcodeproj/project.pbxproj",
    }]


def test_folder_synchronized_xcode_emits_nothing(tmp_path):
    _write(tmp_path / "App.xcodeproj" / "project.pbxproj", _SYNC_PBX)
    assert detect(tmp_path) == []


def test_spm_only_emits_nothing(tmp_path):
    _write(tmp_path / "Package.swift", "// swift-tools-version:5.9\n")
    _write(tmp_path / "Sources" / "App" / "main.swift", "print(1)\n")
    assert detect(tmp_path) == []


def test_run_scan_includes_platform_pitfall_signals_key(tmp_path):
    _write(tmp_path / "App.xcodeproj" / "project.pbxproj", _LEGACY_PBX)
    scan = _scanner.run_scan(str(tmp_path))
    assert scan["platform_pitfall_signals"] == [{
        "signal": "ios_legacy_xcode_no_folder_sync",
        "evidence_path": "App.xcodeproj/project.pbxproj",
    }]
