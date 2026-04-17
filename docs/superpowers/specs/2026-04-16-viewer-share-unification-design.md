# Viewer-Share Unification Design

## Goal

Make the share React app the single UI for both local and remote viewing. The viewer.py becomes a headless API server + static file server for the pre-built React app. All viewer-only features (Scan Reports, Dependencies, Files, Rules CRUD) move into the share React app's ReportPage.

## Architecture

### Current State

```
LOCAL:  python3 viewer.py /repo  -->  embedded HTML (vanilla JS, 32KB)  -->  /api/* (local .archie/ files)
REMOTE: archie-share upload     -->  Supabase store  -->  React SPA on Vercel  -->  Supabase API
```

### Target State

```
LOCAL:  python3 viewer.py /repo  -->  serves pre-built React SPA  -->  /api/* (local .archie/ files)
REMOTE: archie-share upload     -->  Supabase store  -->  same React SPA on Vercel  -->  Supabase API
```

One React app, two data sources. URL-based detection: `localhost` = local API, otherwise = Supabase.

## Data Layer Changes

### 1. Upload Bundle Expansion (upload.py)

Current bundle fields: `blueprint`, `health`, `scan_meta`, `rules_adopted`, `rules_proposed`, `scan_report`, `semantic_duplications`

New fields to add:

| Field | Source File | Notes |
|-------|------------|-------|
| `scan_reports` | `.archie/scan_history/*.md` + `scan_report_*.md` | Array of `{filename, date, content}` |
| `dependency_graph` | `.archie/dependency_graph.json` | Full graph JSON |
| `generated_files` | `CLAUDE.md`, `AGENTS.md`, `.claude/rules/*` | Dict of `{path: content}` |
| `folder_claude_mds` | Recursive `**/CLAUDE.md` | Dict of `{relative_path: content}` |
| `ignored_rules` | `.archie/ignored_rules.json` | Array of ignored rule objects |
| `drift_report` | `.archie/drift_report.json` | Drift findings |
| `health_history` | `.archie/health_history.json` | Array of historical snapshots |

### 2. API Type Extension (api.ts)

```typescript
export interface Bundle {
  blueprint: any
  health?: any
  scan_meta?: any
  rules_adopted?: any
  rules_proposed?: any
  scan_report?: string
  semantic_duplications?: SemanticDuplication[]
  // New fields
  scan_reports?: ScanReport[]
  dependency_graph?: any
  generated_files?: Record<string, string>
  folder_claude_mds?: Record<string, string>
  ignored_rules?: any[]
  drift_report?: any
  health_history?: any[]
}

interface ScanReport {
  filename: string
  date: string
  content: string
}
```

### 3. Data Provider Abstraction (new: lib/data.ts)

```typescript
type DataMode = 'local' | 'remote'

function detectMode(): DataMode {
  return window.location.hostname === 'localhost' ? 'local' : 'remote'
}

async function fetchBundle(tokenOrNull: string | null): Promise<ReportResponse> {
  if (detectMode() === 'local') {
    // Fetch from local viewer.py API endpoints
    const [blueprint, rules, health, ...] = await Promise.all([
      fetch('/api/blueprint').then(r => r.json()),
      fetch('/api/rules').then(r => r.json()),
      // ... all endpoints
    ])
    return { bundle: { blueprint, rules_adopted: rules, health, ... }, created_at: '' }
  } else {
    // Existing Supabase fetch
    return fetchReport(token!)
  }
}
```

### 4. Rules CRUD (local mode only)

The viewer.py already has `POST /api/rules`. The React app needs a rules editor component that:
- Shows adopted rules with edit/delete controls
- Shows proposed rules with "Adopt" button
- Shows ignored rules (collapsible)
- "Add Rule" form
- Only visible in local mode (no CRUD for remote/shared reports)

## UI Changes to ReportPage

### Sidebar Extension

Current sidebar groups + new items marked with *:

```
Overview
  Summary
  Health
  Diagram
  Workspace Topology

*Scan Reports              (new section)

Rules
  Architecture Rules
  Development Rules
  *Rules Management        (new, local mode only - edit/add/delete)

Design
  Key Decisions
  Trade-offs

Practice
  Implementation Guidelines
  Communications

Inventory
  Components
  Technology Stack
  Deployment

*Dependencies              (new section - vis.js graph)

*Files                     (new section - tree browser)

Risks
  Architectural Problems
  Pitfalls

*Share / Get Started       (local: Share button, remote: Try Archie CTA)
```

### New Components Needed

