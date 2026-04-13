const SUPABASE_FUNCTIONS_URL =
  import.meta.env.VITE_SUPABASE_FUNCTIONS_URL ||
  'https://chlmyhkjnirrcrjdsvrc.supabase.co/functions/v1'

export interface Bundle {
  blueprint: any
  health?: any
  scan_meta?: any
  rules_adopted?: any
  rules_proposed?: any
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
