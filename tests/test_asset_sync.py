"""The npm-package mirror must stay byte-identical with canonical sources.

scripts/verify_sync.py does the full-tree check (missing copies, orphan
assets, dead archie.mjs references) but used to be a manual pre-commit step —
a desync could land whenever the committer skipped it, and the wiring tests'
hardcoded spot-check can't catch orphans that exist in only one tree.
Running it under pytest makes the suite itself the gate.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_verify_sync_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_sync.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _load_verify_sync():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "verify_sync", ROOT / "scripts" / "verify_sync.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hook_scripts_mirror_covers_subtree_and_ignores_cruft(tmp_path, monkeypatch):
    """check_hook_scripts_mirror must (a) recurse into subdirs — the npx installer
    ships the whole subtree — and (b) ignore OS cruft like .DS_Store."""
    vs = _load_verify_sync()
    backend = tmp_path / "be" / "hook_scripts"
    mirror = tmp_path / "mi" / "hook_scripts"
    (backend / "sub").mkdir(parents=True)
    mirror.mkdir(parents=True)
    (backend / "a.sh").write_text("x")
    (mirror / "a.sh").write_text("x")
    (backend / "sub" / "nested.sh").write_text("n")   # nested, backend-only
    (backend / ".DS_Store").write_text("junk")         # cruft — must be ignored
    monkeypatch.setattr(vs, "ARCHIE_ASSETS", tmp_path / "be")
    monkeypatch.setattr(vs, "ASSETS", tmp_path / "mi")
    errors = []
    vs.check_hook_scripts_mirror(errors)
    assert any("sub/nested.sh" in e for e in errors)   # rglob covers subdirs
    assert not any(".DS_Store" in e for e in errors)   # cruft ignored
