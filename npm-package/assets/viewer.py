#!/usr/bin/env python3
"""Archie blueprint viewer — zero-dep local HTML inspector.

Run: python3 viewer.py /path/to/repo [--port PORT]
Opens a browser with the full blueprint viewer.

Zero dependencies beyond Python 3.11+ stdlib.
"""
import http.server
import json
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".archie", "venv",
              ".venv", "dist", "build", ".next", ".nuxt", "coverage",
              ".pytest_cache", ".mypy_cache"}


def _load_json(path: Path) -> dict | list:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


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
            continue  # skip root — that's in agent-files
        result[rel] = _read_text(claude_md)
    return result


def _collect_agent_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in ("CLAUDE.md", "AGENTS.md", "CODEBASE_MAP.md"):
        p = root / name
        if p.exists():
            files[name] = _read_text(p)
    for rules_dir in (root / ".claude" / "rules", root / ".cursor" / "rules"):
        if rules_dir.is_dir():
            for f in sorted(rules_dir.rglob("*")):
                if f.is_file():
                    files[str(f.relative_to(root))] = _read_text(f)
    hooks_dir = root / ".claude" / "hooks"
    if hooks_dir.is_dir():
        for f in sorted(hooks_dir.rglob("*")):
            if f.is_file():
                files[str(f.relative_to(root))] = _read_text(f)
    settings = root / ".claude" / "settings.json"
    if settings.exists():
        files[".claude/settings.json"] = _read_text(settings)
    return files


def _collect_enrichments(root: Path) -> dict:
    enrichments_dir = root / ".archie" / "enrichments"
    if not enrichments_dir.is_dir():
        return {}
    merged = {}
    for f in sorted(enrichments_dir.iterdir()):
        if f.name.endswith(".json"):
            data = _load_json(f)
            if isinstance(data, dict):
                merged.update(data)
    return merged


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ArchieHandler(http.server.BaseHTTPRequestHandler):
    """Routes requests to API endpoints or serves the HTML page."""

    def log_message(self, fmt, *args):
        # Suppress default request logging
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        root: Path = self.server.root  # type: ignore[attr-defined]

        if path == "/":
            self._send_html(HTML_PAGE)
        elif path == "/api/blueprint":
            self._send_json(_load_json(root / ".archie" / "blueprint.json"))
        elif path == "/api/scan":
            self._send_json(_load_json(root / ".archie" / "scan.json"))
        elif path == "/api/rules":
            self._send_json(_load_json(root / ".archie" / "rules.json"))
        elif path == "/api/agent-files":
            self._send_json(_collect_agent_files(root))
        elif path == "/api/folder-claude-mds":
            self._send_json(_collect_folder_claude_mds(root))
        elif path == "/api/source":
            self._handle_source(root, qs)
        elif path == "/api/enrichments":
            self._send_json(_collect_enrichments(root))
        else:
            self._send_error(404, "Not found")

    def _handle_source(self, root: Path, qs: dict):
        rel = qs.get("path", [""])[0]
        if not rel:
            self._send_error(400, "Missing path parameter")
            return
        full = (root / rel).resolve()
        if not full.is_relative_to(root.resolve()):
            self._send_error(403, "Access denied")
            return
        if not full.is_file():
            self._send_error(404, "File not found")
            return
        try:
            content = full.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = "(binary file)"
        except OSError:
            content = "(error reading file)"
        self._send_json({"path": rel, "content": content})

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
# Embedded HTML — single-page app
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archie Blueprint Viewer</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"
        onerror="window.marked={parse:function(t){return '<pre>'+t.replace(/</g,'&lt;')+'</pre>'}}"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"
        onerror="window.mermaid={initialize:function(){},run:function(){}}"></script>
<style>
:root {
  --bg: #1a1b26; --bg-card: #24283b; --bg-hover: #292e42;
  --text: #a9b1d6; --text-dim: #565f89; --text-bright: #c0caf5;
  --accent: #7aa2f7; --accent2: #9ece6a; --accent3: #e0af68;
  --border: #3b4261; --error: #f7768e;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,monospace; font-size:14px; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }

/* Layout */
.header { background:var(--bg-card); border-bottom:1px solid var(--border); padding:12px 24px; display:flex; align-items:center; gap:16px; }
.header h1 { font-size:18px; color:var(--text-bright); font-weight:600; }
.header .meta { color:var(--text-dim); font-size:12px; }
.tabs { display:flex; gap:0; background:var(--bg-card); border-bottom:1px solid var(--border); padding:0 16px; }
.tab { padding:10px 20px; cursor:pointer; color:var(--text-dim); border-bottom:2px solid transparent; transition:all .15s; font-size:13px; }
.tab:hover { color:var(--text); background:var(--bg-hover); }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); }
.content { padding:20px 24px; max-width:1400px; margin:0 auto; }
.hidden { display:none !important; }

