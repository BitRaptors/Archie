const SUPABASE_FUNCTIONS_URL =
  import.meta.env.VITE_SUPABASE_FUNCTIONS_URL ||
  'https://chlmyhkjnirrcrjdsvrc.supabase.co/functions/v1'

export interface SemanticDuplication {
  function?: string
  locations?: string[]
  recommendation?: string
}

export interface SemanticFinding {
  id?: string
  category: string // "systemic" | "localized"
  type: string
  severity: string // "error" | "warn" | "info"
  scope: {
    kind?: string
    components_affected?: string[]
    locations?: string[]
  }
  pattern_description?: string
  evidence?: string
  root_cause?: string
  fix_direction?: string
  blueprint_anchor?: string | null
  blast_radius?: number
  blast_radius_delta?: number
  lifecycle_status?: string // "new" | "recurring" | "resolved" | "worsening"
  synthesis_depth?: string // "draft" | "canonical"
  source?: string
}

export interface Bundle {
  blueprint: any
  health?: any
  scan_meta?: any
  rules_adopted?: any
  rules_proposed?: any
  scan_report?: string
  semantic_duplications?: SemanticDuplication[]
  semantic_findings?: {
    findings: SemanticFinding[]
    schema_version?: number
  }
  bundle_version?: string
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
