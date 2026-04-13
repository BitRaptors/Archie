import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, Check, ExternalLink } from 'lucide-react'
import { fetchReport, type Bundle } from '@/lib/api'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { MermaidDiagram } from '@/components/MermaidDiagram'

const INSTALL_CMD = 'npx @bitraptors/archie /path/to/your/project'

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
  const components = bp.components?.components || bp.components || []
  const keyDecisions = bp.decisions?.key_decisions || []
  const rules = bp.architecture_rules || {}
  const tech = bp.technology || {}
  const pitfalls = bp.pitfalls || []
  const diagram = bp.architecture_diagram

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
          {meta.architecture_style && (
            <Badge variant="secondary" className={theme.active.badge}>
              {meta.architecture_style}
            </Badge>
          )}
          {meta.executive_summary && (
            <div className="prose prose-sm max-w-none mt-4">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {meta.executive_summary}
              </ReactMarkdown>
            </div>
          )}
        </header>

        {bundle.scan_meta && (
          <Card>
            <CardHeader>
              <CardTitle>Scan overview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <Stat label="Files" value={bundle.scan_meta.total_files} />
                <Stat label="Dependencies" value={bundle.scan_meta.dependency_count} />
                <Stat
                  label="Frontend ratio"
                  value={`${Math.round((bundle.scan_meta.frontend_ratio || 0) * 100)}%`}
                />
                <Stat label="Subprojects" value={bundle.scan_meta.subprojects?.length ?? 0} />
              </div>
              {bundle.scan_meta.frameworks?.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {bundle.scan_meta.frameworks.map((f: any, i: number) => (
                    <Badge key={i} variant="outline">
                      {f.name}
                      {f.version ? ` ${f.version}` : ''}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {bundle.health && <HealthSection health={bundle.health} />}

        {diagram && (
          <Card>
            <CardHeader>
              <CardTitle>Architecture</CardTitle>
            </CardHeader>
            <CardContent>
              <MermaidDiagram chart={typeof diagram === 'string' ? diagram : diagram.mermaid || ''} />
            </CardContent>
          </Card>
        )}

        {Array.isArray(components) && components.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Components</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {components.map((c: any, i: number) => (
                <div key={i} className="border-l-2 border-teal pl-4">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{c.name}</h3>
                    {c.layer && (
                      <Badge variant="outline" className="text-xs">
                        {c.layer}
                      </Badge>
                    )}
                  </div>
                  {c.responsibility && (
                    <p className="text-sm text-muted-foreground mt-1">{c.responsibility}</p>
                  )}
                  {c.path && (
                    <code className="text-xs text-muted-foreground">{c.path}</code>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {keyDecisions.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Key decisions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {keyDecisions.map((d: any, i: number) => (
                <div key={i}>
                  <h3 className="font-semibold">{d.title || d.name}</h3>
                  {d.rationale && (
                    <div className="prose prose-sm max-w-none mt-1">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{d.rationale}</ReactMarkdown>
                    </div>
                  )}
                  {d.trade_offs && (
                    <p className="text-sm text-muted-foreground mt-1">
                      <strong>Trade-offs:</strong>{' '}
                      {Array.isArray(d.trade_offs) ? d.trade_offs.join('; ') : d.trade_offs}
                    </p>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {(bundle.rules_adopted || bundle.rules_proposed) && (
          <RulesSection adopted={bundle.rules_adopted} proposed={bundle.rules_proposed} />
        )}

        {(rules.file_placement_rules?.length > 0 || rules.naming_conventions?.length > 0) && (
          <Card>
            <CardHeader>
              <CardTitle>Architecture rules</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {rules.file_placement_rules?.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2">File placement</h4>
                  <ul className="text-sm space-y-1 list-disc pl-5">
                    {rules.file_placement_rules.map((r: any, i: number) => (
                      <li key={i}>
                        <code className="text-xs">{r.pattern}</code> → {r.location || r.description}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {rules.naming_conventions?.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2">Naming</h4>
                  <ul className="text-sm space-y-1 list-disc pl-5">
                    {rules.naming_conventions.map((r: any, i: number) => (
                      <li key={i}>
                        {r.applies_to || r.scope}: <code className="text-xs">{r.pattern}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {(tech.stack || tech.run_commands) && (
          <Card>
            <CardHeader>
              <CardTitle>Technology</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {tech.stack && (
                <div className="flex flex-wrap gap-2">
                  {(Array.isArray(tech.stack) ? tech.stack : Object.entries(tech.stack)).map(
                    (s: any, i: number) => (
                      <Badge key={i} variant="outline">
                        {Array.isArray(s) ? `${s[0]}: ${s[1]}` : s.name || s}
                      </Badge>
                    )
                  )}
                </div>
              )}
              {tech.run_commands && (
                <pre className={cn('rounded p-3 text-xs overflow-x-auto', theme.console.bg, theme.console.text)}>
                  {Array.isArray(tech.run_commands)
                    ? tech.run_commands.join('\n')
                    : Object.entries(tech.run_commands)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join('\n')}
                </pre>
              )}
            </CardContent>
          </Card>
        )}

        {pitfalls.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Pitfalls</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm list-disc pl-5">
                {pitfalls.map((p: any, i: number) => (
                  <li key={i}>
                    <strong>{p.title || p.name}:</strong> {p.description || p.summary}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

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
            <button
              onClick={copyInstall}
              className="hover:opacity-80 transition-opacity"
              title="Copy"
            >
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

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground uppercase tracking-wide">{label}</div>
      <div className="text-xl font-semibold mt-1">{value ?? '—'}</div>
    </div>
  )
}

function HealthSection({ health }: { health: any }) {
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

function RulesSection({ adopted, proposed }: { adopted?: any; proposed?: any }) {
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
              {adoptedRules.map((r: any, i: number) => (
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
              <Badge variant="secondary" className="bg-tangerine-50 text-tangerine-800 border-tangerine-200">
                {proposedRules.length}
              </Badge>
            </div>
            <ul className="text-sm space-y-2">
              {proposedRules.map((r: any, i: number) => (
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