/* Cards */
.card { background:var(--bg-card); border:1px solid var(--border); border-radius:8px; margin-bottom:16px; overflow:hidden; }
.card summary, .card-header { padding:12px 16px; font-weight:600; color:var(--text-bright); cursor:pointer; display:flex; align-items:center; gap:8px; }
.card summary:hover, .card-header:hover { background:var(--bg-hover); }
.card-body { padding:16px; border-top:1px solid var(--border); }
.badge { background:var(--accent); color:var(--bg); padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }
.badge.green { background:var(--accent2); }
.badge.yellow { background:var(--accent3); color:#1a1b26; }
.badge.red { background:var(--error); }

/* Tables */
table { width:100%; border-collapse:collapse; font-size:13px; }
th { text-align:left; padding:8px 12px; background:var(--bg); color:var(--text-dim); font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.5px; }
td { padding:8px 12px; border-top:1px solid var(--border); vertical-align:top; }
tr:hover td { background:var(--bg-hover); }

/* Split pane */
.split { display:flex; gap:0; height:calc(100vh - 140px); }
.split .tree-panel { width:280px; min-width:200px; border-right:1px solid var(--border); overflow-y:auto; background:var(--bg-card); padding:8px 0; }
.split .detail-panel { flex:1; overflow-y:auto; padding:20px; }
.tree-item { padding:4px 12px; cursor:pointer; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--text); }
.tree-item:hover { background:var(--bg-hover); }
.tree-item.active { background:var(--bg-hover); color:var(--accent); border-left:2px solid var(--accent); }
.tree-dir { padding:4px 12px; font-size:12px; color:var(--text-dim); font-weight:600; cursor:pointer; user-select:none; }
.tree-dir:hover { color:var(--text); }
.tree-dir::before { content:"▸ "; }
.tree-dir.open::before { content:"▾ "; }
.tree-children { padding-left:12px; }
.tree-children.collapsed { display:none; }

/* Source */
pre.source { background:var(--bg); border:1px solid var(--border); border-radius:6px; padding:16px; overflow-x:auto; font-size:13px; line-height:1.5; color:var(--text-bright); white-space:pre; tab-size:4; }

/* Markdown */
.md-content { line-height:1.7; }
.md-content h1,.md-content h2,.md-content h3,.md-content h4 { color:var(--text-bright); margin:16px 0 8px; }
.md-content h1 { font-size:20px; border-bottom:1px solid var(--border); padding-bottom:8px; }
.md-content h2 { font-size:17px; }
.md-content h3 { font-size:15px; }
.md-content p { margin:8px 0; }
.md-content ul,.md-content ol { margin:8px 0 8px 20px; }
.md-content li { margin:4px 0; }
.md-content code { background:var(--bg); padding:2px 6px; border-radius:3px; font-size:12px; }
.md-content pre { background:var(--bg); border:1px solid var(--border); border-radius:6px; padding:12px; overflow-x:auto; margin:8px 0; }
.md-content pre code { background:none; padding:0; }
.md-content blockquote { border-left:3px solid var(--accent); padding-left:12px; color:var(--text-dim); margin:8px 0; }
.md-content table { margin:8px 0; }

/* Copy button */
.copy-btn { background:var(--bg); border:1px solid var(--border); color:var(--text-dim); padding:4px 10px; border-radius:4px; cursor:pointer; font-size:11px; }
.copy-btn:hover { color:var(--text); border-color:var(--accent); }

/* Enrichment */
.score-bar { display:inline-block; width:60px; height:8px; background:var(--bg); border-radius:4px; overflow:hidden; vertical-align:middle; margin-left:8px; }
.score-fill { height:100%; border-radius:4px; }

/* Sub-tabs */
.sub-tabs { display:flex; gap:0; border-bottom:1px solid var(--border); margin-bottom:16px; flex-wrap:wrap; }
.sub-tab { padding:6px 14px; cursor:pointer; color:var(--text-dim); border-bottom:2px solid transparent; font-size:12px; }
.sub-tab:hover { color:var(--text); }
.sub-tab.active { color:var(--accent); border-bottom-color:var(--accent); }

/* Empty state */
.empty { text-align:center; padding:60px 20px; color:var(--text-dim); }
.empty h2 { color:var(--text); margin-bottom:8px; }

