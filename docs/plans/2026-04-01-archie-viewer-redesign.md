# Archie Viewer Redesign

## Overview

Full rewrite of the `/archie-viewer` GUI. Single HTML page embedded in `viewer.py`, styled with v1's color palette (Ink/Teal/Papaya/Tangerine/Brandy), Tailwind CSS from CDN. Displays all scan and deep-scan artifacts. Includes rule management (enable/disable, severity, add/delete).

## Architecture

### Python Server (`viewer.py`)

Same pattern as current: `http.server.HTTPServer`, single embedded HTML string, auto-opens browser on launch.

### API Endpoints

| Method | Path | Source | Purpose |
|--------|------|--------|---------|
| GET | `/api/blueprint` | `.archie/blueprint.json` | Architecture blueprint |
| GET | `/api/rules` | `.archie/rules.json` | Adopted rules |
| GET | `/api/health` | Run `measure_health.py` or read cached | Latest health metrics |
| GET | `/api/health-history` | `.archie/health_history.json` | Historical health scores |
| GET | `/api/scan-reports` | List `.archie/scan_report_*.md` | All scan report filenames+dates |
| GET | `/api/scan-report/{filename}` | `.archie/scan_report_*.md` | Single report content |
| GET | `/api/function-complexity` | `.archie/function_complexity.json` | Per-function complexity snapshot |
| GET | `/api/drift` | `.archie/drift_report.json` | Drift findings |
| GET | `/api/generated-files` | `CLAUDE.md`, `AGENTS.md`, `.claude/rules/*.md` | Generated markdown files |
| GET | `/api/folder-claude-mds` | `**/CLAUDE.md` (non-root) | Per-folder CLAUDE.md tree |
| GET | `/api/ignored-rules` | `.archie/ignored_rules.json` | Rejected rules |
| POST | `/api/rules` | Write `.archie/rules.json` | Update rules (enable/disable, severity, add/delete) |

### Frontend Stack (all CDN)

- **Tailwind CSS** — utility classes, v1 color palette via CSS variables
- **Chart.js** — trend line charts on dashboard
- **marked.js** — markdown rendering for scan reports and generated files
- **mermaid** — architecture diagrams
- **Vanilla JS** — no framework, modular functions per tab

## Color Palette (from v1)

- **Ink** `#023047` — primary dark, text, backgrounds
- **Teal** `#219ebc` — primary interactive, CTAs, active states
- **Papaya** `#8ecae6` — surfaces, panels, borders
- **Tangerine** `#ffb703` — accent highlights
- **Brandy** `#fb8500` — errors, warnings, destructive

Light default, dark mode via class toggle.

## Tab 1: Dashboard

**Top row — metric cards** (horizontal):
- Erosion, Gini, Top-20% share, Verbosity, LOC
- Each: current value, colored status (good/moderate/high), delta from last scan

**Middle — trend chart** (Chart.js):
- Lines: erosion, gini, verbosity over time from health_history.json
- LOC as secondary axis
- X-axis: scan dates, hover for values

**Bottom — two panels side by side:**
- Left: Top complex functions table (sorted by branching complexity)
- Right: Abstraction waste (single-method classes, tiny functions)

## Tab 2: Scan Reports

**Two-column layout** (v1 Blueprint View pattern):
- Left sidebar (w-64): all `scan_report_*.md` listed by date descending, nav items with `rounded-lg`, active `bg-teal/5 text-teal font-bold`
- Right content: `bg-white/60 rounded-3xl shadow-inner`, markdown rendered with prose styling
- Latest report pre-selected

## Tab 3: Blueprint

**Two-column layout** (v1 Blueprint View pattern):
- Left sidebar: section navigation — Executive Summary, Components, Decisions, Trade-offs, Communication, Technology, Pitfalls, Guidelines, Diagram
- Right content: collapsible cards with `border-papaya-400/60`, tables, mermaid diagrams
- Same data as current viewer, reskinned to v1

## Tab 4: Rules

**Full-width card list** with management controls:

Each rule card:
- Left: toggle switch (enabled/disabled), severity dropdown (error/warn), ID badge
- Center: description bold, rationale smaller below
- Right: source badge (scan-adopted/deep-scan), scope if present

Top bar:
- Filter by severity (all/error/warn)
- Filter by source (all/scan-adopted/deep-scan)
- "Add Rule" button — inline form (id, description, rationale, severity)

Changes auto-save via POST to `/api/rules`. Toast confirmation.

Bottom: collapsible ignored rules section with un-ignore option.

## Tab 5: Files

**Two-column layout:**
- Left sidebar: file tree grouped by type
  - Root: CLAUDE.md, AGENTS.md
  - Rules: .claude/rules/*.md
  - Per-folder: collapsible directory tree of CLAUDE.md files
- Right content: markdown rendered with prose styling, copy button

## Key v1 Layout Patterns

- Page gradient: `bg-gradient-to-br from-papaya-50 via-white to-teal-50/10`
- Cards: `rounded-lg border border-papaya-400/60 bg-white shadow-sm`
- Active nav: `bg-teal/5 text-teal font-bold`
- Inactive nav: `text-ink/60 hover:bg-papaya-300/30`
- Content panels: `bg-white/60 border border-papaya-400/60 rounded-3xl shadow-inner`
- Buttons: `rounded-xl`, teal primary, papaya secondary
- Header: `border-b bg-white/50 backdrop-blur-sm sticky top-0`
- Borders: `border-papaya-400/60` primary, `border-papaya-300` subtle
- Badge: `rounded-full px-2.5 py-0.5 text-xs font-semibold`
