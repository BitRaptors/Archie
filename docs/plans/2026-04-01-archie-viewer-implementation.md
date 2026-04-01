# Archie Viewer Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the `/archie-viewer` as a premium single-page GUI with v1 styling, displaying all scan/deep-scan artifacts and providing rule management.

**Architecture:** Single HTML page embedded in `viewer.py`. Python `http.server` serves the page and API endpoints (GET for data, POST for rule writes). Frontend uses Tailwind CSS, Chart.js, marked.js, mermaid — all from CDN. Vanilla JS, no framework.

**Tech Stack:** Python 3.9+ stdlib, Tailwind CSS CDN, Chart.js CDN, marked.js CDN, mermaid CDN

**Design doc:** `docs/plans/2026-04-01-archie-viewer-redesign.md`

---

### Task 1: Python Server — API Endpoints

**Files:**
- Rewrite: `archie/standalone/viewer.py` (complete rewrite)

**Step 1: Write the Python server with all API endpoints**

The server needs these endpoints:

```python
# GET endpoints (read JSON files from .archie/)
GET /                          → serve HTML_PAGE
GET /api/blueprint             → .archie/blueprint.json
GET /api/rules                 → .archie/rules.json
GET /api/health                → run measure_health.py, return JSON
GET /api/health-history        → .archie/health_history.json
GET /api/scan-reports          → list all .archie/scan_report_*.md with dates
GET /api/scan-report/<name>    → single scan report markdown content
GET /api/function-complexity   → .archie/function_complexity.json
GET /api/drift                 → .archie/drift_report.json
GET /api/generated-files       → CLAUDE.md, AGENTS.md, .claude/rules/*.md
GET /api/folder-claude-mds     → all non-root **/CLAUDE.md files
GET /api/ignored-rules         → .archie/ignored_rules.json

# POST endpoint (write)
POST /api/rules                → write updated rules to .archie/rules.json
```

Key implementation details:
- `/api/health` should read `/tmp/archie_health.json` if it exists (from last scan), otherwise read from `health_history.json` latest entry. Do NOT run measure_health.py on every request — it's too slow.
- `/api/scan-reports` returns `[{"filename": "scan_report_2026-03-31.md", "date": "2026-03-31"}, ...]` sorted by date descending.
- `/api/scan-report/<name>` validates the filename matches `scan_report*.md` pattern to prevent path traversal.
- `POST /api/rules` reads request body as JSON, validates it has a `rules` array, writes to `.archie/rules.json`.
- Reuse `_load_json`, `_read_text`, `_find_free_port`, `_collect_folder_claude_mds`, `_collect_generated_files` from current viewer.
- Keep the auto-open browser behavior.
- Set `HTML_PAGE = ""` as placeholder — we'll fill it in subsequent tasks.

**Step 2: Test the server manually**

Run: `python3 archie/standalone/viewer.py /path/to/project-with-archie-data`
Verify: Server starts, browser opens, API endpoints return JSON when hit with curl.

```bash
curl http://localhost:<port>/api/scan-reports
curl http://localhost:<port>/api/rules
curl http://localhost:<port>/api/health-history
```

**Step 3: Commit**

```bash
git add archie/standalone/viewer.py
git commit -m "feat: viewer server rewrite with full API endpoints"
```

---

### Task 2: HTML Shell — Header, Tabs, v1 Palette

**Files:**
- Modify: `archie/standalone/viewer.py` (fill in `HTML_PAGE`)

**Step 1: Write the HTML shell with Tailwind CDN and v1 color palette**

The HTML needs:
- `<head>`: Tailwind CDN (`<script src="https://cdn.tailwindcss.com">`), Chart.js CDN, marked.js CDN, mermaid CDN
- Tailwind config inline: custom colors (ink, teal, papaya, tangerine, brandy) with all shades
- CSS variables for light/dark mode matching v1's `globals.css`
- Header bar: Archie logo/title, project name, dark mode toggle
- Tab bar: Dashboard, Scan Reports, Blueprint, Rules, Files
- Tab content containers (hidden by default, shown on click)
- JS: tab switching logic, data fetching on load

v1 layout patterns to use:
```
Header: "border-b bg-white/50 px-8 py-6 flex items-center justify-between backdrop-blur-sm sticky top-0 z-20"
Tab bar: "flex items-center gap-8 border-b border-papaya-300 bg-white/30 px-8"
Active tab: "text-teal border-teal border-b-2 font-bold"
Inactive tab: "text-ink/40 hover:text-ink/60 border-transparent"
Page background: "bg-gradient-to-br from-papaya-50 via-white to-teal-50/10 min-h-screen"
```

**Step 2: Test**

Run viewer, verify:
- Page loads with v1 colors (warm papaya background, ink text)
- Header shows project name
- 5 tabs render and switch correctly
- All tabs show empty placeholder content
- Dark mode toggle switches palette

**Step 3: Commit**

```bash
git commit -m "feat: viewer HTML shell with v1 palette and tab navigation"
```

---

### Task 3: Dashboard Tab

**Files:**
- Modify: `archie/standalone/viewer.py` (add dashboard JS/HTML to HTML_PAGE)

