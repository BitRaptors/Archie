"""Tests for viewer.py wiki integration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import viewer  # noqa: E402


def test_md_to_html_heading():
    html = viewer.md_to_html("# Title\n")
    assert "<h1>Title</h1>" in html


def test_md_to_html_paragraph_and_bold():
    html = viewer.md_to_html("Some **bold** text.\n")
    assert "<strong>bold</strong>" in html


def test_md_to_html_bullet_list():
    html = viewer.md_to_html("- one\n- two\n- three\n")
    assert "<ul>" in html
    assert "<li>one</li>" in html
    assert "<li>three</li>" in html
    assert "</ul>" in html


def test_md_to_html_link_preserves_relative_href():
    html = viewer.md_to_html("See [A](../components/a.md).\n")
    assert 'href="../components/a.md"' in html
    assert ">A</a>" in html


def test_md_to_html_fenced_code():
    html = viewer.md_to_html("```\nx = 1\n```\n")
    assert "<pre><code>" in html
    assert "x = 1" in html


def test_md_to_html_escapes_raw_html():
    html = viewer.md_to_html("before <not-a-tag> after\n")
    assert "&lt;not-a-tag&gt;" in html


def test_render_wiki_sidebar(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    (wiki / "decisions").mkdir()
    (wiki / "capabilities").mkdir()
    (wiki / "index.md").write_text("# Test\n")
    (wiki / "components" / "a.md").write_text("# A\n")
    (wiki / "components" / "b.md").write_text("# B\n")
    (wiki / "decisions" / "d.md").write_text("# D\n")
    (wiki / "capabilities" / "auth.md").write_text("# Auth\n")

    html = viewer.render_wiki_sidebar(wiki)
    assert '<nav class="wiki-sidebar">' in html
    assert "Capabilities" in html
    assert "Components" in html
    assert "Decisions" in html
    # Auth comes before A/B because capabilities group is listed first
    auth_pos = html.index("Auth")
    a_pos = html.index(">A<")
    assert auth_pos < a_pos
    # Links reference /wiki/<type>/<slug>
    assert 'href="/wiki/capabilities/auth.md"' in html
    assert 'href="/wiki/components/a.md"' in html


def test_serve_wiki_page(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    (wiki / "index.md").write_text("# Idx\n- one\n")
    (wiki / "components" / "a.md").write_text("# A\nSee [Idx](../index.md)\n")

    html = viewer.render_wiki_page(wiki, page_rel="components/a.md")
    # Sidebar present
    assert '<nav class="wiki-sidebar">' in html
    # Page content rendered
    assert "<h1>A</h1>" in html
    # Link preserved (relative hrefs still valid since the page is served
    # under /wiki/components/a.md, and ../index.md resolves to /wiki/index.md)
    assert 'href="../index.md"' in html


def test_serve_wiki_index(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "index.md").write_text("# Welcome\n")
    html = viewer.render_wiki_page(wiki, page_rel="index.md")
    assert "<h1>Welcome</h1>" in html


def test_serve_wiki_page_404(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "index.md").write_text("# I\n")
    # Missing page returns an empty string — route handler interprets falsy
    # result as 404.
    assert viewer.render_wiki_page(wiki, page_rel="missing.md") == ""