/* Diagram */
.mermaid-container { background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:20px; text-align:center; overflow-x:auto; }
.mermaid-container svg { max-width:100%; }
</style>
</head>
<body>

<div class="header">
  <h1>Archie</h1>
  <span id="repoName" class="meta"></span>
</div>

<div class="tabs" id="mainTabs">
  <div class="tab active" data-tab="blueprint">Blueprint</div>
  <div class="tab" data-tab="agent-files">Agent Files</div>
  <div class="tab" data-tab="folder-tree">Folder CLAUDE.md</div>
  <div class="tab" data-tab="source">Source Files</div>
  <div class="tab" data-tab="enrichments">Enrichments</div>
</div>

<div id="tab-blueprint" class="content"></div>
<div id="tab-agent-files" class="content hidden"></div>
<div id="tab-folder-tree" class="hidden" style="padding:0;"></div>
<div id="tab-source" class="hidden" style="padding:0;"></div>
<div id="tab-enrichments" class="content hidden"></div>

<script>
// --- State ---
let blueprint = {}, scan = {}, rules = {}, agentFiles = {}, folderMds = {}, enrichments = {};

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
  if (window.mermaid && mermaid.initialize) {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', themeVariables: {
      primaryColor: '#7aa2f7', primaryTextColor: '#c0caf5', lineColor: '#3b4261',
      primaryBorderColor: '#3b4261', secondaryColor: '#24283b'
    }});
  }
  const [bpRes, scanRes, rulesRes, afRes, fmRes, enRes] = await Promise.all([
    fetch('/api/blueprint').then(r=>r.json()).catch(()=>({})),
    fetch('/api/scan').then(r=>r.json()).catch(()=>({})),
    fetch('/api/rules').then(r=>r.json()).catch(()=>({})),
    fetch('/api/agent-files').then(r=>r.json()).catch(()=>({})),
    fetch('/api/folder-claude-mds').then(r=>r.json()).catch(()=>({})),
    fetch('/api/enrichments').then(r=>r.json()).catch(()=>({})),
  ]);
  blueprint=bpRes; scan=scanRes; rules=rulesRes; agentFiles=afRes; folderMds=fmRes; enrichments=enRes;

  const meta = blueprint.meta || {};
  document.getElementById('repoName').textContent = meta.repository || '';
  document.title = (meta.repository || 'Archie') + ' — Blueprint Viewer';

  renderBlueprint();
  renderAgentFiles();
  renderFolderTree();
  renderSourceFiles();
  renderEnrichments();
  setupTabs();
});

// --- Tabs ---
function setupTabs() {
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      const id = t.dataset.tab;
      ['blueprint','agent-files','folder-tree','source','enrichments'].forEach(n => {
        const el = document.getElementById('tab-'+n);
        if (el) el.classList.toggle('hidden', n !== id);
      });
    });
  });
}

// --- Helpers ---
function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function renderMd(text) {
  if (!text) return '';
  try { return window.marked ? marked.parse(text) : '<pre>'+esc(text)+'</pre>'; }
  catch { return '<pre>'+esc(text)+'</pre>'; }
}
function detailsCard(title, body, open) {
  return `<details class="card"${open?' open':''}><summary>${esc(title)}</summary><div class="card-body">${body}</div></details>`;
}

