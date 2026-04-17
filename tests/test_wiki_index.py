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
