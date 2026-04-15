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
export type FindingGroup = 'RECURRING' | 'NEW' | 'RESOLVED'

export interface Finding {
  severity: FindingSeverity
  title: string
  description: string
  group?: FindingGroup
}

const SEVERITY_RANK: Record<FindingSeverity, number> = { error: 0, warn: 1, info: 2 }
const GROUP_RANK: Record<FindingGroup, number> = { NEW: 0, RECURRING: 1, RESOLVED: 2 }

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

/** Heuristic count of findings that describe semantic duplication /
 * reimplementation. Best-effort keyword match over scan_report.md's
 * Findings section — used as a fallback when the bundle doesn't carry
 * a structured semantic_duplications array (older scans). */
const SEMANTIC_DUPE_RX = /\b(duplicat|reimplement|near[- ]?dup|near[- ]?twin|similar function)\b/i

export function countSemanticDuplications(findings: Finding[]): number {
  return findings.filter(
    (f) => SEMANTIC_DUPE_RX.test(f.title) || SEMANTIC_DUPE_RX.test(f.description),
  ).length
}

export function severityColor(sev: FindingSeverity): string {
  if (sev === 'error') return 'text-brandy border-brandy/30 bg-brandy/5'
  if (sev === 'warn') return 'text-tangerine-800 border-tangerine/30 bg-tangerine/5'
  return 'text-ink/60 border-ink/10 bg-ink/5'
}