**Step 1: Write the dashboard rendering function**

Fetches `/api/health` and `/api/health-history`. Renders:

**Metric cards row** — 5 cards in a flex row:
```
Card: "rounded-xl border border-papaya-400/60 bg-white p-5 shadow-sm flex-1"
Label: "text-xs font-bold uppercase tracking-widest text-ink/40"
Value: "text-3xl font-black text-ink mt-1"
Status dot: colored circle — green (good), tangerine (moderate), brandy (high)
Delta: "text-xs mt-1" — "+0.03 since last scan" or "no change"
```

Thresholds for status colors:
- Erosion: <0.3 green, 0.3-0.5 tangerine, >0.5 brandy
- Gini: <0.4 green, 0.4-0.6 tangerine, >0.6 brandy
- Top-20%: <0.5 green, 0.5-0.7 tangerine, >0.7 brandy
- Verbosity: <0.05 green, 0.05-0.15 tangerine, >0.15 brandy
- LOC: always teal (neutral), show delta as count

**Trend chart** — Chart.js line chart:
```
Container: "rounded-3xl border border-papaya-400/60 bg-white/60 p-6 shadow-inner mt-6"
```
- Lines: erosion (brandy), gini (ink), verbosity (teal)
- Secondary Y axis for LOC
- X axis: dates from health_history.json
- Tooltip on hover

**Bottom two panels** — flex row:
```
Container: "grid grid-cols-2 gap-6 mt-6"
Panel: "rounded-xl border border-papaya-400/60 bg-white p-5"
```
- Left: Top complex functions table (from `/api/health` → functions array, top 10 by CC)
- Right: Abstraction waste summary (from `/api/health` → waste object)

**Step 2: Test**

Run viewer on BabyWeather.Android (which has health data). Verify:
- 5 metric cards render with correct values and colors
- Chart shows trend lines if health_history.json has >1 entry
- Complex functions table populated
- Waste panel shows counts

**Step 3: Commit**

```bash
git commit -m "feat: viewer dashboard with metric cards, trend chart, complexity table"
```

---

### Task 4: Scan Reports Tab

**Files:**
- Modify: `archie/standalone/viewer.py` (add scan reports JS/HTML)

**Step 1: Write the scan reports rendering function**

Fetches `/api/scan-reports` for the list, `/api/scan-report/<name>` for content.

**Two-column layout** (v1 Blueprint View pattern):
```
Container: "flex gap-6 h-[calc(100vh-140px)]"

Left sidebar:
"w-64 flex-shrink-0 overflow-y-auto pr-4"
Section header: "text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-4"
Nav items: "w-full text-left px-3 py-2 rounded-lg transition-all duration-200 block"
Active: "bg-teal/5 text-teal font-bold"
Inactive: "text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium"
Latest badge: "bg-teal text-white text-[10px] px-2 py-0.5 rounded-full font-bold ml-2"

Right content:
"flex-1 overflow-y-auto bg-white/60 border border-papaya-400/60 rounded-3xl shadow-inner p-10"
Markdown: rendered via marked.js with prose styling
```

Click a report → fetch its content → render markdown in right panel. Latest pre-selected on load.

**Step 2: Test**

Run viewer on a project with multiple scan reports. Verify:
- Left sidebar lists all reports by date
- Clicking switches content
- Markdown renders properly (tables, headers, code blocks)
- Latest is pre-selected

**Step 3: Commit**

```bash
git commit -m "feat: viewer scan reports tab with history navigation"
```

---

### Task 5: Blueprint Tab

**Files:**
- Modify: `archie/standalone/viewer.py` (add blueprint JS/HTML)

**Step 1: Write the blueprint rendering function**

Fetches `/api/blueprint`. Same two-column layout as Scan Reports.

**Left sidebar:** Section navigation for blueprint sections:
- Executive Summary, Components, Decisions, Trade-offs, Communication, Technology, Frontend (if exists), Pitfalls, Implementation Guidelines, Architecture Diagram
- Scroll-to-section on click

**Right content:** Sections rendered as cards:
```
Card: "rounded-xl border border-papaya-400/60 bg-white mb-4 overflow-hidden"
Card header: "px-5 py-4 font-bold text-ink flex items-center justify-between cursor-pointer hover:bg-papaya-50 transition-colors"
Card body: "px-5 py-4 border-t border-papaya-300/50"
Badge: "bg-teal/10 text-teal text-xs font-bold px-2 py-0.5 rounded-full"
```

Components → table. Decisions → left-bordered items. Trade-offs → accept/benefit pairs. Pitfalls → brandy left-border. Diagram → mermaid rendered.

Port the rendering logic from current viewer but with v1 styled cards instead of `<details>`.

**Step 2: Test**

Run on a project with blueprint.json. Verify all sections render, diagram displays, nav scrolls.

**Step 3: Commit**

```bash
git commit -m "feat: viewer blueprint tab with v1 card styling"
```

---

### Task 6: Rules Tab — Read + Management

**Files:**
- Modify: `archie/standalone/viewer.py` (add rules JS/HTML)

