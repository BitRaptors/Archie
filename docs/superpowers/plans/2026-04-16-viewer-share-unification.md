# Viewer-Share Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the viewer.py embedded HTML with the share React app, making one UI for both local and remote viewing. Add the missing viewer-only features (Scan Reports, Dependencies, Files, Rules CRUD) to the React app.

**Architecture:** The viewer.py keeps its API endpoints but drops the embedded HTML. Instead it serves a pre-built React dist from a `viewer_dist/` sibling directory. The React app detects local vs remote mode by hostname and fetches data from the appropriate source. New React components handle the 4 missing feature sections.

**Tech Stack:** Python 3.9+ (stdlib), React 18, TypeScript, Vite 6, Tailwind CSS, vis-network (new dep for dependency graph), react-markdown, mermaid

**Spec:** `docs/superpowers/specs/2026-04-16-viewer-share-unification-design.md`

---

## File Map

### New Files
- `share/viewer/src/lib/data.ts` — Data provider abstraction (local vs remote)
- `share/viewer/src/components/ScanReportsSection.tsx` — Scan reports list + viewer
- `share/viewer/src/components/DependencyGraphSection.tsx` — vis-network interactive graph
- `share/viewer/src/components/FilesSection.tsx` — Tree browser for CLAUDE.md/rule files
- `share/viewer/src/components/RulesManagementSection.tsx` — Rules CRUD (local mode)
- `share/viewer/src/components/ShareButton.tsx` — Share upload trigger
- `scripts/pack_viewer_dist.py` — Build script to copy React dist to npm-package

### Modified Files
- `share/viewer/src/lib/api.ts` — Expand Bundle interface with new fields
- `share/viewer/src/main.tsx` — Add local mode route
- `share/viewer/src/pages/ReportPage.tsx` — Add new sidebar sections + render new components
- `share/viewer/vite.config.ts` — Add /api proxy for local dev
- `share/viewer/package.json` — Add vis-network dependency
- `archie/standalone/viewer.py` — Strip HTML, add static file serving + SPA fallback + /api/share
- `archie/standalone/upload.py` — Expand bundle with new data fields
- `npm-package/bin/archie.mjs` — Copy viewer_dist/ directory
- `scripts/verify_sync.py` — Add viewer_dist sync check

---

## Task 1: Expand Bundle Type & Data Provider

**Files:**
- Modify: `share/viewer/src/lib/api.ts`
- Create: `share/viewer/src/lib/data.ts`

- [ ] **Step 1: Expand the Bundle interface**

In `share/viewer/src/lib/api.ts`, add the new fields after the existing ones:

```typescript
export interface ScanReport {
  filename: string
  date: string
  content: string
}

export interface Bundle {
  blueprint: any
  health?: any
  scan_meta?: any
  rules_adopted?: any
  rules_proposed?: any
  scan_report?: string
  semantic_duplications?: SemanticDuplication[]
  // Viewer-originated fields
  scan_reports?: ScanReport[]
  dependency_graph?: any
  generated_files?: Record<string, string>
  folder_claude_mds?: Record<string, string>
  ignored_rules?: any[]
  proposed_rules?: any[]
  drift_report?: any
  health_history?: any[]
}
```

- [ ] **Step 2: Create the data provider**

Create `share/viewer/src/lib/data.ts`:

```typescript
import { type Bundle, type ReportResponse, fetchReport } from './api'

export type DataMode = 'local' | 'remote'

export function detectMode(): DataMode {
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'local'
    : 'remote'
}

export function isLocalMode(): boolean {
  return detectMode() === 'local'
}

async function fetchJson(url: string): Promise<any> {
  const res = await fetch(url)
  if (!res.ok) return null
  return res.json()
}

export async function fetchLocalBundle(): Promise<ReportResponse> {
  const [blueprint, rules, health, healthHistory, scanReports, drift, depGraph, generatedFiles, folderMds, ignoredRules, proposedRules] = await Promise.all([
    fetchJson('/api/blueprint'),
    fetchJson('/api/rules'),
    fetchJson('/api/health'),
    fetchJson('/api/health-history'),
    fetchJson('/api/scan-reports'),
    fetchJson('/api/drift'),
    fetchJson('/api/dependency-graph'),
    fetchJson('/api/generated-files'),
    fetchJson('/api/folder-claude-mds'),
    fetchJson('/api/ignored-rules'),
    fetchJson('/api/proposed-rules'),
  ])

  // Load full content for each scan report
  const scanReportsWithContent = scanReports
    ? await Promise.all(
        scanReports.map(async (r: { filename: string; date: string }) => {
          const detail = await fetchJson(`/api/scan-report/${r.filename}`)
          return { filename: r.filename, date: r.date, content: detail?.content || '' }
        })
      )
    : []

  const bundle: Bundle = {
    blueprint: blueprint || {},
    health,
    rules_adopted: rules,
    proposed_rules: proposedRules,
    scan_report: scanReportsWithContent.length > 0 ? scanReportsWithContent[0].content : undefined,
    scan_reports: scanReportsWithContent,
    dependency_graph: depGraph,
    generated_files: generatedFiles,
    folder_claude_mds: folderMds,
    ignored_rules: ignoredRules,
    drift_report: drift,
    health_history: healthHistory,
  }

  return { bundle, created_at: new Date().toISOString() }
}

export async function loadBundle(token: string | null): Promise<ReportResponse> {
  if (detectMode() === 'local') {
    return fetchLocalBundle()
  }
  if (!token) throw new Error('No token provided')
  return fetchReport(token)
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd share/viewer && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```
feat(share): add Bundle type extensions and local data provider
```

---

## Task 2: Update Routing & ReportPage Data Loading

**Files:**
- Modify: `share/viewer/src/main.tsx`
- Modify: `share/viewer/src/pages/ReportPage.tsx`
- Modify: `share/viewer/vite.config.ts`

- [ ] **Step 1: Add local mode route to main.tsx**

Replace the Routes block in `share/viewer/src/main.tsx`:

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import 'highlight.js/styles/atom-one-dark.min.css'
import HomePage from './pages/HomePage'
import CoverPage from './pages/CoverPage'
import ReportPage from './pages/ReportPage'
import NotFoundPage from './pages/NotFoundPage'
import { isLocalMode } from './lib/data'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {isLocalMode() ? (
          <Route path="/" element={<ReportPage />} />
        ) : (
          <>
            <Route path="/" element={<HomePage />} />
            <Route path="/r/:token" element={<CoverPage />} />
            <Route path="/r/:token/details" element={<ReportPage />} />
          </>
        )}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
```