// --- Blueprint Tab ---
function renderBlueprint() {
  const el = document.getElementById('tab-blueprint');
  if (!blueprint || !blueprint.meta) { el.innerHTML='<div class="empty"><h2>No Blueprint Found</h2><p>Run /archie-init first.</p></div>'; return; }
  let html = '';

  // Meta / Executive Summary
  const meta = blueprint.meta || {};
  if (meta.executive_summary) {
    html += detailsCard('Executive Summary', `<p>${esc(meta.executive_summary)}</p><p style="color:var(--text-dim);margin-top:8px;"><strong>Architecture:</strong> ${esc(meta.architecture_style||'')}</p>`, true);
  }

  // Components
  const comps = (blueprint.components||{}).components || [];
  if (comps.length) {
    let tbody = comps.map(c => `<tr>
      <td><strong>${esc(c.name)}</strong></td>
      <td><code>${esc(c.location)}</code></td>
      <td>${esc(c.responsibility)}</td>
      <td>${(c.depends_on||[]).map(d=>'<code>'+esc(d)+'</code>').join(', ')}</td>
    </tr>`).join('');
    html += detailsCard(`Components <span class="badge">${comps.length}</span>`,
      `<table><thead><tr><th>Name</th><th>Location</th><th>Responsibility</th><th>Dependencies</th></tr></thead><tbody>${tbody}</tbody></table>`, true);
  }

  // Architecture Rules
  const ar = blueprint.architecture_rules || {};
  const fp = ar.file_placement_rules || [];
  const nc = ar.naming_conventions || [];
  if (fp.length || nc.length) {
    let body = '';
    if (fp.length) {
      body += '<h4 style="margin-bottom:8px;">File Placement</h4><table><thead><tr><th>Type</th><th>Location</th><th>Pattern</th><th>Description</th></tr></thead><tbody>';
      body += fp.map(r=>`<tr><td>${esc(r.component_type)}</td><td><code>${esc(r.location)}</code></td><td><code>${esc(r.naming_pattern)}</code></td><td>${esc(r.description)}</td></tr>`).join('');
      body += '</tbody></table>';
    }
    if (nc.length) {
      body += '<h4 style="margin:16px 0 8px;">Naming Conventions</h4><table><thead><tr><th>Scope</th><th>Pattern</th><th>Examples</th></tr></thead><tbody>';
      body += nc.map(r=>`<tr><td>${esc(r.scope)}</td><td><code>${esc(r.pattern)}</code></td><td>${(r.examples||[]).map(e=>'<code>'+esc(e)+'</code>').join(', ')}</td></tr>`).join('');
      body += '</tbody></table>';
    }
    html += detailsCard('Architecture Rules', body, false);
  }

  // Decisions
  const dec = blueprint.decisions || {};
  if (dec.architectural_style || (dec.key_decisions||[]).length) {
    let body = '';
    if (dec.architectural_style) {
      const d = dec.architectural_style;
      body += `<div style="margin-bottom:16px;padding:12px;background:var(--bg);border-radius:6px;">
        <strong style="color:var(--accent);">${esc(d.title)}</strong><br>
        <strong>Chosen:</strong> ${esc(d.chosen)}<br>
        <strong>Rationale:</strong> ${esc(d.rationale)}<br>
        ${(d.alternatives_rejected||[]).length?'<strong>Rejected:</strong> '+d.alternatives_rejected.map(a=>esc(a)).join(', '):''}
      </div>`;
    }
    (dec.key_decisions||[]).forEach(d => {
      body += `<div style="margin-bottom:8px;padding:8px 12px;border-left:3px solid var(--accent3);">
        <strong>${esc(d.title)}</strong> — ${esc(d.chosen)}<br>
        <span style="color:var(--text-dim)">${esc(d.rationale)}</span>
      </div>`;
    });
    if ((dec.trade_offs||[]).length) {
      body += '<h4 style="margin:12px 0 8px;">Trade-offs</h4>';
      dec.trade_offs.forEach(t => { body += `<div style="margin-bottom:4px;">Accept: ${esc(t.accept)} → Benefit: ${esc(t.benefit)}</div>`; });
    }
    html += detailsCard(`Decisions <span class="badge">${(dec.key_decisions||[]).length}</span>`, body, false);
  }

  // Communication
  const comm = blueprint.communication || {};
  if ((comm.patterns||[]).length || (comm.integrations||[]).length) {
    let body = '';
    (comm.patterns||[]).forEach(p => {
      body += `<div style="margin-bottom:12px;"><strong style="color:var(--accent2);">${esc(p.name)}</strong><br>
        <strong>When:</strong> ${esc(p.when_to_use)}<br>
        <strong>How:</strong> ${esc(p.how_it_works)}</div>`;
    });
    if ((comm.integrations||[]).length) {
      body += '<h4 style="margin:12px 0 8px;">Integrations</h4><table><thead><tr><th>Service</th><th>Purpose</th><th>Integration Point</th></tr></thead><tbody>';
      body += (comm.integrations||[]).map(i=>`<tr><td>${esc(i.service)}</td><td>${esc(i.purpose)}</td><td><code>${esc(i.integration_point)}</code></td></tr>`).join('');
      body += '</tbody></table>';
    }
    html += detailsCard('Communication', body, false);
  }

  // Technology
  const tech = blueprint.technology || {};
  if ((tech.stack||[]).length) {
    let body = '<table><thead><tr><th>Category</th><th>Name</th><th>Version</th><th>Purpose</th></tr></thead><tbody>';
    body += (tech.stack||[]).map(s=>`<tr><td>${esc(s.category)}</td><td><strong>${esc(s.name)}</strong></td><td>${esc(s.version)}</td><td>${esc(s.purpose)}</td></tr>`).join('');
    body += '</tbody></table>';
    if (tech.run_commands && Object.keys(tech.run_commands).length) {
      body += '<h4 style="margin:16px 0 8px;">Run Commands</h4>';
      Object.entries(tech.run_commands).forEach(([k,v]) => {
        body += `<div style="margin-bottom:4px;"><code style="color:var(--accent);">${esc(k)}</code>: <code>${esc(v)}</code></div>`;
      });
    }
    if (tech.project_structure) {
      body += `<h4 style="margin:16px 0 8px;">Project Structure</h4><pre class="source">${esc(tech.project_structure)}</pre>`;
    }
    html += detailsCard(`Technology <span class="badge">${(tech.stack||[]).length}</span>`, body, false);
  }

  // Frontend
  const fe = blueprint.frontend || {};
  if (fe.framework) {
    let body = `<p><strong>Framework:</strong> ${esc(fe.framework)} | <strong>Rendering:</strong> ${esc(fe.rendering_strategy)} | <strong>Styling:</strong> ${esc(fe.styling)}</p>`;
    if ((fe.ui_components||[]).length) {
      body += '<h4 style="margin:12px 0 8px;">UI Components</h4><table><thead><tr><th>Name</th><th>Location</th><th>Type</th><th>Description</th></tr></thead><tbody>';
      body += fe.ui_components.map(c=>`<tr><td>${esc(c.name)}</td><td><code>${esc(c.location)}</code></td><td>${esc(c.component_type)}</td><td>${esc(c.description)}</td></tr>`).join('');
      body += '</tbody></table>';
    }
    if (fe.state_management) {
      const sm = fe.state_management;
      body += `<h4 style="margin:12px 0 8px;">State Management</h4><p><strong>Approach:</strong> ${esc(sm.approach)}</p>`;
    }
    if ((fe.routing||[]).length) {
      body += '<h4 style="margin:12px 0 8px;">Routing</h4><table><thead><tr><th>Path</th><th>Component</th><th>Auth</th><th>Description</th></tr></thead><tbody>';
      body += fe.routing.map(r=>`<tr><td><code>${esc(r.path)}</code></td><td>${esc(r.component)}</td><td>${r.auth_required?'Yes':'No'}</td><td>${esc(r.description)}</td></tr>`).join('');
      body += '</tbody></table>';
    }
    html += detailsCard('Frontend', body, false);
  }

  // Quick Reference
  const qr = blueprint.quick_reference || {};
  if (qr.where_to_put_code || qr.pattern_selection) {
    let body = '';
    if (qr.where_to_put_code && Object.keys(qr.where_to_put_code).length) {
      body += '<h4 style="margin-bottom:8px;">Where to Put Code</h4>';
      Object.entries(qr.where_to_put_code).forEach(([k,v]) => {
        body += `<div style="margin-bottom:4px;"><strong>${esc(k)}</strong> → <code>${esc(v)}</code></div>`;
      });
    }
    if (qr.pattern_selection && Object.keys(qr.pattern_selection).length) {
      body += '<h4 style="margin:12px 0 8px;">Pattern Selection</h4>';
      Object.entries(qr.pattern_selection).forEach(([k,v]) => {
        body += `<div style="margin-bottom:4px;"><strong>${esc(k)}</strong> → ${esc(v)}</div>`;
      });
    }
    html += detailsCard('Quick Reference', body, false);
  }

  // Deployment
  const dep = blueprint.deployment || {};
  if (dep.runtime_environment || (dep.ci_cd||[]).length) {
    let body = `<p><strong>Runtime:</strong> ${esc(dep.runtime_environment)}</p>`;
    if ((dep.compute_services||[]).length) body += `<p><strong>Compute:</strong> ${dep.compute_services.map(s=>esc(s)).join(', ')}</p>`;
    if (dep.container_runtime) body += `<p><strong>Container:</strong> ${esc(dep.container_runtime)}</p>`;
    if (dep.orchestration) body += `<p><strong>Orchestration:</strong> ${esc(dep.orchestration)}</p>`;
    if ((dep.ci_cd||[]).length) body += `<p><strong>CI/CD:</strong> ${dep.ci_cd.map(s=>esc(s)).join(', ')}</p>`;
    if ((dep.distribution||[]).length) body += `<p><strong>Distribution:</strong> ${dep.distribution.map(s=>esc(s)).join(', ')}</p>`;
    if ((dep.key_files||[]).length) body += `<p><strong>Key Files:</strong> ${dep.key_files.map(f=>'<code>'+esc(f)+'</code>').join(', ')}</p>`;
    html += detailsCard('Deployment', body, false);
  }

  // Pitfalls
  const pitfalls = blueprint.pitfalls || [];
  if (pitfalls.length) {
    let body = pitfalls.map(p => `<div style="margin-bottom:12px;border-left:3px solid var(--error);padding:8px 12px;">
      <strong style="color:var(--error);">${esc(p.area)}</strong><br>
      ${esc(p.description)}<br>
      <span style="color:var(--accent2);"><strong>Recommendation:</strong> ${esc(p.recommendation)}</span>
    </div>`).join('');
    html += detailsCard(`Pitfalls <span class="badge red">${pitfalls.length}</span>`, body, false);
  }

  // Implementation Guidelines
  const ig = blueprint.implementation_guidelines || [];
  if (ig.length) {
    let body = '<table><thead><tr><th>Capability</th><th>Category</th><th>Libraries</th><th>Pattern</th></tr></thead><tbody>';
    body += ig.map(g=>`<tr><td><strong>${esc(g.capability)}</strong></td><td>${esc(g.category)}</td><td>${(g.libraries||[]).map(l=>'<code>'+esc(l)+'</code>').join(', ')}</td><td>${esc(g.pattern_description)}</td></tr>`).join('');
    body += '</tbody></table>';
    html += detailsCard(`Implementation Guidelines <span class="badge">${ig.length}</span>`, body, false);
  }

  // Development Rules
  const dr = blueprint.development_rules || [];
  if (dr.length) {
    let body = '<table><thead><tr><th>Category</th><th>Rule</th><th>Source</th></tr></thead><tbody>';
    body += dr.map(r=>`<tr><td><span class="badge">${esc(r.category)}</span></td><td>${esc(r.rule)}</td><td>${esc(r.source)}</td></tr>`).join('');
    body += '</tbody></table>';
    html += detailsCard(`Development Rules <span class="badge">${dr.length}</span>`, body, false);
  }

  // Architecture Diagram
  if (blueprint.architecture_diagram) {
    const src = blueprint.architecture_diagram;
    let body = `<div class="mermaid-container"><pre class="mermaid">${esc(src)}</pre></div>`;
    html += detailsCard('Architecture Diagram', body, false);
  }

  el.innerHTML = html;

  // Render mermaid
  if (window.mermaid && mermaid.run) {
    try { mermaid.run({ nodes: document.querySelectorAll('.mermaid') }); } catch {}
  }
}

