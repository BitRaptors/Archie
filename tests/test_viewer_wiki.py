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