**Step 1: Write the rules rendering function with management controls**

Fetches `/api/rules` and `/api/ignored-rules`.

**Top bar:**
```
Container: "flex items-center justify-between mb-6"
Filters: "flex gap-2"
Filter button: "px-3 py-1.5 rounded-lg text-xs font-bold transition-all"
Active filter: "bg-teal/10 text-teal border border-teal/20"
Inactive filter: "text-ink/40 hover:bg-papaya-300/20 border border-transparent"
Add button: "px-4 py-2 rounded-xl bg-teal text-white font-bold text-sm shadow-lg shadow-teal/20 hover:bg-teal/90"
```

**Each rule card:**
```
Card: "rounded-xl border border-papaya-400/60 bg-white p-4 mb-3 flex items-start gap-4 transition-all hover:shadow-md"

Left column (controls):
- Toggle switch (CSS-only): enabled/disabled state
- Severity dropdown: "rounded-lg border border-papaya-400/60 text-xs font-bold px-2 py-1"

Center column (content):
- ID: "text-[10px] font-bold text-ink/30 uppercase tracking-wider"
- Description: "font-bold text-ink text-sm mt-1"
- Rationale: "text-xs text-ink/60 mt-1 leading-relaxed"
- Scope (if applies_to/file_pattern): "text-[10px] font-mono text-teal bg-teal/5 px-2 py-0.5 rounded mt-2 inline-block"

Right column (metadata):
- Source badge: "text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
  scan-adopted: "bg-papaya-300/30 text-ink/40"
  deep-scan: "bg-teal/10 text-teal"
- Mechanical fields (if check exists): expandable, show check type + patterns
```

**Toggle/severity change:** JavaScript collects all rules, sends POST to `/api/rules` with full rules array. Show toast: "Rules saved" (teal) or "Error saving" (brandy).

**Add Rule form** — inline, appears below the top bar when "Add Rule" clicked:
```
Form: "rounded-xl border border-teal/20 bg-teal/5 p-4 mb-4"
Fields: id (auto-generated scan-NNN), description (text), rationale (textarea), severity (dropdown)
Buttons: Save (teal), Cancel (ghost)
```

**Ignored rules** — collapsible panel at bottom:
```
Toggle: "text-ink/40 text-xs font-bold uppercase tracking-wider cursor-pointer hover:text-ink"
List: each ignored rule with un-ignore button
```

**Step 2: Test**

Run on BabyWeather.Android (which has rules.json with adopted rules). Verify:
- Rules render with correct data
- Toggle switch changes state
- Severity dropdown changes value
- Changes persist (refresh page, rules still changed)
- Add rule form works
- Filters work

**Step 3: Commit**

```bash
git commit -m "feat: viewer rules tab with enable/disable, severity, add rule"
```

---

### Task 7: Files Tab

**Files:**
- Modify: `archie/standalone/viewer.py` (add files JS/HTML)

**Step 1: Write the files rendering function**

Fetches `/api/generated-files` and `/api/folder-claude-mds`. Merges into one tree.

**Two-column layout** (same as Scan Reports/Blueprint):

**Left sidebar — file tree:**
```
Group header: "text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2 mt-4"
```
Groups:
- "Root Files" → CLAUDE.md, AGENTS.md
- "Rule Files" → .claude/rules/*.md
- "Per-Folder CLAUDE.md" → collapsible directory tree

Directory toggle:
```
"px-3 py-1.5 text-xs font-bold text-ink/40 cursor-pointer hover:text-ink flex items-center gap-1"
Arrow: rotates on expand/collapse
```

File items: same nav styling as Scan Reports sidebar.

**Right content:** Markdown rendered via marked.js with prose styling. Copy button top-right.

**Step 2: Test**

Run on a project with generated files and per-folder CLAUDE.md. Verify tree renders, clicking shows content, copy works.

**Step 3: Commit**

```bash
git commit -m "feat: viewer files tab with tree navigation"
```

---

### Task 8: Sync and Deploy

**Files:**
- Copy: `archie/standalone/viewer.py` → `npm-package/assets/viewer.py`
- Copy: `archie/standalone/viewer.py` → BabyWeather.Android `.archie/viewer.py`

**Step 1: Sync to npm-package**

```bash
cp archie/standalone/viewer.py npm-package/assets/viewer.py
python3 scripts/verify_sync.py
```

**Step 2: Update BabyWeather.Android**

```bash
cp archie/standalone/viewer.py /Users/hamutarto/DEV/BitRaptors/BabyWeather.Android/.archie/viewer.py
```

**Step 3: Test end-to-end on BabyWeather.Android**

```bash
python3 /Users/hamutarto/DEV/BitRaptors/BabyWeather.Android/.archie/viewer.py /Users/hamutarto/DEV/BitRaptors/BabyWeather.Android
```

Verify all 5 tabs work with real data.

**Step 4: Commit**

```bash
git add archie/standalone/viewer.py npm-package/assets/viewer.py
git commit -m "feat: archie-viewer complete rewrite with v1 design, rule management, all scan artifacts"
```
