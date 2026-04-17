"""Tests for wiki_index.py — backlinks and provenance."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import wiki_index  # noqa: E402


def test_extract_links_from_page(tmp_path):
    page = tmp_path / "a.md"
    page.write_text(
        "# Title\n"
        "See [B](../components/b.md) and [C](../decisions/c.md).\n"
        "Also [broken]() and [external](https://example.com).\n"
    )
    links = wiki_index.extract_links(page)
    # Only relative links with .md targets are collected. External and empty ignored.
    assert sorted(links) == [("../components/b.md", "B"), ("../decisions/c.md", "C")]


def test_build_backlinks(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    (wiki / "decisions").mkdir(parents=True)
    (wiki / "components" / "a.md").write_text("# A\n[B](../components/b.md)\n")
    (wiki / "components" / "b.md").write_text("# B\n")
    (wiki / "decisions" / "d.md").write_text("# D\n[A](../components/a.md)\n")

    backlinks = wiki_index.build_backlinks(wiki)
    # B is referenced by A
    assert backlinks["components/b.md"] == [
        {"path": "components/a.md", "title": "A", "type": "component"}
    ]
    # A is referenced by D
    assert backlinks["components/a.md"] == [
        {"path": "decisions/d.md", "title": "D", "type": "decision"}
    ]
    # D has no inbound links
    assert "decisions/d.md" not in backlinks or backlinks["decisions/d.md"] == []


def test_inject_referenced_by(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    page = wiki / "components" / "b.md"
    page.write_text("# B\n\nSome content.\n")
    backlinks = {
        "components/b.md": [
            {"path": "components/a.md", "title": "A", "type": "component"},
            {"path": "decisions/d.md", "title": "D", "type": "decision"},
        ]
    }
    wiki_index.inject_referenced_by(wiki, backlinks)
    content = page.read_text()
    assert "## Referenced by" in content
    assert "[A](../components/a.md) (component)" in content
    assert "[D](../decisions/d.md) (decision)" in content


def test_inject_referenced_by_idempotent(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    page = wiki / "components" / "b.md"
    page.write_text("# B\n")
    backlinks = {"components/b.md": [{"path": "components/a.md", "title": "A", "type": "component"}]}
    wiki_index.inject_referenced_by(wiki, backlinks)
    first = page.read_text()
    # Running again with the same backlinks must produce the identical file.
    wiki_index.inject_referenced_by(wiki, backlinks)
    assert page.read_text() == first


def test_write_provenance(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    (wiki / "components" / "a.md").write_text("# A\n")
    wiki_index.write_provenance(wiki, last_refreshed="2026-04-17")
    prov = json.loads((wiki / "_meta" / "provenance.json").read_text())
    assert "components/a.md" in prov
    assert "sha256" in prov["components/a.md"]
    assert prov["components/a.md"]["last_refreshed"] == "2026-04-17"
    assert prov["components/a.md"]["source"] == "wiki_builder"


def test_write_provenance_records_evidence(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "capabilities").mkdir(parents=True)
    (wiki / "capabilities" / "auth.md").write_text("# Auth\n")
    (wiki / "components").mkdir()
    (wiki / "components" / "x.md").write_text("# X\n")

    evidence_map = {"capabilities/auth.md": ["features/auth/**", "routes matching /api/auth/*"]}
    wiki_index.write_provenance(wiki, last_refreshed="2026-04-17", evidence_map=evidence_map)

    prov = json.loads((wiki / "_meta" / "provenance.json").read_text())
    assert prov["capabilities/auth.md"]["evidence"] == ["features/auth/**", "routes matching /api/auth/*"]
    # Pages without an evidence entry don't get the key.
    assert "evidence" not in prov["components/x.md"]
