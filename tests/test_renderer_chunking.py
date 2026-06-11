"""Tests for topic-file chunking (index + per-H2-section files).

Topic bodies above the byte threshold split into .claude/rules/<topic>/
section chunks, with the topic file itself becoming a routing index so
agents load ~1 KB to pick the 2-5 KB chunk they need.
"""
from __future__ import annotations

from pathlib import Path

from archie.standalone import renderer


def _patterns_blueprint(n_patterns: int) -> dict:
    """Blueprint whose patterns topic grows linearly with n_patterns."""
    return {
        "meta": {"repository": "test-repo", "schema_version": "2.0.0"},
        "communication": {
            "patterns": [
                {
                    "name": f"Pattern {i}",
                    "when_to_use": "When the moon is full and the build is green. " * 4,
                    "how_it_works": "Observable chains feed the view model bindings. " * 4,
                    "applicable_when": "Editing service-layer reactive flows.",
                }
                for i in range(n_patterns)
            ]
        },
        "decisions": {
            "key_decisions": [
                {
                    "decision": f"Decision {i}",
                    "rationale": "Keeps the dependency graph acyclic across layers. " * 4,
                }
                for i in range(n_patterns)
            ]
        },
    }


def test_small_topic_stays_single_file() -> None:
    files = renderer.generate_all(_patterns_blueprint(1))
    assert ".claude/rules/patterns.md" in files
    assert not any(p.startswith(".claude/rules/patterns/") for p in files)
    assert "This topic is chunked" not in files[".claude/rules/patterns.md"]


def test_large_topic_chunks_into_index_plus_sections() -> None:
    files = renderer.generate_all(_patterns_blueprint(30))
    index = files[".claude/rules/patterns.md"]
    assert "This topic is chunked" in index
    assert "| Section | File | ~Tokens | Contains |" in index

    chunks = [p for p in files if p.startswith(".claude/rules/patterns/")]
    assert ".claude/rules/patterns/communication-patterns.md" in chunks
    # Every chunk must be reachable from its parent index (top index for
    # section files, the section sub-index for recursed entry files).
    for p in chunks:
        parent_index = files[str(Path(p).parent) + ".md"]
        assert f"/{Path(p).name})" in parent_index
    # Index is small relative to the would-be monolith.
    assert len(index.encode()) < renderer._CHUNK_THRESHOLD_BYTES


def test_oversized_section_recurses_into_entry_chunks() -> None:
    files = renderer.generate_all(_patterns_blueprint(30))
    sub_index = files[".claude/rules/patterns/communication-patterns.md"]
    assert "This section is chunked" in sub_index
    entries = [p for p in files
               if p.startswith(".claude/rules/patterns/communication-patterns/")]
    assert len(entries) == 30
    entry = files[".claude/rules/patterns/communication-patterns/pattern-0.md"]
    assert entry.startswith("# Patterns: Communication Patterns: Pattern 0")
    # Recursion is depth-capped: entry files never spawn their own dirs.
    assert not any(p.count("/") > 4 for p in entries)


def test_chunk_carries_topic_and_section_heading() -> None:
    files = renderer.generate_all(_patterns_blueprint(30))
    chunk = files[".claude/rules/patterns/communication-patterns.md"]
    assert chunk.startswith("# Patterns: Communication Patterns")
    assert "Pattern 0" in chunk and "Pattern 29" in chunk


def test_index_summary_lists_h3_entries() -> None:
    files = renderer.generate_all(_patterns_blueprint(30))
    index = files[".claude/rules/patterns.md"]
    assert "entries: Pattern 0" in index
    assert "+" in index and "more" in index  # capped list advertises the rest


def test_split_h2_ignores_headings_inside_code_fences() -> None:
    body = "intro\n\n## Real\n\ntext\n\n```md\n## Fake\n```\n"
    preamble, sections = renderer._split_h2_sections(body)
    assert preamble == "intro"
    assert [h for h, _ in sections] == ["Real"]
    assert "## Fake" in sections[0][1]


def test_cleanup_removes_retired_enforcement_monolith(tmp_path: Path) -> None:
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "enforcement.md").write_text("old monolith")
    removed = renderer.cleanup_stale_rule_files(tmp_path, {})
    assert removed == [".claude/rules/enforcement.md"]
    assert not (rules / "enforcement.md").exists()


def test_cleanup_prunes_stale_chunks_and_dechunked_dirs(tmp_path: Path) -> None:
    rules = tmp_path / ".claude" / "rules"
    (rules / "patterns").mkdir(parents=True)
    (rules / "patterns" / "renamed-away.md").write_text("stale")
    (rules / "patterns" / "kept.md").write_text("current")
    files = {
        ".claude/rules/patterns.md": "index",
        ".claude/rules/patterns/kept.md": "current",
    }
    removed = renderer.cleanup_stale_rule_files(tmp_path, files)
    assert removed == [".claude/rules/patterns/renamed-away.md"]
    assert (rules / "patterns" / "kept.md").exists()

    # Topic de-chunked next run: whole dir empties out and is removed.
    removed = renderer.cleanup_stale_rule_files(
        tmp_path, {".claude/rules/patterns.md": "single file again"}
    )
    assert ".claude/rules/patterns/kept.md" in removed
    assert not (rules / "patterns").exists()


def test_cleanup_leaves_foreign_files_alone(tmp_path: Path) -> None:
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "hand-written.md").write_text("user file")
    (rules / "other-topic").mkdir()
    (rules / "other-topic" / "note.md").write_text("not ours this run")
    removed = renderer.cleanup_stale_rule_files(
        tmp_path, {".claude/rules/patterns.md": "x"}
    )
    assert removed == []
    assert (rules / "hand-written.md").exists()
    assert (rules / "other-topic" / "note.md").exists()