- [ ] **Step 2: Update ReportPage data loading**

In `share/viewer/src/pages/ReportPage.tsx`, replace the data loading logic (lines 1-44).

Replace the import of `fetchReport`:
```typescript
import { loadBundle, isLocalMode } from '@/lib/data'
import type { Bundle } from '@/lib/api'
```

Replace the useEffect data fetch (lines 36-44):
```typescript
  useEffect(() => {
    if (!isLocalMode() && !token) return
    loadBundle(token ?? null)
      .then((r) => {
        setBundle(r.bundle)
        setCreatedAt(r.created_at)
      })
      .catch((e) => setError(e.message))
  }, [token])
```

- [ ] **Step 3: Add Vite proxy for local development**

Update `share/viewer/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:51174',
        changeOrigin: true,
      },
    },
  },
})
```

Note: The port `51174` is for development only. The actual port will vary — devs should update this to match their viewer.py instance. When served by viewer.py in production, no proxy is needed.

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd share/viewer && npx tsc --noEmit`

- [ ] **Step 5: Commit**

```
feat(share): local mode routing and data loading via data provider
```

---

## Task 3: ScanReportsSection Component

**Files:**
- Create: `share/viewer/src/components/ScanReportsSection.tsx`

- [ ] **Step 1: Create the component**

```typescript
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { FileText, Calendar } from 'lucide-react'
import { type ScanReport } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  reports: ScanReport[]
}

