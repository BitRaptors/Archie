
import { useEffect, useState, useRef, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Copy, Check, ExternalLink, ChevronRight, Layout, Github, Menu, X, Info, Activity, Database, Shield, Zap, Rocket, AlertTriangle, HelpCircle } from 'lucide-react'
import { fetchReport, type Bundle } from '@/lib/api'
import { autoBacktick } from '@/lib/autocode'
import { formatBlueprintTitle } from '@/lib/blueprintTitle'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { MermaidDiagram } from '@/components/MermaidDiagram'
import { filterReportSections } from '@/lib/toc'
import * as Sections from '@/components/ReportSections'
import { extractFindings, rankFindings } from '@/lib/findings'

const INSTALL_CMD = 'npx @bitraptors/archie /path/to/your/project'

export default function ReportPage() {
  const { token } = useParams<{ token: string }>()
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const [createdAt, setCreatedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [activeSection, setActiveSection] = useState('')
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  const contentRef = useRef<HTMLDivElement>(null)
  const scrollingToRef = useRef(false)

  useEffect(() => {
    if (!token) return
    fetchReport(token)
      .then((r) => {
        setBundle(r.bundle)
        setCreatedAt(r.created_at)
      })
      .catch((e) => setError(e.message))
  }, [token])

  const bp = bundle?.blueprint || {}
  const meta = bp.meta || {}
  const diagram: string = typeof bp.architecture_diagram === 'string' ? bp.architecture_diagram : bp.architecture_diagram?.mermaid || ''
  
  const filteredReport = useMemo(() => {
    if (!bundle?.scan_report) return ''
    return filterReportSections(bundle.scan_report, ['Findings', 'Next task', 'Next steps', 'Rules', 'Architecture Rules', 'Guidelines'])
  }, [bundle?.scan_report])

  const findings = useMemo(() => {
    if (!bundle?.scan_report) return []
    return rankFindings(extractFindings(bundle.scan_report))
  }, [bundle?.scan_report])

  // Scroll sync logic — re-attach after bundle loads so contentRef.current exists
  useEffect(() => {
    if (!bundle) return
    const container = contentRef.current
    if (!container) return

    // Collect top-level tracked IDs: sections directly in content, and the
    // nested `#pitfalls` div inside the Problems section plus `#try-archie`
    // footer. Rebuilt once per load to avoid querySelector churn on scroll.
    const TRACKED_IDS = [
      'summary',
      'health',
      'diagram',
      'workspace-topology',
      'archrules',
      'devrules',
      'decisions',
      'tradeoffs',
      'guidelines',
      'communications',
      'components',
      'technology',
      'deployment',
      'problems',
      'pitfalls',
      'try-archie',
    ]

    const handleScroll = () => {
      if (scrollingToRef.current) return
      const offset = 150
      let current = ''
      for (const id of TRACKED_IDS) {
        const el = document.getElementById(id)
        if (!el) continue
        if (el.getBoundingClientRect().top <= offset) current = id
      }
      if (current && current !== activeSection) setActiveSection(current)
    }

    handleScroll()
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [bundle])

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id)
    if (!element) return
    
    scrollingToRef.current = true
    setActiveSection(id)
    setIsSidebarOpen(false)

    const offset = 100
    const bodyRect = document.body.getBoundingClientRect().top
    const elementRect = element.getBoundingClientRect().top
    const elementPosition = elementRect - bodyRect
    const offsetPosition = elementPosition - offset

    window.scrollTo({
      top: offsetPosition,
      behavior: 'smooth'
    })

    setTimeout(() => {
      scrollingToRef.current = false
    }, 800)
  }

  const copyInstall = async () => {
    await navigator.clipboard.writeText(INSTALL_CMD)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8 bg-gradient-to-br from-papaya-50 to-teal-50/20">
        <Card className="max-w-md border-brandy/20 shadow-2xl shadow-brandy/5 rounded-3xl overflow-hidden">
          <CardHeader className="bg-brandy/5 border-b border-brandy/10 p-8">
            <div className="w-12 h-12 rounded-2xl bg-brandy/10 flex items-center justify-center mb-4">
               <AlertTriangle className="text-brandy w-6 h-6" />
            </div>
            <CardTitle className="text-ink decoration-brandy underline-offset-4 decoration-2">Report Expired or Invalid</CardTitle>
          </CardHeader>
          <CardContent className="p-8">
            <p className="text-ink/60 mb-8 leading-relaxed">
              We couldn't find the blueprint you're looking for. It may have been deleted or the link might be broken.
            </p>
            <Link to="/" className="inline-flex items-center gap-2 font-bold text-teal hover:text-teal-700 transition-colors group">
              <ChevronRight className="w-4 h-4 rotate-180 group-hover:-translate-x-1 transition-transform" />
              Return to Archie
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!bundle) {
    return (
      <div className="min-h-screen bg-white">
        <div className="fixed inset-y-0 left-0 w-64 border-r border-papaya-300 hidden lg:block p-8 space-y-6">
           <Skeleton className="h-8 w-32 rounded-lg" />
           <div className="space-y-4 pt-8">
             <Skeleton className="h-4 w-full" />
             <Skeleton className="h-4 w-4/5" />
             <Skeleton className="h-4 w-full" />
             <Skeleton className="h-4 w-3/4" />
           </div>
        </div>
        <div className="lg:ml-64 p-8 md:p-12 lg:p-20 space-y-12 max-w-5xl">
          <header className="space-y-4">
             <Skeleton className="h-4 w-24" />
             <Skeleton className="h-12 w-3/4" />
             <Skeleton className="h-6 w-1/2" />
          </header>
          <Skeleton className="h-[400px] w-full rounded-3xl" />
          <div className="grid grid-cols-3 gap-6">
             <Skeleton className="h-32 rounded-2xl" />
             <Skeleton className="h-32 rounded-2xl" />
             <Skeleton className="h-32 rounded-2xl" />
          </div>
        </div>
      </div>
    )
  }

  const componentsList = bp.components?.components || []
  const keyDecisions = bp.decisions?.key_decisions || []
  const tradeOffs = bp.decisions?.trade_offs || []
  const pitfalls = Array.isArray(bp.pitfalls) ? bp.pitfalls : []
  const archRules = bp.architecture_rules || {}
  const filePlacement = archRules.file_placement_rules || []
  const naming = archRules.naming_conventions || []
  const technology = bp.technology || {}
  const stack = Array.isArray(technology.stack) ? technology.stack : []
  const runCommands = technology.run_commands || {}
  const deployment = bp.deployment || {}
  const implementationGuidelines = [
    ...(bp.implementation_guidelines || []),
    ...(bp.decisions?.implementation_guidelines || []),
    ...(bp.guidelines || []),
    ...(archRules.guidelines || [])
  ]
  const developmentRules = [
    ...(archRules.development_rules || []),
    ...(bp.development_rules || [])
  ]
  // Blueprint exposes `communication` (singular) as an object with
  // `patterns[]` and `integrations[]`. Flatten into the array shape the
  // CommunicationsSection expects ({ type, protocol, description, ... }).
  const commObj = bp.communication || {}
  const communications = [
    ...(bp.communications || []),
    ...(archRules.communications || []),
    ...((commObj.patterns || []).map((p: any) => ({
      type: p.name || 'Pattern',
      protocol: 'pattern',
      description: [p.description, p.when_to_use && `When: ${p.when_to_use}`]
        .filter(Boolean)
        .join(' '),
    }))),
    ...((commObj.integrations || []).map((i: any) => ({
      type: i.name || 'Integration',
      protocol: i.type || 'integration',
      description: i.purpose,
    }))),
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-papaya-50 via-white to-teal-50/10 text-ink scroll-smooth">
      {/* Mobile Header */}
      <header className="lg:hidden sticky top-0 z-40 bg-white/80 backdrop-blur-xl border-b border-papaya-300 px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-teal flex items-center justify-center">
            <Activity className="text-white w-5 h-5" />
          </div>
          <span className="font-black tracking-tight text-xl">Archie</span>
        </Link>
        <button onClick={() => setIsSidebarOpen(true)} className="p-2 -mr-2">
          <Menu className="w-6 h-6" />
        </button>
      </header>

      {/* Sidebar Navigation */}
      <aside 
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 bg-white/50 backdrop-blur-2xl border-r border-papaya-300 transition-transform duration-300 lg:translate-x-0 overflow-hidden flex flex-col",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="p-8 flex items-center justify-between shrink-0">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal shadow-lg shadow-teal/20 flex items-center justify-center">
               <Activity className="text-white w-6 h-6" />
            </div>
            <div>
              <span className="font-black tracking-tight text-2xl block leading-none">Archie</span>
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-teal/40 mt-1 block">Blueprint Viewer</span>
            </div>
          </Link>
          <button onClick={() => setIsSidebarOpen(false)} className="lg:hidden p-2 -mr-2 text-ink/40 hover:text-ink">
            <X className="w-6 h-6" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          {/* Overview */}
          <div className="space-y-1">
            <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Overview</p>
            <NavButton
              active={activeSection === 'summary'}
              onClick={() => scrollToSection('summary')}
              icon={Info}
              label="Executive Summary"
            />
            {bundle.health && (
              <NavButton
                active={activeSection === 'health'}
                onClick={() => scrollToSection('health')}
                icon={Activity}
                label="System Health"
              />
            )}
            {diagram && (
              <NavButton
                active={activeSection === 'diagram'}
                onClick={() => scrollToSection('diagram')}
                icon={Layout}
                label="Architecture Diagram"
              />
            )}
            {bp.workspace_topology && (
              <NavButton
                active={activeSection === 'workspace-topology'}
                onClick={() => scrollToSection('workspace-topology')}
                icon={Database}
                label="Workspace Topology"
              />
            )}
          </div>

          {/* Rules */}
          {((filePlacement.length > 0 || naming.length > 0) || developmentRules.length > 0) && (
            <div className="space-y-1">
              <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Rules</p>
              {(filePlacement.length > 0 || naming.length > 0) && (
                <NavButton
                  active={activeSection === 'archrules'}
                  onClick={() => scrollToSection('archrules')}
                  icon={HelpCircle}
                  label="Architecture Rules"
                />
              )}
              {developmentRules.length > 0 && (
                <NavButton
                  active={activeSection === 'devrules'}
                  onClick={() => scrollToSection('devrules')}
                  icon={Shield}
                  label="Development Rules"
                />
              )}
            </div>
          )}

          {/* Design */}
          {(keyDecisions.length > 0 || tradeOffs.length > 0) && (
            <div className="space-y-1">
              <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Design</p>
              {keyDecisions.length > 0 && (
                <NavButton
                  active={activeSection === 'decisions'}
                  onClick={() => scrollToSection('decisions')}
                  icon={Shield}
                  label="Key Decisions"
                />
              )}
              {tradeOffs.length > 0 && (
                <NavButton
                  active={activeSection === 'tradeoffs'}
                  onClick={() => scrollToSection('tradeoffs')}
                  icon={Activity}
                  label="Trade-offs"
                />
              )}
            </div>
          )}

          {/* Practice */}
          {(implementationGuidelines.length > 0 || communications.length > 0) && (
            <div className="space-y-1">
              <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Practice</p>
              {implementationGuidelines.length > 0 && (
                <NavButton
                  active={activeSection === 'guidelines'}
                  onClick={() => scrollToSection('guidelines')}
                  icon={Info}
                  label="Implementation Guidelines"
                />
              )}
              {communications.length > 0 && (
                <NavButton
                  active={activeSection === 'communications'}
                  onClick={() => scrollToSection('communications')}
                  icon={Activity}
                  label="Communications"
                />
              )}
            </div>
          )}

          {/* Inventory */}
          {(componentsList.length > 0 || stack.length > 0) && (
            <div className="space-y-1">
              <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Inventory</p>
              {componentsList.length > 0 && (
                <NavButton
                  active={activeSection === 'components'}
                  onClick={() => scrollToSection('components')}
                  icon={Database}
                  label={`Components (${componentsList.length})`}
                />
              )}
              {stack.length > 0 && (
                <NavButton
                  active={activeSection === 'technology'}
                  onClick={() => scrollToSection('technology')}
                  icon={Zap}
                  label="Technology Stack"
                />
              )}
              {(deployment.strategy || deployment.platform || (Array.isArray(deployment.infrastructure) && deployment.infrastructure.length > 0)) && (
                <NavButton
                  active={activeSection === 'deployment'}
                  onClick={() => scrollToSection('deployment')}
                  icon={Rocket}
                  label="Deployment"
                />
              )}
            </div>
          )}

          {/* Risks — merged Findings + Pitfalls */}
          {(filteredReport || pitfalls.length > 0) && (
            <div className="space-y-1">
              <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Risks</p>
              <NavButton
                active={activeSection === 'problems'}
                onClick={() => scrollToSection('problems')}
                icon={AlertTriangle}
                label="Architectural Problems"
              />
              {pitfalls.length > 0 && (
                <NavButton
                  active={activeSection === 'pitfalls'}
                  onClick={() => scrollToSection('pitfalls')}
                  icon={Shield}
                  label="Pitfalls"
                />
              )}
            </div>
          )}

          {/* Get started */}
          <div className="space-y-1">
            <p className="px-3 text-[10px] font-black uppercase tracking-[0.2em] text-ink/20 mb-4">Get Started</p>
            <NavButton
              active={activeSection === 'try-archie'}
              onClick={() => scrollToSection('try-archie')}
              icon={Rocket}
              label="Try Archie"
            />
          </div>
        </nav>

        <div className="p-8 bg-papaya-300/10 border-t border-papaya-300/40">
           <a 
             href="https://github.com/BitRaptors/Archie" 
             target="_blank" 
             className="flex items-center justify-between text-ink/40 hover:text-ink transition-colors group"
           >
             <span className="text-xs font-bold uppercase tracking-widest">Open Source</span>
             <Github className="w-4 h-4 group-hover:rotate-12 transition-transform" />
           </a>
        </div>
      </aside>

      {/* Main Content */}
      <main className="lg:ml-72 flex flex-col min-h-screen">
        <div className="flex-1 p-6 md:p-12 lg:p-20 xl:p-24 space-y-32 max-w-6xl w-full mx-auto" ref={contentRef}>
          
          {/* Hero Section */}
          <section id="summary" className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700">
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-ink/30 font-black uppercase tracking-[0.3em] text-[10px]">
                <span className="w-8 h-px bg-current" />
                <span>Blueprint Analysis</span>
                {createdAt && (
                  <span className="ml-auto opacity-60 font-mono tracking-tighter normal-case text-[11px]">
                    {new Date(createdAt).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
                  </span>
                )}
              </div>
              <h1 className="text-5xl md:text-6xl lg:text-7xl font-black tracking-tight leading-[0.95] text-ink">
                {formatBlueprintTitle(meta.repository)}
              </h1>
              <div className="flex flex-wrap gap-2 pt-2">
                {Array.isArray(meta.platforms) && meta.platforms.map((p: string) => (
                  <Badge key={p} className="bg-white/80 backdrop-blur-sm border-papaya-400 text-ink/60 px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest shadow-sm">
                    {p}
                  </Badge>
                ))}
              </div>
            </div>

            {meta.executive_summary && (
              <div className="relative group">
                <div className="absolute -inset-4 bg-teal/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                <div className="relative prose prose-lg max-w-none text-ink/70 leading-relaxed prose-strong:text-ink prose-strong:font-black prose-p:mb-6 first-letter:text-5xl first-letter:font-black first-letter:mr-3 first-letter:float-left first-letter:text-teal font-serif">
                   <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{autoBacktick(meta.executive_summary)}</ReactMarkdown>
                </div>
              </div>
            )}

          </section>

             {/* Health Section */}
          {bundle.health && (
            <section id="health" className="space-y-8 scroll-mt-24">
              <Sections.SectionHeader title="System Health" icon={Activity} />
              <div className={cn("p-10 rounded-3xl border overflow-hidden relative group", theme.surface.panel)}>
                <div className="absolute top-0 right-0 p-8 opacity-[0.03] group-hover:opacity-[0.08] transition-opacity pointer-events-none">
                   <Activity className="w-64 h-64 -mr-20 -mt-20" />
                </div>
                <div className="grid lg:grid-cols-2 gap-16 relative">
                  <div className="space-y-8">
                    <Sections.HealthBar label="Architectural Erosion" value={Math.round((bundle.health.erosion || 0) * 100)} inverted />
                    <Sections.HealthBar label="Logic Concentration (Gini)" value={Math.round((bundle.health.gini || 0) * 100)} inverted />
                    <Sections.HealthBar label="Workload Verbosity" value={Math.round((bundle.health.verbosity || 0) * 100)} inverted />
                  </div>
                  <div className="grid grid-cols-2 gap-8 content-start">
                    <Sections.Stat label="Total LOC" value={bundle.health.total_loc?.toLocaleString() ?? '—'} />
                    <Sections.Stat label="Functions" value={bundle.health.total_functions ?? '—'} />
                    <Sections.Stat label="High Complexity" value={bundle.health.high_cc_functions ?? '—'} />
                    <Sections.Stat label="Duplicate Lines" value={bundle.health.duplicate_lines ?? '—'} />
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Architecture Diagram */}
          {diagram && (
            <section id="diagram" className="space-y-8 scroll-mt-24">
              <Sections.SectionHeader title="Architecture Diagram" icon={Layout} />
              <div className={cn("p-10 rounded-3xl border shadow-2xl shadow-ink/5 bg-white/50 backdrop-blur-md overflow-hidden relative", theme.surface.panel)}>
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(45,161,176,0.03),transparent)] pointer-events-none" />
                <div className="relative">
                  <MermaidDiagram chart={diagram} />
                </div>
                <details className="mt-12 group overflow-hidden">
                  <summary className="list-none cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-ink/5 rounded-xl text-[10px] font-black uppercase tracking-widest text-ink/40 hover:text-ink hover:bg-ink/10 transition-all">
                    <Database className="w-3.5 h-3.5" />
                    <span>Scale Logic (Mermaid Source)</span>
                  </summary>
                  <div className="mt-4 p-8 rounded-2xl font-mono text-xs overflow-x-auto ring-1 ring-white/10 shadow-inner bg-ink text-papaya-300">
                    <pre>{diagram}</pre>
                  </div>
                </details>
              </div>
            </section>
          )}

          {/* 3b. Workspace Topology (monorepo whole-mode blueprints only) */}
          {bp.workspace_topology && (
            <section id="workspace-topology" className="scroll-mt-24">
              <Sections.WorkspaceTopologySection topology={bp.workspace_topology} />
            </section>
          )}

          {/* 4. Architecture Rules */}
          {(filePlacement.length > 0 || naming.length > 0) && (
            <section id="archrules" className="scroll-mt-24">
              <Sections.ArchRulesSection filePlacement={filePlacement} naming={naming} />
            </section>
          )}

          {/* 5. Development Rules */}
          {developmentRules.length > 0 && (
            <section id="devrules" className="scroll-mt-24">
              <Sections.DevelopmentRulesSection rules={developmentRules} />
            </section>
          )}

          {/* 6. Key Decisions */}
          {keyDecisions.length > 0 && (
            <section id="decisions" className="scroll-mt-24">
              <Sections.KeyDecisionsSection decisions={keyDecisions} />
            </section>
          )}

          {/* 7. Trade-offs */}
          {tradeOffs.length > 0 && (
            <section id="tradeoffs" className="scroll-mt-24">
              <Sections.TradeOffsSection tradeoffs={tradeOffs} />
            </section>
          )}

          {/* 8. Implementation Guidelines */}
          {implementationGuidelines.length > 0 && (
            <section id="guidelines" className="scroll-mt-24">
              <Sections.ImplementationGuidelinesSection items={implementationGuidelines} />
            </section>
          )}

          {/* 9. Communications */}
          {communications.length > 0 && (
            <section id="communications" className="scroll-mt-24">
              <Sections.CommunicationsSection communications={communications} />
            </section>
          )}

          {/* 10. Components */}
          {componentsList.length > 0 && (
            <section id="components" className="scroll-mt-24">
              <Sections.ComponentsSection components={componentsList} />
            </section>
          )}

          {/* 11. Technology Stack */}
          {stack.length > 0 && (
            <section id="technology" className="scroll-mt-24">
              <Sections.TechnologySection stack={stack} runCommands={runCommands} />
            </section>
          )}

          {/* Deployment (kept — not in user's spec but still useful if present) */}
          {Object.keys(deployment).length > 0 && (deployment.strategy || deployment.platform || (Array.isArray(deployment.infrastructure) && deployment.infrastructure.length > 0)) && (
            <section id="deployment" className="scroll-mt-24">
              <Sections.DeploymentSection deployment={deployment} />
            </section>
          )}

          {/* 12. Architectural Problems + Pitfalls — merged, end of page */}
          {(findings.length > 0 || pitfalls.length > 0) && (
            <section id="problems" className="space-y-12 scroll-mt-24">
              <Sections.SectionHeader title="Architectural Problems" icon={AlertTriangle} />

              {findings.length > 0 && <Sections.FindingsList findings={findings} />}

              {pitfalls.length > 0 && (
                <div id="pitfalls" className="scroll-mt-24">
                  <Sections.PitfallsSection pitfalls={pitfalls} />
                </div>
              )}
            </section>
          )}

          {/* Conversion Footer */}
          <footer id="try-archie" className="pt-20 pb-32 scroll-mt-24">
             <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-teal to-tangerine rounded-[40px] blur opacity-10 group-hover:opacity-20 transition-opacity duration-1000" />
                <div className="relative p-12 md:p-20 rounded-[38px] bg-white border border-papaya-400 shadow-2xl shadow-ink/5 text-center space-y-8 overflow-hidden">
                  <div className="absolute top-0 right-0 p-12 opacity-5 pointer-events-none">
                    <Activity className="w-96 h-96 -mr-48 -mt-48" />
                  </div>
                  
                  <div className="space-y-4 relative">
                    <div className="w-20 h-20 rounded-3xl bg-teal/10 flex items-center justify-center mx-auto mb-10 shadow-inner border border-teal/20">
                       <Activity className="text-teal w-10 h-10" />
                    </div>
                    <h3 className="text-4xl md:text-5xl font-black tracking-tighter text-ink leading-tight">
                      Archie knows your <br className="hidden md:block" /> codebase like a Senior Architect.
                    </h3>
                    <p className="text-xl text-ink/60 max-w-2xl mx-auto font-medium">
                      Understand complexity, enforce standards, and guide AI agents with precision.
                      Get started in 3 minutes.
                    </p>
                  </div>

                  <div className="relative pt-8 max-w-lg mx-auto">
                    <div className={cn(
                      'rounded-2xl p-6 font-mono text-sm flex items-center justify-between gap-4 shadow-2xl transition-all group/cmd',
                      theme.console.bg,
                      theme.console.text
                    )}>
                      <code className="truncate text-teal-100">{INSTALL_CMD}</code>
                      <button 
                        onClick={copyInstall} 
                        className="p-3 rounded-xl bg-white/10 hover:bg-white/20 text-white transition-all shrink-0 active:scale-90"
                        title="Copy"
                      >
                        {copied ? <Check className="w-5 h-5 text-teal" /> : <Copy className="w-5 h-5" />}
                      </button>
                    </div>
                    {copied && (
                      <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-3 py-1 bg-teal text-white text-[10px] font-black uppercase tracking-widest rounded-full shadow-lg animate-in fade-in zoom-in duration-300">
                         Copied to Keyboard
                      </div>
                    )}
                  </div>

                  <div className="pt-12 flex flex-col md:flex-row items-center justify-center gap-8">
                    <a
                      href="https://github.com/BitRaptors/Archie"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-black uppercase tracking-[0.2em] text-ink/40 hover:text-teal transition-all group"
                    >
                      <span>Explore GitHub</span>
                      <ExternalLink className="w-4 h-4 group-hover:-translate-y-1 group-hover:translate-x-1 transition-transform" />
                    </a>
                    <div className="w-1 h-1 rounded-full bg-ink/10 hidden md:block" />
                    <Link
                      to="/"
                      className="inline-flex items-center gap-2 text-sm font-black uppercase tracking-[0.2em] text-ink/40 hover:text-ink transition-all"
                    >
                      Documentation
                    </Link>
                  </div>
                </div>
             </div>
          </footer>
        </div>
      </main>
    </div>
  )
}

function NavButton({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: any; label: string }) {
  return (
    <button 
      onClick={onClick}
      className={cn(
        "flex items-center gap-4 w-full px-4 py-3 rounded-2xl text-sm font-bold transition-all duration-300 group",
        active 
          ? "bg-teal/10 text-teal shadow-inner ring-1 ring-teal/20" 
          : "text-ink/60 hover:text-ink hover:bg-papaya-300/30"
      )}
    >
      <div className={cn(
        "p-2 rounded-xl transition-all duration-500",
        active ? "bg-teal text-white shadow-lg shadow-teal/30 scale-110" : "bg-ink/5 group-hover:bg-ink/10 text-ink/30 group-hover:text-ink/60"
      )}>
        <Icon className="w-4 h-4" />
      </div>
      <span className="truncate">{label}</span>
      {active && (
        <div className="ml-auto w-1.5 h-1.5 rounded-full bg-teal animate-pulse shadow-[0_0_8px_rgba(45,161,176,0.5)]" />
      )}
    </button>
  )
}
