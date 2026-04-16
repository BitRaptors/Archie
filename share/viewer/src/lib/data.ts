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
