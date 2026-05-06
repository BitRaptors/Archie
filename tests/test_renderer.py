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


from archie.standalone.renderer import build_enforcement_directory


def _mk(id_, topic, source, **extra):
    return {"id": id_, "topic": topic, "_archie_source": source,
            "description": f"desc {id_}", **extra}


def test_build_enforcement_directory_groups_project_by_topic():
    rules = [
        _mk("rx-001", "concurrency", "project"),
        _mk("rx-002", "concurrency", "project"),
        _mk("nav-001", "navigation", "project"),
    ]
    out = build_enforcement_directory(rules)
    assert "enforcement/by-topic/concurrency.md" in out
    assert "enforcement/by-topic/navigation.md" in out
    body = out["enforcement/by-topic/concurrency.md"]
    assert "rx-001" in body and "rx-002" in body
    assert "nav-001" not in body


def test_build_enforcement_directory_routes_platform_to_universal():
    rules = [
        _mk("rx-001", "concurrency", "project"),
        _mk("erosion-god-function", "complexity", "platform"),
        _mk("decay-empty-catch", "quality", "platform"),
    ]
    out = build_enforcement_directory(rules)
    assert "enforcement/universal.md" in out
    universal = out["enforcement/universal.md"]
    assert "erosion-god-function" in universal
    assert "decay-empty-catch" in universal
    # Project rule should NOT be in universal.md
    assert "rx-001" not in universal
    # No by-topic file for platform topic.
    assert "enforcement/by-topic/complexity.md" not in out


def test_build_enforcement_directory_emits_index():
    rules = [
        _mk("rx-001", "concurrency", "project"),
        _mk("nav-001", "navigation", "project"),
        _mk("erosion-god-function", "complexity", "platform"),
    ]
    out = build_enforcement_directory(rules)
    idx = out["enforcement/index.md"]
    assert "Enforcement Rules" in idx
    # Topic table lists every project topic + universal row.
    assert "concurrency" in idx
    assert "navigation" in idx
    assert "Universal" in idx
    # Counts surface.
    assert "1" in idx  # one rule per topic in this fixture


def test_build_enforcement_directory_path_glob_inversion():
    rules = [
        _mk("rx-001", "concurrency", "project",
            triggers={"path_glob": ["Sources/Controllers/**/*.swift"]}),
        _mk("nav-001", "navigation", "project",
            triggers={"path_glob": ["Sources/Controllers/**/*.swift"]}),
        _mk("ui-001", "ui", "project",
            triggers={"path_glob": ["Sources/Views/**/*.swift"]}),
    ]
    out = build_enforcement_directory(rules)
    idx = out["enforcement/index.md"]
    # The Controllers glob should list both concurrency and navigation.
    controllers_section = idx.split("Sources/Controllers")[1].split("|")[0:6]
    joined = " ".join(controllers_section)
    assert "concurrency" in joined
    assert "navigation" in joined


def test_build_enforcement_directory_legacy_rules_use_fallback_heuristic():
    """Rules with no `topic` field still get grouped via the prefix table."""
    rules = [
        {"id": "rx-001", "description": "x", "_archie_source": "project"},
        {"id": "ui-001", "description": "x", "_archie_source": "project"},
    ]
    out = build_enforcement_directory(rules)
    assert "enforcement/by-topic/concurrency.md" in out
    assert "enforcement/by-topic/ui.md" in out


def test_build_enforcement_directory_empty_input_returns_empty_dict():
    assert build_enforcement_directory([]) == {}


def test_build_enforcement_directory_slugifies_topic_with_spaces():
    rules = [_mk("x-001", "Data Access", "project")]
    out = build_enforcement_directory(rules)
    assert "enforcement/by-topic/data-access.md" in out


from archie.standalone.renderer import generate_all


def test_generate_all_partitions_rules_by_archie_source():
    """generate_all should partition rules into project (by-topic/) and
    platform (universal.md) buckets based on _archie_source."""
    bp = {"meta": {"repository": "x", "schema_version": "2.0.0"}}
    rules = [
        {
            "id": "rx-001",
            "topic": "concurrency",
            "description": "test",
            "_archie_source": "project",
        },
        {
            "id": "erosion-god-function",
            "topic": "complexity",
            "description": "test",
            "_archie_source": "platform",
        },
    ]
    files = generate_all(bp, enforcement_rules=rules)
    assert ".claude/rules/enforcement/universal.md" in files
    assert ".claude/rules/enforcement/by-topic/concurrency.md" in files
    # Project rule should NOT leak into universal.md
    assert "rx-001" not in files[".claude/rules/enforcement/universal.md"]
    # Platform rule should NOT leak into by-topic/
    assert "erosion-god-function" not in files[
        ".claude/rules/enforcement/by-topic/concurrency.md"
    ]
