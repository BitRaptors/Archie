
import { theme } from '@/lib/theme'
import { cn } from '@/lib/utils'
// @ts-ignore
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Badge } from './ui/badge'
// @ts-ignore
import { Progress } from './ui/progress'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronRight, FileText, Database, Activity, Shield, Zap, Server, HelpCircle, AlertTriangle, Rocket, Info, Terminal } from 'lucide-react'
// @ts-ignore
import ReactMarkdown from 'react-markdown'
// @ts-ignore
import remarkGfm from 'remark-gfm'

import type { Finding } from '@/lib/findings'
import { isSemanticDupFinding, severityColor } from '@/lib/findings'
import { AutoCode, codeInlineClassName } from '@/lib/autocode'

export function WorkspaceTopologySection({ topology }: { topology: any }) {
  const members: any[] = Array.isArray(topology?.members) ? topology.members : []
  const edges: any[] = Array.isArray(topology?.edges) ? topology.edges : []
  const cycles: any[] = Array.isArray(topology?.cycles) ? topology.cycles : []
  const magnets: any[] = Array.isArray(topology?.dependency_magnets) ? topology.dependency_magnets : []
  const type: string = topology?.type || 'workspace'

  const apps = members.filter((m) => (m.role || '').toLowerCase() === 'app')
  const libs = members.filter((m) => ['lib', 'library'].includes((m.role || '').toLowerCase()))
  const other = members.filter((m) => !apps.includes(m) && !libs.includes(m))

  return (
    <section className="space-y-4">
      <SectionHeader title={`Workspace Topology (${type}, ${members.length})`} icon={Database} />
      <div className={cn('p-8 rounded-3xl border space-y-6', theme.surface.panel)}>
        {edges.length > 0 && (
          <div className="grid md:grid-cols-[1fr,auto] gap-6 items-start">
            <div className="space-y-4">
              {apps.length > 0 && (
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-2">Apps</div>
                  <div className="flex flex-wrap gap-2">
                    {apps.map((m, i) => (
                      <Badge key={i} className="bg-teal/10 border-teal/20 text-teal">
                        {m.name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {libs.length > 0 && (
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-2">Shared libraries</div>
                  <div className="flex flex-wrap gap-2">
                    {libs.map((m, i) => (
                      <Badge key={i} variant="outline" className="border-papaya-400">
                        {m.name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {other.length > 0 && (
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-2">Other</div>
                  <div className="flex flex-wrap gap-2">
                    {other.map((m, i) => (
                      <Badge key={i} variant="outline">
                        {m.name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="text-xs text-ink/40 min-w-[140px]">
              <div className="flex justify-between">
                <span>Edges</span>
                <strong className="text-ink/70">{edges.length}</strong>
              </div>
              <div className="flex justify-between">
                <span>Cycles</span>
                <strong className={cycles.length > 0 ? 'text-brandy' : 'text-ink/70'}>
                  {cycles.length}
                </strong>
              </div>
              <div className="flex justify-between">
                <span>Magnets</span>
                <strong className="text-ink/70">{magnets.length}</strong>
              </div>
            </div>
          </div>
        )}

        {cycles.length > 0 && (
          <div className="border-l-4 border-brandy bg-brandy/5 p-4 rounded-r-xl">
            <div className="text-[10px] font-black uppercase tracking-[0.2em] text-brandy mb-2">
              Cross-workspace cycles detected
            </div>
            <ul className="text-sm space-y-1">
              {cycles.map((c, i) => (
                <li key={i} className="font-mono text-ink/80">
                  {Array.isArray(c) ? c.join(' → ') : String(c)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {magnets.length > 0 && (
          <div>
            <div className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-2">
              Dependency magnets
            </div>
            <ul className="text-sm space-y-1">
              {magnets.map((m, i) => (
                <li key={i}>
                  <code className="font-mono text-ink/70">{m.name}</code>
                  <span className="text-ink/40 ml-2">in_degree = {m.in_degree ?? '?'}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  )
}


function FindingBadge({ label, variant }: { label: string; variant?: 'lifecycle' | 'category' | 'depth' }) {
  const cls = variant === 'lifecycle'
    ? label === 'WORSENING'
      ? 'bg-brandy/10 text-brandy border-brandy/30'
      : label === 'NEW'
        ? 'bg-teal/10 text-teal border-teal/30'
        : label === 'RESOLVED'
          ? 'bg-ink/5 text-ink/40 border-ink/10'
          : 'border-ink/10 text-ink/40'
    : variant === 'depth' && label === 'draft'
      ? 'bg-tangerine/10 text-tangerine-800 border-tangerine/30'
      : 'border-ink/10 text-ink/40'
  return (
    <Badge variant="outline" className={cn('text-[9px] font-black uppercase tracking-widest', cls)}>
      {variant === 'depth' ? 'provisional' : label}
    </Badge>
  )
}

function StructuredFindingDetails({ f }: { f: Finding }) {
  const hasDetails = f.rootCause || f.fixDirection || f.evidence || f.blastRadius != null || f.locations?.length
  if (!hasDetails) return null
  return (
    <div className="mt-3 space-y-2 text-sm overflow-hidden">
      {f.evidence && (
        <div className="text-ink/50 leading-relaxed break-words [overflow-wrap:anywhere]">
          <span className="font-semibold text-ink/70">Evidence: </span>
          <AutoCode text={f.evidence} />
        </div>
      )}
      {f.rootCause && (
        <div className="text-ink/50 leading-relaxed break-words [overflow-wrap:anywhere]">
          <span className="font-semibold text-ink/70">Root cause: </span>
          <AutoCode text={f.rootCause} />
        </div>
      )}
      {f.fixDirection && (
        <div className="text-ink/50 leading-relaxed break-words [overflow-wrap:anywhere]">
          <span className="font-semibold text-ink/70">Fix direction: </span>
          <AutoCode text={f.fixDirection} />
        </div>
      )}
      {f.blastRadius != null && (
        <div className="text-ink/50 leading-relaxed">
          <span className="font-semibold text-ink/70">Blast radius: </span>
          {f.blastRadius}
          {f.blastRadiusDelta != null && (
            <span className={f.blastRadiusDelta > 0 ? 'text-brandy' : f.blastRadiusDelta < 0 ? 'text-teal' : ''}>
              {' '}({f.blastRadiusDelta >= 0 ? '+' : ''}{f.blastRadiusDelta})
            </span>
          )}
        </div>
      )}
      {f.locations && f.locations.length > 0 && (
        <div className="text-ink/50 leading-relaxed break-words [overflow-wrap:anywhere]">
          <span className="font-semibold text-ink/70">Locations: </span>
          <span className="inline-flex flex-wrap gap-1">
            {f.locations.map((loc, i) => (
              <code key={i} className={cn(codeInlineClassName, "text-[10px] break-all")}>{loc}</code>
            ))}
          </span>
        </div>
      )}
    </div>
  )
}

export function FindingsList({
  findings,
  truncate,
  semanticFunctionNames,
}: {
  findings: Finding[]
  truncate?: boolean
  semanticFunctionNames?: string[]
}) {
  return (
    <div className="grid gap-4 overflow-hidden">
      {findings.map((f, i) => {
        const isStructured = !!(f.category || f.findingType)
        return (
          <div
            key={i}
            className={cn(
              'p-4 md:p-6 rounded-2xl border flex gap-3 md:gap-4 transition-all hover:shadow-lg overflow-hidden',
              theme.surface.panel
            )}
          >
            <div
              className={cn(
                'shrink-0 h-8 px-3 rounded-full inline-flex items-center gap-1.5 border text-[10px] font-black uppercase tracking-widest',
                severityColor(f.severity)
              )}
            >
              {f.severity === 'error' ? <Shield className="w-3 h-3" /> : <Zap className="w-3 h-3" />}
              {f.severity}
            </div>
            <div className="min-w-0 flex-1 overflow-hidden">
              <div className="flex items-baseline gap-2 flex-wrap">
                <h3 className="font-bold text-ink break-words [overflow-wrap:anywhere]"><AutoCode text={f.title} /></h3>
                {isSemanticDupFinding(f, { functionNames: semanticFunctionNames }) && (
                  <Badge className="text-[9px] bg-brandy text-white border-brandy font-black uppercase tracking-widest">
                    Semantic Dup
                  </Badge>
                )}
                {f.group && (
                  <FindingBadge label={f.group} variant="lifecycle" />
                )}
                {isStructured && f.category === 'systemic' && (
                  <Badge variant="outline" className="text-[9px] border-ink/10 text-ink/40 font-black uppercase tracking-widest">
                    systemic
                  </Badge>
                )}
                {f.synthesisDepth === 'draft' && (
                  <FindingBadge label="draft" variant="depth" />
                )}
              </div>
              {/* Compact description for localized / truncate mode */}
              {f.description && (!isStructured || f.category === 'localized' || truncate) && (
                <p
                  className={cn(
                    'text-sm text-ink/60 mt-1 leading-relaxed',
                    truncate && 'line-clamp-3'
                  )}
                >
                  <AutoCode text={f.description} />
                </p>
              )}
              {/* Rich details for systemic structured findings (non-truncate) */}
              {isStructured && f.category === 'systemic' && !truncate && (
                <StructuredFindingDetails f={f} />
              )}
              {/* Compact structured details for localized findings */}
              {isStructured && f.category === 'localized' && !truncate && f.fixDirection && (
                <div className="mt-2 text-sm text-ink/50">
                  <span className="font-semibold text-ink/70">Fix: </span>
                  <AutoCode text={f.fixDirection} />
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function SectionHeader({ title, icon: Icon }: { title: string; icon: any }) {
  return (
    <div className="flex items-center gap-3 mb-6 px-1">
      <div className={cn("p-2 rounded-xl shadow-sm border", theme.surface.sectionHeaderIcon)}>
        <Icon className={cn("w-4 h-4", theme.active.iconColor)} />
      </div>
      <h2 className={cn("text-xl font-bold tracking-tight", theme.brand.title)}>{title}</h2>
    </div>
  )
}

export function Stat({ label, value, icon: Icon }: { label: string; value: any; icon?: any }) {
  return (
    <div className={cn("p-4 rounded-2xl border transition-all hover:shadow-md", theme.surface.panel)}>
      <div className="flex items-center gap-2 mb-1">
        {Icon && <Icon className="w-3.5 h-3.5 text-muted-foreground" />}
        <span className="text-[10px] font-black text-ink/30 uppercase tracking-widest leading-none">{label}</span>
      </div>
      <div className="text-2xl font-bold tracking-tight text-ink">{value ?? '—'}</div>
    </div>
  )
}

export function HintPopover({
  hint,
  direction,
  target,
}: {
  hint: string
  direction?: 'lower' | 'higher'
  target?: string
}) {
  const btnRef = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  const ariaLabel = [
    direction ? `${direction === 'lower' ? 'Lower' : 'Higher'} is better` : '',
    target ? `(target ${target})` : '',
    hint,
  ]
    .filter(Boolean)
    .join(' ')

  // Recompute position whenever the popup is shown — handles scroll/resize by
  // re-showing only (cheap; we could also re-compute on scroll but the popover
  // is usually brief enough that one snapshot suffices).
  useEffect(() => {
    if (!open) return
    const update = () => {
      const rect = btnRef.current?.getBoundingClientRect()
      if (!rect) return
      // Viewport-relative — `position: fixed` below matches this frame.
      setPos({
        top: rect.top,
        left: rect.left + rect.width / 2,
      })
    }
    update()
    const handle = () => setOpen(false)
    // Dismiss the popup on scroll/resize so stale coordinates aren't shown.
    window.addEventListener('scroll', handle, true)
    window.addEventListener('resize', handle)
    return () => {
      window.removeEventListener('scroll', handle, true)
      window.removeEventListener('resize', handle)
    }
  }, [open])

  const popover =
    open && pos
      ? createPortal(
          <span
            role="tooltip"
            className="fixed w-72 rounded-xl bg-ink text-papaya-100 text-[11px] leading-relaxed font-normal shadow-2xl overflow-hidden pointer-events-none z-[100]"
            style={{
              top: pos.top - 8,
              left: pos.left,
              transform: 'translate(-50%, -100%)',
            }}
          >
            {direction && (
              <span
                className={cn(
                  'block px-3 pt-3 pb-2 border-b border-white/10 text-[10px] font-black uppercase tracking-[0.15em] inline-flex items-center gap-1.5',
                  direction === 'lower' ? 'text-teal-300' : 'text-tangerine-200',
                )}
              >
                <span className="text-sm leading-none">{direction === 'lower' ? '↓' : '↑'}</span>
                <span>{direction === 'lower' ? 'Lower is better' : 'Higher is better'}</span>
                {target && (
                  <span className="text-white/50 font-medium tracking-normal normal-case">
                    · target {target}
                  </span>
                )}
              </span>
            )}
            <span className="block px-3 py-3 text-papaya-100/90">{hint}</span>
            <span className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-[5px] border-transparent border-t-ink" />
          </span>,
          document.body,
        )
      : null

  return (
    <span className="relative inline-flex">
      <button
        ref={btnRef}
        type="button"
        tabIndex={0}
        aria-label={ariaLabel}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-ink/10 text-ink/40 hover:bg-ink/20 hover:text-ink/60 focus:bg-teal/20 focus:text-teal focus:outline-none text-[10px] font-black cursor-help transition-colors"
      >
        ?
      </button>
      {popover}
    </span>
  )
}

export function HealthBar({
  label,
  value,
  inverted,
  hint,
  direction,
  target,
}: {
  label: string
  value: number
  inverted?: boolean
  hint?: string
  direction?: 'lower' | 'higher'
  target?: string
}) {
  const good = inverted ? value < 30 : value >= 70
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-end gap-2">
        <span className="text-sm font-semibold text-ink/70 inline-flex items-center gap-1.5">
          {label}
          {hint && <HintPopover hint={hint} direction={direction} target={target} />}
        </span>
        <span className={cn("text-lg font-bold tabular-nums", good ? 'text-teal' : 'text-brandy')}>{value}%</span>
      </div>
      <div className="h-2 rounded-full bg-ink/5 overflow-hidden border border-ink/5">
         <div
           className={cn("h-full transition-all duration-1000", good ? 'bg-teal' : 'bg-brandy')}
           style={{ width: `${value}%` }}
         />
      </div>
    </div>
  )
}

// Color-coded severity shared across histogram, top-20, mass block.
const CC_BUCKETS: Array<{ label: string; color: string; textColor: string }> = [
  { label: '1-2', color: 'bg-teal/60', textColor: 'text-teal-700' },
  { label: '3-5', color: 'bg-teal/40', textColor: 'text-teal-700' },
  { label: '6-10', color: 'bg-tangerine/40', textColor: 'text-tangerine-800' },
  { label: '11-20', color: 'bg-tangerine/70', textColor: 'text-tangerine-800' },
  { label: '21-50', color: 'bg-brandy/50', textColor: 'text-brandy' },
  { label: '51-100', color: 'bg-brandy/80', textColor: 'text-brandy' },
  { label: '101+', color: 'bg-brandy', textColor: 'text-brandy' },
]

export function ccSeverityClasses(cc: number): string {
  if (cc <= 10) return 'text-teal border-teal/30 bg-teal/5'
  if (cc <= 50) return 'text-tangerine-800 border-tangerine/30 bg-tangerine/5'
  if (cc <= 100) return 'text-brandy border-brandy/30 bg-brandy/5'
  return 'text-white border-brandy bg-brandy'
}

export function CCDistribution({ distribution, compact }: { distribution: Record<string, number>; compact?: boolean }) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0)
  if (total === 0) return null
  const maxCount = Math.max(...Object.values(distribution))

  return (
    <div className={cn('space-y-2', !compact && 'space-y-3')} title="Distribution of function count across cyclomatic complexity buckets">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30">
          CC Distribution
        </div>
        <div className="text-[10px] text-ink/40 tabular-nums">
          {total.toLocaleString()} functions
        </div>
      </div>
      <div className={cn('space-y-1', compact ? 'space-y-1' : 'space-y-1.5')}>
        {CC_BUCKETS.map(({ label, color, textColor }) => {
          const count = distribution[label] ?? 0
          const pct = total > 0 ? (count / total) * 100 : 0
          const barWidth = maxCount > 0 ? (count / maxCount) * 100 : 0
          return (
            <div key={label} className="flex items-center gap-3 text-[11px] tabular-nums">
              <div className={cn('w-14 font-mono font-semibold shrink-0', textColor)}>CC {label}</div>
              <div className="flex-1 h-3 bg-ink/5 rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all duration-500', color)}
                  style={{ width: `${Math.max(barWidth, count > 0 ? 2 : 0)}%` }}
                />
              </div>
              <div className="w-16 text-right text-ink/60 shrink-0">{count.toLocaleString()}</div>
              <div className="w-12 text-right text-ink/40 shrink-0">{pct.toFixed(1)}%</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function MassConcentration({
  mass,
  totalFunctions,
  highCcFunctions,
  distribution,
}: {
  mass: { total?: number; heavy?: number; heavy_ratio?: number } | undefined
  totalFunctions?: number
  highCcFunctions?: number
  distribution?: Record<string, number>
}) {
  if (!mass || !mass.total) return null
  const total = mass.total ?? 0
  const heavy = mass.heavy ?? 0
  const rest = Math.max(total - heavy, 0)
  const heavyPct = Math.round((mass.heavy_ratio ?? (total > 0 ? heavy / total : 0)) * 100)
  const restPct = 100 - heavyPct
  const restFunctions = Math.max((totalFunctions ?? 0) - (highCcFunctions ?? 0), 0)

  // Optional "functions over CC 100 alone hold X%" line — purely derived from distribution.
  let extremeLine: string | null = null
  if (distribution && distribution['101+']) {
    const extremeCount = distribution['101+']
    if (extremeCount > 0 && heavy > 0) {
      // Approximation for narrative: extreme count * (average of heavy mass bias).
      // We use "~" to make it clear this is an estimate, not an exact number.
      extremeLine = `${extremeCount} function${extremeCount === 1 ? '' : 's'} over CC 100 contribute a large share of the heavy mass.`
    }
  }

  return (
    <div className="rounded-2xl border border-ink/10 bg-white/60 p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30">
          Complexity mass <span className="lowercase font-semibold normal-case text-ink/30">(cc × √sloc)</span>
        </div>
        <div className="text-[10px] text-ink/40 tabular-nums">
          Total {Math.round(total).toLocaleString()}
        </div>
      </div>

      <div className="h-6 rounded-full overflow-hidden border border-ink/5 flex">
        <div
          className="bg-brandy flex items-center justify-center text-[10px] font-black text-white tabular-nums transition-all duration-700"
          style={{ width: `${heavyPct}%` }}
          title={`Heavy mass (CC > 10): ${Math.round(heavy).toLocaleString()} — ${heavyPct}%`}
        >
          {heavyPct >= 15 && `${heavyPct}%`}
        </div>
        <div
          className="bg-teal/60 flex items-center justify-center text-[10px] font-black text-white tabular-nums transition-all duration-700"
          style={{ width: `${restPct}%` }}
          title={`Rest (CC ≤ 10): ${Math.round(rest).toLocaleString()} — ${restPct}%`}
        >
          {restPct >= 15 && `${restPct}%`}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-[11px] tabular-nums">
        <div>
          <div className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 bg-brandy rounded-full" />
            <span className="font-bold text-ink/70">Heavy</span>
          </div>
          <div className="text-ink/50 mt-0.5">
            {Math.round(heavy).toLocaleString()} from {(highCcFunctions ?? 0).toLocaleString()} functions
            <span className="text-ink/30"> (CC &gt; 10)</span>
          </div>
        </div>
        <div>
          <div className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 bg-teal/60 rounded-full" />
            <span className="font-bold text-ink/70">Rest</span>
          </div>
          <div className="text-ink/50 mt-0.5">
            {Math.round(rest).toLocaleString()} from {restFunctions.toLocaleString()} functions
            <span className="text-ink/30"> (CC ≤ 10)</span>
          </div>
        </div>
      </div>

      {extremeLine && (
        <div className="text-[11px] text-ink/50 pt-2 border-t border-ink/5 italic">
          {extremeLine}
        </div>
      )}
    </div>
  )
}

export function TopHighCCList({
  items,
  totalMass,
}: {
  items: any[]
  totalMass?: number
}) {
  if (!items || items.length === 0) return null
  const sumMass = items.reduce((sum, f) => sum + (f.mass || 0), 0)
  const shareOfTotal = totalMass && totalMass > 0 ? (sumMass / totalMass) * 100 : null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30">
          Top {items.length} by complexity mass
        </div>
        <div className="text-[10px] text-ink/40 tabular-nums">
          ranked by cc × √sloc
        </div>
      </div>
      <ul className="space-y-1.5">
        {items.map((f, i) => (
          <li key={i} className="flex items-start gap-2 text-xs">
            <div className="flex gap-1 shrink-0">
              <Badge variant="outline" className={cn('text-[10px] font-bold tabular-nums', ccSeverityClasses(f.cc || 0))}>
                CC {f.cc}
              </Badge>
              {typeof f.mass === 'number' && (
                <Badge variant="outline" className="text-[10px] font-bold tabular-nums text-ink/60 border-ink/10 bg-white">
                  mass {Math.round(f.mass).toLocaleString()}
                </Badge>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-bold text-ink/80 truncate">{f.name || '?'}</div>
              <code className="text-[10px] text-ink/40 font-mono truncate block">
                {f.path}
                {f.line ? `:${f.line}` : ''}
              </code>
            </div>
          </li>
        ))}
      </ul>
      {shareOfTotal !== null && (
        <div className="pt-3 border-t border-ink/5 text-[11px] text-ink/50 italic">
          These {items.length} functions alone hold <strong className="text-ink/80">{shareOfTotal.toFixed(0)}%</strong> of total complexity mass.
        </div>
      )}
    </div>
  )
}

export function DuplicationCard({
  verbosity,
  totalLoc,
  duplicateLines,
  semanticCount,
  semanticSource,
  detailsHref,
}: {
  verbosity: number            // 0..1 textual ratio
  totalLoc?: number
  duplicateLines?: number
  semanticCount: number | null  // null if we couldn't determine
  semanticSource: 'structured' | 'heuristic' | 'unknown'
  detailsHref?: string          // when present, renders a "View all → Architectural Problems" anchor
}) {
  const textualPct = Math.round((verbosity || 0) * 100)
  const textualGood = textualPct < 5
  const semanticGood = semanticCount !== null && semanticCount === 0

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1.5">
        <span className="text-sm font-semibold text-ink/70">Code Duplication</span>
        <HintPopover
          direction="lower"
          target="0 semantic, <5% textual"
          hint="Two measures side by side. Textual duplication catches literal copy-paste (line-identical blocks). Semantic reimplementations are near-twin functions — same logic, different names or signatures — found by the scan's AI analysis. AI-written codebases typically have low textual duplication but hidden semantic duplication."
        />
      </div>

      {/* Textual */}
      <div className="space-y-1.5">
        <div className="flex items-end justify-between gap-2">
          <div className="text-xs text-ink/50 uppercase tracking-[0.15em] font-black">Textual</div>
          <div className={cn("text-lg font-bold tabular-nums", textualGood ? 'text-teal' : 'text-brandy')}>
            {textualPct}%
          </div>
        </div>
        <div className="h-2 rounded-full bg-ink/5 overflow-hidden border border-ink/5">
          <div
            className={cn("h-full transition-all duration-1000", textualGood ? 'bg-teal' : 'bg-brandy')}
            style={{ width: `${textualPct}%` }}
          />
        </div>
        {(duplicateLines != null && totalLoc != null) && (
          <div className="text-[11px] text-ink/40 tabular-nums">
            {duplicateLines.toLocaleString()} duplicate lines of {totalLoc.toLocaleString()} total LOC
          </div>
        )}
      </div>

      {/* Semantic */}
      <div className="space-y-1.5 pt-2 border-t border-ink/5">
        <div className="flex items-end justify-between gap-2">
          <div className="text-xs text-ink/50 uppercase tracking-[0.15em] font-black inline-flex items-center gap-1.5">
            Semantic
          </div>
          <div className={cn("text-lg font-bold tabular-nums", semanticCount === null ? 'text-ink/30' : (semanticGood ? 'text-teal' : 'text-brandy'))}>
            {semanticCount === null ? '—' : semanticCount.toLocaleString()}
          </div>
        </div>
        <div className="text-[11px] text-ink/50 leading-snug">
          {semanticCount === null ? (
            'Not yet analyzed — run /archie-scan to detect near-twin functions.'
          ) : semanticCount === 0 ? (
            'No near-twin functions detected by AI analysis.'
          ) : (
            <>
              <strong className="text-ink/80">{semanticCount}</strong> reimplementation
              {semanticCount === 1 ? '' : 's'} found — near-twin function
              {semanticCount === 1 ? '' : 's'} with same logic under different names.
            </>
          )}
        </div>
        {semanticSource === 'heuristic' && semanticCount !== null && (
          <div className="text-[10px] text-ink/30 italic">
            Derived from scan report text (older bundle). Re-scan for a precise count.
          </div>
        )}

        {detailsHref && semanticCount !== null && semanticCount > 0 && (
          <a
            href={detailsHref}
            onClick={(e) => {
              const id = detailsHref.replace(/^#/, '')
              const el = document.getElementById(id)
              if (el) {
                e.preventDefault()
                const offset = 100
                const top = el.getBoundingClientRect().top + window.scrollY - offset
                window.scrollTo({ top, behavior: 'smooth' })
                history.replaceState(null, '', detailsHref)
              }
            }}
            className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal hover:text-teal-700 transition-colors pt-1 group/dup-link"
          >
            View each in Architectural Problems
            <ChevronRight className="w-3 h-3 transition-transform group-hover/dup-link:translate-x-0.5" />
          </a>
        )}
      </div>
    </div>
  )
}

export function FieldList({ label, items, mono }: { label: string; items: any[]; mono?: boolean }) {
  return (
    <div className="space-y-2 min-w-0">
      <div className="text-[10px] font-black text-ink/30 uppercase tracking-[0.15em] mb-1">{label}</div>
      <ul className="space-y-1.5">
        {items.map((it: any, i: number) => (
          <li key={i} className={cn(
            "flex items-start gap-2 text-sm",
            mono ? 'font-mono text-[11px] text-ink/80' : 'text-ink/70'
          )}>
            <div className="mt-1.5 w-1 h-1 rounded-full bg-teal shrink-0" />
            <span className="break-words overflow-hidden [word-break:break-word]">{typeof it === 'string' ? it : JSON.stringify(it)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function ComponentsSection({ components }: { components: any[] }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Components" icon={Database} />
      <div className="grid gap-4">
        {components.map((c: any, i: number) => (
          <div key={i} className={cn("rounded-3xl border overflow-hidden transition-all group hover:shadow-xl hover:-translate-y-0.5", theme.surface.panel)}>
            <details className="group/details">
              <summary className="list-none cursor-pointer p-6">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="p-3 rounded-2xl bg-white border border-papaya-400 shadow-sm group-hover:border-teal/30 transition-colors">
                      <Server className="w-5 h-5 text-teal" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-bold text-lg text-ink truncate">{c.name}</h3>
                        {c.platform && (
                          <Badge variant="outline" className="text-[10px] uppercase font-bold tracking-wider">
                            {c.platform}
                          </Badge>
                        )}
                      </div>
                      {c.location && (
                        <code className={cn(codeInlineClassName, "mt-1 block truncate text-[10px]")}>
                          {c.location}
                        </code>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-ink/20 group-open/details:rotate-90 transition-transform shrink-0" />
                </div>
              </summary>
              <div className="px-6 pb-6 pt-2 border-t border-papaya-400/30 bg-white/30 backdrop-blur-sm space-y-6">
                {c.responsibility && (
                   <div className="prose prose-sm max-w-none text-ink/70 leading-relaxed italic">
                     <AutoCode text={c.responsibility} />
                   </div>
                )}
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
                  {Array.isArray(c.key_files) && c.key_files.length > 0 && (
                    <div className="min-w-0 overflow-hidden">
                      <FieldList
                        label="Key files"
                        items={c.key_files.map((kf: any) =>
                          typeof kf === 'string' ? kf : `${kf.file}${kf.description ? ` — ${kf.description}` : ''}`
                        )}
                      />
                    </div>
                  )}
                  {Array.isArray(c.depends_on) && c.depends_on.length > 0 && (
                    <div className="min-w-0 overflow-hidden">
                      <FieldList label="Depends on" items={c.depends_on} mono />
                    </div>
                  )}
                   {Array.isArray(c.exposes_to) && c.exposes_to.length > 0 && (
                    <div className="min-w-0 overflow-hidden">
                      <FieldList label="Exposes to" items={c.exposes_to} mono />
                    </div>
                  )}
                </div>
              </div>
            </details>
          </div>
        ))}
      </div>
    </section>
  )
}

export function TradeOffsSection({ tradeoffs }: { tradeoffs: any[] }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Trade-offs" icon={Activity} />
      <div className="grid gap-4">
        {tradeoffs.map((t: any, i: number) => (
          <div key={i} className={cn("p-6 rounded-3xl border transition-all hover:bg-white/50", theme.surface.panel)}>
            {t.accept && (
              <p className="text-lg font-bold text-ink mb-2">
                <AutoCode text={t.accept} />
              </p>
            )}
            {t.benefit && (
              <div className="flex gap-2 items-start text-sm text-ink/70 mb-3">
                <Zap className="w-4 h-4 text-tangerine shrink-0 mt-0.5" />
                <p><strong className="text-ink">Benefit:</strong> <AutoCode text={t.benefit} /></p>
              </div>
            )}
            {t.caused_by && (
              <p className="text-xs text-ink/40 italic pl-6 border-l-2 border-papaya-400">
                Started by: <AutoCode text={t.caused_by} />
              </p>
            )}
            {Array.isArray(t.violation_signals) && t.violation_signals.length > 0 && (
              <div className="mt-4 pt-4 border-t border-papaya-400/20">
                <span className="text-[10px] font-black text-ink/30 uppercase tracking-widest block mb-2">Violation signals</span>
                <div className="flex flex-wrap gap-2">
                  {t.violation_signals.map((s: string, j: number) => (
                    <code key={j} className={cn(codeInlineClassName, "text-[10px] italic")}>
                      {s}
                    </code>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export function PitfallsSection({ pitfalls }: { pitfalls: any[] }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Pitfalls" icon={AlertTriangle} />
      <div className="grid gap-4 lg:grid-cols-2">
        {pitfalls.map((p: any, i: number) => (
          <div key={i} className={cn("p-6 rounded-3xl border flex flex-col transition-all hover:shadow-lg hover:-translate-y-1", theme.surface.panel)}>
            <div className="flex items-center gap-2 mb-3">
              {p.area && <Badge className="bg-brandy/10 text-brandy-700 border-brandy/20 uppercase text-[9px] font-black tracking-widest">{p.area}</Badge>}
              <div className="w-1 h-1 rounded-full bg-brandy/50" />
              <h3 className="font-bold text-ink truncate">{p.title}</h3>
            </div>
            {p.description && <p className="text-sm text-ink/70 leading-relaxed mb-4 flex-1"><AutoCode text={p.description} /></p>}
            {p.recommendation && (
              <div className="bg-teal/5 border border-teal/10 rounded-2xl p-4">
                <span className="text-[9px] font-extrabold text-teal/40 uppercase tracking-[0.2em] block mb-1">Recommendation</span>
                <p className="text-sm font-semibold text-teal-900 leading-tight"><AutoCode text={p.recommendation} /></p>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export function KeyDecisionsSection({ decisions }: { decisions: any[] }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Key Decisions" icon={Shield} />
      <div className="space-y-4">
        {decisions.map((d: any, i: number) => (
          <div key={i} className={cn("p-8 rounded-3xl border transition-all hover:shadow-xl", theme.surface.panel)}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-2 h-2 rounded-full bg-tangerine" />
              <h3 className="font-bold text-xl text-ink leading-none"><AutoCode text={d.title} /></h3>
            </div>
            {d.chosen && <p className="text-lg text-ink font-medium mb-4"><AutoCode text={d.chosen} /></p>}
            {d.rationale && (
              <div className="bg-white/50 border border-papaya-400 p-4 rounded-2xl mb-6">
                <span className="text-[10px] font-black text-ink/30 uppercase tracking-widest block mb-2">Rationale</span>
                <p className="text-sm text-ink/70 leading-relaxed"><AutoCode text={d.rationale} /></p>
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {d.forced_by && (
                <div>
                  <span className="text-[10px] font-black text-ink/30 uppercase tracking-widest block mb-1">Forced by</span>
                  <p className="text-sm font-semibold text-ink/80"><AutoCode text={d.forced_by} /></p>
                </div>
              )}
              {d.enables && (
                <div>
                  <span className="text-[10px] font-black text-ink/30 uppercase tracking-widest block mb-1">Enables</span>
                  <p className="text-sm font-semibold text-ink/80"><AutoCode text={d.enables} /></p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

export function TechnologySection({ stack, runCommands }: { stack: any[]; runCommands: Record<string, string> }) {
  const grouped: Record<string, any[]> = {}
  stack.forEach((s) => {
    const cat = s.category || 'other'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(s)
  })

  return (
    <section className="space-y-6">
      <SectionHeader title="Technology Stack" icon={Zap} />
      
      <div className="columns-1 md:columns-2 lg:columns-3 gap-6">
        {Object.entries(grouped).map(([cat, items]) => (
          <div 
            key={cat} 
            className={cn(
              "break-inside-avoid p-6 rounded-3xl border flex flex-col transition-all hover:shadow-xl group mb-6", 
              theme.surface.panel
            )}
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1.5 h-6 rounded-full bg-teal/20 group-hover:bg-teal transition-colors" />
              <h4 className="text-[10px] font-black text-ink/40 uppercase tracking-[0.2em]">
                {cat}
              </h4>
              <span className="ml-auto text-[10px] font-mono text-ink/20">{items.length}</span>
            </div>
            
            <div className="flex flex-wrap gap-2 mt-auto min-w-0">
              {items.map((s: any, i: number) => (
                <div 
                  key={i} 
                  className="max-w-full min-w-0 px-3 py-1.5 rounded-xl bg-white/60 border border-papaya-300 shadow-sm flex flex-wrap items-center gap-x-2 gap-y-1 transition-all hover:border-teal/30 hover:bg-white"
                >
                  <span className="min-w-0 max-w-full text-xs font-bold text-ink/80 break-words [overflow-wrap:anywhere]">
                    {s.name}
                  </span>
                  {s.version && (
                    <span className="shrink-0 text-[10px] font-mono text-ink/30 border-l border-papaya-300 pl-2">
                      {s.version}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {Object.keys(runCommands).length > 0 && (
        <div className={cn("rounded-3xl border overflow-hidden", theme.surface.panel)}>
          <div className="p-6 border-b border-papaya-400/20 bg-ink/[0.02] flex items-center gap-3">
            <Terminal className="w-4 h-4 text-ink/40" />
            <h4 className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em]">Run commands</h4>
          </div>
          <div className={cn('p-6 font-mono text-xs space-y-4 overflow-x-auto', theme.console.bg, theme.console.text)}>
            {Object.entries(runCommands).map(([k, v]) => (
              <div key={k} className="flex gap-4 group/cmd">
                <div className="w-24 shrink-0 text-right">
                  <span className="opacity-30 group-hover/cmd:opacity-60 transition-opacity uppercase tracking-tighter text-[10px]">{k}</span>
                </div>
                <div className="relative">
                  <span className="text-papaya-200">{v}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

export function DeploymentSection({ deployment }: { deployment: any }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Deployment" icon={Rocket} />
      <div className={cn("p-8 rounded-3xl border grid gap-8 md:grid-cols-2", theme.surface.panel)}>
         {deployment.strategy && (
           <div className="space-y-2">
             <span className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em]">Strategy</span>
             <p className="text-lg font-bold text-ink">{deployment.strategy}</p>
           </div>
         )}
         {deployment.platform && (
           <div className="space-y-2">
             <span className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em]">Platform</span>
             <div className="flex items-center gap-2">
               <div className="p-2 rounded-xl bg-white border border-papaya-400">
                 <Server className="w-4 h-4 text-tangerine" />
               </div>
               <p className="text-lg font-bold text-ink">{deployment.platform}</p>
             </div>
           </div>
         )}
         {Array.isArray(deployment.infrastructure) && deployment.infrastructure.length > 0 && (
           <div className="md:col-span-2 pt-4 border-t border-papaya-400/20">
             <span className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em] block mb-4">Infrastructure</span>
             <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {deployment.infrastructure.map((inf: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-3 bg-white/50 rounded-2xl border border-papaya-400">
                    <div className="w-1.5 h-1.5 rounded-full bg-teal" />
                    <span className="text-sm font-semibold text-ink/80">{typeof inf === 'string' ? inf : inf.item || JSON.stringify(inf)}</span>
                  </div>
                ))}
             </div>
           </div>
         )}
      </div>
    </section>
  )
}

export function ArchRulesSection({ filePlacement, naming }: { filePlacement: any[]; naming: any[] }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Architecture Rules" icon={HelpCircle} />
      <div className={cn("p-8 rounded-3xl border space-y-8", theme.surface.panel)}>
        {filePlacement.length > 0 && (
          <div>
            <h4 className="text-[10px] font-black text-ink/30 uppercase tracking-widest mb-4">File placement</h4>
            <div className="grid gap-4">
              {filePlacement.map((r: any, i: number) => (
                <div key={i} className="flex gap-4 items-start pb-4 border-b border-papaya-400/20 last:border-0 last:pb-0">
                  <div className="p-2 rounded-lg bg-teal/5 text-teal shrink-0">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      {r.component_type && (
                        <Badge variant="outline" className="text-[10px] font-black uppercase text-teal border-teal/20">
                          {r.component_type}
                        </Badge>
                      )}
                      {r.location && <code className={cn(codeInlineClassName, "text-xs")}>{r.location}</code>}
                    </div>
                    {r.description && <p className="text-sm text-ink/70"><AutoCode text={r.description} /></p>}
                    {r.naming_pattern && (
                      <div className="mt-2 flex items-center gap-2">
                         <span className="text-[9px] font-black uppercase text-ink/30">Pattern</span>
                         <code className={cn(codeInlineClassName, "text-xs")}>{r.naming_pattern}</code>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {naming.length > 0 && (
          <div className="pt-8 border-t border-papaya-400/20">
            <h4 className="text-[10px] font-black text-ink/30 uppercase tracking-widest mb-4">Naming conventions</h4>
            <div className="grid gap-6">
              {naming.map((r: any, i: number) => (
                <div key={i} className="space-y-2">
                   <div className="flex items-center gap-2">
                     <span className="text-sm font-bold text-ink">{r.scope}</span>
                     <code className={cn(codeInlineClassName, "text-[10px]")}>{r.pattern}</code>
                   </div>
                   {r.description && <p className="text-sm text-ink/60"><AutoCode text={r.description} /></p>}
                   {Array.isArray(r.examples) && r.examples.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {r.examples.map((e: string, j: number) => (
                        <code key={j} className={cn(codeInlineClassName, "text-[10px]")}>
                          {e}
                        </code>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

export function ImplementationGuidelinesSection({ items }: { items: any[] }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Implementation Guidelines" icon={Info} />
      <div className="grid gap-6">
        {items.map((g: any, i: number) => {
          const description = g.guideline || g.description || g.content || g.pattern_description
          const code = g.code || g.usage_example
          const hasContent =
            description ||
            code ||
            (Array.isArray(g.steps) && g.steps.length > 0) ||
            (Array.isArray(g.tips) && g.tips.length > 0) ||
            (Array.isArray(g.libraries) && g.libraries.length > 0) ||
            (Array.isArray(g.key_files) && g.key_files.length > 0) ||
            (Array.isArray(g.rationale) && g.rationale.length > 0);
          
          return (
            <div key={i} className={cn("rounded-3xl border overflow-hidden transition-all hover:shadow-xl", theme.surface.panel)}>
              <div className={cn(
                "p-6 flex items-center justify-between bg-white/40",
                hasContent && "border-b border-papaya-400/20"
              )}>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-teal/10 text-teal">
                    <Zap className="w-4 h-4" />
                  </div>
                  <h3 className="font-bold text-lg text-ink leading-tight">{g.capability || g.category || g.title || 'Guideline'}</h3>
                </div>
                {g.category && g.capability && (
                  <Badge variant="outline" className="text-[10px] font-black uppercase tracking-widest text-ink/30 border-papaya-400">
                    {g.category}
                  </Badge>
                )}
              </div>

              {hasContent && (
                <div className="p-8 space-y-6">
                  {description && (
                    <div className="prose prose-sm max-w-none text-ink/70 leading-relaxed italic border-l-2 border-teal/20 pl-6">
                      <AutoCode text={typeof description === 'string' ? description : JSON.stringify(description)} />
                    </div>
                  )}

                  {Array.isArray(g.tips) && g.tips.length > 0 && (
                    <div className="grid gap-2">
                      <span className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em] mb-1">Tips</span>
                      {g.tips.map((tip: any, j: number) => (
                        <div key={j} className="flex items-start gap-3 text-sm text-ink/80">
                          <div className="w-1.5 h-1.5 rounded-full bg-teal mt-2 shrink-0" />
                          <span><AutoCode text={typeof tip === 'string' ? tip : JSON.stringify(tip)} /></span>
                        </div>
                      ))}
                    </div>
                  )}

                  {Array.isArray(g.libraries) && g.libraries.length > 0 && (
                    <div>
                      <span className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em] block mb-2">Libraries</span>
                      <div className="flex flex-wrap gap-2">
                        {g.libraries.map((lib: any, j: number) => (
                          <Badge key={j} variant="outline" className="text-xs border-papaya-400">
                            {typeof lib === 'string' ? lib : lib.name || JSON.stringify(lib)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {Array.isArray(g.key_files) && g.key_files.length > 0 && (
                    <div>
                      <span className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em] block mb-2">Key Files</span>
                      <ul className="space-y-1 text-xs font-mono text-ink/60">
                        {g.key_files.map((f: any, j: number) => (
                          <li key={j} className="truncate">{typeof f === 'string' ? f : f.file || f.path || JSON.stringify(f)}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {Array.isArray(g.steps) && g.steps.length > 0 && (
                    <div className="grid gap-3">
                      <span className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em] mb-1">Execution Steps</span>
                      {g.steps.map((step: any, j: number) => (
                        <div key={j} className="flex items-start gap-4 p-4 rounded-2xl bg-white/50 border border-papaya-400 group/step transition-colors hover:border-teal/30">
                          <div className="w-6 h-6 rounded-full bg-teal/10 text-teal flex items-center justify-center text-[10px] font-black shrink-0 mt-0.5">
                            {j + 1}
                          </div>
                          <div className="text-sm text-ink/80 font-medium">
                            <AutoCode text={typeof step === 'string' ? step : step.title || step.content || JSON.stringify(step)} />
                            {step.description && (
                              <p className="mt-1 text-xs text-ink/40 font-normal leading-relaxed"><AutoCode text={step.description} /></p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {code && (
                    <div className="space-y-2">
                      <span className="text-[10px] font-black text-ink/30 uppercase tracking-[0.2em]">Example Implementation</span>
                      <div className={cn("p-6 rounded-2xl font-mono text-xs overflow-x-auto border border-white/20 shadow-inner", theme.console.bg, theme.console.text)}>
                        <pre><code>{code}</code></pre>
                      </div>
                    </div>
                  )}
                  
                  {Array.isArray(g.rationale) && g.rationale.length > 0 && (
                    <div className="pt-4 border-t border-papaya-400/20">
                       <div className="flex gap-2 text-xs text-ink/50">
                         <Info className="w-3.5 h-3.5 shrink-0" />
                         <p><AutoCode text={typeof g.rationale[0] === 'string' ? g.rationale.join(' ') : JSON.stringify(g.rationale)} /></p>
                       </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  )
}

export function DevelopmentRulesSection({ rules }: { rules: any[] }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Development Rules" icon={Shield} />
      <div className="space-y-3">
        {rules.map((r: any, i: number) => (
          <div key={i} className={cn("p-5 rounded-2xl border flex items-start gap-4 transition-all hover:border-brandy/30 hover:bg-white/50", theme.surface.panel)}>
             <div className="p-2 rounded-xl bg-brandy/10 text-brandy shrink-0">
               <Shield className="w-4 h-4" />
             </div>
             <div className="text-sm text-ink/80 leading-relaxed font-medium">
               <AutoCode text={typeof r === 'string' ? r : r.rule || JSON.stringify(r)} />
             </div>
          </div>
        ))}
      </div>
    </section>
  )
}
export function CommunicationsSection({ communications }: { communications: any[] }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="Communications" icon={Activity} />
      <div className="grid gap-4 md:grid-cols-2">
        {communications.map((c: any, i: number) => (
          <div key={i} className={cn("p-6 rounded-3xl border flex flex-col transition-all hover:shadow-lg", theme.surface.panel)}>
            <div className="flex items-center gap-2 mb-4">
               <div className="p-2 rounded-xl bg-ink/5">
                 <Zap className="w-4 h-4 text-tangerine" />
               </div>
               <h3 className="font-bold text-ink">{c.type || 'Communication'}</h3>
               {c.protocol && (
                 <Badge variant="outline" className="ml-auto text-[9px] font-black uppercase tracking-widest text-teal border-teal/20 bg-teal/5">
                   {c.protocol}
                 </Badge>
               )}
            </div>
            
            <div className="space-y-4">
              {c.description && <p className="text-sm text-ink/70 leading-relaxed"><AutoCode text={c.description} /></p>}
              
              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-papaya-400/20">
                {c.sender && (
                  <div>
                    <span className="text-[9px] font-black uppercase text-ink/30 block mb-1">Sender</span>
                    <span className="text-xs font-bold text-ink/80">{c.sender}</span>
                  </div>
                )}
                {c.receiver && (
                  <div>
                    <span className="text-[9px] font-black uppercase text-ink/30 block mb-1">Receiver</span>
                    <span className="text-xs font-bold text-ink/80">{c.receiver}</span>
                  </div>
                )}
              </div>

               {Array.isArray(c.signals) && c.signals.length > 0 && (
                <div className="pt-2">
                  <span className="text-[9px] font-black uppercase text-ink/30 block mb-2">Signals</span>
                  <div className="flex flex-wrap gap-2">
                    {c.signals.map((s: string, j: number) => (
                      <code key={j} className={cn(codeInlineClassName, "text-[10px]")}>
                        {s}
                      </code>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
