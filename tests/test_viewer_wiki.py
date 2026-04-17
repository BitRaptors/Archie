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


import http.server
import threading
import urllib.request
import urllib.error


def test_http_route_wiki_page(tmp_path):
    # Prepare wiki.
    wiki = tmp_path / ".archie" / "wiki"
    (wiki / "components").mkdir(parents=True)
    (wiki / "index.md").write_text("# Idx\n")
    (wiki / "components" / "a.md").write_text("# A\n")

    # Start viewer server in a thread, with wiki UI enabled pointing at tmp_path.
    server = viewer.make_server(
        project_root=tmp_path, host="127.0.0.1", port=0, with_wiki_ui=True
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/wiki/components/a.md") as r:
            body = r.read().decode("utf-8")
            assert r.status == 200
            assert "<h1>A</h1>" in body
            assert '<nav class="wiki-sidebar">' in body
        # Missing page returns 404.
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/wiki/components/missing.md")
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_http_route_disabled_when_flag_off(tmp_path):
    wiki = tmp_path / ".archie" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "index.md").write_text("# I\n")
    server = viewer.make_server(
        project_root=tmp_path, host="127.0.0.1", port=0, with_wiki_ui=False
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        # With wiki disabled, /wiki/ returns 404.
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/wiki/")
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_md_to_html_escapes_href_attribute_quotes():
    # Attacker tries to break out of href="" with a quote.
    html = viewer.md_to_html('See [x](" onmouseover="alert(1)).\n')
    # Quote must be entity-encoded, not raw.
    assert 'onmouseover="alert(1)"' not in html
    assert '&quot;' in html or "&#x27;" in html or 'onmouseover=&quot;' in html


def test_md_to_html_blocks_javascript_urls():
    html = viewer.md_to_html("[x](javascript:alert(1))\n")
    # javascript: scheme must be blocked or neutralized.
    assert "javascript:alert" not in html.lower()


def test_md_to_html_blocks_data_urls():
    html = viewer.md_to_html("[x](data:text/html,<script>alert(1)</script>)\n")
    assert "data:text/html" not in html.lower()


def test_md_to_html_strips_yaml_frontmatter():
    html = viewer.md_to_html(
        "---\ntype: decision\nslug: x\n---\n\n# Title\n"
    )
    assert "<h1>Title</h1>" in html
    assert "type: decision" not in html
    assert "---" not in html


def test_http_route_bare_wiki_redirects(tmp_path):
    archie = tmp_path / ".archie"
    (archie / "wiki").mkdir(parents=True)
    (archie / "wiki" / "index.md").write_text("# I\n")
    server = viewer.make_server(
        project_root=tmp_path, host="127.0.0.1", port=0, with_wiki_ui=True
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        # urllib follows redirects by default — so the final response is 200
        # AND the URL we end up at should include the trailing slash.
        req = urllib.request.Request(f"http://127.0.0.1:{port}/wiki")
        req.add_header("User-Agent", "test")
        # Use an opener that doesn't follow redirects so we can assert on 301.
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        # Default opener follows redirects; use raw handler check via explicit urlopen on non-redirect-following:
        # Simplest: check via HTTPConnection.
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", port)
        conn.request("GET", "/wiki")
        r = conn.getresponse()
        assert r.status == 301
        assert r.getheader("Location") == "/wiki/"
        r.read()  # consume
        conn.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)
