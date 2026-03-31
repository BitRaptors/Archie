#!/usr/bin/env python3
"""Archie blueprint viewer — zero-dep local HTML inspector.

Run: python3 viewer.py /path/to/repo [--port PORT]
Opens a browser showing only Archie-generated output.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import http.server
import json
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from _common import _load_json  # noqa: E402

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
    for rules_dir in (root / ".claude" / "rules", root / ".cursor" / "rules"):
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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        root: Path = self.server.root  # type: ignore[attr-defined]

        if path == "/":
            self._send_html(HTML_PAGE)
        elif path == "/api/blueprint":
            self._send_json(_load_json(root / ".archie" / "blueprint.json"))
        elif path == "/api/rules":
            self._send_json(_load_json(root / ".archie" / "rules.json"))
        elif path == "/api/generated-files":
            self._send_json(_collect_generated_files(root))
        elif path == "/api/folder-claude-mds":
            self._send_json(_collect_folder_claude_mds(root))
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

.header { background:var(--bg-card); border-bottom:1px solid var(--border); padding:12px 24px; display:flex; align-items:center; gap:16px; }
.header h1 { font-size:18px; color:var(--text-bright); font-weight:600; }
.header .meta { color:var(--text-dim); font-size:12px; }
.tabs { display:flex; gap:0; background:var(--bg-card); border-bottom:1px solid var(--border); padding:0 16px; }
.tab { padding:10px 20px; cursor:pointer; color:var(--text-dim); border-bottom:2px solid transparent; transition:all .15s; font-size:13px; }
.tab:hover { color:var(--text); background:var(--bg-hover); }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); }
.content { padding:20px 24px; max-width:1400px; margin:0 auto; }
.hidden { display:none !important; }

.card { background:var(--bg-card); border:1px solid var(--border); border-radius:8px; margin-bottom:16px; overflow:hidden; }
.card summary, .card-header { padding:12px 16px; font-weight:600; color:var(--text-bright); cursor:pointer; display:flex; align-items:center; gap:8px; }
.card summary:hover, .card-header:hover { background:var(--bg-hover); }
.card-body { padding:16px; border-top:1px solid var(--border); }
.badge { background:var(--accent); color:var(--bg); padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }
.badge.green { background:var(--accent2); }
.badge.yellow { background:var(--accent3); color:#1a1b26; }
.badge.red { background:var(--error); }

table { width:100%; border-collapse:collapse; font-size:13px; }
th { text-align:left; padding:8px 12px; background:var(--bg); color:var(--text-dim); font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.5px; }
td { padding:8px 12px; border-top:1px solid var(--border); vertical-align:top; }
tr:hover td { background:var(--bg-hover); }

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

pre.source { background:var(--bg); border:1px solid var(--border); border-radius:6px; padding:16px; overflow-x:auto; font-size:13px; line-height:1.5; color:var(--text-bright); white-space:pre; tab-size:4; }

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

.copy-btn { background:var(--bg); border:1px solid var(--border); color:var(--text-dim); padding:4px 10px; border-radius:4px; cursor:pointer; font-size:11px; }
.copy-btn:hover { color:var(--text); border-color:var(--accent); }

.sub-tabs { display:flex; gap:0; border-bottom:1px solid var(--border); margin-bottom:16px; flex-wrap:wrap; }
.sub-tab { padding:6px 14px; cursor:pointer; color:var(--text-dim); border-bottom:2px solid transparent; font-size:12px; }
.sub-tab:hover { color:var(--text); }
.sub-tab.active { color:var(--accent); border-bottom-color:var(--accent); }

.empty { text-align:center; padding:60px 20px; color:var(--text-dim); }
.empty h2 { color:var(--text); margin-bottom:8px; }

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
  <div class="tab" data-tab="generated-files">Generated Files</div>
  <div class="tab" data-tab="folder-tree">Folder CLAUDE.md</div>
  <div class="tab" data-tab="rules">Rules</div>
</div>

<div id="tab-blueprint" class="content"></div>
<div id="tab-generated-files" class="content hidden"></div>
<div id="tab-folder-tree" class="hidden" style="padding:0;"></div>
<div id="tab-rules" class="content hidden"></div>

<script>
let blueprint = {}, rules = {}, generatedFiles = {}, folderMds = {};

document.addEventListener('DOMContentLoaded', async () => {
  if (window.mermaid && mermaid.initialize) {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', themeVariables: {
      primaryColor: '#7aa2f7', primaryTextColor: '#c0caf5', lineColor: '#3b4261',
      primaryBorderColor: '#3b4261', secondaryColor: '#24283b'
    }});
  }
  const [bpRes, rulesRes, gfRes, fmRes] = await Promise.all([
    fetch('/api/blueprint').then(r=>r.json()).catch(()=>({})),
    fetch('/api/rules').then(r=>r.json()).catch(()=>({})),
    fetch('/api/generated-files').then(r=>r.json()).catch(()=>({})),
    fetch('/api/folder-claude-mds').then(r=>r.json()).catch(()=>({})),
  ]);
  blueprint=bpRes; rules=rulesRes; generatedFiles=gfRes; folderMds=fmRes;

  const meta = blueprint.meta || {};
  document.getElementById('repoName').textContent = meta.repository || '';
  document.title = (meta.repository || 'Archie') + ' — Blueprint Viewer';

  renderBlueprint();
  renderGeneratedFiles();
  renderFolderTree();
  renderRules();
  setupTabs();
});

function setupTabs() {
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      const id = t.dataset.tab;
      ['blueprint','generated-files','folder-tree','rules'].forEach(n => {
        const el = document.getElementById('tab-'+n);
        if (el) el.classList.toggle('hidden', n !== id);
      });
    });
  });
}

function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function renderMd(text) {
  if (!text) return '';
  try { return window.marked ? marked.parse(text) : '<pre>'+esc(text)+'</pre>'; }
  catch { return '<pre>'+esc(text)+'</pre>'; }
}
function detailsCard(title, body, open) {
  return `<details class="card"${open?' open':''}><summary>${title}</summary><div class="card-body">${body}</div></details>`;
}

// --- Blueprint Tab ---
function renderBlueprint() {
  const el = document.getElementById('tab-blueprint');
  if (!blueprint || !blueprint.meta) { el.innerHTML='<div class="empty"><h2>No Blueprint Found</h2><p>Run /archie-init first.</p></div>'; return; }
  let html = '';

  // Meta
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
      body += `<h4 style="margin:12px 0 8px;">State Management</h4><p><strong>Approach:</strong> ${esc(fe.state_management.approach)}</p>`;
    }
    html += detailsCard('Frontend', body, false);
  }

  // Deployment
  const dep = blueprint.deployment || {};
  if (dep.runtime_environment || (dep.ci_cd||[]).length) {
    let body = `<p><strong>Runtime:</strong> ${esc(dep.runtime_environment)}</p>`;
    if ((dep.compute_services||[]).length) body += `<p><strong>Compute:</strong> ${dep.compute_services.map(s=>esc(s)).join(', ')}</p>`;
    if (dep.container_runtime) body += `<p><strong>Container:</strong> ${esc(dep.container_runtime)}</p>`;
    if ((dep.ci_cd||[]).length) body += `<p><strong>CI/CD:</strong> ${dep.ci_cd.map(s=>esc(s)).join(', ')}</p>`;
    if ((dep.distribution||[]).length) body += `<p><strong>Distribution:</strong> ${dep.distribution.map(s=>esc(s)).join(', ')}</p>`;
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

  // Architecture Diagram
  if (blueprint.architecture_diagram) {
    let body = `<div class="mermaid-container"><pre class="mermaid">${esc(blueprint.architecture_diagram)}</pre></div>`;
    html += detailsCard('Architecture Diagram', body, false);
  }

  el.innerHTML = html;
  if (window.mermaid && mermaid.run) {
    try { mermaid.run({ nodes: document.querySelectorAll('.mermaid') }); } catch {}
  }
}

// --- Generated Files Tab (CLAUDE.md, AGENTS.md, rule files) ---
function renderGeneratedFiles() {
  const el = document.getElementById('tab-generated-files');
  const keys = Object.keys(generatedFiles);
  if (!keys.length) { el.innerHTML='<div class="empty"><h2>No Generated Files Found</h2></div>'; return; }

  let subTabsHtml = '<div class="sub-tabs" id="gfSubTabs">';
  keys.forEach((k,i) => { subTabsHtml += `<div class="sub-tab${i===0?' active':''}" data-key="${esc(k)}">${esc(k.split('/').pop())}</div>`; });
  subTabsHtml += '</div>';

  let panelsHtml = '';
  keys.forEach((k,i) => {
    const content = generatedFiles[k];
    panelsHtml += `<div class="gf-panel${i>0?' hidden':''}" data-key="${esc(k)}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <code style="color:var(--text-dim)">${esc(k)}</code>
        <button class="copy-btn" onclick="navigator.clipboard.writeText(generatedFiles['${k.replace(/'/g,"\\'")}'])">Copy</button>
      </div>
      <div class="md-content">${renderMd(content)}</div>
    </div>`;
  });

  el.innerHTML = subTabsHtml + panelsHtml;
  document.querySelectorAll('#gfSubTabs .sub-tab').forEach(st => {
    st.addEventListener('click', () => {
      document.querySelectorAll('#gfSubTabs .sub-tab').forEach(x=>x.classList.remove('active'));
      st.classList.add('active');
      document.querySelectorAll('.gf-panel').forEach(p=>p.classList.toggle('hidden', p.dataset.key!==st.dataset.key));
    });
  });
}

// --- Folder CLAUDE.md Tree Tab ---
function renderFolderTree() {
  const el = document.getElementById('tab-folder-tree');
  const keys = Object.keys(folderMds).sort();
  if (!keys.length) { el.innerHTML='<div class="content"><div class="empty"><h2>No Per-Folder CLAUDE.md Files</h2><p>Run /archie-intent-layer first.</p></div></div>'; return; }

  const tree = {};
  keys.forEach(k => {
    const parts = k.replace(/\/CLAUDE\.md$/, '').split('/');
    let node = tree;
    parts.forEach(p => { if (!node[p]) node[p] = {}; node = node[p]; });
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

// --- Rules Tab ---
function renderRules() {
  const el = document.getElementById('tab-rules');
  const ruleList = (rules.rules || []);
  if (!ruleList.length) { el.innerHTML='<div class="empty"><h2>No Rules Found</h2></div>'; return; }

  // Group by type
  const byType = {};
  ruleList.forEach(r => {
    const t = r.type || 'other';
    if (!byType[t]) byType[t] = [];
    byType[t].push(r);
  });

  let html = `<p style="color:var(--text-dim);margin-bottom:16px;">${ruleList.length} rules extracted from blueprint</p>`;

  Object.entries(byType).sort().forEach(([type, items]) => {
    let body = '<table><thead><tr><th>ID</th><th>Severity</th><th>Description</th></tr></thead><tbody>';
    body += items.map(r => {
      const sevClass = r.severity === 'error' ? 'red' : r.severity === 'warning' ? 'yellow' : '';
      return `<tr>
        <td><code>${esc(r.id)}</code></td>
        <td><span class="badge ${sevClass}">${esc(r.severity)}</span></td>
        <td>${esc(r.description || r.rule || '')}</td>
      </tr>`;
    }).join('');
    body += '</tbody></table>';
    html += detailsCard(`${esc(type)} <span class="badge">${items.length}</span>`, body, false);
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

    server = http.server.HTTPServer(("localhost", port), ArchieHandler)
    server.root = root  # type: ignore[attr-defined]

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
