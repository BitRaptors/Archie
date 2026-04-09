"""Tests for the renderer adapter (archie.renderer.render)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


from archie.renderer.render import render_outputs


MINIMAL_BLUEPRINT = {"meta": {"repository": "test-repo", "schema_version": "2.0.0"}}


def test_render_outputs_creates_claude_md(tmp_path: Path) -> None:
    """render_outputs should write CLAUDE.md to disk."""
    render_outputs(MINIMAL_BLUEPRINT, tmp_path)
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists(), "CLAUDE.md was not created"
    content = claude_md.read_text()
    assert "test-repo" in content


def test_render_outputs_creates_rules(tmp_path: Path) -> None:
    """render_outputs should create .claude/rules/ directory with rule files."""
    render_outputs(MINIMAL_BLUEPRINT, tmp_path)
    rules_dir = tmp_path / ".claude" / "rules"
    assert rules_dir.exists(), ".claude/rules/ directory was not created"
    rule_files = list(rules_dir.glob("*.md"))
    assert len(rule_files) > 0, "No rule files found in .claude/rules/"


def test_render_outputs_returns_file_map(tmp_path: Path) -> None:
    """render_outputs should return a dict with expected keys."""
    result = render_outputs(MINIMAL_BLUEPRINT, tmp_path)
    assert isinstance(result, dict)
    assert "CLAUDE.md" in result
    assert "AGENTS.md" in result
    # Should have at least one rule file path
    claude_rule_paths = [k for k in result if k.startswith(".claude/rules/")]
    assert len(claude_rule_paths) > 0, "No .claude/rules/ entries in file map"


def test_render_outputs_codex_target_omits_claude_md(tmp_path: Path) -> None:
    """render_outputs with target='codex' should NOT write CLAUDE.md."""
    render_outputs(MINIMAL_BLUEPRINT, tmp_path, target="codex")
    claude_md = tmp_path / "CLAUDE.md"
    agents_md = tmp_path / "AGENTS.md"
    assert not claude_md.exists(), "CLAUDE.md should not be created with target=codex"
    assert agents_md.exists(), "AGENTS.md should still be created with target=codex"


def test_render_outputs_claude_target_writes_both(tmp_path: Path) -> None:
    """render_outputs with target='claude' (default) should write both CLAUDE.md and AGENTS.md."""
    render_outputs(MINIMAL_BLUEPRINT, tmp_path)  # default target
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_render_outputs_both_target_writes_both(tmp_path: Path) -> None:
    """render_outputs with target='both' should write both files."""
    render_outputs(MINIMAL_BLUEPRINT, tmp_path, target="both")
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_renderer_cli_accepts_target_codex(tmp_path: Path) -> None:
    """Standalone renderer CLI should accept --target=codex and write only AGENTS.md."""
    # Set up a minimal blueprint in the tmp project
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    blueprint_path = archie_dir / "blueprint.json"
    blueprint_path.write_text(json.dumps(MINIMAL_BLUEPRINT))

    repo_root = Path(__file__).resolve().parent.parent
    renderer = repo_root / "archie" / "standalone" / "renderer.py"

    result = subprocess.run(
        [sys.executable, str(renderer), str(tmp_path), "--target=codex"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"renderer failed: {result.stderr}"
    assert not (tmp_path / "CLAUDE.md").exists(), "CLAUDE.md should not exist for codex target"
    assert (tmp_path / "AGENTS.md").exists(), "AGENTS.md should exist for codex target"
