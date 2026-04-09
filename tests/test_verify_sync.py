"""Tests for scripts/verify_sync.py — sync check between canonical and vendored assets."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFY_SYNC = REPO_ROOT / "scripts" / "verify_sync.py"


def test_verify_sync_passes_on_clean_repo() -> None:
    """verify_sync.py should exit 0 when canonical and assets match."""
    result = subprocess.run(
        [sys.executable, str(VERIFY_SYNC)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"verify_sync failed unexpectedly:\n{result.stdout}\n{result.stderr}"


def test_verify_sync_detects_missing_prompt_asset(tmp_path: Path) -> None:
    """If a file exists in archie/prompts/ but not in npm-package/assets/prompts/, verify_sync must fail."""
    # Make a copy of the repo into tmp_path so we can corrupt it
    shutil.copytree(
        REPO_ROOT,
        tmp_path / "repo",
        ignore=shutil.ignore_patterns("__pycache__", ".git", "node_modules", ".venv", "venv"),
    )
    repo_copy = tmp_path / "repo"

    # Delete the prompt's asset copy
    (repo_copy / "npm-package" / "assets" / "prompts" / "scan_analyzer.md").unlink()

    result = subprocess.run(
        [sys.executable, str(repo_copy / "scripts" / "verify_sync.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "verify_sync should fail when a prompt asset is missing"
    assert "scan_analyzer.md" in result.stdout, f"Error message should mention the missing prompt: {result.stdout}"


def test_verify_sync_detects_prompt_content_drift(tmp_path: Path) -> None:
    """If archie/prompts/X.md and assets/prompts/X.md differ in content, verify_sync must fail."""
    shutil.copytree(
        REPO_ROOT,
        tmp_path / "repo",
        ignore=shutil.ignore_patterns("__pycache__", ".git", "node_modules", ".venv", "venv"),
    )
    repo_copy = tmp_path / "repo"

    # Corrupt the asset copy
    asset = repo_copy / "npm-package" / "assets" / "prompts" / "scan_analyzer.md"
    asset.write_text(asset.read_text() + "\nDRIFT")

    result = subprocess.run(
        [sys.executable, str(repo_copy / "scripts" / "verify_sync.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "OUT OF SYNC" in result.stdout or "scan_analyzer" in result.stdout
