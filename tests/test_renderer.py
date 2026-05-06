"""Tests for the renderer adapter (archie.renderer.render)."""
from __future__ import annotations

from pathlib import Path


from archie.renderer.render import render_outputs


MINIMAL_BLUEPRINT = {"meta": {"repository": "test-repo", "schema_version": "2.0.0"}}

# Blueprint with enough content to exercise at least one rule builder. The
# renderer is correctly lazy — empty sections don't emit empty files — so a
# fixture for "rule files exist" needs real architecture data.
BLUEPRINT_WITH_RULES = {
    "meta": {"repository": "test-repo", "schema_version": "2.0.0"},
    "architecture_rules": {
        "naming_conventions": [
            {"scope": "files", "pattern": "snake_case", "examples": ["a.py"], "description": "Python uses snake_case"}
        ],
        "file_placement_rules": [],
    },
}


def test_render_outputs_creates_agents_md_canonical(tmp_path: Path) -> None:
    """AGENTS.md is the canonical, blueprint-derived doc on disk.

    AGENTS.md is the vendor-neutral standard read by Cursor, Codex, Aider,
    Continue, Cline, Cody, and Claude Code itself, so it carries the rich
    body. CLAUDE.md is a static pointer (covered separately).
    """
    render_outputs(MINIMAL_BLUEPRINT, tmp_path)
    agents_md = tmp_path / "AGENTS.md"
    assert agents_md.exists(), "AGENTS.md was not created"
    content = agents_md.read_text()
    assert "test-repo" in content


def test_render_outputs_creates_claude_md_pointer(tmp_path: Path) -> None:
    """CLAUDE.md is a static pointer to AGENTS.md, not a duplicate body.

    Claude Code auto-loads CLAUDE.md; the pointer tells the session where
    the canonical context lives without paying duplicate tokens.
    """
    render_outputs(MINIMAL_BLUEPRINT, tmp_path)
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists(), "CLAUDE.md was not created"
    content = claude_md.read_text()
    assert "AGENTS.md" in content, "pointer must reference AGENTS.md"
    assert "test-repo" not in content, "pointer must not duplicate canonical body"


def test_render_outputs_creates_rules(tmp_path: Path) -> None:
    """render_outputs should create .claude/rules/ directory with rule files
    when the blueprint carries content for at least one rule builder."""
    render_outputs(BLUEPRINT_WITH_RULES, tmp_path)
    rules_dir = tmp_path / ".claude" / "rules"
    assert rules_dir.exists(), ".claude/rules/ directory was not created"
    rule_files = list(rules_dir.glob("*.md"))
    assert len(rule_files) > 0, "No rule files found in .claude/rules/"


def test_render_outputs_returns_file_map(tmp_path: Path) -> None:
    """render_outputs should return a dict with expected keys."""
    result = render_outputs(BLUEPRINT_WITH_RULES, tmp_path)
    assert isinstance(result, dict)
    assert "CLAUDE.md" in result
    assert "AGENTS.md" in result
    # Should have at least one rule file path
    claude_rule_paths = [k for k in result if k.startswith(".claude/rules/")]
    assert len(claude_rule_paths) > 0, "No .claude/rules/ entries in file map"


def test_render_outputs_minimal_blueprint_emits_no_rule_files(tmp_path: Path) -> None:
    """A blueprint with only meta and no architecture content should produce
    CLAUDE.md/AGENTS.md but no rule files. Empty rule files would just bloat
    the agent's context — the renderer correctly skips them."""
    result = render_outputs(MINIMAL_BLUEPRINT, tmp_path)
    assert "CLAUDE.md" in result
    assert "AGENTS.md" in result
    rule_paths = [k for k in result if k.startswith(".claude/rules/")]
    assert rule_paths == [], f"minimal blueprint must not emit rule files; got {rule_paths}"


from archie.standalone.renderer import _topic_for_rule


def test_topic_for_rule_uses_topic_field_when_present():
    rule = {"id": "rx-001", "topic": "concurrency"}
    assert _topic_for_rule(rule) == "concurrency"


def test_topic_for_rule_slugifies_topic_field():
    rule = {"id": "x-001", "topic": "Data Access"}
    assert _topic_for_rule(rule) == "data-access"


def test_topic_for_rule_falls_back_to_known_prefix():
    # No topic field — fall back to prefix heuristic.
    assert _topic_for_rule({"id": "rx-001"}) == "concurrency"
    assert _topic_for_rule({"id": "combine-002"}) == "concurrency"
    assert _topic_for_rule({"id": "nav-001"}) == "navigation"
    assert _topic_for_rule({"id": "ui-003"}) == "ui"
    assert _topic_for_rule({"id": "swiftui-001"}) == "ui"
    assert _topic_for_rule({"id": "snapkit-001"}) == "ui"
    assert _topic_for_rule({"id": "rswift-001"}) == "ui"
    assert _topic_for_rule({"id": "firebase-002"}) == "data-access"
    assert _topic_for_rule({"id": "mapbox-001"}) == "mapping"
    assert _topic_for_rule({"id": "map-003"}) == "mapping"
    assert _topic_for_rule({"id": "layer-001"}) == "layering"
    assert _topic_for_rule({"id": "file-placement-001"}) == "layering"
    assert _topic_for_rule({"id": "svc-001"}) == "services"
    assert _topic_for_rule({"id": "sing-001"}) == "services"
    assert _topic_for_rule({"id": "model-001"}) == "layering"
    assert _topic_for_rule({"id": "dep-001"}) == "dependencies"
    assert _topic_for_rule({"id": "secret-001"}) == "security"
    assert _topic_for_rule({"id": "gdpr-001"}) == "security"
    assert _topic_for_rule({"id": "testing-001"}) == "testing"
    assert _topic_for_rule({"id": "res-001"}) == "resources"


def test_topic_for_rule_unknown_prefix_returns_misc():
    assert _topic_for_rule({"id": "totally-unknown-001"}) == "misc"


def test_topic_for_rule_no_id_returns_misc():
    assert _topic_for_rule({}) == "misc"


def test_topic_for_rule_handles_malformed_topic_field():
    assert _topic_for_rule({"id": "x-001", "topic": 42}) == "misc"
    assert _topic_for_rule({"id": "x-001", "topic": None}) == "misc"
    assert _topic_for_rule({"id": "x-001", "topic": ""}) == "misc"
    assert _topic_for_rule({"id": "x-001", "topic": "   "}) == "misc"


def test_topic_for_rule_handles_non_string_id():
    # rule["id"] is malformed (int, None) — must not crash, falls back to misc
    assert _topic_for_rule({"id": 42}) == "misc"
    assert _topic_for_rule({"id": None}) == "misc"
