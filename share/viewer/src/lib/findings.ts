import type { SemanticFinding, Bundle } from './api'

/** Extract ranked findings from a scan_report.md string.
 *
 * Scan reports follow this shape:
 *
 *   ## Findings
 *   <preamble>
 *   ### RECURRING (previously documented, still present)
 *   1. **[error] Title text.** Description text spanning one or more lines.
 *   2. **[warn] Another title.** More description.
 *   ### NEW (first observed in scan #N)
 *   ### RESOLVED
 */

export type FindingSeverity = 'error' | 'warn' | 'info'
export type FindingGroup = 'RECURRING' | 'NEW' | 'RESOLVED' | 'WORSENING'

export interface Finding {
  severity: FindingSeverity
  title: string
  description: string
  group?: FindingGroup
  /** Rich fields from semantic_findings (v2 bundles) */
  category?: string       // "systemic" | "localized"
  findingType?: string    // e.g. "god_component", "layering_violation"
  evidence?: string
  rootCause?: string
  fixDirection?: string
  blastRadius?: number
  blastRadiusDelta?: number
  blueprintAnchor?: string | null
  synthesisDepth?: string // "draft" | "canonical"
  locations?: string[]
  componentsAffected?: string[]
}

const SEVERITY_RANK: Record<FindingSeverity, number> = { error: 0, warn: 1, info: 2 }
const GROUP_RANK: Record<FindingGroup, number> = { WORSENING: 0, NEW: 1, RECURRING: 2, RESOLVED: 3 }