// --- Agent Files Tab ---
function renderAgentFiles() {
  const el = document.getElementById('tab-agent-files');
  const keys = Object.keys(agentFiles);
  if (!keys.length) { el.innerHTML='<div class="empty"><h2>No Agent Files Found</h2></div>'; return; }

  let subTabsHtml = '<div class="sub-tabs" id="agentSubTabs">';
  keys.forEach((k,i) => { subTabsHtml += `<div class="sub-tab${i===0?' active':''}" data-key="${esc(k)}">${esc(k.split('/').pop())}</div>`; });
  subTabsHtml += '</div>';

  let panelsHtml = '';
  keys.forEach((k,i) => {
    const content = agentFiles[k];
    panelsHtml += `<div class="agent-panel${i>0?' hidden':''}" data-key="${esc(k)}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <code style="color:var(--text-dim)">${esc(k)}</code>
        <button class="copy-btn" onclick="navigator.clipboard.writeText(agentFiles['${k.replace(/'/g,"\\'")}'])">Copy</button>
      </div>
      <div class="md-content">${renderMd(content)}</div>
    </div>`;
  });

  el.innerHTML = subTabsHtml + panelsHtml;
  document.querySelectorAll('#agentSubTabs .sub-tab').forEach(st => {
    st.addEventListener('click', () => {
      document.querySelectorAll('#agentSubTabs .sub-tab').forEach(x=>x.classList.remove('active'));
      st.classList.add('active');
      document.querySelectorAll('.agent-panel').forEach(p=>p.classList.toggle('hidden', p.dataset.key!==st.dataset.key));
    });
  });
}

