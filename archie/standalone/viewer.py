#!/usr/bin/env python3
"""Archie blueprint viewer — zero-dep local HTML inspector.

Run: python3 viewer.py /path/to/repo [--port PORT]
Opens a browser showing only Archie-generated output.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import html as _html
import http.server
import json
import os
import re
import re as _re
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from _common import _load_json  # noqa: E402

# ---------------------------------------------------------------------------
# Markdown → HTML renderer
# ---------------------------------------------------------------------------

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
    # Strip YAML frontmatter — leading '---\n...\n---\n' block.
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:]
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
        href = match.group(2).strip()
        # Block dangerous schemes. Localhost-only HTTP, but defensive defense-in-depth.
        if _re.match(r"^(javascript|data|vbscript):", href, _re.IGNORECASE):
            href = "#blocked"
        href_attr = _html.escape(href, quote=True)
        placeholders.append(f'<a href="{href_attr}">{_html.escape(match.group(1))}</a>')
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".archie", "venv",
              ".venv", "dist", "build", ".next", ".nuxt", "coverage",
              ".pytest_cache", ".mypy_cache"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _collect_folder_claude_mds(root: Path) -> dict[str, str]:
    result = {}
    for claude_md in root.rglob("CLAUDE.md"):
        if any(part in _SKIP_DIRS for part in claude_md.parts):
            continue
        rel = str(claude_md.relative_to(root))
        if rel == "CLAUDE.md":
            continue  # skip root — shown in generated-files tab
        result[rel] = _read_text(claude_md)
    return result


def _collect_generated_files(root: Path) -> dict[str, str]:
    """Collect only files that Archie generated."""
    files: dict[str, str] = {}
    # Root output files
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = root / name
        if p.exists():
            files[name] = _read_text(p)
    # Rule files
    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        for f in sorted(rules_dir.rglob("*")):
            if f.is_file():
                files[str(f.relative_to(root))] = _read_text(f)
    return files


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ArchieHandler(http.server.BaseHTTPRequestHandler):
    """Routes requests to API endpoints or serves the HTML page."""

    def log_message(self, fmt, *args):
        pass

    def _handle_wiki(self):
        if self.path == "/wiki":
            # Redirect bare /wiki to /wiki/ so relative paths in HTML resolve correctly.
            self.send_response(301)
            self.send_header("Location", "/wiki/")
            self.end_headers()
            return

        wiki_root = self.server.root / ".archie" / "wiki"
        if not wiki_root.exists():
            self.send_error(404, "Wiki not found — run /archie-deep-scan first.")
            return

        parsed = urlparse(self.path)
        path = parsed.path

        # JSON meta files
        if path.startswith("/wiki/_meta/"):
            meta_file = wiki_root / Path(path[len("/wiki/"):]).name
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
        page_rel = path[len("/wiki/"):] or "index.md"
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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        root: Path = self.server.root  # type: ignore[attr-defined]
        archie_dir = root / ".archie"

        if getattr(self.server, "with_wiki_ui", False) and (path == "/wiki" or path.startswith("/wiki/")):
            self._handle_wiki()
            return

        if path == "/":
            self._send_html(HTML_PAGE)

        elif path == "/api/wiki-enabled":
            self._send_json({"enabled": bool(getattr(self.server, "with_wiki_ui", False))})

        elif path == "/api/blueprint":
            self._send_json(_load_json(archie_dir / "blueprint.json"))

        elif path == "/api/rules":
            self._send_json(_load_json(archie_dir / "rules.json"))

        elif path == "/api/health":
            # Read full health data saved by scan/deep-scan
            data = _load_json(archie_dir / "health.json")
            if not data:
                # Fallback to history summary (no functions/waste detail)
                history = _load_json(archie_dir / "health_history.json")
                # Handle both formats: plain list or {"history": [...]}
                if isinstance(history, dict):
                    history = history.get("history", [])
                if isinstance(history, list) and history:
                    data = history[-1]
            self._send_json(data or {})

        elif path == "/api/health-history":
            data = _load_json(archie_dir / "health_history.json")
            # Handle both formats: plain list or {"history": [...]}
            if isinstance(data, dict):
                data = data.get("history", [])
            if not isinstance(data, list):
                data = []
            self._send_json(data)

        elif path == "/api/scan-reports":
            reports = []
            if archie_dir.is_dir():
                # Primary: scan_history/ directory (one file per scan)
                history_dir = archie_dir / "scan_history"
                if history_dir.is_dir():
                    for f in sorted(history_dir.glob("*.md"), reverse=True):
                        name = f"scan_history/{f.name}"
                        # New format: scan_NNN_YYYY-MM-DDTHHMM.md
                        m = re.search(r"(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})", f.name)
                        if m:
                            date_str = f"{m.group(1)} {m.group(2)}:{m.group(3)} UTC"
                        else:
                            # Old format: scan_NNN_YYYY-MM-DD.md
                            m = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
                            date_str = m.group(1) if m else ""
                        reports.append({"filename": name, "date": date_str})
                # Legacy: scan_report_*.md in .archie/ (older format)
                if not reports:
                    for f in sorted(archie_dir.glob("scan_report_*.md"), reverse=True):
                        name = f.name
                        m = re.search(r"scan_report_(\d{4}-\d{2}-\d{2})\.md$", name)
                        date_str = m.group(1) if m else ""
                        reports.append({"filename": name, "date": date_str})
                # Fallback: scan_report.md (no history dir, no dated files)
                if not reports:
                    sr = archie_dir / "scan_report.md"
                    if sr.exists():
                        content = _read_text(sr)
                        dm = re.search(r"(\d{4}-\d{2}-\d{2})", content)
                        date_str = dm.group(1) if dm else ""
                        reports.append({"filename": "scan_report.md", "date": date_str})
            self._send_json(reports)

        elif path.startswith("/api/scan-report/"):
            filename = path[len("/api/scan-report/"):]
            # Validate filename to prevent path traversal
            if not re.match(r"^(scan_history/)?scan[\w_\-]*\.md$", filename) or ".." in filename or "\\" in filename:
                self._send_error(400, "Invalid filename")
                return
            report_path = archie_dir / filename
            if not report_path.exists():
                self._send_error(404, "Report not found")
                return
            content = _read_text(report_path)
            self._send_json({"filename": filename, "content": content})

        elif path == "/api/drift":
            self._send_json(_load_json(archie_dir / "drift_report.json"))

        elif path == "/api/findings":
            data = _load_json(archie_dir / "findings.json")
            if isinstance(data, dict) and isinstance(data.get("findings"), list):
                self._send_json(data["findings"])
            elif isinstance(data, list):
                self._send_json(data)
            else:
                self._send_json([])

        elif path == "/api/generated-files":
            self._send_json(_collect_generated_files(root))

        elif path == "/api/folder-claude-mds":
            self._send_json(_collect_folder_claude_mds(root))

        elif path == "/api/ignored-rules":
            self._send_json(_load_json(archie_dir / "ignored_rules.json"))

        elif path == "/api/proposed-rules":
            self._send_json(_load_json(archie_dir / "proposed_rules.json"))

        elif path == "/api/dependency-graph":
            self._send_json(_load_json(archie_dir / "dependency_graph.json"))

        else:
            self._send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        root: Path = self.server.root  # type: ignore[attr-defined]

        if path == "/api/rules":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body)
            except (ValueError, json.JSONDecodeError):
                self._send_error(400, "Invalid JSON")
                return

            if not isinstance(data, dict) or "rules" not in data or not isinstance(data["rules"], list):
                self._send_error(400, "Body must have a 'rules' key with an array value")
                return

            rules_path = root / ".archie" / "rules.json"
            rules_path.parent.mkdir(parents=True, exist_ok=True)
            rules_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self._send_json({"ok": True})
        else:
            self._send_error(404, "Not found")

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, msg: str):
        body = json.dumps({"error": msg}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Embedded HTML — single-page app (placeholder, filled in subsequent tasks)
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archie Viewer</title>

<script src="https://cdn.tailwindcss.com" onerror="document.body.innerHTML='<h1>Failed to load Tailwind CSS. Check your internet connection.</h1>'"></script>
<script>
tailwind.config = {
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#023047', 50: '#e6f0f5', 100: '#b3d1e0', 200: '#80b3cc', 300: '#4d94b8', 400: '#1a76a3', 500: '#023047', 600: '#022a3f', 700: '#012337', 800: '#011d2f', 900: '#011627', 950: '#000d17' },
        teal: { DEFAULT: '#219ebc', 50: '#e8f5f8', 100: '#b8e1ea', 200: '#88cddc', 300: '#58b9ce', 400: '#38adc5', 500: '#219ebc', 600: '#1b8ea9', 700: '#167d96', 800: '#116d83', 900: '#0c5c70' },
        papaya: { DEFAULT: '#8ecae6', 50: '#f5fafd', 100: '#daeef7', 200: '#bfe2f1', 300: '#a4d6eb', 400: '#8ecae6', 500: '#6bb8d9', 600: '#4aa6cc', 700: '#3494bf', 800: '#2382b2', 900: '#1870a5' },
        tangerine: { DEFAULT: '#ffb703', 50: '#fff8e6', 100: '#ffebb3', 200: '#ffde80', 300: '#ffd14d', 400: '#ffc41a', 500: '#ffb703', 600: '#e6a503', 700: '#cc9202', 800: '#b38002', 900: '#996e01' },
        brandy: { DEFAULT: '#fb8500', 50: '#fff3e6', 100: '#fdd9b3', 200: '#fcbf80', 300: '#fba54d', 400: '#fb8b1a', 500: '#fb8500', 600: '#e27800', 700: '#c96a00', 800: '#b05d00', 900: '#974f00' },
      }
    }
  }
}
</script>

<script src="https://cdn.jsdelivr.net/npm/chart.js" onerror="console.warn('Chart.js failed to load — charts will be unavailable')"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js" onerror="console.warn('marked.js failed to load — markdown rendering will be unavailable')"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js" onerror="console.warn('mermaid failed to load — diagrams will be unavailable')"></script>
<script src="https://cdn.jsdelivr.net/npm/vis-network/standalone/umd/vis-network.min.js" onerror="console.warn('vis-network failed to load — dependency graph will be unavailable')"></script>

<style>
  /* Scrollbar styling */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #8ecae640; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #8ecae680; }

  /* Prose markdown styling */
  .prose-archie h1 { font-size: 1.5rem; font-weight: 700; margin-top: 1.5rem; margin-bottom: 0.75rem; }
  .prose-archie h2 { font-size: 1.25rem; font-weight: 700; margin-top: 1.25rem; margin-bottom: 0.5rem; }
  .prose-archie h3 { font-size: 1.1rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem; }
  .prose-archie p { margin-bottom: 0.5rem; line-height: 1.6; }
  .prose-archie ul { list-style-type: disc; padding-left: 1.5rem; margin-bottom: 0.5rem; }
  .prose-archie ol { list-style-type: decimal; padding-left: 1.5rem; margin-bottom: 0.5rem; }
  .prose-archie li { margin-bottom: 0.25rem; }
  .prose-archie code { background: #e6f0f5; padding: 0.15rem 0.35rem; border-radius: 0.25rem; font-size: 0.875em; }
  .prose-archie pre { background: #011627; color: #e6f0f5; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; margin-bottom: 0.75rem; }
  .prose-archie pre code { background: transparent; padding: 0; color: inherit; }
  .prose-archie blockquote { border-left: 3px solid #8ecae6; padding-left: 1rem; color: #4d94b8; margin-bottom: 0.75rem; }
  .prose-archie table { width: 100%; border-collapse: collapse; margin-bottom: 0.75rem; }
  .prose-archie th, .prose-archie td { border: 1px solid #b3d1e0; padding: 0.4rem 0.75rem; text-align: left; }
  .prose-archie th { background: #e6f0f5; font-weight: 600; }

  /* Tab button states */
  .tab-btn { color: rgba(2,48,71,0.4); border-color: transparent; cursor: pointer; background: none; }
  .tab-btn:hover { color: rgba(2,48,71,0.6); }
  .tab-btn.active { color: #219ebc; border-color: #219ebc; }

</style>
</head>

<body class="bg-gradient-to-br from-papaya-50 via-white to-teal-50/10 min-h-screen">

<!-- Header bar -->
<div class="border-b bg-white/50 px-8 py-4 flex items-center justify-between backdrop-blur-sm sticky top-0 z-20">
  <div class="flex items-center gap-4">
    <div class="p-2 rounded-2xl bg-white border border-papaya-400 shadow-sm">
      <span class="text-xl font-black text-teal">A</span>
    </div>
    <div>
      <h1 class="text-xl font-bold tracking-tight text-ink">Archie</h1>
      <p id="repoName" class="text-[10px] text-ink-300 font-bold uppercase tracking-widest"></p>
    </div>
  </div>
</div>

<!-- Tab bar -->
<div class="flex items-center gap-8 border-b border-papaya-300 bg-white/30 px-8 shrink-0">
  <button class="tab-btn active py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]" data-tab="dashboard">Dashboard</button>
  <button class="tab-btn py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]" data-tab="reports">Scan Reports</button>
  <button class="tab-btn py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]" data-tab="blueprint">Blueprint</button>
  <button class="tab-btn py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]" data-tab="rules">Rules</button>
  <button class="tab-btn py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]" data-tab="files">Files</button>
  <button class="tab-btn py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]" data-tab="dependencies">Dependencies</button>
  <button id="tab-btn-wiki" class="tab-btn py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px] hidden" data-tab="wiki">Wiki</button>
  <button class="tab-btn py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]" data-tab="workspace">Workspace</button>
</div>

<!-- Tab content containers -->
<div id="tab-dashboard" class="tab-content p-8 max-w-7xl mx-auto"></div>
<div id="tab-reports" class="tab-content hidden"></div>
<div id="tab-blueprint" class="tab-content hidden"></div>
<div id="tab-rules" class="tab-content hidden p-8 max-w-5xl mx-auto"></div>
<div id="tab-files" class="tab-content hidden"></div>
<div id="tab-dependencies" class="tab-content hidden" style="height: calc(100vh - 140px)"></div>
<div id="tab-wiki" class="tab-content hidden" style="height: calc(100vh - 140px)"></div>
<div id="tab-workspace" class="tab-content hidden p-8 max-w-7xl mx-auto"></div>

<script>
// ---------------------------------------------------------------------------
// Global data stores
// ---------------------------------------------------------------------------
let health = {}, healthHistory = [], scanReports = [], blueprint = {},
    rules = {}, ignoredRules = {}, generatedFiles = {}, folderMds = {},
    drift = {}, depGraph = {}, proposedRules = {}, findings = [];

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    btn.classList.add('active');
    const target = document.getElementById('tab-' + btn.dataset.tab);
    if (target) target.classList.remove('hidden');
    // Trigger render for the active tab
    const renderers = {
      dashboard: renderDashboard,
      reports: renderReports,
      blueprint: renderBlueprint,
      rules: renderRules,
      files: renderFiles,
      dependencies: renderDependencies,
      wiki: renderWiki,
      workspace: renderWorkspace
    };
    if (renderers[btn.dataset.tab]) renderers[btn.dataset.tab]();
  });
});

// Reveal the Wiki tab when the server reports the wiki UI is enabled
fetch('/api/wiki-enabled')
  .then(r => r.json())
  .then(d => {
    if (d && d.enabled) {
      const btn = document.getElementById('tab-btn-wiki');
      if (btn) btn.classList.remove('hidden');
    }
  })
  .catch(() => {});

// Lazy-load the wiki into an iframe on first activation, then keep it mounted
function renderWiki() {
  const el = document.getElementById('tab-wiki');
  if (el.dataset.loaded) return;
  el.dataset.loaded = '1';
  el.innerHTML = '<iframe src="/wiki/" style="border:0; width:100%; height:100%; display:block;" title="Archie Wiki"></iframe>';
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------
async function fetchJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.warn('Failed to fetch', url, e);
    return null;
  }
}

async function loadData() {
  const [h, hh, sr, bp, r, ir, gf, fm, dr, dg, pr, fnd] = await Promise.all([
    fetchJSON('/api/health'),
    fetchJSON('/api/health-history'),
    fetchJSON('/api/scan-reports'),
    fetchJSON('/api/blueprint'),
    fetchJSON('/api/rules'),
    fetchJSON('/api/ignored-rules'),
    fetchJSON('/api/generated-files'),
    fetchJSON('/api/folder-claude-mds'),
    fetchJSON('/api/drift'),
    fetchJSON('/api/dependency-graph'),
    fetchJSON('/api/proposed-rules'),
    fetchJSON('/api/findings'),
  ]);
  health = h || {};
  healthHistory = hh || [];
  scanReports = sr || [];
  blueprint = bp || {};
  rules = r || {};
  ignoredRules = ir || {};
  generatedFiles = gf || {};
  folderMds = fm || {};
  drift = dr || {};
  depGraph = dg || {};
  proposedRules = pr || {};
  findings = Array.isArray(fnd) ? fnd : [];

  // Set repo name
  const repoNameEl = document.getElementById('repoName');
  if (blueprint.meta && blueprint.meta.repository) {
    repoNameEl.textContent = blueprint.meta.repository;
  } else {
    repoNameEl.textContent = window.location.host;
  }

  renderDashboard();
}

// ---------------------------------------------------------------------------
// Render functions (placeholders — filled in tasks 3-7)
// ---------------------------------------------------------------------------
let _dashboardChart = null;
function renderDashboard() {
  const el = document.getElementById('tab-dashboard');
  if (!health || Object.keys(health).length === 0) {
    el.innerHTML = '<div class="flex items-center justify-center h-64"><div class="text-center"><p class="text-ink/40 text-lg mb-2">No health data available</p><p class="text-ink/30 text-sm">Run <code class="text-teal">/archie-scan</code> for a quick health check or <code class="text-teal">/archie-deep-scan</code> for a full baseline.</p></div></div>';
    return;
  }

  // Helpers
  const fmt = (v, d=2) => (v == null || isNaN(v)) ? '--' : Number(v).toFixed(d);
  const fmtInt = v => (v == null || isNaN(v)) ? '--' : Number(v).toLocaleString();
  const statusDot = (color) => '<span class="w-2 h-2 rounded-full inline-block ml-2" style="background:' + color + '"></span>';
  const threshColor = (v, lo, hi) => v < lo ? '#10b981' : v <= hi ? '#ffb703' : '#fb8500';

  // Compute deltas from healthHistory
  const prev = (healthHistory && healthHistory.length >= 2) ? healthHistory[healthHistory.length - 2] : null;
  const deltaStr = (cur, prevVal) => {
    if (prev == null || prevVal == null || cur == null) return '';
    const d = cur - prevVal;
    if (Math.abs(d) < 0.0001) return '<span class="text-xs mt-2 text-ink/40">no change</span>';
    const sign = d > 0 ? '+' : '';
    return '<span class="text-xs mt-2 text-ink/40">' + sign + d.toFixed(3) + '</span>';
  };
  const locDelta = () => {
    if (!prev || prev.total_loc == null || health.total_loc == null) return '';
    const d = health.total_loc - prev.total_loc;
    if (d === 0) return '<span class="text-xs mt-2 text-ink/40">no change</span>';
    const sign = d > 0 ? '+' : '';
    const pct = prev.total_loc ? ((d / prev.total_loc) * 100).toFixed(1) : '0.0';
    return '<span class="text-xs mt-2 text-ink/40">' + sign + fmtInt(d) + ' (' + sign + pct + '%)</span>';
  };

  // Card builder
  const card = (label, value, dotColor, delta) => {
    return '<div class="rounded-xl border border-papaya-400/60 bg-white p-5 shadow-sm flex-1 min-w-0">'
      + '<div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">' + label + '</div>'
      + '<div class="text-3xl font-black text-ink mt-1">' + value + statusDot(dotColor) + '</div>'
      + (delta ? '<div>' + delta + '</div>' : '')
      + '</div>';
  };

  const erosion = health.erosion != null ? health.erosion : 0;
  const gini = health.gini != null ? health.gini : 0;
  const top20 = health.top20_share != null ? health.top20_share : 0;
  const verbosity = health.verbosity != null ? health.verbosity : 0;
  const loc = health.total_loc != null ? health.total_loc : 0;

  // Top row cards
  let html = '<div class="flex gap-4 mb-6 flex-wrap">';
  html += card('Erosion', fmt(erosion), threshColor(erosion, 0.3, 0.5), deltaStr(erosion, prev && prev.erosion));
  html += card('Gini', fmt(gini), threshColor(gini, 0.4, 0.6), deltaStr(gini, prev && prev.gini));
  html += card('Top-20%', fmt(top20), threshColor(top20, 0.5, 0.7), deltaStr(top20, prev && prev.top20_share));
  html += card('Verbosity', fmt(verbosity, 3), threshColor(verbosity, 0.05, 0.15), deltaStr(verbosity, prev && prev.verbosity));
  html += card('LOC', fmtInt(loc), '#219ebc', locDelta());
  html += '</div>';

  // Metric legend
  html += '<div class="rounded-xl border border-papaya-400/60 bg-white/60 p-4 mb-6 text-xs text-ink/60">';
  html += '<div class="font-bold text-ink/80 mb-2 text-sm">What these metrics mean</div>';
  html += '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">';
  html += '<div><span class="font-bold text-ink/80">Erosion</span> — How many files break the expected structure (missing docs, inconsistent naming, no tests). Lower is better. <span class="text-teal">&lt;0.3 good</span>, <span class="text-tangerine">0.3–0.5 moderate</span>, <span class="text-brandy">&gt;0.5 high</span></div>';
  html += '<div><span class="font-bold text-ink/80">Gini</span> — How unevenly code is distributed across files. A high Gini means a few files hold most of the code (god-files). <span class="text-teal">&lt;0.4 good</span>, <span class="text-tangerine">0.4–0.6 moderate</span>, <span class="text-brandy">&gt;0.6 high</span></div>';
  html += '<div><span class="font-bold text-ink/80">Top-20%</span> — What share of total code lives in the largest 20% of files. High means code is concentrated in a few large files. <span class="text-teal">&lt;0.5 good</span>, <span class="text-tangerine">0.5–0.7 moderate</span>, <span class="text-brandy">&gt;0.7 high</span></div>';
  html += '<div><span class="font-bold text-ink/80">Verbosity</span> — Ratio of comment lines to code lines. Very high means over-documented or commented-out code. <span class="text-teal">&lt;0.05 good</span>, <span class="text-tangerine">0.05–0.15 moderate</span>, <span class="text-brandy">&gt;0.15 high</span></div>';
  html += '<div><span class="font-bold text-ink/80">LOC</span> — Total lines of code in the project (excluding blanks and comments). Not good or bad on its own — useful for tracking growth over time.</div>';
  html += '</div></div>';

  // Trend chart
  if (healthHistory && healthHistory.length > 0 && typeof Chart !== 'undefined') {
    html += '<div class="rounded-3xl border border-papaya-400/60 bg-white/60 p-6 shadow-inner mb-6">';
    html += '<div class="text-sm font-bold text-ink mb-4">Health Trend</div>';
    html += '<canvas id="dashTrendChart" height="100"></canvas>';
    html += '</div>';
  }

  // Bottom panels
  html += '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">';

  // Left: Top Complex Functions
  html += '<div class="rounded-xl border border-papaya-400/60 bg-white p-5">';
  html += '<div class="text-sm font-bold text-ink mb-4">Top Complex Functions</div>';
  const fns = (health.functions || []).slice().sort((a, b) => (b.cc || 0) - (a.cc || 0)).slice(0, 10);
  if (fns.length === 0) {
    html += '<p class="text-xs text-ink/40">No function data. Run <code class="text-teal">/archie-scan</code> to analyze.</p>';
  } else {
    html += '<table class="w-full text-xs">';
    html += '<thead><tr>'
      + '<th class="text-left py-2 px-3 text-[10px] font-bold uppercase tracking-widest text-ink/40 border-b border-papaya-300/50">Function</th>'
      + '<th class="text-left py-2 px-3 text-[10px] font-bold uppercase tracking-widest text-ink/40 border-b border-papaya-300/50">File</th>'
      + '<th class="text-left py-2 px-3 text-[10px] font-bold uppercase tracking-widest text-ink/40 border-b border-papaya-300/50">Branching Complexity</th>'
      + '</tr></thead><tbody>';
    fns.forEach(fn => {
      const cc = fn.cc || 0;
      const ccColor = cc > 15 ? '#fb8500' : cc > 10 ? '#ffb703' : '#219ebc';
      html += '<tr>'
        + '<td class="py-2 px-3 border-b border-papaya-100 font-mono">' + (fn.name || '--') + '</td>'
        + '<td class="py-2 px-3 border-b border-papaya-100 text-ink/60 truncate max-w-[200px]" title="' + (fn.path || '') + '">' + (fn.path || '--') + '</td>'
        + '<td class="py-2 px-3 border-b border-papaya-100 font-bold" style="color:' + ccColor + '">' + cc + '</td>'
        + '</tr>';
    });
    html += '</tbody></table>';
  }
  html += '</div>';

  // Right: Abstraction Waste
  html += '<div class="rounded-xl border border-papaya-400/60 bg-white p-5">';
  html += '<div class="text-sm font-bold text-ink mb-4">Abstraction Waste</div>';
  const waste = health.waste || {};
  const smcCount = waste.single_method_class_count || 0;
  const tfCount = waste.tiny_function_count || 0;

  html += '<div class="grid grid-cols-2 gap-4 mb-4">';
  html += '<div><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">Single-Method Classes</div>'
    + '<div class="text-3xl font-black text-ink mt-1">' + smcCount + '</div></div>';
  html += '<div><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">Tiny Functions</div>'
    + '<div class="text-3xl font-black text-ink mt-1">' + tfCount + '</div></div>';
  html += '</div>';

  // Single-method classes list
  const smcList = waste.single_method_classes || [];
  if (smcList.length > 0) {
    html += '<details class="mb-3"><summary class="text-xs font-bold text-ink/60 cursor-pointer">Single-Method Classes (' + smcList.length + ')</summary>';
    html += '<ul class="mt-2 space-y-1">';
    smcList.slice(0, 5).forEach(item => {
      const name = typeof item === 'string' ? item : (item.name || item.class_name || '--');
      const path = typeof item === 'string' ? '' : (item.path || item.file || '');
      html += '<li class="text-xs text-ink/60"><span class="font-mono">' + name + '</span>'
        + (path ? ' <span class="text-ink/30">' + path + '</span>' : '') + '</li>';
    });
    if (smcList.length > 5) html += '<li class="text-xs text-ink/30">... and ' + (smcList.length - 5) + ' more</li>';
    html += '</ul></details>';
  } else {
    html += '<p class="text-xs text-ink/30 mb-3">Single-method classes: None detected</p>';
  }

  // Tiny functions list
  const tfList = waste.tiny_functions || [];
  if (tfList.length > 0) {
    html += '<details><summary class="text-xs font-bold text-ink/60 cursor-pointer">Tiny Functions (' + tfList.length + ')</summary>';
    html += '<ul class="mt-2 space-y-1">';
    tfList.slice(0, 5).forEach(item => {
      const name = typeof item === 'string' ? item : (item.name || '--');
      const path = typeof item === 'string' ? '' : (item.path || item.file || '');
      html += '<li class="text-xs text-ink/60"><span class="font-mono">' + name + '</span>'
        + (path ? ' <span class="text-ink/30">' + path + '</span>' : '') + '</li>';
    });
    if (tfList.length > 5) html += '<li class="text-xs text-ink/30">... and ' + (tfList.length - 5) + ' more</li>';
    html += '</ul></details>';
  } else {
    html += '<p class="text-xs text-ink/30">Tiny functions: None detected</p>';
  }

  html += '</div>';
  html += '</div>';  // close grid

  // --- Drift Findings panel (from deep scan) ---
  const driftCategories = [
    { key: 'pattern_divergences', label: 'Pattern Divergences', color: '#ffb703' },
    { key: 'naming_violations', label: 'Naming Violations', color: '#219ebc' },
    { key: 'dependency_violations', label: 'Dependency Violations', color: '#fb8500' },
    { key: 'structural_outliers', label: 'Structural Outliers', color: '#023047' },
    { key: 'antipattern_clusters', label: 'Anti-pattern Clusters', color: '#fb8500' },
    { key: 'deep_findings', label: 'Deep Architectural Findings (AI)', color: '#fb8500' }
  ];
  const allDriftFindings = [];
  driftCategories.forEach(cat => {
    (drift[cat.key] || []).forEach(f => allDriftFindings.push({ ...f, _category: cat.label, _color: cat.color }));
  });

  if (allDriftFindings.length > 0) {
    html += '<div class="rounded-xl border border-papaya-400/60 bg-white p-5 mt-6">';
    html += '<div class="text-sm font-bold text-ink mb-4">Drift Findings <span class="bg-brandy/10 text-brandy text-xs font-bold px-2 py-0.5 rounded-full ml-2">' + allDriftFindings.length + '</span></div>';

    // Group by severity: errors first, then warnings
    const errors = allDriftFindings.filter(f => f.severity === 'error');
    const warns = allDriftFindings.filter(f => f.severity !== 'error');

    function renderFinding(f) {
      const sevBadge = f.severity === 'error'
        ? '<span class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-brandy/10 text-brandy">error</span>'
        : '<span class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-tangerine/10 text-tangerine">warn</span>';
      const catBadge = '<span class="text-[10px] font-bold text-ink/30 uppercase tracking-wider ml-2">' + esc(f._category) + '</span>';
      const file = f.file || f.folder || f.location || '';
      const msg = f.message || f.finding || f.description || '';
      const evidence = f.evidence || f.decision_or_pattern || '';
      return '<div class="py-3 border-b border-papaya-100 last:border-0">'
        + '<div class="flex items-center gap-2 mb-1">' + sevBadge + catBadge
        + (file ? ' <code class="text-[10px] text-teal ml-auto">' + esc(file) + '</code>' : '') + '</div>'
        + '<p class="text-xs text-ink">' + esc(msg) + '</p>'
        + (evidence ? '<p class="text-[10px] text-ink/40 mt-1">Evidence: ' + esc(evidence) + '</p>' : '')
        + '</div>';
    }

    errors.forEach(f => { html += renderFinding(f); });
    warns.forEach(f => { html += renderFinding(f); });
    html += '</div>';
  } else if (drift && drift.summary) {
    html += '<div class="rounded-xl border border-papaya-400/60 bg-white p-5 mt-6">';
    html += '<div class="text-sm font-bold text-ink mb-2">Drift Findings</div>';
    html += '<p class="text-xs text-ink/40">No drift findings. Drift detection requires a blueprint from <code class="text-teal">/archie-deep-scan</code>.</p>';
    html += '</div>';
  }

  el.innerHTML = html;

  // Render Chart.js trend chart
  if (healthHistory && healthHistory.length > 0 && typeof Chart !== 'undefined') {
    const canvas = document.getElementById('dashTrendChart');
    if (canvas) {
      if (_dashboardChart) { _dashboardChart.destroy(); _dashboardChart = null; }
      const labels = healthHistory.map(h => {
        if (!h.timestamp) return '?';
        const d = new Date(h.timestamp);
        return String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
      });
      _dashboardChart = new Chart(canvas, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            { label: 'Erosion', data: healthHistory.map(h => h.erosion), borderColor: '#fb8500', backgroundColor: 'rgba(251,133,0,0.1)', yAxisID: 'y', tension: 0.3, pointRadius: 3, fill: false },
            { label: 'Gini', data: healthHistory.map(h => h.gini), borderColor: '#023047', backgroundColor: 'rgba(2,48,71,0.1)', yAxisID: 'y', tension: 0.3, pointRadius: 3, fill: false },
            { label: 'Verbosity', data: healthHistory.map(h => h.verbosity), borderColor: '#219ebc', backgroundColor: 'rgba(33,158,188,0.1)', yAxisID: 'y', tension: 0.3, pointRadius: 3, fill: false },
            { label: 'LOC', data: healthHistory.map(h => h.total_loc), borderColor: '#ffb703', backgroundColor: 'rgba(255,183,3,0.15)', yAxisID: 'y1', tension: 0.3, pointRadius: 3, type: 'bar', borderWidth: 1 }
          ]
        },
        options: {
          responsive: true,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: { type: 'linear', position: 'left', min: 0, max: 1, title: { display: true, text: 'Score (0-1)' },
              ticks: { font: { size: 10 } } },
            y1: { type: 'linear', position: 'right', title: { display: true, text: 'LOC' },
              grid: { drawOnChartArea: false }, ticks: { font: { size: 10 } } }
          },
          plugins: { legend: { labels: { font: { size: 11 } } } }
        }
      });
    }
  }
}

function renderReports() {
  const el = document.getElementById('tab-reports');
  if (!scanReports || scanReports.length === 0) {
    el.innerHTML = '<div class="flex items-center justify-center h-full"><p class="text-ink/40 text-lg">No scan reports found. Run <code>/archie-scan</code> first.</p></div>';
    return;
  }

  const reportCache = {};
  let activeReport = null;

  function formatDate(dateStr) {
    if (!dateStr) return 'Unknown';
    // Check if date includes time (e.g., "2026-04-12 15:23 UTC")
    const timeMatch = dateStr.match(/(\d{4}-\d{2}-\d{2})\s+(\d{2}):(\d{2})/);
    if (timeMatch) {
      const d = new Date(timeMatch[1] + 'T' + timeMatch[2] + ':' + timeMatch[3] + ':00Z');
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' }) + ' UTC';
    }
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function buildSidebar() {
    return scanReports.map((r, i) => {
      const isActive = r.filename === activeReport;
      const isLatest = i === 0;
      const activeClasses = 'bg-teal/5 text-teal font-bold';
      const inactiveClasses = 'text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium';
      return '<button data-report="' + r.filename + '" class="block w-full text-left px-3 py-2.5 rounded-lg transition-all duration-200 cursor-pointer text-sm ' + (isActive ? activeClasses : inactiveClasses) + '">'
        + formatDate(r.date)
        + (isLatest ? ' <span class="bg-teal text-white text-[9px] px-1.5 py-0.5 rounded-full font-bold ml-2 uppercase">Latest</span>' : '')
        + '</button>';
    }).join('');
  }

  function renderLayout() {
    el.innerHTML = '<div class="flex gap-6 h-[calc(100vh-140px)] p-8 max-w-7xl mx-auto">'
      + '<div class="w-64 flex-shrink-0 overflow-y-auto pr-4">'
        + '<div class="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-4">Scan History</div>'
        + '<nav id="reports-nav">' + buildSidebar() + '</nav>'
      + '</div>'
      + '<div id="report-content" class="flex-1 overflow-y-auto bg-white/60 border border-papaya-400/60 rounded-3xl shadow-inner p-10">'
        + '<p class="text-ink/40">Select a report...</p>'
      + '</div>'
    + '</div>';

    el.querySelectorAll('[data-report]').forEach(btn => {
      btn.addEventListener('click', () => selectReport(btn.getAttribute('data-report')));
    });
  }

  function selectReport(filename) {
    activeReport = filename;
    document.getElementById('reports-nav').innerHTML = buildSidebar();
    el.querySelectorAll('[data-report]').forEach(btn => {
      btn.addEventListener('click', () => selectReport(btn.getAttribute('data-report')));
    });

    const contentEl = document.getElementById('report-content');

    if (reportCache[filename]) {
      contentEl.innerHTML = '<div class="prose-archie">' + (window.marked ? marked.parse(reportCache[filename]) : reportCache[filename]) + '</div>';
      return;
    }

    contentEl.innerHTML = '<p class="text-ink/40 animate-pulse">Loading report...</p>';

    fetch('/api/scan-report/' + filename)
      .then(r => r.json())
      .then(data => {
        reportCache[filename] = data.content;
        if (activeReport === filename) {
          contentEl.innerHTML = '<div class="prose-archie">' + (window.marked ? marked.parse(data.content) : data.content) + '</div>';
        }
      })
      .catch(() => {
        if (activeReport === filename) {
          contentEl.innerHTML = '<p class="text-red-500">Failed to load report.</p>';
        }
      });
  }

  renderLayout();
  selectReport(scanReports[0].filename);
}

function esc(s) { if (s == null) return ''; const d = document.createElement('div'); d.textContent = String(s); return d.innerHTML; }

// Render a 4-field finding/pitfall card (problem_statement, evidence, root_cause,
// fix_direction). Falls back to the legacy {title/area, description, recommendation,
// stems_from} shape so bundles written before the schema change still render.
function renderFourFieldItem(item) {
  const sev = (item.severity || 'warn').toLowerCase();
  const sevColor = sev === 'error' ? 'brandy' : (sev === 'info' ? 'teal' : 'tangerine');
  const problem = item.problem_statement || item.title || item.area || '';
  const evidence = Array.isArray(item.evidence) ? item.evidence : [];
  const rootCause = item.root_cause || '';
  const fix = item.fix_direction;
  const appliesTo = Array.isArray(item.applies_to) ? item.applies_to : [];
  const legacyDesc = !item.problem_statement ? (item.description || '') : '';
  const legacyRec = !item.problem_statement ? (item.recommendation || '') : '';

  let c = '<div class="border-l-[3px] border-' + sevColor + ' pl-4 py-2 mb-4">';
  c += '<div class="flex items-start justify-between gap-3">';
  c += '<div class="font-bold text-sm text-ink flex-1">' + esc(problem) + '</div>';
  c += '<div class="flex items-center gap-2 shrink-0">';
  c += '<span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-' + sevColor + '/10 text-' + sevColor + '">' + esc(sev) + '</span>';
  if (item.status && item.status !== 'active') c += '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal/10 text-teal">' + esc(item.status) + '</span>';
  if (item.id) c += '<span class="text-[10px] font-mono text-ink/40">' + esc(item.id) + '</span>';
  c += '</div></div>';

  if (legacyDesc) c += '<div class="text-xs text-ink/70 mt-1.5">' + esc(legacyDesc) + '</div>';
  if (legacyRec) c += '<div class="text-xs text-teal mt-1">' + esc(legacyRec) + '</div>';

  if (evidence.length) {
    c += '<div class="mt-2"><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40 mb-1">Evidence</div>';
    c += '<ul class="text-xs text-ink/70 space-y-0.5 list-disc list-inside">';
    evidence.forEach(e => { c += '<li>' + esc(e) + '</li>'; });
    c += '</ul></div>';
  }
  if (rootCause) {
    c += '<div class="mt-2"><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40 mb-1">Root Cause</div>';
    c += '<div class="text-xs text-ink/70">' + esc(rootCause) + '</div></div>';
  }
  if (Array.isArray(fix) && fix.length) {
    c += '<div class="mt-2"><div class="text-[10px] font-bold uppercase tracking-widest text-teal mb-1">Fix Direction</div>';
    c += '<ol class="text-xs text-ink/70 space-y-0.5 list-decimal list-inside">';
    fix.forEach(step => { c += '<li>' + esc(step) + '</li>'; });
    c += '</ol></div>';
  } else if (typeof fix === 'string' && fix) {
    c += '<div class="mt-2"><div class="text-[10px] font-bold uppercase tracking-widest text-teal mb-1">Fix Direction</div>';
    c += '<div class="text-xs text-ink/70">' + esc(fix) + '</div></div>';
  }

  const footer = [];
  if (typeof item.confidence === 'number') footer.push('confidence: ' + item.confidence);
  if (appliesTo.length) footer.push('Applies to: ' + appliesTo.map(a => esc(a)).join(', '));
  if (item.pitfall_id) footer.push('Pitfall: ' + esc(item.pitfall_id));
  if (footer.length) c += '<div class="text-[10px] text-ink/40 mt-2">' + footer.join(' · ') + '</div>';

  c += '</div>';
  return c;
}

function renderBlueprint() {
  const el = document.getElementById('tab-blueprint');
  if (!blueprint || Object.keys(blueprint).length === 0) {
    let hint = '<div class="flex items-center justify-center h-full"><div class="text-center max-w-md">';
    hint += '<p class="text-ink/40 text-lg mb-3">Blueprint requires <code class="text-teal">/archie-deep-scan</code></p>';
    hint += '<p class="text-ink/30 text-sm mb-4">The blueprint contains architectural decisions, component boundaries, trade-offs, and pitfalls — produced by the full multi-agent analysis.</p>';
    const available = [];
    if (health && Object.keys(health).length) available.push('Dashboard (health scores)');
    if (scanReports && scanReports.length) available.push('Scan Reports');
    if (rules && ((rules.rules && rules.rules.length) || (Array.isArray(rules) && rules.length))) available.push('Rules');
    if (depGraph && depGraph.nodes && depGraph.nodes.length) available.push('Dependencies (graph)');
    if (available.length) {
      hint += '<p class="text-ink/40 text-sm">Available now from <code class="text-teal">/archie-scan</code>:</p>';
      hint += '<ul class="text-ink/50 text-sm mt-1 text-left inline-block">';
      available.forEach(a => { hint += '<li class="py-0.5">&#10003; ' + a + '</li>'; });
      hint += '</ul>';
    }
    hint += '</div></div>';
    el.innerHTML = hint;
    return;
  }

  // --- Section definitions ---
  const sections = [];
  const bp = blueprint;
  const meta = bp.meta || {};
  const comp = Array.isArray(bp.components) ? { components: bp.components } : (bp.components || {});
  const dec = bp.decisions || {};
  const comm = bp.communication || {};
  const tech = bp.technology || {};
  const fe = bp.frontend;
  const dep = bp.deployment || {};
  const pits = bp.pitfalls;
  const impl = bp.implementation_guidelines;
  const devRules = bp.development_rules;
  const diagram = bp.architecture_diagram;

  if (meta.executive_summary || meta.architecture_style) sections.push({ id: 'summary', label: 'Executive Summary' });
  if (comp.components && comp.components.length) sections.push({ id: 'components', label: 'Components' });
  if (dec.architectural_style || (dec.key_decisions && dec.key_decisions.length)) sections.push({ id: 'decisions', label: 'Decisions' });
  if (dec.trade_offs && dec.trade_offs.length) sections.push({ id: 'tradeoffs', label: 'Trade-offs' });
  if ((comm.patterns && comm.patterns.length) || (comm.integrations && comm.integrations.length)) sections.push({ id: 'communication', label: 'Communication' });
  if (tech.stack && tech.stack.length) sections.push({ id: 'technology', label: 'Technology' });
  if (fe && (fe.framework || fe.rendering_strategy || fe.styling)) sections.push({ id: 'frontend', label: 'Frontend' });
  if (dep.runtime_environment || (dep.compute_services && dep.compute_services.length) || (dep.ci_cd && dep.ci_cd.length)) sections.push({ id: 'deployment', label: 'Deployment' });
  if (findings && findings.length) sections.push({ id: 'problems', label: 'Architectural Problems' });
  if (pits && pits.length) sections.push({ id: 'pitfalls', label: 'Pitfalls' });
  if (impl && impl.length) sections.push({ id: 'guidelines', label: 'Guidelines' });
  if (devRules && devRules.length) sections.push({ id: 'devrules', label: 'Dev Rules' });
  if (diagram) sections.push({ id: 'diagram', label: 'Diagram' });

  let activeSection = sections.length > 0 ? sections[0].id : '';

  // --- Table helpers ---
  const th = (text) => '<th class="text-left py-2 px-3 text-[10px] font-bold uppercase tracking-widest text-ink/40 border-b border-papaya-300/50">' + esc(text) + '</th>';
  const td = (text, extra) => '<td class="py-2 px-3 border-b border-papaya-100' + (extra ? ' ' + extra : '') + '">' + esc(text) + '</td>';

  // --- Card builder ---
  function bpCard(id, title, count, contentHtml, hint) {
    const countBadge = count != null ? ' <span class="bg-teal/10 text-teal text-xs font-bold px-2 py-0.5 rounded-full ml-2">' + count + '</span>' : '';
    const hintIcon = hint
      ? ' <span class="inline-flex items-center justify-center w-4 h-4 rounded-full bg-ink/10 text-ink/40 text-[10px] font-black align-middle ml-1 cursor-help" title="' + esc(hint) + '" onclick="event.stopPropagation()">?</span>'
      : '';
    return '<div id="bp-' + id + '" class="mb-6">'
      + '<div class="rounded-xl border border-papaya-400/60 bg-white overflow-hidden">'
        + '<div class="px-5 py-4 font-bold text-ink flex items-center justify-between cursor-pointer hover:bg-papaya-50 transition-colors" onclick="this.nextElementSibling.classList.toggle(\'hidden\')">'
          + '<span>' + esc(title) + countBadge + hintIcon + '</span>'
          + '<span class="text-ink/30 text-xs">&#9660;</span>'
        + '</div>'
        + '<div class="px-5 py-4 border-t border-papaya-300/50">'
          + contentHtml
        + '</div>'
      + '</div>'
    + '</div>';
  }

  // --- Render sections ---
  function renderSections() {
    let html = '';

    // Executive Summary
    if (sections.find(s => s.id === 'summary')) {
      let c = '';
      if (meta.executive_summary) c += '<p class="text-sm text-ink/80 leading-relaxed">' + esc(meta.executive_summary) + '</p>';
      if (meta.architecture_style) c += '<div class="mt-3"><span class="bg-teal/10 text-teal text-xs font-bold px-2.5 py-1 rounded-full">' + esc(meta.architecture_style) + '</span></div>';
      html += bpCard('summary', 'Executive Summary', null, c);
    }

    // Components
    if (sections.find(s => s.id === 'components')) {
      const comps = comp.components;
      let c = '<table class="w-full text-xs"><thead><tr>' + th('Name') + th('Location') + th('Responsibility') + th('Dependencies') + '</tr></thead><tbody>';
      comps.forEach(cm => {
        const deps = (cm.depends_on || []).join(', ');
        c += '<tr>' + td(cm.name || '--') + '<td class="py-2 px-3 border-b border-papaya-100 font-mono text-ink/60">' + esc(cm.location || cm.path || '--') + '</td>' + td(cm.responsibility || cm.role || '--') + td(deps || '--') + '</tr>';
      });
      c += '</tbody></table>';
      html += bpCard('components', 'Components', comps.length, c);
    }

    // Decisions
    if (sections.find(s => s.id === 'decisions')) {
      let c = '';
      const as = dec.architectural_style;
      if (as) {
        c += '<div class="rounded-lg border border-teal/30 bg-teal/5 p-4 mb-4">';
        c += '<div class="font-bold text-sm text-ink">' + esc(as.title || 'Architectural Style') + '</div>';
        c += '<div class="text-sm text-teal font-bold mt-1">' + esc(as.chosen || as.style || '') + '</div>';
        if (as.rationale || as.details) c += '<div class="text-xs text-ink/60 mt-1">' + esc(as.rationale || as.details) + '</div>';
        if (as.confidence) c += '<div class="text-xs text-ink/40 mt-1">Confidence: ' + as.confidence + '</div>';
        if (as.alternatives_rejected && as.alternatives_rejected.length) {
          c += '<div class="text-xs text-ink/40 mt-2">Rejected: ' + as.alternatives_rejected.map(a => esc(a)).join(', ') + '</div>';
        }
        c += '</div>';
      }
      const kd = dec.key_decisions || [];
      kd.forEach(d => {
        c += '<div class="border-l-[3px] border-tangerine pl-4 py-2 mb-3">';
        c += '<div class="font-bold text-sm text-ink">' + esc(d.title || '') + '</div>';
        c += '<div class="text-xs text-teal font-semibold mt-0.5">' + esc(d.chosen || '') + '</div>';
        if (d.rationale) c += '<div class="text-xs text-ink/60 mt-1">' + esc(d.rationale) + '</div>';
        c += '</div>';
      });
      html += bpCard('decisions', 'Decisions', kd.length + (dec.architectural_style ? 1 : 0), c);
    }

    // Trade-offs
    if (sections.find(s => s.id === 'tradeoffs')) {
      const toffs = dec.trade_offs;
      let c = '';
      toffs.forEach(t => {
        c += '<div class="mb-4 p-3 rounded-lg bg-papaya-100/50">';
        c += '<div class="text-sm"><span class="font-bold text-ink">Accept:</span> <span class="text-ink/80">' + esc(t.accept || '') + '</span></div>';
        c += '<div class="text-sm mt-1"><span class="font-bold text-teal">Benefit:</span> <span class="text-ink/80">' + esc(t.benefit || '') + '</span></div>';
        if (t.caused_by) c += '<div class="text-xs text-ink/50 mt-1">Caused by: ' + esc(t.caused_by) + '</div>';
        if (t.violation_signals && t.violation_signals.length) {
          c += '<div class="mt-2 flex flex-wrap gap-1">';
          t.violation_signals.forEach(vs => {
            c += '<span class="bg-brandy/10 text-brandy text-[10px] font-bold px-2 py-0.5 rounded-full">' + esc(vs) + '</span>';
          });
          c += '</div>';
        }
        c += '</div>';
      });
      html += bpCard('tradeoffs', 'Trade-offs', toffs.length, c);
    }

    // Communication
    if (sections.find(s => s.id === 'communication')) {
      let c = '';
      const pats = comm.patterns || [];
      if (pats.length) {
        c += '<div class="mb-4">';
        c += '<div class="text-xs font-bold uppercase tracking-widest text-ink/40 mb-2">Patterns</div>';
        pats.forEach(p => {
          c += '<div class="mb-3 p-3 rounded-lg bg-papaya-100/30">';
          c += '<div class="font-bold text-sm text-ink">' + esc(p.name || '') + '</div>';
          if (p.when_to_use) c += '<div class="text-xs text-ink/60 mt-1"><span class="font-semibold">When:</span> ' + esc(p.when_to_use) + '</div>';
          if (p.how_it_works) c += '<div class="text-xs text-ink/60 mt-1"><span class="font-semibold">How:</span> ' + esc(p.how_it_works) + '</div>';
          c += '</div>';
        });
        c += '</div>';
      }
      const ints = comm.integrations || [];
      if (ints.length) {
        c += '<div class="text-xs font-bold uppercase tracking-widest text-ink/40 mb-2">Integrations</div>';
        c += '<table class="w-full text-xs"><thead><tr>' + th('Service') + th('Purpose') + th('Integration Point') + '</tr></thead><tbody>';
        ints.forEach(ig => {
          c += '<tr>' + td(ig.service || '--') + td(ig.purpose || '--') + td(ig.integration_point || '--') + '</tr>';
        });
        c += '</tbody></table>';
      }
      html += bpCard('communication', 'Communication', pats.length + ints.length, c);
    }

    // Technology
    if (sections.find(s => s.id === 'technology')) {
      let c = '<table class="w-full text-xs"><thead><tr>' + th('Category') + th('Name') + th('Version') + th('Purpose') + '</tr></thead><tbody>';
      (tech.stack || []).forEach(s => {
        c += '<tr>' + td(s.category || '--') + '<td class="py-2 px-3 border-b border-papaya-100 font-bold">' + esc(s.name || '--') + '</td>' + td(s.version || '--') + td(s.purpose || '--') + '</tr>';
      });
      c += '</tbody></table>';
      const rc = tech.run_commands;
      if (rc && Object.keys(rc).length) {
        c += '<div class="mt-4"><div class="text-xs font-bold uppercase tracking-widest text-ink/40 mb-2">Run Commands</div>';
        c += '<div class="font-mono text-xs bg-ink/5 rounded-lg p-3 space-y-1">';
        Object.entries(rc).forEach(([k, v]) => {
          c += '<div><span class="text-teal font-bold">' + esc(k) + ':</span> <span class="text-ink/70">' + esc(v) + '</span></div>';
        });
        c += '</div></div>';
      }
      html += bpCard('technology', 'Technology', (tech.stack || []).length, c);
    }

    // Frontend
    if (sections.find(s => s.id === 'frontend')) {
      let c = '<div class="grid grid-cols-2 gap-4 mb-4">';
      if (fe.framework) c += '<div><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">Framework</div><div class="text-sm font-bold text-ink mt-0.5">' + esc(fe.framework) + '</div></div>';
      if (fe.rendering_strategy) c += '<div><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">Rendering</div><div class="text-sm font-bold text-ink mt-0.5">' + esc(fe.rendering_strategy) + '</div></div>';
      if (fe.styling) c += '<div><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">Styling</div><div class="text-sm font-bold text-ink mt-0.5">' + esc(fe.styling) + '</div></div>';
      if (fe.state_management) c += '<div><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">State Management</div><div class="text-sm font-bold text-ink mt-0.5">' + esc(fe.state_management) + '</div></div>';
      c += '</div>';
      if (fe.ui_components && fe.ui_components.length) {
        c += '<div class="text-xs font-bold uppercase tracking-widest text-ink/40 mb-2">UI Components</div>';
        c += '<div class="flex flex-wrap gap-1.5">';
        fe.ui_components.forEach(uc => {
          c += '<span class="bg-teal/10 text-teal text-[10px] font-bold px-2 py-0.5 rounded-full">' + esc(typeof uc === 'string' ? uc : uc.name || uc) + '</span>';
        });
        c += '</div>';
      }
      html += bpCard('frontend', 'Frontend', null, c);
    }

    // Deployment
    if (sections.find(s => s.id === 'deployment')) {
      let c = '<div class="grid grid-cols-2 gap-4 mb-4">';
      if (dep.runtime_environment) c += '<div><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">Runtime</div><div class="text-sm font-bold text-ink mt-0.5">' + esc(dep.runtime_environment) + '</div></div>';
      if (dep.container_runtime) c += '<div><div class="text-[10px] font-bold uppercase tracking-widest text-ink/40">Container Runtime</div><div class="text-sm font-bold text-ink mt-0.5">' + esc(dep.container_runtime) + '</div></div>';
      c += '</div>';
      if (dep.compute_services && dep.compute_services.length) {
        c += '<div class="mt-3"><div class="text-xs font-bold uppercase tracking-widest text-ink/40 mb-1">Compute Services</div>';
        c += '<div class="flex flex-wrap gap-1.5">';
        dep.compute_services.forEach(cs => { c += '<span class="bg-teal/10 text-teal text-[10px] font-bold px-2 py-0.5 rounded-full">' + esc(cs) + '</span>'; });
        c += '</div></div>';
      }
      if (dep.ci_cd && dep.ci_cd.length) {
        c += '<div class="mt-3"><div class="text-xs font-bold uppercase tracking-widest text-ink/40 mb-1">CI/CD</div>';
        c += '<div class="flex flex-wrap gap-1.5">';
        dep.ci_cd.forEach(ci => { c += '<span class="bg-tangerine/10 text-tangerine text-[10px] font-bold px-2 py-0.5 rounded-full">' + esc(ci) + '</span>'; });
        c += '</div></div>';
      }
      if (dep.distribution && dep.distribution.length) {
        c += '<div class="mt-3"><div class="text-xs font-bold uppercase tracking-widest text-ink/40 mb-1">Distribution</div>';
        c += '<div class="flex flex-wrap gap-1.5">';
        dep.distribution.forEach(d => { c += '<span class="bg-ink/10 text-ink text-[10px] font-bold px-2 py-0.5 rounded-full">' + esc(d) + '</span>'; });
        c += '</div></div>';
      }
      html += bpCard('deployment', 'Deployment', null, c);
    }

    // Architectural Problems (findings.json — shared store from scan + deep-scan)
    if (sections.find(s => s.id === 'problems')) {
      const sevRank = { error: 0, warn: 1, info: 2 };
      const ranked = findings.slice().sort((a, b) => {
        const sa = sevRank[a.severity] != null ? sevRank[a.severity] : 3;
        const sb = sevRank[b.severity] != null ? sevRank[b.severity] : 3;
        if (sa !== sb) return sa - sb;
        return (b.confidence || 0) - (a.confidence || 0);
      });
      let c = '';
      ranked.forEach(f => { c += renderFourFieldItem(f); });
      html += bpCard('problems', 'Architectural Problems', findings.length, c, 'Concrete problems observed in specific files.');
    }

    // Pitfalls
    if (sections.find(s => s.id === 'pitfalls')) {
      let c = '';
      pits.forEach(p => { c += renderFourFieldItem(p); });
      html += bpCard('pitfalls', 'Pitfalls', pits.length, c, 'Classes of problem rooted in architectural decisions — the trap itself, not each instance.');
    }

    // Implementation Guidelines
    if (sections.find(s => s.id === 'guidelines')) {
      let c = '<table class="w-full text-xs"><thead><tr>' + th('Capability') + th('Category') + th('Libraries') + th('Pattern') + '</tr></thead><tbody>';
      impl.forEach(g => {
        const libs = (g.libraries || []).join(', ');
        c += '<tr>' + td(g.capability || '--') + td(g.category || '--') + td(libs || '--') + td(g.pattern_description || '--') + '</tr>';
      });
      c += '</tbody></table>';
      html += bpCard('guidelines', 'Implementation Guidelines', impl.length, c);
    }

    // Dev Rules
    if (sections.find(s => s.id === 'devrules')) {
      let c = '<ul class="list-disc list-inside space-y-1 text-sm text-ink/80">';
      devRules.forEach(r => {
        const ruleText = typeof r === 'string' ? r : (r.rule || r.description || '');
        c += '<li>' + esc(ruleText);
        if (r.confidence) c += ' <span class="text-[10px] text-ink/40">(confidence: ' + r.confidence + ')</span>';
        c += '</li>';
      });
      c += '</ul>';
      html += bpCard('devrules', 'Development Rules', devRules.length, c);
    }

    // Architecture Diagram
    if (sections.find(s => s.id === 'diagram')) {
      let c = '<pre class="mermaid">' + esc(diagram) + '</pre>';
      html += bpCard('diagram', 'Architecture Diagram', null, c);
    }

    return html;
  }

  // --- Build sidebar ---
  function buildBpSidebar() {
    return sections.map(s => {
      const isActive = s.id === activeSection;
      const activeClasses = 'bg-teal/5 text-teal font-bold';
      const inactiveClasses = 'text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium';
      return '<button data-bpsection="' + s.id + '" class="block w-full text-left px-3 py-2.5 rounded-lg transition-all duration-200 cursor-pointer text-sm ' + (isActive ? activeClasses : inactiveClasses) + '">'
        + esc(s.label) + '</button>';
    }).join('');
  }

  // --- Layout ---
  el.innerHTML = '<div class="flex gap-6 h-[calc(100vh-140px)] p-8 max-w-7xl mx-auto">'
    + '<div class="w-64 flex-shrink-0 overflow-y-auto pr-4">'
      + '<div class="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-4">SECTIONS</div>'
      + '<nav id="bp-nav">' + buildBpSidebar() + '</nav>'
    + '</div>'
    + '<div id="blueprintContent" class="flex-1 overflow-y-auto bg-white/60 border border-papaya-400/60 rounded-3xl shadow-inner p-8">'
      + renderSections()
    + '</div>'
  + '</div>';

  // --- Click handlers for sidebar nav ---
  function attachBpNavHandlers() {
    el.querySelectorAll('[data-bpsection]').forEach(btn => {
      btn.addEventListener('click', () => {
        const sid = btn.getAttribute('data-bpsection');
        activeSection = sid;
        document.getElementById('bp-nav').innerHTML = buildBpSidebar();
        attachBpNavHandlers();
        const target = document.getElementById('bp-' + sid);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }
  attachBpNavHandlers();

  // --- IntersectionObserver for active section tracking ---
  const contentEl = document.getElementById('blueprintContent');
  if (contentEl && typeof IntersectionObserver !== 'undefined') {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const sid = entry.target.id.replace('bp-', '');
          if (sid !== activeSection) {
            activeSection = sid;
            document.getElementById('bp-nav').innerHTML = buildBpSidebar();
            attachBpNavHandlers();
          }
        }
      });
    }, { root: contentEl, threshold: 0.3 });
    sections.forEach(s => {
      const secEl = document.getElementById('bp-' + s.id);
      if (secEl) observer.observe(secEl);
    });
  }

  // --- Mermaid rendering ---
  if (diagram && typeof mermaid !== 'undefined') {
    setTimeout(() => { try { mermaid.run({ nodes: document.querySelectorAll('.mermaid') }); } catch(e) {} }, 100);
  }
}

function renderRules() {
  const container = document.getElementById('tab-rules');
  const ruleList = rules.rules || [];
  const ignored = (ignoredRules && ignoredRules.ignored) || [];
  const proposed = (proposedRules && proposedRules.rules) || [];

  // Filter proposed rules to only show ones not already adopted
  const adoptedIds = new Set(ruleList.map(r => r.id));
  const pendingProposed = proposed.filter(r => !adoptedIds.has(r.id));

  if (ruleList.length === 0 && ignored.length === 0 && pendingProposed.length === 0) {
    container.innerHTML = '<p class="text-ink/40 text-sm">No rules found. Run <code class="text-teal">/archie-scan</code> to discover architectural rules.</p>';
    return;
  }

  let html = '';

  // Top bar: filters + add button
  html += '<div class="flex items-center justify-between mb-6">';
  html += '<div class="flex gap-2" id="ruleFilters">';
  html += '<button class="filter-btn active px-3 py-1.5 rounded-lg text-xs font-bold bg-teal/10 text-teal border border-teal/20" data-filter="all">All</button>';
  html += '<button class="filter-btn px-3 py-1.5 rounded-lg text-xs font-bold text-ink/40 hover:bg-papaya-300/20 border border-transparent" data-filter="error">Errors</button>';
  html += '<button class="filter-btn px-3 py-1.5 rounded-lg text-xs font-bold text-ink/40 hover:bg-papaya-300/20 border border-transparent" data-filter="warn">Warnings</button>';
  html += '</div>';
  html += '<button onclick="showAddRuleForm()" class="px-4 py-2 rounded-xl bg-teal text-white font-bold text-sm shadow-lg shadow-teal/20 hover:bg-teal/90 transition-colors">+ Add Rule</button>';
  html += '</div>';

  // Add rule form (hidden)
  html += '<div id="addRuleForm" class="hidden rounded-xl border border-teal/20 bg-teal/5 p-5 mb-6">';
  html += '<h3 class="text-sm font-bold text-ink mb-4">Add New Rule</h3>';
  html += '<div class="grid grid-cols-2 gap-4 mb-4">';
  html += '<div>';
  html += '<label class="text-[10px] font-bold uppercase tracking-widest text-ink/40 block mb-1">ID</label>';
  html += '<input id="newRuleId" class="w-full px-3 py-2 rounded-lg border border-papaya-400/60 bg-white text-sm text-ink" placeholder="scan-006">';
  html += '</div>';
  html += '<div>';
  html += '<label class="text-[10px] font-bold uppercase tracking-widest text-ink/40 block mb-1">Severity</label>';
  html += '<select id="newRuleSeverity" class="w-full px-3 py-2 rounded-lg border border-papaya-400/60 bg-white text-sm">';
  html += '<option value="error">Error</option>';
  html += '<option value="warn">Warning</option>';
  html += '</select>';
  html += '</div>';
  html += '</div>';
  html += '<div class="mb-4">';
  html += '<label class="text-[10px] font-bold uppercase tracking-widest text-ink/40 block mb-1">Description</label>';
  html += '<input id="newRuleDesc" class="w-full px-3 py-2 rounded-lg border border-papaya-400/60 bg-white text-sm" placeholder="What is forbidden/required">';
  html += '</div>';
  html += '<div class="mb-4">';
  html += '<label class="text-[10px] font-bold uppercase tracking-widest text-ink/40 block mb-1">Rationale</label>';
  html += '<textarea id="newRuleRationale" rows="2" class="w-full px-3 py-2 rounded-lg border border-papaya-400/60 bg-white text-sm" placeholder="Why &#8212; the architectural reasoning"></textarea>';
  html += '</div>';
  html += '<div class="flex gap-2">';
  html += '<button onclick="addRule()" class="px-4 py-2 rounded-lg bg-teal text-white font-bold text-sm">Save</button>';
  html += '<button onclick="document.getElementById(\\x27addRuleForm\\x27).classList.add(\\x27hidden\\x27)" class="px-4 py-2 rounded-lg text-ink/40 hover:text-ink text-sm font-medium">Cancel</button>';
  html += '</div>';
  html += '</div>';

  // Rule cards
  html += '<div id="rulesList">';
  ruleList.forEach((rule, i) => {
    const sev = rule.severity || 'warn';
    const enabled = rule.enabled !== false;
    const src = rule.source || 'blueprint';
    const scope = rule.applies_to || rule.file_pattern || '';
    const id = rule.id || 'rule-' + i;
    const desc = rule.description || '';
    const rationale = rule.rationale || '';
    const check = rule.check || '';

    html += '<div class="rounded-xl border border-papaya-400/60 bg-white p-4 mb-3 flex items-start gap-4 transition-all hover:shadow-md rule-card" data-severity="' + sev + '" data-rule-index="' + i + '">';

    // Left: toggle + severity
    html += '<div class="flex flex-col items-center gap-3 pt-1">';
    html += '<label class="relative inline-flex items-center cursor-pointer">';
    html += '<input type="checkbox" class="sr-only peer rule-toggle" data-index="' + i + '"' + (enabled ? ' checked' : '') + '>';
    html += '<div class="w-9 h-5 bg-papaya-300/50 peer-focus:outline-none rounded-full peer peer-checked:bg-teal transition-colors"></div>';
    html += '<div class="absolute left-0.5 top-0.5 bg-white w-4 h-4 rounded-full transition-transform peer-checked:translate-x-4 shadow-sm"></div>';
    html += '</label>';
    html += '<select class="rule-severity rounded-md border border-papaya-400/60 text-[10px] font-bold px-1.5 py-0.5 bg-transparent text-ink" data-index="' + i + '">';
    html += '<option value="error"' + (sev === 'error' ? ' selected' : '') + '>error</option>';
    html += '<option value="warn"' + (sev === 'warn' ? ' selected' : '') + '>warn</option>';
    html += '</select>';
    html += '</div>';

    // Center: content
    html += '<div class="flex-1 min-w-0">';
    html += '<div class="text-[10px] font-bold text-ink/30 uppercase tracking-wider">' + esc(id) + '</div>';
    html += '<div class="font-bold text-ink text-sm mt-1">' + esc(desc) + '</div>';
    if (rationale) {
      html += '<div class="text-xs text-ink/60 mt-1 leading-relaxed">' + esc(rationale) + '</div>';
    }
    if (scope) {
      html += '<span class="text-[10px] font-mono text-teal bg-teal/5 px-2 py-0.5 rounded mt-2 inline-block">' + esc(scope) + '</span>';
    }
    if (check) {
      html += '<details class="mt-2">';
      html += '<summary class="text-[10px] text-ink/30 cursor-pointer hover:text-ink/50">Mechanical check details</summary>';
      html += '<div class="mt-1 text-[10px] text-ink/40 font-mono">';
      html += 'check: ' + esc(check);
      if (rule.forbidden_patterns) {
        const fp = Array.isArray(rule.forbidden_patterns) ? rule.forbidden_patterns : [rule.forbidden_patterns];
        html += ', forbidden: ' + esc(fp.join(', '));
      }
      if (rule.required_in_content) {
        const ric = Array.isArray(rule.required_in_content) ? rule.required_in_content : [rule.required_in_content];
        html += ', required: ' + esc(ric.join(', '));
      }
      html += '</div>';
      html += '</details>';
    }
    html += '</div>';

    // Right: source badge + delete
    html += '<div class="flex flex-col items-end gap-2">';
    html += '<span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-papaya-300/30 text-ink/40">' + esc(src) + '</span>';
    const conf = rule.confidence;
    if (conf !== undefined && conf < 1.0) {
      const pct = Math.round(conf * 100);
      const confColor = pct >= 80 ? 'text-teal' : pct >= 50 ? 'text-tangerine' : 'text-brandy';
      html += '<span class="text-[10px] font-bold ' + confColor + ' px-2 py-0.5 rounded-full bg-papaya-300/15">' + pct + '% conf</span>';
    }
    html += '<button class="text-ink/20 hover:text-brandy text-xs" onclick="deleteRule(' + i + ')">&#10005;</button>';
    html += '</div>';

    html += '</div>';
  });
  html += '</div>';

  // Proposed rules section (not yet adopted)
  if (pendingProposed.length > 0) {
    html += '<div class="mt-8">';
    html += '<div class="text-ink/40 text-[11px] font-black uppercase tracking-[0.15em] mb-3">';
    html += '&#9670; Proposed Rules (' + pendingProposed.length + ') &#8212; <span class="font-normal normal-case tracking-normal">discovered by /archie-scan, not yet adopted</span>';
    html += '</div>';
    html += '<div class="space-y-3">';
    pendingProposed.forEach((rule, idx) => {
      const sev = rule.severity || 'warn';
      const desc = rule.description || '';
      const rationale = rule.rationale || '';
      const rid = rule.id || 'proposed-' + idx;
      const scope = rule.applies_to || rule.file_pattern || '';
      const conf = rule.confidence;

      html += '<div class="rounded-xl border-2 border-dashed border-papaya-400/40 bg-papaya-50/50 p-4 flex items-start gap-4">';

      // Left: severity badge
      html += '<div class="flex flex-col items-center gap-2 pt-1">';
      html += '<span class="text-[10px] font-bold px-1.5 py-0.5 rounded border ' + (sev === 'error' ? 'border-brandy/30 text-brandy' : 'border-tangerine/30 text-tangerine') + '">' + sev + '</span>';
      html += '</div>';

      // Center: content
      html += '<div class="flex-1 min-w-0">';
      html += '<div class="text-[10px] font-bold text-ink/30 uppercase tracking-wider">' + esc(rid) + '</div>';
      html += '<div class="font-bold text-ink/70 text-sm mt-1">' + esc(desc) + '</div>';
      if (rationale) {
        html += '<div class="text-xs text-ink/50 mt-1 leading-relaxed italic">' + esc(rationale) + '</div>';
      }
      if (scope) {
        html += '<span class="text-[10px] font-mono text-teal/70 bg-teal/5 px-2 py-0.5 rounded mt-2 inline-block">' + esc(scope) + '</span>';
      }
      html += '</div>';

      // Right: adopt button + confidence
      html += '<div class="flex flex-col items-end gap-2">';
      html += '<span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-tangerine/10 text-tangerine">proposed</span>';
      if (conf !== undefined && conf < 1.0) {
        const pct = Math.round(conf * 100);
        html += '<span class="text-[10px] font-bold text-ink/30 px-2 py-0.5">' + pct + '% conf</span>';
      }
      html += '<button onclick="adoptProposedRule(' + idx + ')" class="px-3 py-1 rounded-lg bg-teal text-white text-[10px] font-bold hover:bg-teal/90 transition-colors">Adopt</button>';
      html += '</div>';

      html += '</div>';
    });
    html += '</div>';
    html += '</div>';
  }

  // Ignored rules section
  if (ignored.length > 0) {
    html += '<div class="mt-8">';
    html += '<div class="text-ink/40 text-[11px] font-black uppercase tracking-[0.15em] cursor-pointer hover:text-ink mb-3" onclick="this.nextElementSibling.classList.toggle(\\x27hidden\\x27)">';
    html += '&#9656; Ignored Rules (' + ignored.length + ')';
    html += '</div>';
    html += '<div class="hidden space-y-2">';
    ignored.forEach((ir, idx) => {
      html += '<div class="flex items-center justify-between px-3 py-2 rounded-lg bg-papaya-50 text-xs">';
      html += '<span class="text-ink/60">' + esc(ir.id || '') + ' &#8212; ' + esc(ir.description || '') + '</span>';
      html += '<button onclick="unignoreRule(' + idx + ')" class="text-teal text-[10px] font-bold hover:underline">Restore</button>';
      html += '</div>';
    });
    html += '</div>';
    html += '</div>';
  }

  container.innerHTML = html;

  // Event listeners: filter buttons
  container.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.remove('active', 'bg-teal/10', 'text-teal', 'border-teal/20');
        b.classList.add('text-ink/40', 'border-transparent');
      });
      btn.classList.add('active', 'bg-teal/10', 'text-teal', 'border-teal/20');
      btn.classList.remove('text-ink/40', 'border-transparent');
      const filter = btn.dataset.filter;
      container.querySelectorAll('.rule-card').forEach(card => {
        if (filter === 'all' || card.dataset.severity === filter) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });
    });
  });

  // Event listeners: toggle switches
  container.querySelectorAll('.rule-toggle').forEach(toggle => {
    toggle.addEventListener('change', (e) => {
      const idx = parseInt(e.target.dataset.index);
      if (rules.rules && rules.rules[idx]) {
        rules.rules[idx].enabled = e.target.checked;
        saveRules();
      }
    });
  });

  // Event listeners: severity selects
  container.querySelectorAll('.rule-severity').forEach(sel => {
    sel.addEventListener('change', (e) => {
      const idx = parseInt(e.target.dataset.index);
      if (rules.rules && rules.rules[idx]) {
        rules.rules[idx].severity = e.target.value;
        saveRules();
      }
    });
  });
}

function showAddRuleForm() {
  document.getElementById('addRuleForm').classList.remove('hidden');
  const ruleList = (rules.rules || []);
  let maxNum = 0;
  ruleList.forEach(r => { const m = (r.id||'').match(/scan-(\\d+)/); if (m) maxNum = Math.max(maxNum, parseInt(m[1])); });
  document.getElementById('newRuleId').value = 'scan-' + String(maxNum + 1).padStart(3, '0');
}

async function saveRules() {
  try {
    const res = await fetch('/api/rules', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(rules) });
    if (res.ok) showToast('Rules saved', 'teal');
    else showToast('Error saving rules', 'brandy');
  } catch(e) { showToast('Error saving rules', 'brandy'); }
}

function addRule() {
  const id = document.getElementById('newRuleId').value.trim();
  const desc = document.getElementById('newRuleDesc').value.trim();
  const rationale = document.getElementById('newRuleRationale').value.trim();
  const severity = document.getElementById('newRuleSeverity').value;
  if (!id || !desc) { showToast('ID and description required', 'brandy'); return; }
  if (!rules.rules) rules.rules = [];
  rules.rules.push({ id, description: desc, rationale, severity, source: 'manual', enabled: true });
  document.getElementById('addRuleForm').classList.add('hidden');
  saveRules();
  renderRules();
}

function deleteRule(index) {
  if (!rules.rules) return;
  rules.rules.splice(index, 1);
  saveRules();
  renderRules();
}

function showToast(message, color) {
  const toast = document.createElement('div');
  toast.className = 'fixed bottom-6 right-6 px-4 py-3 rounded-xl shadow-xl text-white text-sm font-bold z-50 transition-opacity duration-300';
  toast.style.backgroundColor = color === 'teal' ? '#219ebc' : '#fb8500';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 2000);
}

function unignoreRule(index) {
  if (!ignoredRules || !ignoredRules.ignored) return;
  const restored = ignoredRules.ignored.splice(index, 1)[0];
  if (!restored) return;
  if (!rules.rules) rules.rules = [];
  rules.rules.push({ id: restored.id, description: restored.description || '', severity: 'warn', source: 'restored', enabled: true });
  saveRules();
  renderRules();
}

function adoptProposedRule(index) {
  const proposed = (proposedRules && proposedRules.rules) || [];
  const adoptedIds = new Set((rules.rules || []).map(r => r.id));
  const pending = proposed.filter(r => !adoptedIds.has(r.id));
  const rule = pending[index];
  if (!rule) return;
  if (!rules.rules) rules.rules = [];
  const adopted = Object.assign({}, rule, { source: 'scan-adopted', enabled: true });
  rules.rules.push(adopted);
  saveRules();
  renderRules();
}

function renderFiles() {
  const el = document.getElementById('tab-files');
  const gfKeys = Object.keys(generatedFiles || {});
  const fmKeys = Object.keys(folderMds || {});

  if (gfKeys.length === 0 && fmKeys.length === 0) {
    let filesHint = '<div class="flex items-center justify-center h-full"><div class="text-center max-w-md">';
    filesHint += '<p class="text-ink/40 text-lg mb-3">Generated files require <code class="text-teal">/archie-deep-scan</code></p>';
    filesHint += '<p class="text-ink/30 text-sm mb-4">CLAUDE.md, AGENTS.md, and per-folder context files are produced by the full multi-agent analysis.</p>';
    const filesAvailable = [];
    if (health && Object.keys(health).length) filesAvailable.push('Dashboard');
    if (scanReports && scanReports.length) filesAvailable.push('Scan Reports');
    if (depGraph && depGraph.nodes && depGraph.nodes.length) filesAvailable.push('Dependencies');
    if (filesAvailable.length) {
      filesHint += '<p class="text-ink/40 text-sm">Check these tabs for scan results:</p>';
      filesHint += '<ul class="text-ink/50 text-sm mt-1 text-left inline-block">';
      filesAvailable.forEach(a => { filesHint += '<li class="py-0.5">&#10003; ' + a + '</li>'; });
      filesHint += '</ul>';
    }
    filesHint += '</div></div>';
    el.innerHTML = filesHint;
    return;
  }

  // Categorize generated files
  const rootFiles = gfKeys.filter(k => k === 'CLAUDE.md' || k === 'AGENTS.md');
  const ruleFiles = gfKeys.filter(k => k.startsWith('.claude/rules/'));

  // Build directory tree for per-folder CLAUDE.md
  function buildTree(paths) {
    const tree = {};
    paths.forEach(function(p) {
      var parts = p.replace(/\/CLAUDE\.md$/, '').split('/');
      var node = tree;
      parts.forEach(function(part) {
        if (!node[part]) node[part] = {};
        node = node[part];
      });
      node._file = p;
    });
    return tree;
  }

  var activeFile = '';

  // Determine first available file
  if (rootFiles.indexOf('CLAUDE.md') !== -1) activeFile = 'CLAUDE.md';
  else if (rootFiles.length > 0) activeFile = rootFiles[0];
  else if (ruleFiles.length > 0) activeFile = ruleFiles[0];
  else if (fmKeys.length > 0) activeFile = fmKeys[0];

  function getFileContent(key) {
    if (generatedFiles[key]) return generatedFiles[key];
    if (folderMds[key]) return folderMds[key];
    return '';
  }

  function navItem(key, label) {
    var isActive = key === activeFile;
    var activeClasses = 'bg-teal/5 text-teal font-bold';
    var inactiveClasses = 'text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium';
    return '<button data-filekey="' + esc(key) + '" class="block w-full text-left px-3 py-2 rounded-lg transition-all duration-200 cursor-pointer text-xs truncate ' + (isActive ? activeClasses : inactiveClasses) + '" title="' + esc(key) + '">'
      + esc(label) + '</button>';
  }

  function renderTreeNode(node, depth) {
    var html = '';
    var sortedKeys = Object.keys(node).filter(function(k) { return k !== '_file'; }).sort();
    sortedKeys.forEach(function(k) {
      var child = node[k];
      var childKeys = Object.keys(child).filter(function(ck) { return ck !== '_file'; });
      if (child._file && childKeys.length === 0) {
        // Leaf node
        html += '<div class="ml-' + (depth > 0 ? '3' : '0') + '">' + navItem(child._file, k + '/CLAUDE.md') + '</div>';
      } else {
        // Directory node
        html += '<div class="ml-' + (depth > 0 ? '3' : '0') + '">';
        html += '<div class="px-3 py-1.5 text-xs font-bold text-ink/40 cursor-pointer hover:text-ink flex items-center gap-1" onclick="this.querySelector(\'.arrow\').classList.toggle(\'rotate-90\'); this.nextElementSibling.classList.toggle(\'hidden\')">';
        html += '<span class="arrow transition-transform duration-200 text-[10px]">&#9654;</span>';
        html += '<span>' + esc(k) + '</span>';
        html += '</div>';
        html += '<div class="ml-3 hidden">';
        if (child._file) {
          html += navItem(child._file, 'CLAUDE.md');
        }
        html += renderTreeNode(child, depth + 1);
        html += '</div>';
        html += '</div>';
      }
    });
    return html;
  }

  function buildSidebar() {
    var html = '';

    // Group 1: Root Files
    if (rootFiles.length > 0) {
      html += '<div class="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2 mt-5">Root Files</div>';
      rootFiles.forEach(function(k) { html += navItem(k, k); });
    }

    // Group 2: Rule Files
    if (ruleFiles.length > 0) {
      html += '<div class="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2 mt-5">Rule Files</div>';
      ruleFiles.forEach(function(k) {
        var filename = k.split('/').pop();
        html += navItem(k, filename);
      });
    }

    // Group 3: Per-Folder CLAUDE.md
    if (fmKeys.length > 0) {
      html += '<div class="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2 mt-5">Per-Folder CLAUDE.md</div>';
      var tree = buildTree(fmKeys);
      html += renderTreeNode(tree, 0);
    }

    return html;
  }

  function renderContent() {
    var contentEl = document.getElementById('files-content');
    if (!activeFile) {
      contentEl.innerHTML = '<p class="text-ink/40">Select a file...</p>';
      return;
    }
    var raw = getFileContent(activeFile);
    var rendered = window.marked ? marked.parse(raw) : esc(raw);
    contentEl.innerHTML = '<div class="flex items-center justify-between mb-6">'
      + '<code class="text-[10px] text-ink/40">' + esc(activeFile) + '</code>'
      + '<button id="files-copy-btn" class="px-3 py-1 rounded-lg border border-papaya-400/60 text-[10px] text-ink/40 hover:text-ink hover:border-teal transition-colors">Copy</button>'
      + '</div>'
      + '<div class="prose-archie text-sm">' + rendered + '</div>';

    document.getElementById('files-copy-btn').addEventListener('click', function() {
      navigator.clipboard.writeText(raw).then(function() {
        var btn = document.getElementById('files-copy-btn');
        btn.textContent = 'Copied!';
        btn.classList.add('text-teal', 'border-teal');
        setTimeout(function() { btn.textContent = 'Copy'; btn.classList.remove('text-teal', 'border-teal'); }, 1500);
      });
    });
  }

  function attachFileNavHandlers() {
    el.querySelectorAll('[data-filekey]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        activeFile = btn.getAttribute('data-filekey');
        // Save expanded folder state before rebuilding sidebar
        var nav = document.getElementById('files-nav');
        var expanded = [];
        nav.querySelectorAll('.arrow.rotate-90').forEach(function(arrow) {
          var label = arrow.parentElement.querySelector('span:last-child');
          if (label) expanded.push(label.textContent);
        });
        nav.innerHTML = buildSidebar();
        // Restore expanded folder state
        nav.querySelectorAll('.arrow').forEach(function(arrow) {
          var label = arrow.parentElement.querySelector('span:last-child');
          if (label && expanded.indexOf(label.textContent) !== -1) {
            arrow.classList.add('rotate-90');
            arrow.parentElement.nextElementSibling.classList.remove('hidden');
          }
        });
        attachFileNavHandlers();
        renderContent();
      });
    });
  }

  // Layout
  el.innerHTML = '<div class="flex gap-6 h-[calc(100vh-140px)] p-8 max-w-7xl mx-auto">'
    + '<div class="w-64 flex-shrink-0 overflow-y-auto pr-4">'
      + '<nav id="files-nav">' + buildSidebar() + '</nav>'
    + '</div>'
    + '<div id="files-content" class="flex-1 overflow-y-auto bg-white/60 border border-papaya-400/60 rounded-3xl shadow-inner p-10">'
      + '<p class="text-ink/40">Select a file...</p>'
    + '</div>'
  + '</div>';

  attachFileNavHandlers();
  if (activeFile) renderContent();
}

// ---------------------------------------------------------------------------
// Dependencies graph
// ---------------------------------------------------------------------------
let _depNetwork = null;

function renderDependencies() {
  const el = document.getElementById('tab-dependencies');
  const nodes = (depGraph.nodes || []);
  const edges = (depGraph.edges || []);
  const cycles = (depGraph.cycles || []);
  const stats = depGraph.stats || {};

  if (!nodes.length) {
    el.innerHTML = '<div class="flex items-center justify-center h-full">'
      + '<div class="text-center">'
      + '<div class="text-ink/30 text-lg font-bold mb-2">No dependency graph</div>'
      + '<div class="text-ink/40 text-sm">Run <code class="bg-papaya-300/20 px-2 py-1 rounded">/archie-scan</code> to generate</div>'
      + '</div></div>';
    return;
  }

  // Archie brand palette for components
  const palette = ['#023047','#219ebc','#fb8500','#ffb703','#8ecae6','#e76f51','#2a9d8f','#264653','#f4a261','#e9c46a'];
  const compSet = [...new Set(nodes.map(n => n.component).filter(Boolean))].sort();
  const compColor = {};
  compSet.forEach((c, i) => { compColor[c] = palette[i % palette.length]; });
  const defaultColor = '#94a3b8';

  // Build vis.js datasets
  const visNodes = new vis.DataSet(nodes.map(n => {
    const bg = n.component ? compColor[n.component] : defaultColor;
    const size = Math.max(12, Math.min(40, 8 + Math.log2(Math.max(n.fileCount, 1)) * 6));
    return {
      id: n.id, label: n.label, title: n.id,
      size: size,
      color: {
        background: bg, border: n.inCycle ? '#dc2626' : bg,
        highlight: { background: bg, border: '#023047' }
      },
      borderWidth: n.inCycle ? 3 : 1,
      font: { size: 11, color: '#023047' },
      _meta: n
    };
  }));

  const visEdges = new vis.DataSet(edges.map((e, i) => ({
    id: i, from: e.from, to: e.to,
    arrows: 'to',
    width: Math.max(1, Math.min(5, Math.log2(Math.max(e.weight, 1)) + 1)),
    color: {
      color: e.inCycle ? '#dc2626' : (e.crossComponent ? '#fb8500' : '#94a3b8'),
      opacity: 0.7
    },
    dashes: e.crossComponent && !e.inCycle,
    _meta: e
  })));

  // Layout
  el.innerHTML = '<div class="flex h-full">'
    + '<div id="dep-graph-container" class="flex-1 relative">'
      + '<div id="dep-graph" class="w-full h-full"></div>'
      + '<div id="dep-stats" class="absolute top-4 left-4 bg-white/90 backdrop-blur rounded-xl shadow px-4 py-2 text-xs text-ink/60">'
        + stats.nodeCount + ' directories &middot; '
        + stats.edgeCount + ' edges &middot; '
        + stats.cycleCount + ' cycle' + (stats.cycleCount !== 1 ? 's' : '')
      + '</div>'
    + '</div>'
    + '<div id="dep-sidebar" class="w-72 flex-shrink-0 border-l border-papaya-400/60 overflow-y-auto p-4 hidden">'
      + '<div id="dep-detail"></div>'
    + '</div>'
  + '</div>';

  // Legend
  let legend = '<div class="absolute bottom-4 left-4 bg-white/90 backdrop-blur rounded-xl shadow px-4 py-3 text-[10px]">';
  if (compSet.length) {
    legend += '<div class="font-bold text-ink/40 uppercase tracking-wider mb-1">Components</div>';
    compSet.forEach(c => {
      legend += '<div class="flex items-center gap-1.5 mb-0.5">'
        + '<span class="inline-block w-3 h-3 rounded-full" style="background:' + compColor[c] + '"></span>'
        + '<span class="text-ink/60">' + esc(c) + '</span></div>';
    });
  }
  if (stats.cycleCount > 0) {
    legend += '<div class="flex items-center gap-1.5 mt-1"><span class="inline-block w-3 h-3 rounded-full border-2 border-red-500 bg-transparent"></span><span class="text-ink/60">In cycle</span></div>';
  }
  legend += '<div class="flex items-center gap-1.5 mt-1"><span class="inline-block w-6 border-t-2 border-dashed border-orange-400"></span><span class="text-ink/60">Cross-component</span></div>';
  legend += '</div>';
  document.getElementById('dep-graph-container').insertAdjacentHTML('beforeend', legend);

  // Render vis.js network
  if (typeof vis === 'undefined') {
    document.getElementById('dep-graph').innerHTML = '<div class="flex items-center justify-center h-full text-ink/40">vis-network library failed to load</div>';
    return;
  }

  const container = document.getElementById('dep-graph');
  if (_depNetwork) { _depNetwork.destroy(); _depNetwork = null; }

  _depNetwork = new vis.Network(container, { nodes: visNodes, edges: visEdges }, {
    physics: {
      solver: 'barnesHut',
      barnesHut: { gravitationalConstant: -3000, springLength: 150, springConstant: 0.02, damping: 0.3 },
      stabilization: { iterations: 150, fit: true }
    },
    interaction: { hover: true, tooltipDelay: 200, hideEdgesOnDrag: true },
    layout: { improvedLayout: true }
  });

  // Freeze layout after stabilization so dragging nodes stays put
  _depNetwork.once('stabilizationIterationsDone', function() {
    _depNetwork.setOptions({ physics: { enabled: false } });
  });

  // Click handler — show node details in sidebar
  _depNetwork.on('click', function(params) {
    const sidebar = document.getElementById('dep-sidebar');
    const detail = document.getElementById('dep-detail');
    if (params.nodes.length === 0) { sidebar.classList.add('hidden'); return; }

    const nodeId = params.nodes[0];
    const node = visNodes.get(nodeId);
    const meta = node._meta;

    const incoming = edges.filter(e => e.to === nodeId);
    const outgoing = edges.filter(e => e.from === nodeId);

    let html = '<div class="text-xs">';
    html += '<div class="font-bold text-ink text-sm mb-3">' + esc(meta.id) + '</div>';
    if (meta.component) html += '<div class="mb-2"><span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full text-white" style="background:' + (compColor[meta.component] || defaultColor) + '">' + esc(meta.component) + '</span></div>';
    html += '<div class="grid grid-cols-2 gap-2 mb-4">';
    html += '<div class="bg-papaya-50 rounded-lg p-2 text-center"><div class="text-lg font-bold text-ink">' + meta.fileCount + '</div><div class="text-[10px] text-ink/40">files</div></div>';
    html += '<div class="bg-papaya-50 rounded-lg p-2 text-center"><div class="text-lg font-bold text-ink">' + meta.inDegree + ' / ' + meta.outDegree + '</div><div class="text-[10px] text-ink/40">in / out</div></div>';
    html += '</div>';
    if (meta.inCycle) html += '<div class="mb-3 px-2 py-1 rounded bg-red-50 text-red-700 text-[10px] font-bold">Part of a circular dependency</div>';

    if (incoming.length) {
      html += '<div class="font-bold text-ink/40 uppercase tracking-wider text-[10px] mb-1">Depends on this (' + incoming.length + ')</div>';
      incoming.sort((a,b) => b.weight - a.weight).forEach(e => {
        html += '<div class="flex justify-between py-0.5 text-ink/70"><span>' + esc(e.from.split('/').pop()) + '</span><span class="text-ink/30">' + e.weight + '</span></div>';
      });
      html += '<div class="mb-3"></div>';
    }
    if (outgoing.length) {
      html += '<div class="font-bold text-ink/40 uppercase tracking-wider text-[10px] mb-1">Imports from (' + outgoing.length + ')</div>';
      outgoing.sort((a,b) => b.weight - a.weight).forEach(e => {
        html += '<div class="flex justify-between py-0.5 text-ink/70"><span>' + esc(e.to.split('/').pop()) + '</span><span class="text-ink/30">' + e.weight + '</span></div>';
      });
    }
    html += '</div>';

    detail.innerHTML = html;
    sidebar.classList.remove('hidden');
  });
}

// ---------------------------------------------------------------------------
// Workspace Topology tab
// ---------------------------------------------------------------------------
function renderWorkspace() {
  const el = document.getElementById('tab-workspace');
  const wt = (blueprint && blueprint.workspace_topology) || null;

  if (!wt || (!wt.members && !wt.edges)) {
    el.innerHTML = '<div class="flex items-center justify-center h-64"><div class="text-center max-w-md">'
      + '<p class="text-ink/40 text-lg mb-2">No workspace topology available</p>'
      + '<p class="text-ink/30 text-sm">This view shows up only after running <code class="text-teal">/archie-deep-scan</code> '
      + 'in <code>whole</code> mode on a workspace monorepo. For single projects this is expected.</p>'
      + '</div></div>';
    return;
  }

  const members = Array.isArray(wt.members) ? wt.members : [];
  const edges = Array.isArray(wt.edges) ? wt.edges : [];
  const cycles = Array.isArray(wt.cycles) ? wt.cycles : [];
  const magnets = Array.isArray(wt.dependency_magnets) ? wt.dependency_magnets : [];
  const wsType = wt.type || 'workspace';

  const apps = members.filter(m => (m.role || '').toLowerCase() === 'app');
  const libs = members.filter(m => ['lib', 'library'].includes((m.role || '').toLowerCase()));
  const other = members.filter(m => !apps.includes(m) && !libs.includes(m));

  // Build mermaid diagram
  let mermaidSrc = 'graph LR\n';
  for (const m of members) {
    if (!m.name) continue;
    const safe = String(m.name).replace(/"/g, "'");
    const role = (m.role || '').toLowerCase();
    if (role === 'app') mermaidSrc += '  ' + safe + '(["' + safe + '"])\n';
    else if (role === 'lib' || role === 'library') mermaidSrc += '  ' + safe + '["' + safe + '"]\n';
    else mermaidSrc += '  ' + safe + '("' + safe + '")\n';
  }
  for (const e of edges) {
    if (!e.from || !e.to) continue;
    const label = e.count ? '|' + e.count + '|' : '';
    mermaidSrc += '  ' + e.from + ' --> ' + label + e.to + '\n';
  }

  const groupHtml = (label, list) => {
    if (!list.length) return '';
    return '<div class="mb-3">'
      + '<div class="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-2">' + label + '</div>'
      + '<div class="flex flex-wrap gap-2">'
      + list.map(m => '<span class="px-3 py-1 rounded-full bg-papaya-50 border border-papaya-300 text-xs font-bold">' + esc(m.name) + '</span>').join('')
      + '</div></div>';
  };

  let html = '<h2 class="text-2xl font-black mb-2">Workspace Topology</h2>'
    + '<p class="text-ink/50 mb-6">' + esc(wsType) + ' · ' + members.length + ' workspace' + (members.length !== 1 ? 's' : '') + '</p>'
    + '<div class="bg-white rounded-2xl border border-papaya-300 p-6 mb-6">'
    + '  <div class="grid grid-cols-3 gap-4 text-center text-sm mb-4">'
    + '    <div><div class="text-2xl font-black">' + edges.length + '</div><div class="text-ink/40 text-xs uppercase tracking-widest">Edges</div></div>'
    + '    <div><div class="text-2xl font-black ' + (cycles.length > 0 ? 'text-brandy' : '') + '">' + cycles.length + '</div><div class="text-ink/40 text-xs uppercase tracking-widest">Cycles</div></div>'
    + '    <div><div class="text-2xl font-black">' + magnets.length + '</div><div class="text-ink/40 text-xs uppercase tracking-widest">Magnets</div></div>'
    + '  </div>'
    + groupHtml('Apps', apps)
    + groupHtml('Shared libraries', libs)
    + groupHtml('Other', other)
    + '</div>';

  if (edges.length > 0) {
    html += '<div class="bg-white rounded-2xl border border-papaya-300 p-6 mb-6">'
      + '<h3 class="text-lg font-bold mb-4">Dependency Graph</h3>'
      + '<pre class="mermaid">' + esc(mermaidSrc) + '</pre>'
      + '</div>';
  }

  if (cycles.length > 0) {
    html += '<div class="bg-brandy/5 border-l-4 border-brandy rounded-r-xl p-6 mb-6">'
      + '<div class="text-xs font-black uppercase tracking-[0.2em] text-brandy mb-3">Cross-workspace cycles</div>'
      + '<ul class="space-y-1 font-mono text-sm">'
      + cycles.map(c => '<li>' + esc(Array.isArray(c) ? c.join(' → ') : String(c)) + '</li>').join('')
      + '</ul></div>';
  }

  if (magnets.length > 0) {
    html += '<div class="bg-white rounded-2xl border border-papaya-300 p-6">'
      + '<h3 class="text-lg font-bold mb-4">Dependency magnets</h3>'
      + '<ul class="space-y-2 text-sm">'
      + magnets.map(m => '<li><code class="font-mono">' + esc(m.name) + '</code> <span class="text-ink/40 ml-2">in_degree = ' + (m.in_degree != null ? m.in_degree : '?') + '</span></li>').join('')
      + '</ul></div>';
  }

  el.innerHTML = html;

  if (typeof mermaid !== 'undefined') {
    setTimeout(() => { try { mermaid.run({ nodes: el.querySelectorAll('.mermaid') }); } catch(e) {} }, 100);
  }
}

// ---------------------------------------------------------------------------
// Initialize
// ---------------------------------------------------------------------------
if (typeof mermaid !== 'undefined') {
  mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'loose' });
}

document.addEventListener('DOMContentLoaded', loadData);
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Wiki sidebar
# ---------------------------------------------------------------------------

_SIDEBAR_ORDER = [
    "capabilities", "decisions", "components", "data-models",
    "patterns", "pitfalls", "guidelines", "rules",
]
_SIDEBAR_LABELS = {
    "capabilities": "Capabilities",
    "decisions": "Decisions",
    "components": "Components",
    "data-models": "Data models",
    "patterns": "Patterns",
    "pitfalls": "Pitfalls",
    "guidelines": "Guidelines",
    "rules": "Rules",
}

# Root-level single-page outputs that should appear as their own section in the sidebar
_SIDEBAR_ROOT_PAGES = [
    ("utilities.md", "Utilities catalog"),
    ("technology.md", "Technology"),
    ("quick-reference.md", "Quick reference"),
    ("frontend.md", "Frontend"),
    ("architecture.md", "Architecture"),
]


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
        pages = sorted(
            (p for p in d.glob("*.md") if p.name != "index.md"),
            key=lambda p: _page_title(p).lower(),
        )
        if not pages:
            continue
        parts.append(f"<h3>{_SIDEBAR_LABELS[subdir]}</h3>")
        parts.append("<ul>")
        # Surface a per-section overview link when index.md exists (e.g. decisions/index.md)
        idx = d / "index.md"
        if idx.exists():
            rel_idx = idx.relative_to(wiki_root).as_posix()
            parts.append(f'<li><a href="/wiki/{rel_idx}"><em>Overview</em></a></li>')
        for page in pages:
            rel = page.relative_to(wiki_root).as_posix()
            title = _html.escape(_page_title(page))
            parts.append(f'<li><a href="/wiki/{rel}">{title}</a></li>')
        parts.append("</ul>")

    # Root-level single-page outputs as a "More" section
    root_present = [(name, label) for name, label in _SIDEBAR_ROOT_PAGES
                    if (wiki_root / name).exists()]
    if root_present:
        parts.append("<h3>More</h3>")
        parts.append("<ul>")
        for name, label in root_present:
            parts.append(f'<li><a href="/wiki/{name}">{_html.escape(label)}</a></li>')
        parts.append("</ul>")

    parts.append("</nav>")
    return "\n".join(parts)


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


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def make_server(project_root, host: str, port: int, with_wiki_ui: "bool | None" = None):
    """Factory used by the viewer CLI and tests. Returns a configured HTTPServer.

    When ``with_wiki_ui`` is None (default), the wiki UI is auto-enabled if
    ``.archie/wiki/`` exists. Pass True/False explicitly to override.
    """
    if with_wiki_ui is None:
        with_wiki_ui = (Path(project_root) / ".archie" / "wiki").exists()
    server = http.server.HTTPServer((host, port), ArchieHandler)
    server.root = Path(project_root)  # type: ignore[attr-defined]
    server.with_wiki_ui = with_wiki_ui  # type: ignore[attr-defined]
    return server


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 viewer.py /path/to/repo [--port PORT] [--with-wiki-ui|--no-wiki-ui]", file=sys.stderr)
        print("  Wiki UI is auto-enabled when .archie/wiki/ exists.", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    port = None
    with_wiki_ui = None  # None = auto-detect from .archie/wiki/ presence
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
        elif arg == "--with-wiki-ui":
            with_wiki_ui = True
        elif arg == "--no-wiki-ui":
            with_wiki_ui = False

    if port is None:
        port = _find_free_port()

    try:
        server = make_server(
            project_root=root,
            host="localhost",
            port=port,
            with_wiki_ui=with_wiki_ui,
        )
    except OSError as e:
        print(f"Error: Could not start server on port {port} ({e})", file=sys.stderr)
        print("Try a different port: python3 viewer.py /path/to/repo --port 8888", file=sys.stderr)
        sys.exit(1)

    url = f"http://localhost:{port}"
    print(f"Archie Viewer: {url}", file=sys.stderr)
    print(f"Project: {root}", file=sys.stderr)
    print("Press Ctrl+C to stop.", file=sys.stderr)

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        server.shutdown()