export function extractFindings(scanReport: string): Finding[] {
  if (!scanReport) return []

  const lines = scanReport.split('\n')
  let inFindings = false
  let currentGroup: FindingGroup | undefined

  // Find the ## Findings heading, capture until next ## heading
  const findingsLines: Array<{ text: string; group?: FindingGroup }> = []
  for (const line of lines) {
    if (!inFindings) {
      if (/^##\s+Findings\b/i.test(line)) inFindings = true
      continue
    }
    if (/^##\s+/.test(line) && !/^###/.test(line)) break

    const groupMatch = line.match(/^###\s+(RECURRING|NEW|RESOLVED)\b/i)
    if (groupMatch) {
      currentGroup = groupMatch[1].toUpperCase() as FindingGroup
      continue
    }
    findingsLines.push({ text: line, group: currentGroup })
  }

  // Now walk collected lines; a finding starts with `N. **[sev] Title.**` and
  // continues on subsequent non-numbered, non-empty lines.
  const findings: Finding[] = []
  let current: Finding | null = null

  for (const { text, group } of findingsLines) {
    const startMatch = text.match(/^\s*\d+\.\s*\*\*\[(\w+)\]\s*([^*]+?)\*\*\s*(.*)$/)
    if (startMatch) {
      if (current) findings.push(current)
      const sev = startMatch[1].toLowerCase() as FindingSeverity
      const title = startMatch[2].trim().replace(/[.:]+$/, '')
      const description = startMatch[3].trim()
      current = {
        severity: ['error', 'warn', 'info'].includes(sev) ? sev : 'warn',
        title,
        description,
        group,
      }
    } else if (current && text.trim() && !/^#/.test(text)) {
      current.description = (current.description + ' ' + text.trim()).trim()
    } else if (!text.trim()) {
      if (current) {
        findings.push(current)
        current = null
      }
    }
  }
  if (current) findings.push(current)

  return findings
}

/** Sort findings by severity error>warn>info first, then NEW>RECURRING>RESOLVED. */
export function rankFindings(findings: Finding[]): Finding[] {
  return [...findings].sort((a, b) => {
    const sa = SEVERITY_RANK[a.severity]
    const sb = SEVERITY_RANK[b.severity]
    if (sa !== sb) return sa - sb
    const ga = a.group ? GROUP_RANK[a.group] : 3
    const gb = b.group ? GROUP_RANK[b.group] : 3
    return ga - gb
  })
}

/** Pick up to `total` findings, reserving up to `minErrors` slots for errors.
 *
 * Behavior:
 * - If ≥ minErrors errors exist: show `minErrors` errors + fill remaining (total - minErrors) with warns/info.
 * - If fewer than minErrors errors exist: show all errors + fill the rest with warns/info.
 * - Non-error slots are filled from warns first, then info. */
export function pickTopFindings(
  findings: Finding[],
  total = 6,
  minErrors = 4,
): Finding[] {
  const ranked = rankFindings(findings)
  const errors = ranked.filter((f) => f.severity === 'error')
  const nonErrors = ranked.filter((f) => f.severity !== 'error')
  const errorSlots = Math.min(errors.length, Math.max(minErrors, 0), total)
  const fillSlots = Math.max(0, total - errorSlots)
  return [...errors.slice(0, errorSlots), ...nonErrors.slice(0, fillSlots)]
}

/** Heuristic keyword match for findings that describe semantic duplication /
 * reimplementation. Used for count (fallback when no structured data) and
 * for tagging matching findings visibly in the UI.
 *
 * Captures:
 *   - duplicat(ed|ion), reimplement(ation), near-dup, near-twin, similar function
 *   - "N separate <X> implementations"   (e.g., "3 separate generateSlug implementations")
 *   - "duplicate <X> of", "copies of <X>"
 */
// Word-start boundary only. Word-END boundary is deliberately omitted so
// "duplicat" matches "duplicated", "duplication", "duplicates"; "reimplement"
// matches "reimplementation", etc.
export const SEMANTIC_DUPE_RX =
  /\b(duplicat|reimplement|near[- ]?dup|near[- ]?twin|similar function|\d+\s+separate\s+\S+\s+implementations?|multiple\s+\S+\s+implementations?|copies\s+of)/i

function _escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function _matchesFunctionName(haystack: string, rawName: string): boolean {
  // Split the entry on separators, keep only identifier-looking tokens with a
  // camelCase transition (lowercase followed by uppercase). This filters out
  // generic words like "violation", "package", "import" that would cause
  // false positives on unrelated findings.
  const tokens = rawName
    .split(/[\s/()]+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 5 && /[a-z][A-Z]/.test(t))

  for (const tok of tokens) {
    // (1) Exact match — `\bgenerateMessageId\b` in the text.
    const exactRx = new RegExp(`\\b${_escapeRegex(tok)}\\b`)
    if (exactRx.test(haystack)) return true

    // (2) Relaxed match — allow whitespace between camelCase parts so that
    // "generate MessageId" in the prose still matches "generateMessageId".
    const parts = tok.split(/(?<=[a-z])(?=[A-Z])/).map(_escapeRegex)
    if (parts.length >= 2) {
      const relaxRx = new RegExp(`\\b${parts.join('\\s*')}\\b`)
      if (relaxRx.test(haystack)) return true
    }
  }
  return false
}

export function isSemanticDupFinding(
  f: Finding,
  opts?: { functionNames?: string[] },
): boolean {
  if (SEMANTIC_DUPE_RX.test(f.title) || SEMANTIC_DUPE_RX.test(f.description)) {
    return true
  }
  // Structured hint: the bundle may carry a list of function names known to be
  // reimplementations (Agent C's duplications output). Match conservatively on
  // camelCase identifiers only, exact or separated by whitespace.
  const names = opts?.functionNames
  if (names && names.length > 0) {
    const haystack = `${f.title}\n${f.description}`
    for (const raw of names) {
      if (_matchesFunctionName(haystack, raw)) return true
    }
  }
  return false
}

export function countSemanticDuplications(findings: Finding[]): number {
  return findings.filter((f) => isSemanticDupFinding(f)).length
}

// ---------------------------------------------------------------------------
// v2 semantic_findings → Finding[] converter
// ---------------------------------------------------------------------------

function mapLifecycleToGroup(status?: string): FindingGroup | undefined {
  if (!status) return undefined
  const s = status.toLowerCase()
  if (s === 'new') return 'NEW'
  if (s === 'recurring') return 'RECURRING'
  if (s === 'resolved') return 'RESOLVED'
  if (s === 'worsening') return 'WORSENING'
  return undefined
}

function buildSemanticTitle(f: SemanticFinding): string {
  if (f.pattern_description) return f.pattern_description
  const typeLabel = f.type.replace(/_/g, ' ')
  const components = f.scope?.components_affected?.join(', ')
  return components ? `${typeLabel} — ${components}` : typeLabel
}

function buildSemanticBody(f: SemanticFinding): string {
  const parts: string[] = []
  if (f.evidence) parts.push(f.evidence)
  if (f.root_cause) parts.push(`Root cause: ${f.root_cause}`)
  if (f.fix_direction) parts.push(`Fix: ${f.fix_direction}`)
  if (f.blast_radius != null) {
    const delta = f.blast_radius_delta != null
      ? ` (${f.blast_radius_delta >= 0 ? '+' : ''}${f.blast_radius_delta})`
      : ''
    parts.push(`Blast radius: ${f.blast_radius}${delta}`)
  }
  if (f.blueprint_anchor) parts.push(`Anchor: ${f.blueprint_anchor}`)
  if (f.scope?.locations?.length) {
    parts.push(`Locations: ${f.scope.locations.join(', ')}`)
  }
  return parts.join(' | ')
}

/** Convert v2 semantic_findings to the Finding[] type used by the renderer. */
export function semanticFindingsToFindings(
  sf: Bundle['semantic_findings'],
): Finding[] {
  if (!sf?.findings?.length) return []
  return sf.findings.map((f) => ({
    severity: (['error', 'warn', 'info'].includes(f.severity) ? f.severity : 'warn') as FindingSeverity,
    group: mapLifecycleToGroup(f.lifecycle_status),
    title: buildSemanticTitle(f),
    description: buildSemanticBody(f),
    category: f.category,
    findingType: f.type,
    evidence: f.evidence,
    rootCause: f.root_cause,
    fixDirection: f.fix_direction,
    blastRadius: f.blast_radius,
    blastRadiusDelta: f.blast_radius_delta,
    blueprintAnchor: f.blueprint_anchor,
    synthesisDepth: f.synthesis_depth,
    locations: f.scope?.locations,
    componentsAffected: f.scope?.components_affected,
  }))
}

export function severityColor(sev: FindingSeverity): string {
  if (sev === 'error') return 'text-brandy border-brandy/30 bg-brandy/5'
  if (sev === 'warn') return 'text-tangerine-800 border-tangerine/30 bg-tangerine/5'
  return 'text-ink/60 border-ink/10 bg-ink/5'
}