// --- Folder CLAUDE.md Tree Tab ---
function renderFolderTree() {
  const el = document.getElementById('tab-folder-tree');
  const keys = Object.keys(folderMds).sort();
  if (!keys.length) { el.innerHTML='<div class="content"><div class="empty"><h2>No Per-Folder CLAUDE.md Files</h2></div></div>'; return; }

  // Build tree structure
  const tree = {};
  keys.forEach(k => {
    const parts = k.replace(/\/CLAUDE\.md$/, '').split('/');
    let node = tree;
    parts.forEach(p => { if (!node[p]) node[p] = {}; node[p] = node[p]; });
  });

  function renderTreeNode(obj, prefix, depth) {
    let html = '';
    Object.keys(obj).sort().forEach(k => {
      const fullKey = prefix ? prefix+'/'+k : k;
      const mdKey = fullKey + '/CLAUDE.md';
      const hasMd = keys.includes(mdKey);
      const children = Object.keys(obj[k]);
      if (children.length) {
        html += `<div class="tree-dir open" onclick="this.classList.toggle('open');this.nextElementSibling.classList.toggle('collapsed')">${esc(k)}</div>`;
        html += `<div class="tree-children">`;
        if (hasMd) html += `<div class="tree-item" data-md="${esc(mdKey)}" style="padding-left:${(depth+1)*12}px">${esc(k)}/CLAUDE.md</div>`;
        html += renderTreeNode(obj[k], fullKey, depth+1);
        html += '</div>';
      } else if (hasMd) {
        html += `<div class="tree-item" data-md="${esc(mdKey)}" style="padding-left:${depth*12}px">${esc(k)}/CLAUDE.md</div>`;
      }
    });
    return html;
  }

  el.innerHTML = `<div class="split">
    <div class="tree-panel" id="folderTreePanel">${renderTreeNode(tree, '', 0)}</div>
    <div class="detail-panel" id="folderDetail"><div class="empty"><p>Select a folder to view its CLAUDE.md</p></div></div>
  </div>`;

  document.querySelectorAll('#folderTreePanel .tree-item').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('#folderTreePanel .tree-item').forEach(x=>x.classList.remove('active'));
      item.classList.add('active');
      const key = item.dataset.md;
      const content = folderMds[key] || '';
      document.getElementById('folderDetail').innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <code style="color:var(--text-dim)">${esc(key)}</code>
        <button class="copy-btn" onclick="navigator.clipboard.writeText(folderMds['${key.replace(/'/g,"\\'")}'])">Copy</button>
      </div><div class="md-content">${renderMd(content)}</div>`;
    });
  });
}

// --- Source Files Tab ---
function renderSourceFiles() {
  const el = document.getElementById('tab-source');
  const files = (scan.file_tree || []).map(f => typeof f === 'string' ? f : f.path).filter(Boolean).sort();
  if (!files.length) { el.innerHTML='<div class="content"><div class="empty"><h2>No Scan Data</h2><p>Run /archie-init first.</p></div></div>'; return; }

  // Build directory tree from flat file list
  const tree = {};
  files.forEach(f => {
    const parts = f.split('/');
    let node = tree;
    parts.forEach((p,i) => {
      if (i === parts.length-1) { node[p] = null; } // leaf
      else { if (!node[p]) node[p] = {}; node = node[p]; }
    });
  });

  function renderFTree(obj, prefix, depth) {
    let html = '';
    const entries = Object.entries(obj).sort(([a,av],[b,bv]) => {
      if ((av===null) !== (bv===null)) return av===null ? 1 : -1;
      return a.localeCompare(b);
    });
    entries.forEach(([k,v]) => {
      if (v === null) {
        const fullPath = prefix ? prefix+'/'+k : k;
        html += `<div class="tree-item" data-path="${esc(fullPath)}" style="padding-left:${depth*12+8}px">${esc(k)}</div>`;
      } else {
        html += `<div class="tree-dir open" onclick="this.classList.toggle('open');this.nextElementSibling.classList.toggle('collapsed')" style="padding-left:${depth*12}px">${esc(k)}</div>`;
        html += `<div class="tree-children">${renderFTree(v, prefix?prefix+'/'+k:k, depth+1)}</div>`;
      }
    });
    return html;
  }

  el.innerHTML = `<div class="split">
    <div class="tree-panel" id="sourceTreePanel">${renderFTree(tree, '', 0)}</div>
    <div class="detail-panel" id="sourceDetail"><div class="empty"><p>Select a file to view its content</p></div></div>
  </div>`;

  document.querySelectorAll('#sourceTreePanel .tree-item').forEach(item => {
    item.addEventListener('click', async () => {
      document.querySelectorAll('#sourceTreePanel .tree-item').forEach(x=>x.classList.remove('active'));
      item.classList.add('active');
      const path = item.dataset.path;
      document.getElementById('sourceDetail').innerHTML = '<p style="color:var(--text-dim)">Loading...</p>';
      try {
        const res = await fetch('/api/source?path='+encodeURIComponent(path));
        const data = await res.json();
        document.getElementById('sourceDetail').innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <code style="color:var(--text-dim)">${esc(data.path)}</code>
          <button class="copy-btn" onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.textContent)">Copy</button>
        </div><pre class="source">${esc(data.content)}</pre>`;
      } catch {
        document.getElementById('sourceDetail').innerHTML = '<p style="color:var(--error)">Error loading file</p>';
      }
    });
  });
}

