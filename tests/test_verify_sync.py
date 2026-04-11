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


def test_codex_scan_skill_exists_and_resolves() -> None:
    """The Codex archie-scan SKILL.md must exist and reference only valid prompts."""
    skill = REPO_ROOT / "npm-package" / "assets" / "codex" / "skills" / "archie-scan" / "SKILL.md"
    assert skill.exists(), f"Missing Codex skill: {skill}"

    content = skill.read_text()
    assert content.startswith("---"), "SKILL.md must have YAML frontmatter"
    assert "name: archie-scan" in content
    assert "description:" in content
    assert ".archie/prompts/scan_analyzer.md" in content, "SKILL.md must reference the scan analyzer prompt"


def test_verify_sync_detects_unresolved_prompt_reference(tmp_path: Path) -> None:
    """If a connector references a prompt file that doesn't exist, verify_sync must fail."""
    shutil.copytree(
        REPO_ROOT,
        tmp_path / "repo",
        ignore=shutil.ignore_patterns("__pycache__", ".git", "node_modules", ".venv", "venv"),
    )
    repo_copy = tmp_path / "repo"

    # Inject a bad reference into a SKILL.md
    skill_md = repo_copy / "npm-package" / "assets" / "codex" / "skills" / "archie-scan" / "SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    if skill_md.exists():
        # Append a bad reference to the existing file
        skill_md.write_text(skill_md.read_text() + "\nReference: .archie/prompts/nonexistent.md\n")
    else:
        # SKILL.md doesn't exist yet (Task 7's job). Simulate one with frontmatter and a bad reference.
        skill_md.write_text("---\nname: archie-scan\n---\nReference: .archie/prompts/nonexistent.md\n")

    result = subprocess.run(
        [sys.executable, str(repo_copy / "scripts" / "verify_sync.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "nonexistent.md" in result.stdout, f"Should report unresolved reference: {result.stdout}"