export function ScanReportsSection({ reports }: Props) {
  const [activeIdx, setActiveIdx] = useState(0)

  if (reports.length === 0) return null

  const active = reports[activeIdx]

  return (
    <div className="flex gap-6 min-h-[400px]">
      {/* Sidebar list */}
      {reports.length > 1 && (
        <div className="w-56 shrink-0 space-y-1 overflow-y-auto max-h-[70vh]">
          {reports.map((r, i) => (
            <button
              key={r.filename}
              onClick={() => setActiveIdx(i)}
              className={cn(
                'w-full text-left px-3 py-2 rounded-xl text-xs transition-colors',
                i === activeIdx
                  ? 'bg-teal/10 text-teal font-bold'
                  : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
              )}
            >
              <div className="flex items-center gap-2">
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{r.filename.replace(/\.md$/, '')}</span>
              </div>
              {r.date && (
                <div className="flex items-center gap-1 mt-0.5 text-[10px] text-ink/30">
                  <Calendar className="w-3 h-3" />
                  <span>{r.date}</span>
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Report content */}
      <div className="flex-1 overflow-y-auto max-h-[70vh] bg-white/60 border border-papaya-400/60 rounded-2xl p-8">
        <div className="prose-archie text-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {active.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd share/viewer && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```
feat(share): add ScanReportsSection component
```

---

## Task 4: DependencyGraphSection Component

**Files:**
- Modify: `share/viewer/package.json` (add vis-network)
- Create: `share/viewer/src/components/DependencyGraphSection.tsx`

- [ ] **Step 1: Install vis-network**

Run: `cd share/viewer && npm install vis-network vis-data`

- [ ] **Step 2: Create the component**

Port the dependency graph visualization from viewer.py (lines ~1200-1450 of the embedded JS). Create `share/viewer/src/components/DependencyGraphSection.tsx`:

```typescript
import { useEffect, useRef, useState } from 'react'
import { Network, type Options } from 'vis-network'
import { DataSet } from 'vis-data'
import { cn } from '@/lib/utils'

interface DepNode {
  id: string
  label?: string
  component?: string
  files?: number
  in_cycle?: boolean
}

interface DepEdge {
  from: string
  to: string
  cross_component?: boolean
}

interface Props {
  graph: {
    nodes: DepNode[]
    edges: DepEdge[]
    cycles?: string[][]
  }
}

const COMPONENT_COLORS = [
  '#219ebc', '#ffb703', '#fb8500', '#8ecae6', '#023047',
  '#e63946', '#457b9d', '#2a9d8f', '#e9c46a', '#264653',
]

export function DependencyGraphSection({ graph }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const [selected, setSelected] = useState<DepNode | null>(null)

  useEffect(() => {
    if (!containerRef.current || !graph.nodes?.length) return

    // Assign colors by component
    const components = [...new Set(graph.nodes.map(n => n.component).filter(Boolean))]
    const colorMap: Record<string, string> = {}
    components.forEach((c, i) => {
      colorMap[c!] = COMPONENT_COLORS[i % COMPONENT_COLORS.length]
    })

    const nodes = new DataSet(
      graph.nodes.map(n => ({
        id: n.id,
        label: n.label || n.id.split('/').pop() || n.id,
        title: n.id,
        value: n.files || 1,
        color: {
          background: colorMap[n.component || ''] || '#8ecae6',
          border: n.in_cycle ? '#e63946' : colorMap[n.component || ''] || '#8ecae6',
          highlight: { background: '#ffb703', border: '#fb8500' },
        },
        borderWidth: n.in_cycle ? 3 : 1,
        font: { size: 11, color: '#023047' },
      }))
    )

    const edges = new DataSet(
      graph.edges.map((e, i) => ({
        id: `e${i}`,
        from: e.from,
        to: e.to,
        arrows: 'to',
        dashes: e.cross_component || false,
        color: { color: e.cross_component ? '#fb850080' : '#8ecae680' },
        width: 1,
      }))
    )

    const options: Options = {
      physics: {
        solver: 'barnesHut',
        barnesHut: { gravitationalConstant: -3000, springLength: 150 },
        stabilization: { iterations: 200 },
      },
      interaction: { hover: true, tooltipDelay: 100 },
      nodes: { shape: 'dot', scaling: { min: 8, max: 30 } },
      edges: { smooth: { type: 'continuous' } },
    }

    const network = new Network(containerRef.current, { nodes, edges }, options)
    networkRef.current = network

    network.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0]
        const node = graph.nodes.find(n => n.id === nodeId) || null
        setSelected(node)
      } else {
        setSelected(null)
      }
    })

    network.once('stabilizationIterationsDone', () => {
      network.setOptions({ physics: { enabled: false } })
    })

    return () => {
      network.destroy()
      networkRef.current = null
    }
  }, [graph])

  const cycleCount = graph.cycles?.length || 0
  const incomingEdges = selected ? graph.edges.filter(e => e.to === selected.id) : []
  const outgoingEdges = selected ? graph.edges.filter(e => e.from === selected.id) : []

  return (
    <div className="flex gap-6">
      <div className="flex-1">
        {/* Stats bar */}
        <div className="flex gap-4 mb-4 text-xs text-ink/50">
          <span>{graph.nodes.length} modules</span>
          <span>{graph.edges.length} dependencies</span>
          {cycleCount > 0 && (
            <span className="text-brandy font-bold">{cycleCount} cycles</span>
          )}
        </div>
        {/* Graph container */}
        <div
          ref={containerRef}
          className="w-full h-[500px] border border-papaya-400/60 rounded-2xl bg-white/60"
        />
        {/* Legend */}
        <div className="flex flex-wrap gap-3 mt-3 text-[10px] text-ink/40">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full border-2 border-red-500 bg-white inline-block" />
            In cycle
          </span>
          <span className="flex items-center gap-1">
            <span className="w-6 h-0 border-t-2 border-dashed border-brandy inline-block" />
            Cross-component
          </span>
        </div>
      </div>

      {/* Detail sidebar */}
      {selected && (
        <div className="w-64 shrink-0 bg-white/60 border border-papaya-400/60 rounded-2xl p-5 text-xs space-y-3">
          <p className="font-bold text-sm text-ink truncate" title={selected.id}>{selected.id}</p>
          {selected.component && (
            <p className="text-ink/40">Component: <span className="text-ink font-medium">{selected.component}</span></p>
          )}
          {selected.files != null && (
            <p className="text-ink/40">Files: <span className="text-ink font-medium">{selected.files}</span></p>
          )}
          <div>
            <p className="text-ink/40 mb-1">Incoming ({incomingEdges.length})</p>
            <div className="space-y-0.5 max-h-32 overflow-y-auto">
              {incomingEdges.map((e, i) => (
                <p key={i} className="text-ink/70 truncate">{e.from}</p>
              ))}
            </div>
          </div>
          <div>
            <p className="text-ink/40 mb-1">Outgoing ({outgoingEdges.length})</p>
            <div className="space-y-0.5 max-h-32 overflow-y-auto">
              {outgoingEdges.map((e, i) => (
                <p key={i} className="text-ink/70 truncate">{e.to}</p>
              ))}
            </div>
          </div>
          {selected.in_cycle && (
            <p className="text-brandy font-bold">Part of a dependency cycle</p>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd share/viewer && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```
feat(share): add DependencyGraphSection with vis-network
```

---

## Task 5: FilesSection Component

**Files:**
- Create: `share/viewer/src/components/FilesSection.tsx`

- [ ] **Step 1: Create the component**

Port the Files tab tree logic from viewer.py. Create `share/viewer/src/components/FilesSection.tsx`:

```typescript
import { useState, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { ChevronRight, FileText, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  generatedFiles?: Record<string, string>
  folderClaudeMds?: Record<string, string>
}

interface TreeNode {
  [key: string]: TreeNode | { _file: string }
}

function buildTree(keys: string[]): TreeNode {
  const tree: TreeNode = {}
  keys.forEach(key => {
    const parts = key.replace(/\/CLAUDE\.md$/, '').split('/')
    let current = tree
    parts.forEach((part, i) => {
      if (!current[part]) current[part] = {}
      if (i === parts.length - 1) {
        ;(current[part] as any)._file = key
      } else {
        current = current[part] as TreeNode
      }
    })
  })
  return tree
}

function TreeView({
  node,
  depth,
  activeFile,
  onSelect,
}: {
  node: TreeNode
  depth: number
  activeFile: string | null
  onSelect: (key: string) => void
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const keys = Object.keys(node)
    .filter(k => k !== '_file')
    .sort()

  return (
    <>
      {keys.map(k => {
        const child = node[k] as any
        const childKeys = Object.keys(child).filter(ck => ck !== '_file')
        const isLeaf = child._file && childKeys.length === 0
        const isOpen = expanded[k] ?? false

        if (isLeaf) {
          return (
            <button
              key={k}
              onClick={() => onSelect(child._file)}
              className={cn(
                'w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors',
                depth > 0 && 'ml-3',
                activeFile === child._file
                  ? 'bg-teal/10 text-teal font-bold'
                  : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
              )}
            >
              {k}/CLAUDE.md
            </button>
          )
        }

        return (
          <div key={k} className={cn(depth > 0 && 'ml-3')}>
            <button
              onClick={() => setExpanded(prev => ({ ...prev, [k]: !prev[k] }))}
              className="w-full flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-ink/40 hover:text-ink cursor-pointer"
            >
              <ChevronRight
                className={cn(
                  'w-3 h-3 transition-transform duration-200',
                  isOpen && 'rotate-90'
                )}
              />
              <span>{k}</span>
            </button>
            {isOpen && (
              <div>
                {child._file && (
                  <button
                    onClick={() => onSelect(child._file)}
                    className={cn(
                      'w-full text-left px-3 py-1.5 ml-3 rounded-lg text-xs transition-colors',
                      activeFile === child._file
                        ? 'bg-teal/10 text-teal font-bold'
                        : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
                    )}
                  >
                    CLAUDE.md
                  </button>
                )}
                <TreeView
                  node={child}
                  depth={depth + 1}
                  activeFile={activeFile}
                  onSelect={onSelect}
                />
              </div>
            )}
          </div>
        )
      })}
    </>
  )
}

export function FilesSection({ generatedFiles, folderClaudeMds }: Props) {
  const [activeFile, setActiveFile] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const allFiles = useMemo(() => {
    const files: Record<string, string> = {}
    if (generatedFiles) Object.assign(files, generatedFiles)
    if (folderClaudeMds) Object.assign(files, folderClaudeMds)
    return files
  }, [generatedFiles, folderClaudeMds])

  const rootFiles = useMemo(
    () => Object.keys(generatedFiles || {}).filter(k => !k.includes('/')).sort(),
    [generatedFiles]
  )
  const ruleFiles = useMemo(
    () => Object.keys(generatedFiles || {}).filter(k => k.startsWith('.claude/rules/')).sort(),
    [generatedFiles]
  )
  const fmKeys = useMemo(() => Object.keys(folderClaudeMds || {}).sort(), [folderClaudeMds])
  const tree = useMemo(() => buildTree(fmKeys), [fmKeys])

  const content = activeFile ? allFiles[activeFile] || '' : ''

  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="flex gap-6 min-h-[400px]">
      {/* Sidebar */}
      <div className="w-56 shrink-0 overflow-y-auto max-h-[70vh] space-y-4">
        {rootFiles.length > 0 && (
          <div>
            <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2">
              Root Files
            </p>
            {rootFiles.map(k => (
              <button
                key={k}
                onClick={() => setActiveFile(k)}
                className={cn(
                  'w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors',
                  activeFile === k
                    ? 'bg-teal/10 text-teal font-bold'
                    : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
                )}
              >
                {k}
              </button>
            ))}
          </div>
        )}
        {ruleFiles.length > 0 && (
          <div>
            <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2">
              Rule Files
            </p>
            {ruleFiles.map(k => (
              <button
                key={k}
                onClick={() => setActiveFile(k)}
                className={cn(
                  'w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors',
                  activeFile === k
                    ? 'bg-teal/10 text-teal font-bold'
                    : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
                )}
              >
                {k.split('/').pop()}
              </button>
            ))}
          </div>
        )}
        {fmKeys.length > 0 && (
          <div>
            <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2">
              Per-Folder CLAUDE.md
            </p>
            <TreeView node={tree} depth={0} activeFile={activeFile} onSelect={setActiveFile} />
          </div>
        )}
      </div>

      {/* Content pane */}
      <div className="flex-1 overflow-y-auto max-h-[70vh] bg-white/60 border border-papaya-400/60 rounded-2xl p-8">
        {activeFile ? (
          <>
            <div className="flex items-center justify-between mb-6">
              <code className="text-[10px] text-ink/40">{activeFile}</code>
              <button
                onClick={handleCopy}
                className="px-3 py-1 rounded-lg border border-papaya-400/60 text-[10px] text-ink/40 hover:text-ink hover:border-teal transition-colors flex items-center gap-1"
              >
                {copied ? <><Check className="w-3 h-3" /> Copied!</> : <><Copy className="w-3 h-3" /> Copy</>}
              </button>
            </div>
            <div className="prose-archie text-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {content}
              </ReactMarkdown>
            </div>
          </>
        ) : (
          <p className="text-ink/40">Select a file...</p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd share/viewer && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```
feat(share): add FilesSection tree browser component
```

---

## Task 6: RulesManagementSection Component

**Files:**
- Create: `share/viewer/src/components/RulesManagementSection.tsx`

- [ ] **Step 1: Create the component**

```typescript
import { useState } from 'react'
import { Shield, Trash2, Plus, ChevronDown, Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { isLocalMode } from '@/lib/data'

interface Rule {
  id: string
  severity: string
  description: string
  rationale?: string
  confidence?: number
  applies_to?: string
  source?: string
  check_type?: string
  check_value?: string
}

interface Props {
  adopted: Rule[]
  proposed?: Rule[]
  ignored?: Rule[]
  onRulesChange?: (rules: Rule[]) => void
}

export function RulesManagementSection({ adopted, proposed, ignored, onRulesChange }: Props) {
  const [filter, setFilter] = useState<'all' | 'error' | 'warn'>('all')
  const [showIgnored, setShowIgnored] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newRule, setNewRule] = useState({ id: '', severity: 'warn', description: '', rationale: '' })
  const local = isLocalMode()

  const filtered = adopted.filter(r =>
    filter === 'all' ? true : r.severity === filter
  )

  const saveRules = async (rules: Rule[]) => {
    if (!local) return
    await fetch('/api/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    })
    onRulesChange?.(rules)
  }

  const handleDelete = (id: string) => {
    const updated = adopted.filter(r => r.id !== id)
    saveRules(updated)
  }

  const handleSeverityChange = (id: string, severity: string) => {
    const updated = adopted.map(r => r.id === id ? { ...r, severity } : r)
    saveRules(updated)
  }

  const handleAdopt = (rule: Rule) => {
    const updated = [...adopted, { ...rule, source: 'proposed' }]
    saveRules(updated)
  }

  const handleAddRule = () => {
    if (!newRule.id || !newRule.description) return
    const updated = [...adopted, { ...newRule, source: 'manual' }]
    saveRules(updated)
    setNewRule({ id: '', severity: 'warn', description: '', rationale: '' })
    setShowAddForm(false)
  }

  return (
    <div className="space-y-6">
      {/* Filter bar */}
      <div className="flex items-center gap-2">
        {(['all', 'error', 'warn'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              'px-3 py-1 rounded-lg text-xs font-bold transition-colors',
              filter === f ? 'bg-teal text-white' : 'bg-papaya-50 text-ink/40 hover:text-ink'
            )}
          >
            {f === 'all' ? `All (${adopted.length})` : `${f} (${adopted.filter(r => r.severity === f).length})`}
          </button>
        ))}
        {local && (
          <button
            onClick={() => setShowAddForm(true)}
            className="ml-auto px-3 py-1 rounded-lg text-xs font-bold bg-teal/10 text-teal hover:bg-teal/20 flex items-center gap-1"
          >
            <Plus className="w-3 h-3" /> Add Rule
          </button>
        )}
      </div>

      {/* Add rule form */}
      {showAddForm && local && (
        <div className="border border-teal/30 rounded-2xl p-4 space-y-3 bg-teal/5">
          <input
            placeholder="Rule ID (e.g. no-direct-db-access)"
            value={newRule.id}
            onChange={e => setNewRule(prev => ({ ...prev, id: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-papaya-300 text-sm bg-white"
          />
          <select
            value={newRule.severity}
            onChange={e => setNewRule(prev => ({ ...prev, severity: e.target.value }))}
            className="px-3 py-2 rounded-lg border border-papaya-300 text-sm bg-white"
          >
            <option value="error">Error</option>
            <option value="warn">Warning</option>
          </select>
          <textarea
            placeholder="Description"
            value={newRule.description}
            onChange={e => setNewRule(prev => ({ ...prev, description: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-papaya-300 text-sm bg-white"
            rows={2}
          />
          <textarea
            placeholder="Rationale (optional)"
            value={newRule.rationale}
            onChange={e => setNewRule(prev => ({ ...prev, rationale: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-papaya-300 text-sm bg-white"
            rows={2}
          />
          <div className="flex gap-2">
            <button onClick={handleAddRule} className="px-3 py-1 rounded-lg text-xs bg-teal text-white font-bold flex items-center gap-1">
              <Check className="w-3 h-3" /> Save
            </button>
            <button onClick={() => setShowAddForm(false)} className="px-3 py-1 rounded-lg text-xs bg-papaya-50 text-ink/50 font-bold flex items-center gap-1">
              <X className="w-3 h-3" /> Cancel
            </button>
          </div>
        </div>
      )}

      {/* Rule cards */}
      <div className="space-y-3">
        {filtered.map(rule => (
          <div key={rule.id} className="border border-papaya-400/60 rounded-2xl p-4 bg-white/60">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  {local ? (
                    <select
                      value={rule.severity}
                      onChange={e => handleSeverityChange(rule.id, e.target.value)}
                      className={cn(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full border-0',
                        rule.severity === 'error' ? 'bg-brandy/10 text-brandy' : 'bg-tangerine/10 text-tangerine-700'
                      )}
                    >
                      <option value="error">error</option>
                      <option value="warn">warn</option>
                    </select>
                  ) : (
                    <span className={cn(
                      'text-[10px] font-bold px-2 py-0.5 rounded-full',
                      rule.severity === 'error' ? 'bg-brandy/10 text-brandy' : 'bg-tangerine/10 text-tangerine-700'
                    )}>
                      {rule.severity}
                    </span>
                  )}
                  <code className="text-[11px] text-ink/40">{rule.id}</code>
                  {rule.source && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-papaya-50 text-ink/30">{rule.source}</span>
                  )}
                  {rule.confidence != null && rule.confidence < 100 && (
                    <span className="text-[10px] text-ink/30">{rule.confidence}%</span>
                  )}
                </div>
                <p className="text-sm text-ink">{rule.description}</p>
                {rule.rationale && <p className="text-xs text-ink/50 mt-1">{rule.rationale}</p>}
                {rule.applies_to && <code className="text-[10px] text-ink/30 mt-1 block">{rule.applies_to}</code>}
              </div>
              {local && (
                <button
                  onClick={() => handleDelete(rule.id)}
                  className="text-ink/20 hover:text-brandy transition-colors p-1"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Proposed rules */}
      {proposed && proposed.length > 0 && (
        <div>
          <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] mb-3">
            Proposed Rules ({proposed.length})
          </p>
          <div className="space-y-3">
            {proposed.map((rule: Rule) => (
              <div key={rule.id} className="border border-dashed border-teal/30 rounded-2xl p-4 bg-teal/5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full',
                        rule.severity === 'error' ? 'bg-brandy/10 text-brandy' : 'bg-tangerine/10 text-tangerine-700'
                      )}>
                        {rule.severity}
                      </span>
                      <code className="text-[11px] text-ink/40">{rule.id}</code>
                    </div>
                    <p className="text-sm text-ink">{rule.description}</p>
                    {rule.rationale && <p className="text-xs text-ink/50 mt-1">{rule.rationale}</p>}
                  </div>
                  {local && (
                    <button
                      onClick={() => handleAdopt(rule)}
                      className="px-3 py-1 rounded-lg text-xs bg-teal text-white font-bold"
                    >
                      Adopt
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ignored rules */}
      {ignored && ignored.length > 0 && (
        <div>
          <button
            onClick={() => setShowIgnored(!showIgnored)}
            className="flex items-center gap-2 text-[11px] font-black text-ink/30 uppercase tracking-[0.15em]"
          >
            <ChevronDown className={cn('w-3 h-3 transition-transform', showIgnored && 'rotate-180')} />
            Ignored Rules ({ignored.length})
          </button>
          {showIgnored && (
            <div className="space-y-2 mt-2 opacity-50">
              {ignored.map((rule: Rule, i: number) => (
                <div key={i} className="border border-papaya-200 rounded-xl p-3 text-xs text-ink/40">
                  <code>{rule.id}</code> — {rule.description}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd share/viewer && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```
feat(share): add RulesManagementSection with CRUD for local mode
```

---

## Task 7: ShareButton Component

**Files:**
- Create: `share/viewer/src/components/ShareButton.tsx`

- [ ] **Step 1: Create the component**

```typescript
import { useState } from 'react'
import { Share2, Copy, Check, Loader2, ExternalLink } from 'lucide-react'
import { isLocalMode } from '@/lib/data'

export function ShareButton() {
  const [state, setState] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [shareUrl, setShareUrl] = useState('')
  const [copied, setCopied] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  if (!isLocalMode()) return null

  const handleShare = async () => {
    setState('uploading')
    try {
      const res = await fetch('/api/share', { method: 'POST' })
      if (!res.ok) {
        const data = await res.json().catch(() => ({ error: 'Upload failed' }))
        throw new Error(data.error || 'Upload failed')
      }
      const data = await res.json()
      setShareUrl(data.url)
      setState('done')
    } catch (e: any) {
      setErrorMsg(e.message)
      setState('error')
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  if (state === 'done') {
    return (
      <div className="space-y-3">
        <p className="text-xs text-ink/50">Blueprint shared successfully!</p>
        <div className="flex items-center gap-2">
          <input
            readOnly
            value={shareUrl}
            className="flex-1 px-3 py-2 rounded-lg border border-papaya-300 text-xs bg-white truncate"
          />
          <button onClick={handleCopy} className="px-3 py-2 rounded-lg text-xs bg-teal text-white font-bold flex items-center gap-1">
            {copied ? <><Check className="w-3 h-3" /> Copied</> : <><Copy className="w-3 h-3" /> Copy</>}
          </button>
        </div>
        <a
          href={shareUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-teal hover:underline flex items-center gap-1"
        >
          <ExternalLink className="w-3 h-3" /> Open in browser
        </a>
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="space-y-2">
        <p className="text-xs text-brandy">{errorMsg}</p>
        <button onClick={handleShare} className="px-4 py-2 rounded-xl text-xs bg-teal text-white font-bold">
          Try again
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={handleShare}
      disabled={state === 'uploading'}
      className="px-4 py-2 rounded-xl text-sm bg-teal text-white font-bold flex items-center gap-2 hover:bg-teal-600 transition-colors disabled:opacity-50"
    >
      {state === 'uploading' ? (
        <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</>
      ) : (
        <><Share2 className="w-4 h-4" /> Share Blueprint</>
      )}
    </button>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd share/viewer && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```
feat(share): add ShareButton component for local mode upload
```

---

## Task 8: Integrate New Sections into ReportPage

**Files:**
- Modify: `share/viewer/src/pages/ReportPage.tsx`

- [ ] **Step 1: Add imports for new components**

Add at the top of ReportPage.tsx imports:

```typescript
import { ScanReportsSection } from '@/components/ScanReportsSection'
import { DependencyGraphSection } from '@/components/DependencyGraphSection'
import { FilesSection } from '@/components/FilesSection'
import { RulesManagementSection } from '@/components/RulesManagementSection'
import { ShareButton } from '@/components/ShareButton'
import { isLocalMode } from '@/lib/data'
```

- [ ] **Step 2: Add rules state management**

In the state declarations area (around line 26-31), add:

```typescript
const [adoptedRules, setAdoptedRules] = useState<any[]>([])
```

In the useEffect where bundle loads (the loadBundle `.then`), add after `setCreatedAt`:

```typescript
setAdoptedRules(r.bundle.rules_adopted?.rules || r.bundle.rules_adopted || [])
```

- [ ] **Step 3: Add TRACKED_IDS for new sections**

Find the `TRACKED_IDS` array and add the new section IDs. The full array should be:

```typescript
const TRACKED_IDS = [
  'summary', 'health', 'diagram', 'workspace-topology',
  'scan-reports',
  'archrules', 'devrules', 'rules-management',
  'decisions', 'tradeoffs',
  'guidelines', 'communications',
  'components', 'technology', 'deployment',
  'dependencies',
  'files',
  'problems',
  'share',
]
```

- [ ] **Step 4: Add sidebar navigation buttons**

In the sidebar `<nav>` section, add the new entries in their correct positions.

After the "Workspace Topology" NavButton (in the Overview group), add:

```tsx
{/* Scan Reports */}
{bundle.scan_reports && bundle.scan_reports.length > 0 && (
  <div className="space-y-1">
    <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Reports</p>
    <NavButton
      active={activeSection === 'scan-reports'}
      onClick={() => scrollToSection('scan-reports')}
      icon={FileText}
      label="Scan Reports"
    />
  </div>
)}
```

After the Development Rules NavButton (in the Rules group), add:

```tsx
{isLocalMode() && (
  <NavButton
    active={activeSection === 'rules-management'}
    onClick={() => scrollToSection('rules-management')}
    icon={Shield}
    label="Rules Management"
  />
)}
```

After the Inventory group (after Deployment), add:

```tsx
{/* Dependencies */}
{bundle.dependency_graph && bundle.dependency_graph.nodes?.length > 0 && (
  <div className="space-y-1">
    <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Graph</p>
    <NavButton
      active={activeSection === 'dependencies'}
      onClick={() => scrollToSection('dependencies')}
      icon={Database}
      label="Dependencies"
    />
  </div>
)}

{/* Files */}
{(bundle.generated_files || bundle.folder_claude_mds) && (
  <div className="space-y-1">
    <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Files</p>
    <NavButton
      active={activeSection === 'files'}
      onClick={() => scrollToSection('files')}
      icon={FileText}
      label="Browse Files"
    />
  </div>
)}
```

Replace the "Get Started" footer section with:

```tsx
{/* Share / Get Started */}
<div className="space-y-1">
  <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">
    {isLocalMode() ? 'Share' : 'Get Started'}
  </p>
  <NavButton
    active={activeSection === 'share'}
    onClick={() => scrollToSection('share')}
    icon={isLocalMode() ? Share2 : Rocket}
    label={isLocalMode() ? 'Share Blueprint' : 'Try Archie'}
  />
</div>
```

Add `Share2` to the lucide-react import line.

- [ ] **Step 5: Add section content in the main content area**

In the main content area, add the new sections in their correct positions.

After Workspace Topology section (before Architecture Rules):

```tsx
{/* Scan Reports */}
{bundle.scan_reports && bundle.scan_reports.length > 0 && (
  <section id="scan-reports" className="scroll-mt-8">
    <Sections.SectionHeader title="Scan Reports" icon={FileText} />
    <ScanReportsSection reports={bundle.scan_reports} />
  </section>
)}
```

After Development Rules section:

```tsx
{/* Rules Management (local only) */}
{isLocalMode() && (
  <section id="rules-management" className="scroll-mt-8">
    <Sections.SectionHeader title="Rules Management" icon={Shield} />
    <RulesManagementSection
      adopted={adoptedRules}
      proposed={bundle.proposed_rules}
      ignored={bundle.ignored_rules}
      onRulesChange={setAdoptedRules}
    />
  </section>
)}
```

After Deployment section:

```tsx
{/* Dependencies */}
{bundle.dependency_graph && bundle.dependency_graph.nodes?.length > 0 && (
  <section id="dependencies" className="scroll-mt-8">
    <Sections.SectionHeader title="Dependencies" icon={Database} />
    <DependencyGraphSection graph={bundle.dependency_graph} />
  </section>
)}

{/* Files */}
{(bundle.generated_files || bundle.folder_claude_mds) && (
  <section id="files" className="scroll-mt-8">
    <Sections.SectionHeader title="Generated Files" icon={FileText} />
    <FilesSection
      generatedFiles={bundle.generated_files}
      folderClaudeMds={bundle.folder_claude_mds}
    />
  </section>
)}
```

Replace the footer "Try Archie" section with:

```tsx
{/* Share / Get Started */}
<section id="share" className="scroll-mt-8">
  {isLocalMode() ? (
    <div className="text-center py-8">
      <Sections.SectionHeader title="Share Blueprint" icon={Share2} />
      <p className="text-sm text-ink/50 mb-6">Share this architecture blueprint with your team</p>
      <ShareButton />
    </div>
  ) : (
    /* Keep existing Try Archie CTA */
    <div className="text-center py-8">
      {/* ... existing CTA code ... */}
    </div>
  )}
</section>
```

- [ ] **Step 6: Add FileText import**

Make sure `FileText` and `Share2` are in the lucide-react import.

- [ ] **Step 7: Verify TypeScript compiles**

Run: `cd share/viewer && npx tsc --noEmit`

- [ ] **Step 8: Commit**

```
feat(share): integrate all new sections into ReportPage
```

---

## Task 9: Expand upload.py Bundle

**Files:**
- Modify: `archie/standalone/upload.py`

- [ ] **Step 1: Add new data fields to build_bundle()**

In `archie/standalone/upload.py`, find the `build_bundle()` function (around line 122). Add the new fields to the bundle dict before the return statement:

```python
    # --- NEW: viewer-originated fields ---

    # Scan reports (historical)
    scan_history_dir = archie_dir / "scan_history"
    scan_reports = []
    if scan_history_dir.is_dir():
        for f in sorted(scan_history_dir.glob("*.md"), reverse=True):
            scan_reports.append({
                "filename": f.name,
                "date": f.name.replace("scan_report_", "").replace(".md", ""),
                "content": f.read_text(encoding="utf-8", errors="replace"),
            })
    # Legacy scan_report_*.md in archie_dir
    for f in sorted(archie_dir.glob("scan_report_*.md"), reverse=True):
        scan_reports.append({
            "filename": f.name,
            "date": f.name.replace("scan_report_", "").replace(".md", ""),
            "content": f.read_text(encoding="utf-8", errors="replace"),
        })
    if scan_reports:
        bundle["scan_reports"] = scan_reports

    # Dependency graph
    dep_graph_path = archie_dir / "dependency_graph.json"
    if dep_graph_path.exists():
        bundle["dependency_graph"] = json.loads(dep_graph_path.read_text(encoding="utf-8"))

    # Generated files (CLAUDE.md, AGENTS.md, .claude/rules/*)
    generated_files = {}
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = root / name
        if p.exists():
            generated_files[name] = p.read_text(encoding="utf-8", errors="replace")
    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        for f in sorted(rules_dir.rglob("*")):
            if f.is_file():
                generated_files[str(f.relative_to(root))] = f.read_text(encoding="utf-8", errors="replace")
    if generated_files:
        bundle["generated_files"] = generated_files

    # Folder CLAUDE.md files
    skip_dirs = {".git", "node_modules", ".venv", "__pycache__", ".archie", "dist", "build"}
    folder_mds = {}
    for claude_md in root.rglob("CLAUDE.md"):
        if any(part in skip_dirs for part in claude_md.parts):
            continue
        rel = str(claude_md.relative_to(root))
        if rel == "CLAUDE.md":
            continue
        folder_mds[rel] = claude_md.read_text(encoding="utf-8", errors="replace")
    if folder_mds:
        bundle["folder_claude_mds"] = folder_mds

    # Ignored rules
    ignored_path = archie_dir / "ignored_rules.json"
    if ignored_path.exists():
        bundle["ignored_rules"] = json.loads(ignored_path.read_text(encoding="utf-8"))

    # Drift report
    drift_path = archie_dir / "drift_report.json"
    if drift_path.exists():
        bundle["drift_report"] = json.loads(drift_path.read_text(encoding="utf-8"))

    # Health history
    history_path = archie_dir / "health_history.json"
    if history_path.exists():
        bundle["health_history"] = json.loads(history_path.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Test upload.py still runs**

Run: `python3 archie/standalone/upload.py --help` (or whatever the CLI entrypoint is)
Expected: no import errors

- [ ] **Step 3: Commit**

```
feat(upload): expand bundle with scan reports, deps, files, drift, history
```

---

## Task 10: Strip viewer.py HTML & Add Static File Serving

**Files:**
- Modify: `archie/standalone/viewer.py`

- [ ] **Step 1: Remove the HTML_PAGE string**

Find the `HTML_PAGE = """...` string (starts around line 245, ends around line 1900+). Replace the entire multi-line string with:

```python
HTML_PAGE = None  # Removed — viewer now serves pre-built React dist
```

- [ ] **Step 2: Add static file serving and SPA fallback**

Replace the `do_GET` handler's `if path == "/"` block and add static file serving. The full `do_GET` method becomes:

```python
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        root: Path = self.server.root  # type: ignore
        archie_dir = root / ".archie"

        # API endpoints (keep all existing ones exactly as they are)
        if path == "/api/blueprint":
            self._send_json(_load_json(archie_dir / "blueprint.json"))
        elif path == "/api/rules":
            self._send_json(_load_json(archie_dir / "rules.json"))
        elif path == "/api/health":
            # ... keep existing health logic ...
        elif path == "/api/health-history":
            # ... keep existing ...
        elif path == "/api/scan-reports":
            # ... keep existing ...
        elif path.startswith("/api/scan-report/"):
            # ... keep existing ...
        elif path == "/api/drift":
            # ... keep existing ...
        elif path == "/api/generated-files":
            # ... keep existing ...
        elif path == "/api/folder-claude-mds":
            # ... keep existing ...
        elif path == "/api/ignored-rules":
            # ... keep existing ...
        elif path == "/api/proposed-rules":
            # ... keep existing ...
        elif path == "/api/dependency-graph":
            # ... keep existing ...
        else:
            # Static file serving (React dist) with SPA fallback
            self._serve_static(path)
```

- [ ] **Step 3: Add static file serving methods**

Add these methods to the `ArchieHandler` class:

```python
    def _serve_static(self, url_path: str):
        """Serve files from viewer_dist/, falling back to index.html for SPA routing."""
        dist_dir: Path = self.server.dist_dir  # type: ignore

        # Map URL path to file
        if url_path == "/" or url_path == "":
            file_path = dist_dir / "index.html"
        else:
            # Strip leading slash
            relative = url_path.lstrip("/")
            file_path = dist_dir / relative

        # Security: prevent path traversal
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(dist_dir.resolve())):
                self._send_error(403, "Forbidden")
                return
        except (ValueError, OSError):
            self._send_error(400, "Bad path")
            return

        # Serve file if exists, otherwise SPA fallback to index.html
        if not file_path.is_file():
            file_path = dist_dir / "index.html"

        if not file_path.is_file():
            self._send_error(404, "Viewer dist not found. Run: cd share/viewer && npm run build")
            return

        content = file_path.read_bytes()
        content_type = self._guess_type(file_path.name)

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        # Cache static assets (hashed filenames) aggressively
        if "/assets/" in url_path:
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _guess_type(filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return {
            "html": "text/html; charset=utf-8",
            "js": "application/javascript; charset=utf-8",
            "css": "text/css; charset=utf-8",
            "json": "application/json; charset=utf-8",
            "svg": "image/svg+xml",
            "png": "image/png",
            "ico": "image/x-icon",
            "woff": "font/woff",
            "woff2": "font/woff2",
        }.get(ext, "application/octet-stream")
```

- [ ] **Step 4: Update server startup to set dist_dir**

In the `main()` function (or wherever the HTTP server is created), add `dist_dir` to the server:

```python
    server = http.server.HTTPServer(("", port), ArchieHandler)
    server.root = root  # type: ignore
    server.dist_dir = Path(__file__).parent / "viewer_dist"  # type: ignore
```

- [ ] **Step 5: Add /api/share POST endpoint**

In the `do_POST` method, add a new endpoint after the `/api/rules` handler:

```python
        elif path == "/api/share":
            try:
                root: Path = self.server.root  # type: ignore
                # Import upload logic
                upload_script = Path(__file__).parent / "upload.py"
                if not upload_script.exists():
                    self._send_error(500, "upload.py not found")
                    return

                import importlib.util
                spec = importlib.util.spec_from_file_location("upload", str(upload_script))
                upload_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(upload_mod)

                bundle = upload_mod.build_bundle(root)
                result = upload_mod.upload(bundle)
                self._send_json({"ok": True, "url": result})
            except Exception as e:
                self._send_error(500, str(e))
```

- [ ] **Step 6: Verify viewer.py runs without errors**

Run: `python3 archie/standalone/viewer.py --help` (or start it up briefly)
Expected: no import/syntax errors

- [ ] **Step 7: Commit**

```
feat(viewer): strip embedded HTML, serve React dist with SPA fallback
```

---

## Task 11: Build & Pack Script

**Files:**
- Create: `scripts/pack_viewer_dist.py`
- Modify: `npm-package/bin/archie.mjs`

- [ ] **Step 1: Create the pack script**

Create `scripts/pack_viewer_dist.py`:

```python
#!/usr/bin/env python3
"""Build the share viewer React app and copy dist to npm-package/assets/viewer_dist/."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER_DIR = ROOT / "share" / "viewer"
DIST_DIR = VIEWER_DIR / "dist"
TARGET_DIR = ROOT / "npm-package" / "assets" / "viewer_dist"

def main():
    print("Building share viewer...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(VIEWER_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Build failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("Build OK.")

    if not DIST_DIR.is_dir():
        print(f"Error: dist/ not found at {DIST_DIR}", file=sys.stderr)
        sys.exit(1)

    # Clean and copy
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    shutil.copytree(DIST_DIR, TARGET_DIR)
    print(f"Copied dist -> {TARGET_DIR}")

    # Also copy to archie/standalone/viewer_dist for local dev
    local_target = ROOT / "archie" / "standalone" / "viewer_dist"
    if local_target.exists():
        shutil.rmtree(local_target)
    shutil.copytree(DIST_DIR, local_target)
    print(f"Copied dist -> {local_target}")

    print("Done.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update archie.mjs to copy viewer_dist/**

In `npm-package/bin/archie.mjs`, find the section that copies Python scripts to `.archie/` (around line 107-116). After the script copy loop, add:

```javascript
    // Copy viewer dist (React SPA)
    const viewerDistSrc = join(ASSETS, "viewer_dist");
    const viewerDistDest = join(archieDir, "viewer_dist");
    if (existsSync(viewerDistSrc)) {
      // Remove old dist if exists
      if (existsSync(viewerDistDest)) {
        rmSync(viewerDistDest, { recursive: true, force: true });
      }
      cpSync(viewerDistSrc, viewerDistDest, { recursive: true });
      console.log("  Copied viewer_dist/");
    }
```

Add `cpSync` and `rmSync` to the imports from `fs` at the top of the file if not already there.

- [ ] **Step 3: Verify the pack script runs**

Run: `python3 scripts/pack_viewer_dist.py`
Expected: builds successfully and copies to both targets

- [ ] **Step 4: Commit**

```
feat(build): add pack_viewer_dist script and archie.mjs viewer_dist copy
```

---

## Task 12: Sync & Verify

**Files:**
- Modify: `scripts/verify_sync.py`
- Copy: `archie/standalone/viewer.py` -> `npm-package/assets/viewer.py`
- Copy: `archie/standalone/upload.py` -> `npm-package/assets/upload.py`

- [ ] **Step 1: Sync modified files**

```bash
cp archie/standalone/viewer.py npm-package/assets/viewer.py
cp archie/standalone/upload.py npm-package/assets/upload.py
```

- [ ] **Step 2: Update verify_sync.py**

Add viewer_dist directory check to `verify_sync.py`. Add a check that `npm-package/assets/viewer_dist/index.html` exists:

```python
# Check viewer_dist exists in npm-package
viewer_dist = Path("npm-package/assets/viewer_dist/index.html")
if not viewer_dist.exists():
    errors.append(f"Missing: {viewer_dist} — run: python3 scripts/pack_viewer_dist.py")
```

- [ ] **Step 3: Run sync verification**

Run: `python3 scripts/verify_sync.py`
Expected: PASS

- [ ] **Step 4: Commit**

```
chore: sync viewer.py + upload.py to npm-package, update verify_sync
```

---

## Task 13: End-to-End Testing

- [ ] **Step 1: Test local mode**

```bash
# Build the React app
cd share/viewer && npm run build && cd ../..

# Copy dist to standalone
cp -r share/viewer/dist archie/standalone/viewer_dist

# Start viewer pointing at a project with a blueprint
python3 archie/standalone/viewer.py /path/to/project-with-blueprint
```

Open the URL in a browser. Verify:
- React app loads (not the old embedded HTML)
- Dashboard/Overview section shows health metrics
- Scan Reports section shows historical reports
- Rules section shows adopted rules + management controls
- Dependencies section shows vis-network graph (if dependency_graph.json exists)
- Files section shows tree browser with CLAUDE.md files
- Share button is visible and works

- [ ] **Step 2: Test remote mode**

```bash
cd share/viewer && npm run dev
```

Open `http://localhost:5173` — should show HomePage (not ReportPage).
Navigate to a valid `/r/:token/details` URL — should show ReportPage with remote data.

- [ ] **Step 3: Test share upload from local mode**

In the local viewer, click "Share Blueprint". Verify:
- Upload starts
- Returns a share URL
- Copy button works
- Opening the URL shows the same data on the remote viewer

- [ ] **Step 4: Final commit**

```
test: verify viewer-share unification end-to-end
```