// --- Enrichments Tab ---
function renderEnrichments() {
  const el = document.getElementById('tab-enrichments');
  const folders = Object.keys(enrichments).sort();
  if (!folders.length) { el.innerHTML='<div class="empty"><h2>No Enrichments Found</h2><p>Run /archie-enrich first.</p></div>'; return; }

  let html = '';
  folders.forEach(folder => {
    const info = enrichments[folder];
    if (!info || typeof info !== 'object') return;
    // Score
    const checks = {
      has_purpose: !!info.purpose,
      has_patterns: (info.patterns||[]).length > 0,
      has_anti_patterns: (info.anti_patterns||[]).length > 0,
      has_code_examples: (info.code_examples||[]).length > 0,
      has_debugging: !!(info.debugging_tips||info.debugging),
      has_file_descriptions: !!(info.file_descriptions && Object.keys(info.file_descriptions).length),
    };
    const passed = Object.values(checks).filter(Boolean).length;
    const total = Object.keys(checks).length;
    const pct = Math.round((passed/total)*100);
    const color = pct >= 80 ? 'var(--accent2)' : pct >= 50 ? 'var(--accent3)' : 'var(--error)';

    let body = '';
    if (info.purpose) body += `<p><strong>Purpose:</strong> ${esc(info.purpose)}</p>`;

    if ((info.patterns||[]).length) {
      body += '<h4 style="margin:12px 0 8px;">Patterns</h4>';
      info.patterns.forEach(p => {
        if (typeof p === 'object') body += `<div style="margin-bottom:4px;"><strong>${esc(p.name||'')}</strong>: ${esc(p.description||p.when_to_use||'')}</div>`;
        else body += `<div style="margin-bottom:4px;">${esc(p)}</div>`;
      });
    }
    if ((info.anti_patterns||[]).length) {
      body += '<h4 style="margin:12px 0 8px;">Anti-Patterns</h4>';
      info.anti_patterns.forEach(p => {
        if (typeof p === 'object') body += `<div style="margin-bottom:4px;border-left:2px solid var(--error);padding-left:8px;"><strong>${esc(p.name||'')}</strong>: ${esc(p.description||p.why_avoid||'')}</div>`;
        else body += `<div style="margin-bottom:4px;">${esc(p)}</div>`;
      });
    }
    if ((info.code_examples||[]).length) {
      body += '<h4 style="margin:12px 0 8px;">Code Examples</h4>';
      info.code_examples.forEach(ex => {
        if (typeof ex === 'object') body += `<div style="margin-bottom:8px;"><strong>${esc(ex.title||ex.description||'')}</strong><pre class="source">${esc(ex.code||ex.example||'')}</pre></div>`;
        else body += `<pre class="source">${esc(ex)}</pre>`;
      });
    }
    const debug = info.debugging_tips || info.debugging;
    if (debug) {
      body += '<h4 style="margin:12px 0 8px;">Debugging Tips</h4>';
      if (Array.isArray(debug)) debug.forEach(d => { body += `<div style="margin-bottom:4px;">- ${esc(typeof d==='object'?(d.tip||d.description||JSON.stringify(d)):d)}</div>`; });
      else if (typeof debug === 'string') body += `<p>${esc(debug)}</p>`;
    }

    html += detailsCard(`${esc(folder)} <span class="score-bar"><span class="score-fill" style="width:${pct}%;background:${color}"></span></span> <span style="color:${color};font-size:12px;margin-left:4px;">${pct}%</span>`, body, false);
  });

  el.innerHTML = html;
}
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 viewer.py /path/to/repo [--port PORT]", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    port = None
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
            break

    if port is None:
        port = _find_free_port()

    blueprint_path = root / ".archie" / "blueprint.json"
    if not blueprint_path.exists():
        print(f"Warning: {blueprint_path} not found. Run /archie-init first.", file=sys.stderr)

    # Create server
    server = http.server.HTTPServer(("127.0.0.1", port), ArchieHandler)
    server.root = root  # type: ignore[attr-defined]

    url = f"http://localhost:{port}"
    print(f"Archie Viewer — {root.name}")
    print(f"Serving on {url}")
    print("Press Ctrl+C to stop.\n")

    # Auto-open browser
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
