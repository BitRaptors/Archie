import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, Check, ExternalLink, ChevronRight } from 'lucide-react'
import { fetchReport, type Bundle } from '@/lib/api'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { MermaidDiagram } from '@/components/MermaidDiagram'

const INSTALL_CMD = 'npx @bitraptors/archie /path/to/your/project'

type Any = any

export default function ReportPage() {
  const { token } = useParams<{ token: string }>()
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const [createdAt, setCreatedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!token) return
    fetchReport(token)
      .then((r) => {
        setBundle(r.bundle)
        setCreatedAt(r.created_at)
      })
      .catch((e) => setError(e.message))
  }, [token])

  const copyInstall = async () => {
    await navigator.clipboard.writeText(INSTALL_CMD)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle>Report not found</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground mb-4">
              This shared blueprint may have been removed, or the URL is incorrect.
            </p>
            <Link to="/" className="text-teal hover:underline">
              ← Back home
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!bundle) {
    return (
      <div className="min-h-screen p-8 space-y-4 max-w-5xl mx-auto">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const bp = bundle.blueprint || {}
  const meta = bp.meta || {}
  const componentsList: Any[] = bp.components?.components || []
  const decisions = bp.decisions || {}
  const keyDecisions: Any[] = decisions.key_decisions || []
  const tradeOffs: Any[] = decisions.trade_offs || []
  const outOfScope: Any[] = decisions.out_of_scope || []
  const archStyleObj = decisions.architectural_style
  const archRules = bp.architecture_rules || {}
  const filePlacement: Any[] = archRules.file_placement_rules || []
  const naming: Any[] = archRules.naming_conventions || []
  const tech = bp.technology || {}
  const techStack: Any[] = Array.isArray(tech.stack) ? tech.stack : []
  const runCommands: Record<string, string> = tech.run_commands && typeof tech.run_commands === 'object' ? tech.run_commands : {}
  const communication = bp.communication || {}
  const pitfalls: Any[] = Array.isArray(bp.pitfalls) ? bp.pitfalls : []
  const implGuidelines: Any[] = Array.isArray(bp.implementation_guidelines) ? bp.implementation_guidelines : []
  const devRules: Any[] = Array.isArray(bp.development_rules) ? bp.development_rules : []
  const deployment = bp.deployment || {}
  const diagram: string = typeof bp.architecture_diagram === 'string' ? bp.architecture_diagram : bp.architecture_diagram?.mermaid || ''

  return (
    <div className="min-h-screen">
      <div className="max-w-5xl mx-auto p-6 md:p-10 space-y-8">
        <header className="space-y-3">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Link to="/" className={cn('hover:underline', theme.brand.title)}>
              Archie
            </Link>
            <span>/</span>
            <span>shared blueprint</span>
            {createdAt && (
              <span className="ml-auto text-xs">
                {new Date(createdAt).toLocaleDateString()}
              </span>
            )}
          </div>
          <h1 className="text-3xl md:text-4xl font-bold">
            {meta.repository || 'Architecture Blueprint'}
          </h1>
          {Array.isArray(meta.platforms) && meta.platforms.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {meta.platforms.map((p: string) => (
                <Badge key={p} className={theme.active.badge}>
                  {p}
                </Badge>
              ))}
            </div>
          )}
          {meta.executive_summary && (
            <div className="prose prose-sm max-w-none mt-4">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{meta.executive_summary}</ReactMarkdown>
            </div>
          )}
          {meta.architecture_style && (
            <details className="mt-2 group">
              <summary className="cursor-pointer text-sm font-medium text-teal hover:underline inline-flex items-center gap-1">
                <ChevronRight className="w-4 h-4 group-open:rotate-90 transition-transform" />
                Architecture style
              </summary>
              <div className="prose prose-sm max-w-none mt-2 text-muted-foreground">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{meta.architecture_style}</ReactMarkdown>
              </div>
            </details>
          )}
        </header>

        {bundle.scan_meta && <ScanOverview scanMeta={bundle.scan_meta} />}

        {bundle.scan_report && <ScanReportSection markdown={bundle.scan_report} />}

        {bundle.health && <HealthSection health={bundle.health} />}

        {diagram && (
          <Card>
            <CardHeader>
              <CardTitle>Architecture diagram</CardTitle>
            </CardHeader>
            <CardContent>
              <MermaidDiagram chart={diagram} />
              <details className="mt-4 text-xs">
                <summary className="cursor-pointer text-muted-foreground">View source</summary>
                <pre className={cn('mt-2 p-3 rounded overflow-x-auto', theme.console.bg, theme.console.text)}>
                  {diagram}
                </pre>
              </details>
            </CardContent>
          </Card>
        )}

        {archStyleObj && <ArchitecturalStyle style={archStyleObj} />}

        {componentsList.length > 0 && <ComponentsSection components={componentsList} />}

        {keyDecisions.length > 0 && <KeyDecisionsSection decisions={keyDecisions} />}

        {tradeOffs.length > 0 && <TradeOffsSection tradeoffs={tradeOffs} />}

        {outOfScope.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Out of scope</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="text-sm space-y-1 list-disc pl-5 text-muted-foreground">
                {outOfScope.map((item: Any, i: number) => (
                  <li key={i}>{typeof item === 'string' ? item : item.item || JSON.stringify(item)}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {pitfalls.length > 0 && <PitfallsSection pitfalls={pitfalls} />}

        {(bundle.rules_adopted || bundle.rules_proposed) && (
          <RulesSection adopted={bundle.rules_adopted} proposed={bundle.rules_proposed} />
        )}

        {(filePlacement.length > 0 || naming.length > 0) && (
          <ArchRulesSection filePlacement={filePlacement} naming={naming} />
        )}

        {(techStack.length > 0 || Object.keys(runCommands).length > 0) && (
          <TechnologySection stack={techStack} runCommands={runCommands} />
        )}

        {(communication.patterns || communication.integrations) && (
          <CommunicationSection communication={communication} />
        )}

        {implGuidelines.length > 0 && <ImplementationGuidelinesSection items={implGuidelines} />}

        {devRules.length > 0 && <DevelopmentRulesSection rules={devRules} />}

        {Object.keys(deployment).length > 0 && <DeploymentSection deployment={deployment} />}

        <footer className={cn('border-t mt-12 pt-8 pb-12 text-center', theme.surface.dividerStrong)}>
          <h3 className={cn('text-lg font-semibold mb-2', theme.brand.title)}>
            Get this for your codebase
          </h3>
          <p className="text-muted-foreground mb-4">
            Senior-architect-level analysis of your own codebase. Takes 3 minutes.
          </p>
          <div
            className={cn(
              'rounded-lg p-4 font-mono text-sm inline-flex items-center gap-3',
              theme.console.bg,
              theme.console.text
            )}
          >
            <code>{INSTALL_CMD}</code>
            <button onClick={copyInstall} className="hover:opacity-80 transition-opacity" title="Copy">
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <div className="mt-4">
            <a
              href="https://github.com/BitRaptors/Archie"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-teal"
            >
              Learn more <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: Any }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground uppercase tracking-wide">{label}</div>
      <div className="text-xl font-semibold mt-1">{value ?? '—'}</div>
    </div>
  )
}

function ScanOverview({ scanMeta }: { scanMeta: Any }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Scan overview</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <Stat label="Files" value={scanMeta.total_files?.toLocaleString?.() ?? scanMeta.total_files} />
          <Stat
            label="Frontend ratio"
            value={`${Math.round((scanMeta.frontend_ratio || 0) * 100)}%`}
          />
          <Stat label="Subprojects" value={scanMeta.subprojects?.length ?? 0} />
        </div>
        {Array.isArray(scanMeta.frameworks) && scanMeta.frameworks.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Frameworks</div>
            <div className="flex flex-wrap gap-2">
              {scanMeta.frameworks.map((f: Any, i: number) => (
                <Badge key={i} variant="outline">
                  {f.name}
                  {f.version ? ` ${f.version}` : ''}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {Array.isArray(scanMeta.subprojects) && scanMeta.subprojects.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Subprojects</div>
            <div className="flex flex-wrap gap-2">
              {scanMeta.subprojects.map((s: Any, i: number) => (
                <Badge key={i} variant="outline">
                  {s.name}
                  {s.type ? ` · ${s.type}` : ''}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function HealthSection({ health }: { health: Any }) {
  const erosionPct = Math.round((health.erosion || 0) * 100)
  const giniPct = Math.round((health.gini || 0) * 100)
  const top20Pct = Math.round((health.top20_share || 0) * 100)
  const verbosityPct = Math.round((health.verbosity || 0) * 100)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Health</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <HealthBar label="Erosion" value={erosionPct} inverted />
        <HealthBar label="Concentration (Gini)" value={giniPct} inverted />
        <HealthBar label="Top-20% share" value={top20Pct} inverted />
        <HealthBar label="Verbosity" value={verbosityPct} inverted />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm pt-2 border-t">
          <Stat label="LOC" value={health.total_loc?.toLocaleString() ?? '—'} />
          <Stat label="Functions" value={health.total_functions ?? '—'} />
          <Stat label="High-CC" value={health.high_cc_functions ?? '—'} />
          <Stat label="Duplicate lines" value={health.duplicate_lines ?? '—'} />
        </div>
        {Array.isArray(health.top_high_cc) && health.top_high_cc.length > 0 && (
          <div className="pt-2">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
              Top high-complexity functions
            </div>
            <div className="text-sm space-y-1">
              {health.top_high_cc.map((f: Any, i: number) => (
                <div key={i} className="flex items-start gap-2 font-mono text-xs">
                  <Badge
                    variant="outline"
                    className={cn(
                      'shrink-0 text-xs',
                      f.cc >= 20 ? 'border-brandy text-brandy' : 'border-tangerine text-tangerine-800'
                    )}
                  >
                    CC {f.cc}
                  </Badge>
                  <span className="truncate">
                    <span className="font-semibold">{f.name}</span>{' '}
                    <span className="text-muted-foreground">
                      {f.path}
                      {f.line ? `:${f.line}` : ''}
                    </span>
                    {f.sloc ? <span className="text-muted-foreground"> · {f.sloc} sloc</span> : null}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        {Array.isArray(health.top_duplicates) && health.top_duplicates.length > 0 && (
          <div className="pt-2">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
              Largest duplicate blocks
            </div>
            <ul className="text-sm space-y-1">
              {health.top_duplicates.map((d: Any, i: number) => (
                <li key={i} className="text-xs">
                  <Badge variant="outline" className="mr-2">{d.lines} lines</Badge>
                  <span className="font-mono text-muted-foreground">
                    {(d.locations || []).join(', ')}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ScanReportSection({ markdown }: { markdown: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Scan report</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="prose prose-sm max-w-none prose-headings:scroll-mt-20 prose-table:text-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
        </div>
      </CardContent>
    </Card>
  )
}

function HealthBar({ label, value, inverted }: { label: string; value: number; inverted?: boolean }) {
  const good = inverted ? value < 30 : value >= 70
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span>{label}</span>
        <span className={good ? 'text-teal font-medium' : 'text-brandy font-medium'}>{value}%</span>
      </div>
      <Progress value={value} />
    </div>
  )
}

function ArchitecturalStyle({ style }: { style: Any }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{style.title || 'Architectural style'}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {style.chosen && (
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">Chosen</div>
            <p>{style.chosen}</p>
          </div>
        )}
        {style.rationale && (
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">Rationale</div>
            <p className="text-muted-foreground">{style.rationale}</p>
          </div>
        )}
        {Array.isArray(style.alternatives_rejected) && style.alternatives_rejected.length > 0 && (
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
              Alternatives rejected
            </div>
            <ul className="list-disc pl-5 text-muted-foreground space-y-1">
              {style.alternatives_rejected.map((a: string, i: number) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ComponentsSection({ components }: { components: Any[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Components ({components.length})</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {components.map((c: Any, i: number) => (
          <details key={i} className="border-l-2 border-teal pl-4 pb-2 group">
            <summary className="cursor-pointer">
              <div className="inline-flex items-center gap-2 flex-wrap">
                <ChevronRight className="w-4 h-4 inline group-open:rotate-90 transition-transform" />
                <span className="font-semibold">{c.name}</span>
                {c.platform && (
                  <Badge variant="outline" className="text-xs">
                    {c.platform}
                  </Badge>
                )}
                {c.location && (
                  <code className="text-xs text-muted-foreground">{c.location}</code>
                )}
              </div>
            </summary>
            <div className="mt-2 space-y-2 text-sm ml-6">
              {c.responsibility && <p className="text-muted-foreground">{c.responsibility}</p>}
              {Array.isArray(c.key_files) && c.key_files.length > 0 && (
                <FieldList
                  label="Key files"
                  items={c.key_files.map((kf: Any) =>
                    typeof kf === 'string' ? kf : `${kf.file}${kf.description ? ` — ${kf.description}` : ''}`
                  )}
                />
              )}
              {Array.isArray(c.depends_on) && c.depends_on.length > 0 && (
                <FieldList label="Depends on" items={c.depends_on} mono />
              )}
              {Array.isArray(c.exposes_to) && c.exposes_to.length > 0 && (
                <FieldList label="Exposes to" items={c.exposes_to} mono />
              )}
              {Array.isArray(c.key_interfaces) && c.key_interfaces.length > 0 && (
                <FieldList label="Key interfaces" items={c.key_interfaces} mono />
              )}
            </div>
          </details>
        ))}
      </CardContent>
    </Card>
  )
}

function FieldList({ label, items, mono }: { label: string; items: Any[]; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">{label}</div>
      <ul className="list-disc pl-5 space-y-0.5">
        {items.map((it: Any, i: number) => (
          <li key={i} className={mono ? 'font-mono text-xs' : ''}>
            {typeof it === 'string' ? it : JSON.stringify(it)}
          </li>
        ))}
      </ul>
    </div>
  )
}

function KeyDecisionsSection({ decisions }: { decisions: Any[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Key decisions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {decisions.map((d: Any, i: number) => (
          <div key={i} className="pb-4 border-b last:border-b-0 last:pb-0">
            <h3 className="font-semibold">{d.title}</h3>
            {d.chosen && <p className="text-sm mt-1">{d.chosen}</p>}
            {d.rationale && (
              <p className="text-sm text-muted-foreground mt-2">
                <strong className="text-foreground">Why:</strong> {d.rationale}
              </p>
            )}
            <div className="grid md:grid-cols-2 gap-3 mt-3 text-sm">
              {d.forced_by && (
                <div>
                  <span className="text-xs uppercase tracking-wide text-muted-foreground">Forced by:</span>
                  <p>{d.forced_by}</p>
                </div>
              )}
              {d.enables && (
                <div>
                  <span className="text-xs uppercase tracking-wide text-muted-foreground">Enables:</span>
                  <p>{d.enables}</p>
                </div>
              )}
            </div>
            {Array.isArray(d.alternatives_rejected) && d.alternatives_rejected.length > 0 && (
              <div className="mt-3">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">Rejected alternatives:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {d.alternatives_rejected.map((a: string, j: number) => (
                    <Badge key={j} variant="outline" className="text-xs">
                      {a}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function TradeOffsSection({ tradeoffs }: { tradeoffs: Any[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trade-offs</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {tradeoffs.map((t: Any, i: number) => (
          <div key={i} className="pb-4 border-b last:border-b-0 last:pb-0 text-sm">
            {t.accept && (
              <p>
                <strong>Accept:</strong> {t.accept}
              </p>
            )}
            {t.benefit && (
              <p className="mt-1 text-muted-foreground">
                <strong className="text-foreground">Benefit:</strong> {t.benefit}
              </p>
            )}
            {t.caused_by && (
              <p className="mt-1 text-muted-foreground">
                <strong className="text-foreground">Caused by:</strong> {t.caused_by}
              </p>
            )}
            {Array.isArray(t.violation_signals) && t.violation_signals.length > 0 && (
              <div className="mt-2">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">Violation signals:</span>
                <ul className="list-disc pl-5 mt-1 space-y-0.5 text-xs font-mono">
                  {t.violation_signals.map((s: string, j: number) => (
                    <li key={j}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function PitfallsSection({ pitfalls }: { pitfalls: Any[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Pitfalls</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {pitfalls.map((p: Any, i: number) => (
          <div key={i} className="pb-4 border-b last:border-b-0 last:pb-0 text-sm">
            <div className="flex items-center gap-2 flex-wrap">
              {p.area && <Badge variant="outline">{p.area}</Badge>}
              {p.title && <h3 className="font-semibold">{p.title}</h3>}
            </div>
            {p.description && <p className="mt-2">{p.description}</p>}
            {p.recommendation && (
              <p className="mt-2 text-muted-foreground">
                <strong className="text-foreground">Recommendation:</strong> {p.recommendation}
              </p>
            )}
            {Array.isArray(p.stems_from) && p.stems_from.length > 0 && (
              <div className="mt-2">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">Stems from:</span>
                <ul className="list-disc pl-5 mt-1 space-y-0.5">
                  {p.stems_from.map((s: string, j: number) => (
                    <li key={j}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
            {Array.isArray(p.applies_to) && p.applies_to.length > 0 && (
              <div className="mt-2">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">Applies to:</span>
                <ul className="list-disc pl-5 mt-1 space-y-0.5 text-xs font-mono">
                  {p.applies_to.map((a: string, j: number) => (
                    <li key={j}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function ArchRulesSection({ filePlacement, naming }: { filePlacement: Any[]; naming: Any[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Architecture rules</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {filePlacement.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">File placement</h4>
            <ul className="text-sm space-y-2">
              {filePlacement.map((r: Any, i: number) => (
                <li key={i} className="border-l-2 border-papaya pl-3">
                  {r.component_type && (
                    <Badge variant="outline" className="text-xs mr-2">
                      {r.component_type}
                    </Badge>
                  )}
                  {r.location && <code className="text-xs">{r.location}</code>}
                  {r.description && <p className="text-muted-foreground mt-1">{r.description}</p>}
                  {r.naming_pattern && (
                    <p className="text-xs font-mono mt-1">pattern: {r.naming_pattern}</p>
                  )}
                  {r.example && <p className="text-xs text-muted-foreground font-mono mt-1">e.g. {r.example}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}
        {naming.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Naming conventions</h4>
            <ul className="text-sm space-y-2">
              {naming.map((r: Any, i: number) => (
                <li key={i} className="border-l-2 border-papaya pl-3">
                  {r.scope && <strong>{r.scope}: </strong>}
                  <code className="text-xs">{r.pattern}</code>
                  {r.description && <p className="text-muted-foreground mt-1">{r.description}</p>}
                  {Array.isArray(r.examples) && r.examples.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {r.examples.map((e: string, j: number) => (
                        <code key={j} className="text-xs bg-muted px-1 rounded">
                          {e}
                        </code>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function TechnologySection({ stack, runCommands }: { stack: Any[]; runCommands: Record<string, string> }) {
  const grouped: Record<string, Any[]> = {}
  stack.forEach((s) => {
    const cat = s.category || 'other'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(s)
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Technology</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {Object.entries(grouped).map(([cat, items]) => (
          <div key={cat}>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">{cat}</div>
            <div className="flex flex-wrap gap-2">
              {items.map((s: Any, i: number) => (
                <Badge key={i} variant="outline" title={s.purpose || ''}>
                  {s.name}
                  {s.version ? ` ${s.version}` : ''}
                </Badge>
              ))}
            </div>
          </div>
        ))}
        {Object.keys(runCommands).length > 0 && (
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">Run commands</div>
            <div className={cn('rounded p-3 font-mono text-xs space-y-1 overflow-x-auto', theme.console.bg, theme.console.text)}>
              {Object.entries(runCommands).map(([k, v]) => (
                <div key={k}>
                  <span className="opacity-60">{k}:</span> {v}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function CommunicationSection({ communication }: { communication: Any }) {
  const patterns: Any[] = Array.isArray(communication.patterns) ? communication.patterns : []
  const integrations: Any[] = Array.isArray(communication.integrations) ? communication.integrations : []
  return (
    <Card>
      <CardHeader>
        <CardTitle>Communication</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {patterns.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Patterns</h4>
            <ul className="space-y-2">
              {patterns.map((p: Any, i: number) => (
                <li key={i} className="border-l-2 border-teal pl-3">
                  {p.name && <strong>{p.name}</strong>}
                  {p.description && <p className="text-muted-foreground mt-1">{p.description}</p>}
                  {p.when_to_use && (
                    <p className="text-muted-foreground mt-1">
                      <em>When:</em> {p.when_to_use}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {integrations.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Integrations</h4>
            <ul className="space-y-2">
              {integrations.map((it: Any, i: number) => (
                <li key={i} className="border-l-2 border-tangerine pl-3">
                  {it.name && <strong>{it.name}</strong>}
                  {it.purpose && <p className="text-muted-foreground mt-1">{it.purpose}</p>}
                  {it.type && <Badge variant="outline" className="text-xs mt-1">{it.type}</Badge>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ImplementationGuidelinesSection({ items }: { items: Any[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Implementation guidelines ({items.length})</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((g: Any, i: number) => (
          <details key={i} className="border-l-2 border-papaya pl-3 pb-2 group">
            <summary className="cursor-pointer">
              <div className="inline-flex items-center gap-2 flex-wrap">
                <ChevronRight className="w-4 h-4 inline group-open:rotate-90 transition-transform" />
                <span className="font-semibold text-sm">{g.capability || g.category}</span>
                {g.category && g.capability && (
                  <Badge variant="outline" className="text-xs">{g.category}</Badge>
                )}
              </div>
            </summary>
            <div className="mt-2 space-y-2 text-sm ml-6">
              {g.pattern_description && <p className="text-muted-foreground">{g.pattern_description}</p>}
              {g.usage_example && (
                <pre className={cn('rounded p-2 text-xs overflow-x-auto', theme.console.bg, theme.console.text)}>
                  {g.usage_example}
                </pre>
              )}
              {Array.isArray(g.tips) && g.tips.length > 0 && (
                <FieldList label="Tips" items={g.tips} />
              )}
              {Array.isArray(g.libraries) && g.libraries.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {g.libraries.map((l: string, j: number) => (
                    <Badge key={j} variant="outline" className="text-xs">{l}</Badge>
                  ))}
                </div>
              )}
              {Array.isArray(g.key_files) && g.key_files.length > 0 && (
                <FieldList label="Key files" items={g.key_files} mono />
              )}
            </div>
          </details>
        ))}
      </CardContent>
    </Card>
  )
}

function DevelopmentRulesSection({ rules }: { rules: Any[] }) {
  const byCategory: Record<string, Any[]> = {}
  rules.forEach((r) => {
    const cat = r.category || 'other'
    if (!byCategory[cat]) byCategory[cat] = []
    byCategory[cat].push(r)
  })
  return (
    <Card>
      <CardHeader>
        <CardTitle>Development rules ({rules.length})</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {Object.entries(byCategory).map(([cat, items]) => (
          <div key={cat}>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">{cat}</div>
            <ul className="space-y-2">
              {items.map((r: Any, i: number) => (
                <li key={i} className="border-l-2 border-teal pl-3">
                  <p>{r.rule}</p>
                  {r.source && (
                    <code className="text-xs text-muted-foreground">{r.source}</code>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function DeploymentSection({ deployment }: { deployment: Any }) {
  const entries = Object.entries(deployment).filter(([, v]) => {
    if (v == null) return false
    if (Array.isArray(v) && v.length === 0) return false
    if (typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 0) return false
    return true
  })
  if (entries.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Deployment</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {entries.map(([k, v]) => (
          <div key={k}>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
              {k.replace(/_/g, ' ')}
            </div>
            <DeploymentValue value={v} />
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function DeploymentValue({ value }: { value: Any }) {
  if (typeof value === 'string') return <p className="text-muted-foreground">{value}</p>
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc pl-5 text-muted-foreground space-y-1">
        {value.map((v, i) => (
          <li key={i}>
            {typeof v === 'string' ? v : v.name || JSON.stringify(v)}
            {typeof v === 'object' && v.description && (
              <span className="text-xs"> — {v.description}</span>
            )}
          </li>
        ))}
      </ul>
    )
  }
  if (typeof value === 'object') {
    return (
      <ul className="list-disc pl-5 text-muted-foreground space-y-1">
        {Object.entries(value).map(([k, v]) => (
          <li key={k}>
            <strong>{k}:</strong>{' '}
            {typeof v === 'string' ? v : Array.isArray(v) ? v.join(', ') : JSON.stringify(v)}
          </li>
        ))}
      </ul>
    )
  }
  return <p>{String(value)}</p>
}

function RulesSection({ adopted, proposed }: { adopted?: Any; proposed?: Any }) {
  const adoptedRules = adopted?.rules || []
  const proposedRules = proposed?.rules || []
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rules</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {adoptedRules.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <h4 className="font-medium">Adopted</h4>
              <Badge className={theme.active.badge}>{adoptedRules.length}</Badge>
            </div>
            <ul className="text-sm space-y-2">
              {adoptedRules.map((r: Any, i: number) => (
                <li key={i} className="flex gap-2">
                  <Badge variant="outline" className="text-xs shrink-0">
                    {r.id}
                  </Badge>
                  <span>{r.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {proposedRules.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <h4 className="font-medium">Proposed</h4>
              <Badge
                variant="secondary"
                className="bg-tangerine-50 text-tangerine-800 border-tangerine-200"
              >
                {proposedRules.length}
              </Badge>
            </div>
            <ul className="text-sm space-y-2">
              {proposedRules.map((r: Any, i: number) => (
                <li key={i} className="flex gap-2">
                  <Badge variant="outline" className="text-xs shrink-0">
                    {r.id}
                  </Badge>
                  <span>
                    {r.description}
                    {r.confidence != null && (
                      <span className="text-muted-foreground ml-2">
                        ({Math.round(r.confidence * 100)}% confidence)
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
