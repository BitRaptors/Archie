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
