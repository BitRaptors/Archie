const SUPABASE_FUNCTIONS_URL =
  import.meta.env.VITE_SUPABASE_FUNCTIONS_URL ||
  'https://chlmyhkjnirrcrjdsvrc.supabase.co/functions/v1'

export interface SemanticDuplication {
  function?: string
  locations?: string[]
  recommendation?: string
}

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

export interface ReportResponse {
  bundle: Bundle
  created_at: string
}

export async function fetchReport(token: string): Promise<ReportResponse> {
  const res = await fetch(`${SUPABASE_FUNCTIONS_URL}/blueprint?token=${token}`)
  if (!res.ok) throw new Error(`Report not found (${res.status})`)
  return res.json()
}