#### ScanReportsSection
- List of scan reports (sidebar with dates, main with rendered markdown)
- Conditional: only shown if `bundle.scan_reports` exists and has entries

#### DependencyGraphSection
- vis-network interactive graph (port from viewer.py)
- Node sizing by file count, color by component
- Red border for cycles, dashed edges for cross-component
- Click node for detail sidebar
- Conditional: only shown if `bundle.dependency_graph` exists

#### FilesSection
- Tree browser for generated_files + folder_claude_mds
- Groups: Root Files, Rule Files, Per-Folder CLAUDE.md
- Markdown rendering for selected file
- Conditional: only shown if either files dict has entries

#### RulesManagementSection
- Edit severity, toggle, delete adopted rules
- Adopt proposed rules
- Show ignored rules
- Add new rule form
- Local mode only (`detectMode() === 'local'`)

#### ShareButton
- Visible in local mode only
- Calls upload.py logic (or a new `/api/share` endpoint on viewer.py)
- Shows resulting share URL with copy button

## viewer.py Changes

### Remove
- The entire `HTML_PAGE` string (~1500 lines of embedded HTML/CSS/JS)
- The `renderFiles()`, `renderDashboard()`, etc. JS functions

### Keep
- All `/api/*` endpoint handlers (they become the local data source)
- `POST /api/rules` handler
- Python HTTP server infrastructure

### Add
- Static file serving for the pre-built React dist (index.html, JS/CSS bundles)
- `POST /api/share` endpoint (runs upload logic, returns share URL)
- SPA fallback: any non-`/api/` route serves `index.html` (for React Router)

### React Dist Embedding
- The pre-built React dist gets embedded in viewer.py as base64-encoded assets (same single-file approach)
- Build script: `npm run build` in `share/viewer/`, then a Python script packs `dist/` into viewer.py
- Alternative: viewer.py reads from a `viewer_dist/` sibling directory. The npm package ships this directory alongside viewer.py.

Decision: **Use a sibling directory** (`viewer_dist/`). Simpler build flow, and the npm package already copies multiple files to `.archie/`. One more directory is cleaner than base64-encoding a React bundle into Python.

## Routing

### Local Mode
```
/              -> React SPA (index.html from viewer_dist/)
/r/:token      -> not used locally (no token routing needed)
/api/*         -> viewer.py API handlers
/*             -> SPA fallback to index.html
```

The React app detects local mode and skips the token-based data fetch, instead calling `/api/*` directly.

### Remote Mode (Vercel)
```
/              -> HomePage (install CTA)
/r/:token      -> CoverPage -> ReportPage (fetches from Supabase)
```

No changes to remote routing.

### React Router Update

```typescript
// main.tsx
<Routes>
  <Route path="/" element={isLocal ? <ReportPage /> : <HomePage />} />
  <Route path="/r/:token" element={<CoverPage />} />
  <Route path="/r/:token/details" element={<ReportPage />} />
</Routes>
```

Local mode: `/` goes directly to ReportPage (no cover page, no token needed).

## Build & Distribution Flow

### Development
```bash
cd share/viewer
npm run dev          # Vite dev server on :5173
                     # For local testing: run viewer.py separately, 
                     # configure Vite proxy to forward /api/* to viewer.py
```

### Build & Package
```bash
cd share/viewer
npm run build                          # -> dist/
python3 scripts/pack_viewer_dist.py    # copies dist/ to npm-package/assets/viewer_dist/
```

### npm Package Distribution
```
npm-package/assets/
  viewer.py            (headless API server + static file server)
  viewer_dist/         (pre-built React SPA)
    index.html
    assets/
      index-[hash].js
      index-[hash].css
  upload.py
  ...other scripts...
```

archie.mjs copies `viewer_dist/` directory to `.archie/viewer_dist/` alongside viewer.py.

## Migration Checklist

1. Expand upload.py bundle with new fields
2. Expand Supabase function to store/return new fields  
3. Add Bundle type extensions in api.ts
4. Create data provider abstraction (lib/data.ts)
5. Build 4 new React components (ScanReports, Dependencies, Files, RulesManagement)
6. Add ShareButton component
7. Extend ReportPage sidebar + section rendering
8. Extend scroll tracking (TRACKED_IDS)
9. Strip viewer.py HTML, add static file serving + SPA fallback
10. Add `/api/share` endpoint to viewer.py
11. Create build/pack script for viewer_dist
12. Update archie.mjs to copy viewer_dist/ directory
13. Update vite.config.ts with /api proxy for local dev
14. Test local mode end-to-end
15. Test remote mode (Vercel) end-to-end
16. Update verify_sync.py for new files
