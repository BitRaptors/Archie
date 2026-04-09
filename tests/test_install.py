"""Smoke tests for npm-package/bin/archie.mjs (the dual-target installer)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIE_MJS = REPO_ROOT / "npm-package" / "bin" / "archie.mjs"


def _has_node() -> bool:
    return shutil.which("node") is not None


pytestmark = pytest.mark.skipif(not _has_node(), reason="node not available")


def _run_installer(project_root: Path, target: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    args = ["node", str(ARCHIE_MJS), str(project_root)]
    if target is not None:
        args.append(f"--target={target}")
    return subprocess.run(args, capture_output=True, text=True, env=env or os.environ.copy())


def test_installer_accepts_target_flag(tmp_path: Path) -> None:
    """archie.mjs --target=claude must run without error."""
    result = _run_installer(tmp_path, target="claude")
    assert result.returncode == 0, f"installer failed: {result.stderr}"


def test_installer_rejects_unknown_target(tmp_path: Path) -> None:
    """archie.mjs --target=blah must fail with a clear error."""
    result = _run_installer(tmp_path, target="blah")
    assert result.returncode != 0
    assert "target" in (result.stderr + result.stdout).lower()
