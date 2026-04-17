# LLM Wiki — Plan 4: Viewer Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve `.archie/wiki/**` as browsable HTML inside the existing `viewer.py`. Adds a `/wiki/*` route, a sidebar driven by `_meta/backlinks.json`, a minimal markdown→HTML renderer, and a `--with-wiki-ui` flag so the feature is opt-in until v1.1.

**Architecture:** `viewer.py` already serves a zero-dep HTTP interface over the blueprint dashboard. Plan 4 extends it with three new route handlers: `GET /wiki/`, `GET /wiki/<path>`, and `GET /wiki/_meta/<file>.json`. The markdown renderer is a single-file minimalist (headings, paragraphs, bullet lists, inline/block links, code blocks, bold/italic) — no external dependency. The sidebar is generated server-side from the current `_meta/backlinks.json` and grouped by page type.

**Tech Stack:** Python 3.9+ stdlib, pytest. No new dependencies. The HTML uses the existing viewer stylesheet (one additional CSS block added inline to `viewer.py` output).

**Depends on:** Plans 1, 2, 3 — the wiki must exist and be kept fresh.

**Reference spec:** `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` §3.5

---

## File structure (this plan)

**Modified files:**
- `archie/standalone/viewer.py` — new routes, flag, markdown renderer.
- `tests/test_viewer_wiki.py` — new test module.
- `npm-package/assets/viewer.py` — sync.

No new modules. Everything lives in `viewer.py` to keep the zero-dep contract (one file, stdlib only).

---

## Task 1: Markdown → HTML renderer

**Files:**
- Modify: `archie/standalone/viewer.py`
- Create: `tests/test_viewer_wiki.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_viewer_wiki.py`:

```python
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
    # A stray '<' in prose must not produce an unclosed tag.
    html = viewer.md_to_html("before <not-a-tag> after\n")
    assert "&lt;not-a-tag&gt;" in html
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_viewer_wiki.py -v -k md_to_html`
Expected: FAIL — `md_to_html` missing.

- [ ] **Step 3: Implement a minimal markdown renderer in `viewer.py`**

Find a logical home near the other rendering helpers in `archie/standalone/viewer.py`. Add:

```python
import html as _html
import re as _re


_MD_LINK_RE = _re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_MD_BOLD_RE = _re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC_RE = _re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_MD_CODE_INLINE_RE = _re.compile(r"`([^`]+)`")


def md_to_html(text: str) -> str:
    """Minimal markdown -> HTML. Supports: #/##/### headings, paragraphs,
    unordered lists, fenced code blocks, inline code, bold, italic, links.

    Does NOT support: tables, images, HTML passthrough, blockquotes,
    ordered lists, nested lists. Anything unsupported is passed through as
    paragraph text with HTML escaping.
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    in_list = False
    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith("```"):
            if in_list:
                out.append("</ul>")
                in_list = False
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(_html.escape(lines[i]))
                i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            i += 1  # consume closing fence
            continue

        # Headings
        m = _re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Bullet list item
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line[2:])}</li>")
            i += 1
            continue

        # Blank line
        if line.strip() == "":
            if in_list:
                out.append("</ul>")
                in_list = False
            i += 1
            continue

        # Paragraph
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<p>{_inline(line)}</p>")
        i += 1

    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _inline(text: str) -> str:
    """Apply inline markdown (link, bold, italic, inline code), then escape
    leftovers. Links are substituted first with placeholders to protect hrefs
    from HTML escaping."""
    placeholders: list[str] = []

    def _sub_link(match):
        idx = len(placeholders)
        placeholders.append(f'<a href="{match.group(2)}">{_html.escape(match.group(1))}</a>')
        return f"\x00L{idx}\x00"

    text = _MD_LINK_RE.sub(_sub_link, text)

    def _sub_code(match):
        idx = len(placeholders)
        placeholders.append(f"<code>{_html.escape(match.group(1))}</code>")
        return f"\x00L{idx}\x00"

    text = _MD_CODE_INLINE_RE.sub(_sub_code, text)

    # Escape everything else, then apply bold/italic on the escaped string.
    text = _html.escape(text)
    text = _MD_BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _MD_ITALIC_RE.sub(r"<em>\1</em>", text)

    # Restore placeholders.
    for idx, replacement in enumerate(placeholders):
        text = text.replace(f"\x00L{idx}\x00", replacement)
    return text
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_viewer_wiki.py -v -k md_to_html`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/viewer.py tests/test_viewer_wiki.py
git commit -m "feat(viewer): add minimal markdown-to-HTML renderer"
```

---

## Task 2: Wiki sidebar from backlinks

**Files:**
- Modify: `archie/standalone/viewer.py`
- Modify: `tests/test_viewer_wiki.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_viewer_wiki.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_viewer_wiki.py -v -k sidebar`
Expected: FAIL.

- [ ] **Step 3: Implement the sidebar renderer**

Append to `archie/standalone/viewer.py`:

```python
_SIDEBAR_ORDER = ["capabilities", "decisions", "components", "patterns", "pitfalls"]
_SIDEBAR_LABELS = {
    "capabilities": "Capabilities",
    "decisions": "Decisions",
    "components": "Components",
    "patterns": "Patterns",
    "pitfalls": "Pitfalls",
}


def _page_title(page: Path) -> str:
    for line in page.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return page.stem


def render_wiki_sidebar(wiki_root: Path) -> str:
    """Produce the sidebar HTML: sections per type, sorted by title within each."""
    parts = ['<nav class="wiki-sidebar">']
    parts.append('<h2><a href="/wiki/">Wiki index</a></h2>')
    for subdir in _SIDEBAR_ORDER:
        d = wiki_root / subdir
        if not d.exists():
            continue
        pages = sorted(d.glob("*.md"), key=lambda p: _page_title(p).lower())
        if not pages:
            continue
        parts.append(f"<h3>{_SIDEBAR_LABELS[subdir]}</h3>")
        parts.append("<ul>")
        for page in pages:
            rel = page.relative_to(wiki_root).as_posix()
            title = _html.escape(_page_title(page))
            parts.append(f'<li><a href="/wiki/{rel}">{title}</a></li>')
        parts.append("</ul>")
    parts.append("</nav>")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_viewer_wiki.py -v -k sidebar`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/viewer.py tests/test_viewer_wiki.py
git commit -m "feat(viewer): render wiki sidebar grouped by type"
```

---

## Task 3: Route handler + wiki page HTML

**Files:**
- Modify: `archie/standalone/viewer.py`
- Modify: `tests/test_viewer_wiki.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_viewer_wiki.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_viewer_wiki.py -v -k "serve_wiki"`
Expected: FAIL.

- [ ] **Step 3: Implement `render_wiki_page`**

Append to `archie/standalone/viewer.py`:

```python
_WIKI_CSS = """
<style>
  body.wiki { font: 14px/1.5 -apple-system, system-ui, sans-serif; margin: 0; display: flex; }
  .wiki-sidebar { width: 240px; padding: 16px; border-right: 1px solid #eee; height: 100vh; overflow-y: auto; flex-shrink: 0; }
  .wiki-sidebar h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .05em; color: #666; }
  .wiki-sidebar h3 { font-size: 12px; text-transform: uppercase; color: #888; margin: 16px 0 4px; }
  .wiki-sidebar ul { list-style: none; padding: 0; margin: 0; }
  .wiki-sidebar li a { color: #1a73e8; text-decoration: none; display: block; padding: 2px 0; font-size: 13px; }
  .wiki-sidebar li a:hover { text-decoration: underline; }
  .wiki-content { padding: 24px 32px; max-width: 820px; }
  .wiki-content h1 { font-size: 22px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
  .wiki-content h2 { font-size: 16px; margin-top: 24px; }
  .wiki-content h3 { font-size: 14px; color: #444; }
  .wiki-content a { color: #1a73e8; }
  .wiki-content pre { background: #f6f8fa; padding: 12px; border-radius: 6px; overflow-x: auto; }
  .wiki-content code { background: #f6f8fa; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
</style>
"""


def render_wiki_page(wiki_root: Path, page_rel: str) -> str:
    """Return the full HTML (doc + sidebar + content) for a wiki page, or ''
    when the page does not exist (route handler turns '' into a 404)."""
    page = (wiki_root / page_rel).resolve()
    try:
        page.relative_to(wiki_root.resolve())
    except ValueError:
        return ""  # path traversal attempt
    if not page.exists() or not page.is_file() or page.suffix != ".md":
        return ""
    content_html = md_to_html(page.read_text(encoding="utf-8"))
    sidebar = render_wiki_sidebar(wiki_root)
    title = _page_title(page)
    return (
        "<!DOCTYPE html><html><head>"
        f"<title>{_html.escape(title)} — Archie Wiki</title>"
        f"{_WIKI_CSS}"
        "</head><body class='wiki'>"
        f"{sidebar}"
        f"<main class='wiki-content'>{content_html}</main>"
        "</body></html>"
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_viewer_wiki.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/viewer.py tests/test_viewer_wiki.py
git commit -m "feat(viewer): render wiki page with sidebar and styled content"
```

---

## Task 4: HTTP route + `--with-wiki-ui` flag

**Files:**
- Modify: `archie/standalone/viewer.py`
- Modify: `tests/test_viewer_wiki.py`

- [ ] **Step 1: Inspect current HTTP server setup**

Read the top of `archie/standalone/viewer.py` to understand how routes are dispatched. (Archie's viewer uses `http.server.BaseHTTPRequestHandler` — we extend the existing handler.)

```bash
grep -n "do_GET\|BaseHTTPRequestHandler\|ROUTES\|self.path" archie/standalone/viewer.py | head -20
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_viewer_wiki.py`:

```python
import http.server
import threading
import urllib.request


def test_http_route_wiki_page(tmp_path):
    # Prepare wiki.
    wiki = tmp_path / "wiki"
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
    wiki = tmp_path / "wiki"
    (wiki / "index.md").parent.mkdir(parents=True, exist_ok=True)
    (wiki / "index.md").write_text("# I\n")
    server = viewer.make_server(
        project_root=tmp_path, host="127.0.0.1", port=0, with_wiki_ui=False
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        # With wiki disabled, /wiki/ returns 404.
        import urllib.error
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/wiki/")
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        thread.join(timeout=2)
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/test_viewer_wiki.py -v -k http_route`
Expected: FAIL — `make_server` may already exist but does not accept `with_wiki_ui`.

- [ ] **Step 4: Extend the request handler and `make_server`**

This step edits whatever existing request-handler class viewer.py has. Locate it by pattern:

```bash
grep -n "class .*RequestHandler\|def do_GET" archie/standalone/viewer.py
```

At the top of `do_GET`, add early dispatch for `/wiki/`:

```python
        if self.server.with_wiki_ui and self.path.startswith("/wiki/"):
            self._handle_wiki()
            return
```

Define `_handle_wiki` on the same handler class:

```python
    def _handle_wiki(self):
        wiki_root = self.server.project_root / ".archie" / "wiki"
        if not wiki_root.exists():
            self.send_error(404, "Wiki not found — run /archie-deep-scan first.")
            return

        # JSON meta files
        if self.path.startswith("/wiki/_meta/"):
            meta_file = wiki_root / Path(self.path[len("/wiki/"):]).name
            if meta_file.exists():
                body = meta_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)
            return

        # Index when requesting /wiki/ or /wiki
        page_rel = self.path[len("/wiki/"):] or "index.md"
        if not page_rel.endswith(".md"):
            page_rel = page_rel.rstrip("/") + "/index.md" if page_rel else "index.md"

        html = render_wiki_page(wiki_root, page_rel)
        if not html:
            self.send_error(404, f"Wiki page not found: {page_rel}")
            return
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
```

Create or update `make_server` so it attaches `project_root` and `with_wiki_ui` to the `HTTPServer` instance (both must be accessible as `self.server.<attr>` inside the handler):

```python
import http.server as _http_server


def make_server(project_root: Path, host: str, port: int, with_wiki_ui: bool = False):
    """Factory used by viewer CLI and tests. Returns a configured HTTPServer."""
    server = _http_server.HTTPServer((host, port), _RequestHandler)
    server.project_root = Path(project_root)
    server.with_wiki_ui = with_wiki_ui
    return server
```

(`_RequestHandler` is the existing handler class. If the existing code already has a factory or a parametrized handler, adapt these hooks rather than duplicating.)

- [ ] **Step 5: Add CLI flag to the viewer entry point**

Near the CLI `argparse` in `viewer.py`:

```python
    parser.add_argument("--with-wiki-ui", action="store_true",
                        help="Serve .archie/wiki at /wiki/ (experimental).")
```

And when calling `make_server`:

```python
    server = make_server(
        project_root=project_root,
        host=args.host,
        port=args.port,
        with_wiki_ui=args.with_wiki_ui,
    )
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_viewer_wiki.py -v`
Expected: all tests pass (including both HTTP tests).

Also run the existing viewer tests to confirm no regressions:

```bash
python -m pytest tests/ -v -k viewer
```

- [ ] **Step 7: Commit**

```bash
git add archie/standalone/viewer.py tests/test_viewer_wiki.py
git commit -m "feat(viewer): serve .archie/wiki/ behind --with-wiki-ui flag"
```

---

## Task 5: NPM sync + manual smoke

**Files:**
- Modify: `npm-package/assets/viewer.py`

- [ ] **Step 1: Sync**

```bash
cp archie/standalone/viewer.py npm-package/assets/viewer.py
python3 scripts/verify_sync.py
```

Expected: exit 0.

- [ ] **Step 2: Manual smoke**

On a project with a populated `.archie/wiki/`:

```bash
python3 .archie/viewer.py --with-wiki-ui --port 8765 "$PWD" &
VIEWER_PID=$!
sleep 1
open http://127.0.0.1:8765/wiki/
# Or visit manually; verify:
#  - sidebar lists all page types
#  - clicking a link navigates correctly
#  - markdown renders (headings, lists, links, code)
#  - 404 for missing pages
kill $VIEWER_PID
```

- [ ] **Step 3: Commit**

```bash
git add npm-package/
git commit -m "chore(wiki): sync viewer wiki UI to npm-package assets"
```

---

## Task 6: Documentation + release note

**Files:**
- Modify: `docs/ARCHITECTURE.md` (brief note about wiki)
- Optionally: `README.md` (feature mention)

- [ ] **Step 1: Add a one-paragraph note to `docs/ARCHITECTURE.md`**

Near the section describing what `/archie-deep-scan` produces, add:

```markdown
### LLM Wiki (v1.0)

Deep-scan also generates a browsable wiki at `.archie/wiki/` with one markdown
page per decision, component, pattern, pitfall, and capability. Every page
ends with a `## Referenced by` section driven by `_meta/backlinks.json`, so
agents can traverse the architecture graph by following standard markdown
links. `/archie-scan` keeps the wiki fresh incrementally. Serve it through
the local viewer with `python3 .archie/viewer.py --with-wiki-ui`.

Feature flag: `ARCHIE_WIKI_ENABLED=false` disables all wiki generation.
```

- [ ] **Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs(wiki): note LLM Wiki in architecture overview"
```

---

## Self-review checklist

- [ ] Spec §3.5 (viewer integration) fully implemented: `/wiki/*` route, sidebar, 404 for missing, flag gating.
- [ ] `--with-wiki-ui` defaults OFF in v1.0 (per rollout plan in spec §11).
- [ ] Markdown renderer handles the formatting actually emitted by wiki_builder (headings, bullets, bold, inline code, fenced code, links). Extend if a future page type uses something else (tables/images — out of scope for v1.0).
- [ ] `_meta/*.json` served under `/wiki/_meta/` for potential future client-side consumers.
- [ ] No `TODO` or placeholder steps.
- [ ] Tests green: `python -m pytest tests/test_viewer_wiki.py -v`.
- [ ] `scripts/verify_sync.py` passes.
- [ ] Manual smoke confirms browseable UI works end-to-end.
