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


def _fake_home(tmp_path: Path, *, has_claude: bool, has_codex: bool) -> dict:
    """Return an env dict with HOME pointing at a fake home with optional .claude / .codex dirs."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    if has_claude:
        (fake_home / ".claude").mkdir()
    if has_codex:
        (fake_home / ".codex").mkdir()
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    return env


def test_installer_auto_detects_codex_only(tmp_path: Path) -> None:
    """With only ~/.codex, --target=auto should resolve to codex."""
    project = tmp_path / "project"
    project.mkdir()
    env = _fake_home(tmp_path, has_claude=False, has_codex=True)
    result = _run_installer(project, target="auto", env=env)
    assert result.returncode == 0, f"installer failed: {result.stderr}"
    assert "codex" in (result.stdout + result.stderr).lower()


def test_installer_auto_detects_claude_only(tmp_path: Path) -> None:
    """With only ~/.claude, --target=auto should resolve to claude."""
    project = tmp_path / "project"
    project.mkdir()
    env = _fake_home(tmp_path, has_claude=True, has_codex=False)
    result = _run_installer(project, target="auto", env=env)
    assert result.returncode == 0
    # Existing Claude assets should land
    assert (project / ".claude" / "commands" / "archie-scan.md").exists()


def test_installer_auto_detects_both(tmp_path: Path) -> None:
    """With both ~/.claude and ~/.codex, --target=auto should install both."""
    project = tmp_path / "project"
    project.mkdir()
    env = _fake_home(tmp_path, has_claude=True, has_codex=True)
    result = _run_installer(project, target="auto", env=env)
    assert result.returncode == 0


def test_installer_codex_target_writes_skill_md(tmp_path: Path) -> None:
    """--target=codex must write the archie-scan SKILL.md to .agents/skills/archie-scan/."""
    project = tmp_path / "project"
    project.mkdir()
    result = _run_installer(project, target="codex")
    assert result.returncode == 0, f"installer failed: {result.stderr}"

    skill = project / ".agents" / "skills" / "archie-scan" / "SKILL.md"
    assert skill.exists(), f"missing: {skill}"
    content = skill.read_text()
    assert "name: archie-scan" in content
    assert ".archie/prompts/scan_analyzer.md" in content


def test_installer_codex_target_writes_shared_prompts(tmp_path: Path) -> None:
    """--target=codex must also write .archie/prompts/scan_analyzer.md."""
    project = tmp_path / "project"
    project.mkdir()
    _run_installer(project, target="codex")
    prompt = project / ".archie" / "prompts" / "scan_analyzer.md"
    assert prompt.exists(), f"missing: {prompt}"


def test_installer_codex_target_skips_claude_assets(tmp_path: Path) -> None:
    """--target=codex must NOT install Claude command files."""
    project = tmp_path / "project"
    project.mkdir()
    _run_installer(project, target="codex")
    claude_cmd = project / ".claude" / "commands" / "archie-scan.md"
    assert not claude_cmd.exists(), "Claude command should not be installed for --target=codex"


def test_installer_both_target_installs_both(tmp_path: Path) -> None:
    """--target=both must install both Claude and Codex assets."""
    project = tmp_path / "project"
    project.mkdir()
    _run_installer(project, target="both")
    assert (project / ".claude" / "commands" / "archie-scan.md").exists()
    assert (project / ".agents" / "skills" / "archie-scan" / "SKILL.md").exists()
