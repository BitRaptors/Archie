
import { useState, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Download, Copy, Check, FileText, Code, Database, Terminal, Server, Star, Rocket, Zap, Shield, GitPullRequest, Trash2, ChevronLeft, Github, ChevronRight, Loader2, CheckCircle2, X } from 'lucide-react'
import { MermaidDiagram } from '@/components/MermaidDiagram'
import { SourceFileModal } from '@/components/SourceFileModal'
import { useAuth } from '@/hooks/useAuth'
import { SERVER_TOKEN } from '@/context/auth'
import { useActiveRepository, useSetActiveRepository, useDeleteRepository, useWorkspaceRepositories } from '@/hooks/api/useWorkspace'
import { useDeliveryApply } from '@/hooks/api/useDelivery'
import { useRepositoriesQuery } from '@/hooks/api/useRepositoriesQuery'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { DebugView } from '@/components/DebugView'
import { Progress } from '@/components/ui/progress' // Assuming progress exists or I will create it

interface BlueprintData {
    analysis_id: string
    repository_id: string
    type?: string
    content: string
    path: string
}

interface BlueprintViewProps {
    analysisId?: string
    repoId?: string
    onBack: () => void
    initialTab?: 'backend' | 'claude' | 'cursor' | 'mcp' | 'debug' | 'delivery'
}

export function BlueprintView({ analysisId, repoId, onBack, initialTab }: BlueprintViewProps) {
    const { token, isAuthenticated } = useAuth()
    const { mutate: setActiveRepo, isPending: isSettingActive } = useSetActiveRepository()
    const { mutate: deleteAnalysis, isPending: isDeleting } = useDeleteRepository()
    const { data: activeRepo } = useActiveRepository()
    const { data: repos } = useRepositoriesQuery()
    const { data: workspaceRepos } = useWorkspaceRepositories()
    const deliveryApply = useDeliveryApply()

    const [backendBlueprint, setBackendBlueprint] = useState<BlueprintData | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [activeTab, setActiveTab] = useState<'backend' | 'claude' | 'cursor' | 'mcp' | 'debug'>(initialTab === 'delivery' ? 'backend' : (initialTab || 'backend'))
    const [isSyncPanelOpen, setIsSyncPanelOpen] = useState(false)
    const [syncSettings, setSyncSettings] = useState({
        targetRepo: '',
        strategy: 'pr' as 'pr' | 'commit',
        outputs: ['claude_md', 'cursor_rules', 'agents_md', 'mcp_claude', 'mcp_cursor']
    })
    const [deliveryResult, setDeliveryResult] = useState<any>(null)
    const [needsSync, setNeedsSync] = useState(false)
    const [projectPath, setProjectPath] = useState<string | null>(null)
    const [copied, setCopied] = useState(false)
    const [sourceFilePath, setSourceFilePath] = useState<string | null>(null)
    const [agentFiles, setAgentFiles] = useState<{
        claude_md: string
        cursor_rules: string
        agents_md: string
    } | null>(null)
    const [debugData, setDebugData] = useState<any>({
        gathered: {},
        phases: [],
        summary: {}
    })

    // Determine which ID to use
    const effectiveId = repoId || analysisId

    const fetchBlueprints = useCallback(async () => {
        if (!effectiveId || !token) return

        setIsLoading(true)
        setError(null)
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

        try {
            // Determine endpoint based on what ID we have (repoId implies workspace source)
            const backendUrl = repoId
                ? `${API_URL}/api/v1/workspace/repositories/${repoId}/blueprint`
                : `${API_URL}/api/v1/analyses/${analysisId}/blueprint?type=backend`

            const backendRes = await fetch(backendUrl, {
                headers: { Authorization: `Bearer ${token}` }
            })

            if (!backendRes.ok) throw new Error('Failed to load blueprint')
            const backendData = await backendRes.json()
            setBackendBlueprint(backendData)

            // Fetch agent files
            const agentUrl = repoId
                ? `${API_URL}/api/v1/workspace/repositories/${repoId}/agent-files`
                : `${API_URL}/api/v1/analyses/${analysisId}/agent-files`

            const agentRes = await fetch(agentUrl, { headers: { Authorization: `Bearer ${token}` } })
            if (agentRes.ok) setAgentFiles(await agentRes.json())

            // Fetch analysis data if we have an analysisId (debug data usually tied to analysis run)
            const targetAnalysisId = analysisId || backendData.analysis_id
            if (targetAnalysisId) {
                try {
                    const adRes = await fetch(`${API_URL}/api/v1/analyses/${targetAnalysisId}/analysis-data`, {
                        headers: { Authorization: `Bearer ${token}` }
                    })
                    if (adRes.ok) setDebugData(await adRes.json())
                } catch (e) { console.warn("Failed to load debug data", e) }
            }

            setIsLoading(false)
        } catch (err: any) {
            setIsLoading(false)
            setError(err.message)
        }
    }, [effectiveId, repoId, analysisId, token])

    const fetchProjectPath = useCallback(async () => {
        if (!token) return
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        try {
            const res = await fetch(`${API_URL}/api/v1/system/path`, {
                headers: { Authorization: `Bearer ${token}` },
            })
            if (res.ok) {
                const data = await res.json()
                setProjectPath(data.path)
            }
        } catch (err) {
            console.error(err)
        }
    }, [token])

    useEffect(() => {
        fetchBlueprints()
        fetchProjectPath()
    }, [fetchBlueprints, fetchProjectPath])

    const handleDownload = (content: string, filename: string) => {
        const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
    }

    const getMcpConfig = () => {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const config = {
            mcpServers: {
                "architecture-blueprints": {
                    url: `${API_URL}/mcp/sse`
                }
            }
        }
        return JSON.stringify(config, null, 2)
    }

    if (isLoading) {
        return (
            <div className="p-8 space-y-4">
                <Skeleton className="h-8 w-1/3" />
                <div className="flex gap-4">
                    <Skeleton className="h-10 w-32" />
                    <Skeleton className="h-10 w-32" />
                </div>
                <Skeleton className="h-96 w-full" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-full min-h-[60vh] p-8 animate-in fade-in zoom-in-95 duration-500">
                <div className="relative group">
                    <div className="absolute inset-0 bg-primary/20 rounded-full blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    <div className="relative w-24 h-24 bg-card border rounded-2xl flex items-center justify-center shadow-2xl mb-8 transform group-hover:-translate-y-1 transition-transform duration-500">
                        <FileText className="w-10 h-10 text-primary/80" />
                        <div className="absolute -right-2 -top-2 w-8 h-8 bg-destructive/10 rounded-full flex items-center justify-center border border-card shadow-sm">
                            <X className="w-4 h-4 text-destructive" />
                        </div>
                    </div>
                </div>

                <h3 className="text-2xl font-bold tracking-tight mb-3 text-center">Unable to Load Blueprint</h3>
                <p className="text-muted-foreground max-w-[400px] text-center mb-8 text-sm leading-relaxed">
                    We encountered an issue while retrieving the blueprint data. This could happen if the analysis hasn't completed or if the data is missing.
                </p>

                <div className="flex items-center gap-3">
                    <Button
                        variant="outline"
                        size="lg"
                        onClick={onBack}
                        className="h-11 px-8"
                    >
                        Return to Dashboard
                    </Button>
                    <Button
                        size="lg"
                        className="h-11 px-8 gap-2"
                        onClick={() => fetchBlueprints()}
                    >
                        Try Again
                    </Button>
                </div>

                <div className="mt-12 p-4 bg-muted/50 border rounded-lg max-w-md w-full text-center">
                    <p className="text-xs font-mono text-muted-foreground">
                        {error}
                    </p>
                </div>
            </div>
        )
    }

    const isActive = activeRepo?.active_repo_id === backendBlueprint?.repository_id
    const currentRepoId = repoId || backendBlueprint?.repository_id
    const repoFullName =
        workspaceRepos?.find((r: any) => r.repo_id === currentRepoId)?.name ||
        repos?.find((r: any) => r.id === currentRepoId || r.full_name === currentRepoId)?.full_name ||
        activeRepo?.repository?.name

    return (
        <div className="flex flex-col h-full animate-in fade-in zoom-in-95 duration-300">
            {/* Header */}
            <div className="border-b bg-card/50 px-6 py-4 flex items-center justify-between backdrop-blur-sm sticky top-0 z-10">
                <div className="flex items-center gap-4">
                    <div>
                        <h2 className="text-lg font-semibold tracking-tight">
                            Architecture Blueprint
                        </h2>
                        <p className="text-xs text-muted-foreground font-mono">
                            {repoId ? `Repo: ${repoId}` : `Analysis: ${analysisId?.slice(0, 8)}`}
                        </p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 h-9"
                        onClick={() => {
                            if (window.confirm("Are you sure you want to delete this blueprint and analysis data? This action cannot be undone.")) {
                                deleteAnalysis(repoId || backendBlueprint?.repository_id || '', {
                                    onSuccess: () => {
                                        onBack()
                                    }
                                })
                            }
                        }}
                        disabled={isDeleting}
                    >
                        <Trash2 className="w-4 h-4 mr-2" />
                        {isDeleting ? "Deleting..." : "Delete Analysis"}
                    </Button>

                    <div className="w-px h-6 bg-border" />

                    {repoFullName && <Button variant="outline" size="sm" className="h-9 gap-2" asChild>
                        <a
                            href={`https://github.com/${repoFullName}`}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            <Github className="w-4 h-4" />
                            Repository
                        </a>
                    </Button>}
                    <Button
                        size="sm"
                        className={cn(
                            "h-9 gap-2 shadow-lg",
                            needsSync
                                ? theme.status.syncRequired
                                : theme.interactive.ctaLarge
                        )}
                        onClick={() => {
                            setDeliveryResult(null)
                            setIsSyncPanelOpen(true)
                        }}
                    >
                        <Zap className="w-4 h-4 fill-current" />
                        {needsSync ? 'Sync Required' : 'Sync with Agent'}
                    </Button>
                    {backendBlueprint && (
                        <Button
                            size="sm"
                            variant={isActive ? "secondary" : "default"}
                            disabled={isActive || isSettingActive}
                            onClick={() => {
                                if (backendBlueprint) {
                                    setActiveRepo(backendBlueprint.repository_id)
                                    setNeedsSync(true)
                                }
                            }}
                            className={cn(isActive && theme.active.blueprintBtn)}
                        >
                            {isActive ? (
                                <><Check className="w-4 h-4 mr-2" /> Active Blueprint</>
                            ) : (
                                <><Star className="w-4 h-4 mr-2" /> Activate as Context</>
                            )}
                        </Button>
                    )}
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden flex flex-col p-6 gap-6 max-w-7xl mx-auto w-full">
                {/* Tabs */}
                <div className="flex items-center gap-1 overflow-x-auto pb-2 border-b">
                    <TabButton
                        active={activeTab === 'backend'}
                        onClick={() => setActiveTab('backend')}
                        icon={<Database className="w-4 h-4" />}
                    >
                        Blueprint
                    </TabButton>
                    <TabButton
                        active={activeTab === 'claude'}
                        onClick={() => setActiveTab('claude')}
                        icon={<FileText className="w-4 h-4" />}
                        className={theme.featureTab.claude}
                    >
                        CLAUDE.md
                    </TabButton>
                    <TabButton
                        active={activeTab === 'cursor'}
                        onClick={() => setActiveTab('cursor')}
                        icon={<Terminal className="w-4 h-4" />}
                        className={theme.featureTab.cursor}
                    >
                        Cursor Rules
                    </TabButton>
                    <TabButton
                        active={activeTab === 'mcp'}
                        onClick={() => setActiveTab('mcp')}
                        icon={<Server className="w-4 h-4" />}
                    >
                        MCP Setup
                    </TabButton>
                    {(analysisId || backendBlueprint?.analysis_id) && (
                        <TabButton
                            active={activeTab === 'debug'}
                            onClick={() => setActiveTab('debug')}
                            icon={<Code className="w-4 h-4" />}
                            className={theme.featureTab.debug}
                        >
                            Analysis Data & Prompts
                            {debugData?.phases?.length > 0 && (
                                <Badge variant="secondary" className={cn("ml-2 h-5 px-1.5 min-w-[1.25rem] flex items-center justify-center", theme.featureTab.debugBadge)}>
                                    {debugData.phases.length}
                                </Badge>
                            )}
                        </TabButton>
                    )}
                </div>

                {/* View container */}
                <div className="flex-1 overflow-y-auto min-h-0 bg-card border rounded-lg shadow-sm">
                    {activeTab === 'backend' && backendBlueprint && (
                        <div className="p-8 relative">
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleDownload(backendBlueprint.content, 'blueprint.md')}
                                className="absolute top-8 right-8 z-10 bg-white/80 backdrop-blur-sm"
                            >
                                <Download className="w-4 h-4 mr-2" />
                                Download Markdown
                            </Button>
                            <div className="prose dark:prose-invert max-w-none">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    urlTransform={(url) => {
                                        // Preserve source:// links — default transform strips custom protocols
                                        if (url.startsWith('source://')) return url
                                        return url
                                    }}
                                    components={{
                                        code({ className, children, ...props }) {
                                            if (className === 'language-mermaid') {
                                                return <MermaidDiagram chart={String(children).trim()} />
                                            }
                                            return <code className={className} {...props}>{children}</code>
                                        },
                                        pre({ children, node, ...props }) {
                                            const child = node?.children?.[0] as any
                                            if (child?.tagName === 'code' && child?.properties?.className?.[0] === 'language-mermaid') {
                                                return <>{children}</>
                                            }
                                            return <pre {...props}>{children}</pre>
                                        },
                                        a({ href, children, ...props }) {
                                            if (href?.startsWith('source://')) {
                                                const filePath = href.replace('source://', '')
                                                return (
                                                    <a
                                                        href="#"
                                                        onClick={(e) => { e.preventDefault(); setSourceFilePath(filePath) }}
                                                        className="text-blue-600 hover:underline cursor-pointer"
                                                        title={`View source: ${filePath}`}
                                                        {...props}
                                                    >
                                                        {children}
                                                    </a>
                                                )
                                            }
                                            return <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
                                        },
                                    }}
                                >
                                    {backendBlueprint.content}
                                </ReactMarkdown>
                            </div>
                        </div>
                    )}

                    {activeTab === 'claude' && agentFiles?.claude_md && (
                        <div className="p-8">
                            <div className="bg-green-50/50 border border-green-200 text-green-800 p-4 rounded-lg mb-6 text-sm">
                                <strong>CLAUDE.md</strong>: Place this in your project root for AI context.
                                <Button variant="link" className="h-auto p-0 ml-2 text-green-700 underline" onClick={() => handleDownload(agentFiles.claude_md, 'CLAUDE.md')}>Download</Button>
                            </div>
                            <div className="prose dark:prose-invert prose-green max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{agentFiles.claude_md}</ReactMarkdown>
                            </div>
                        </div>
                    )}

                    {activeTab === 'cursor' && agentFiles?.cursor_rules && (
                        <div className="p-8">
                            <div className="bg-purple-50/50 border border-purple-200 text-purple-800 p-4 rounded-lg mb-6 text-sm">
                                <strong>.cursor/rules/architecture.md</strong>: Place this in your cursor rules folder.
                                <Button variant="link" className="h-auto p-0 ml-2 text-purple-700 underline" onClick={() => handleDownload(agentFiles.cursor_rules, 'architecture.md')}>Download</Button>
                            </div>
                            <div className="prose dark:prose-invert prose-purple max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{agentFiles.cursor_rules}</ReactMarkdown>
                            </div>
                        </div>
                    )}

                    {activeTab === 'mcp' && (
                        <div className="p-8 max-w-3xl">
                            <h3 className="text-lg font-semibold mb-4">MCP Configuration</h3>
                            <p className="text-muted-foreground mb-4">
                                Add this to <code className="text-xs bg-muted px-1.5 py-0.5 rounded">.mcp.json</code> (Claude Code) or <code className="text-xs bg-muted px-1.5 py-0.5 rounded">.cursor/mcp.json</code> (Cursor) in your project root.
                            </p>
                            <div className="relative group">
                                <pre className="p-4 bg-muted rounded-lg overflow-x-auto text-sm font-mono border">
                                    {getMcpConfig()}
                                </pre>
                                <Button
                                    size="sm"
                                    className="absolute top-2 right-2 invisible group-hover:visible transition-all"
                                    onClick={() => {
                                        navigator.clipboard.writeText(getMcpConfig())
                                        setCopied(true)
                                        setTimeout(() => setCopied(false), 2000)
                                    }}
                                >
                                    {copied ? <Check className="w-3 h-3 mr-2" /> : <Copy className="w-3 h-3 mr-2" />}
                                    {copied ? "Copy" : "Copy"}
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* Sync Panel Overlay */}
                    {isSyncPanelOpen && (
                        <div className="fixed inset-0 z-[100] flex justify-end animate-in fade-in duration-300">
                            <div className={cn("absolute inset-0", theme.surface.overlay)} onClick={() => setIsSyncPanelOpen(false)} />
                            <div className="relative w-full max-w-xl bg-white shadow-2xl border-l flex flex-col animate-in slide-in-from-right duration-500 fill-mode-forwards">
                                <div className={cn("p-6 border-b flex items-center justify-between", theme.surface.footer)}>
                                    <div className="flex items-center gap-3">
                                        <div className={cn("p-2", theme.brand.syncIcon)}>
                                            <Zap className="w-5 h-5 text-white fill-current" />
                                        </div>
                                        <div>
                                            <h3 className="text-lg font-bold tracking-tight">Sync Pipeline</h3>
                                            <p className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Deploy to GitHub</p>
                                        </div>
                                    </div>
                                    <Button variant="ghost" size="icon" onClick={() => setIsSyncPanelOpen(false)}>
                                        <X className="w-5 h-5" />
                                    </Button>
                                </div>

                                <div className="flex-1 overflow-y-auto p-8 space-y-8">
                                    {/* Status HUD */}
                                    <div className="grid grid-cols-2 gap-4">
                                        <Card className={cn("p-4 shadow-sm", theme.status.successHud)}>
                                            <div className={cn("flex items-center gap-2 mb-2", theme.status.successHudIcon)}>
                                                <Shield className="w-4 h-4" />
                                                <span className="text-[10px] font-bold uppercase tracking-widest leading-none">Status</span>
                                            </div>
                                            <div className="text-xl font-bold text-foreground leading-none">Verified</div>
                                            <p className={cn("text-[10px] mt-1 uppercase font-bold", theme.status.successHudSubtext)}>Ready for push</p>
                                        </Card>
                                        <Card className={cn("p-4 shadow-sm", theme.surface.panelStrong)}>
                                            <div className="flex items-center gap-2 text-muted-foreground mb-2">
                                                <Rocket className="w-4 h-4" />
                                                <span className="text-[10px] font-bold uppercase tracking-widest leading-none">Target</span>
                                            </div>
                                            <div className="text-xl font-bold text-foreground leading-none truncate" title={syncSettings.targetRepo || "None selected"}>
                                                {syncSettings.targetRepo.split('/')[1] || "—"}
                                            </div>
                                            <p className="text-[10px] text-muted-foreground mt-1 uppercase font-bold truncate">{syncSettings.targetRepo || "Select repo below"}</p>
                                        </Card>
                                    </div>

                                    {/* Configuration */}
                                    <div className={cn("space-y-6 p-6 rounded-xl", theme.surface.config)}>
                                        <div className="space-y-4">
                                            <label className="text-[11px] font-black text-muted-foreground uppercase tracking-widest block">Destination Repository</label>
                                            <select
                                                value={syncSettings.targetRepo}
                                                onChange={(e) => {
                                                    setSyncSettings(prev => ({ ...prev, targetRepo: e.target.value }))
                                                    setDeliveryResult(null)
                                                }}
                                                className={cn("w-full h-11 px-4 rounded-lg border bg-white shadow-sm font-medium transition-all outline-none text-sm", theme.surface.inputBorder, theme.interactive.focusRing)}
                                            >
                                                <option value="">Select a repository...</option>
                                                {repos?.map((r) => (
                                                    <option key={r.full_name} value={r.full_name}>{r.full_name}</option>
                                                ))}
                                            </select>
                                        </div>

                                        <div className="space-y-4">
                                            <label className="text-[11px] font-black text-muted-foreground uppercase tracking-widest block">Sync Strategy</label>
                                            <div className="flex p-1 bg-white border rounded-lg shadow-sm">
                                                <button
                                                    onClick={() => {
                                                        setSyncSettings(prev => ({ ...prev, strategy: 'pr' }))
                                                        setDeliveryResult(null)
                                                    }}
                                                    className={cn(
                                                        "flex-1 py-2 text-xs font-bold rounded-md transition-all",
                                                        syncSettings.strategy === 'pr' ? theme.interactive.strategyActive : theme.interactive.strategyInactive
                                                    )}
                                                >
                                                    Pull Request
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setSyncSettings(prev => ({ ...prev, strategy: 'commit' }))
                                                        setDeliveryResult(null)
                                                    }}
                                                    className={cn(
                                                        "flex-1 py-2 text-xs font-bold rounded-md transition-all",
                                                        syncSettings.strategy === 'commit' ? theme.interactive.strategyActive : theme.interactive.strategyInactive
                                                    )}
                                                >
                                                    Direct Commit
                                                </button>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Pipeline Activity & Directives (Preserved from tab) */}
                                    <div className="space-y-6">
                                        <div className="space-y-3">
                                            <h4 className="text-[11px] font-black text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                                                <Terminal className="w-3.5 h-3.5" /> Recent Activity
                                            </h4>
                                            <div className="space-y-2">
                                                {[
                                                    { time: '10m ago', task: 'Architectural map updated', status: 'success' },
                                                    { time: '1h ago', task: 'Security scan completed', status: 'success' },
                                                ].map((log, i) => (
                                                    <div key={i} className={cn("flex items-center justify-between text-xs py-2 border-b", theme.surface.divider)}>
                                                        <div className="flex items-center gap-2">
                                                            <div className={cn("w-1.5 h-1.5 rounded-full", "bg-teal")} />
                                                            <span className="text-foreground/80">{log.task}</span>
                                                        </div>
                                                        <span className="text-[10px] text-muted-foreground font-medium">{log.time}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        <div className="space-y-3">
                                            <h4 className="text-[11px] font-black text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                                                <Code className="w-3.5 h-3.5" /> Active Directives
                                            </h4>
                                            <div className={cn("rounded-lg p-4 font-mono text-[10px] overflow-x-auto leading-relaxed", theme.console.directives)}>
                                                {`# Delivery Manifest
context: architecture-mcp
source: ${backendBlueprint?.repository_id || 'active'}
target: .cursor/rules/
strategy: ${syncSettings.strategy === 'pr' ? 'pull-request' : 'force-sync'}`}
                                            </div>
                                        </div>
                                    </div>

                                    {deliveryResult && (
                                        <div className={cn("p-4 rounded-xl animate-in fade-in slide-in-from-top-2 duration-300", theme.status.successPanel)}>
                                            <div className={cn("flex items-center gap-2 font-bold text-xs mb-2", theme.status.successText)}>
                                                <CheckCircle2 className="w-4 h-4" />
                                                DELIVERED SUCCESSFULLY
                                            </div>
                                            {deliveryResult.pr_url ? (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="w-full bg-white border-teal-200 text-teal-700 hover:bg-teal-50 hover:text-teal-800 gap-2"
                                                    asChild
                                                >
                                                    <a href={deliveryResult.pr_url} target="_blank" rel="noopener noreferrer">
                                                        <GitPullRequest className="w-3.5 h-3.5" />
                                                        View Pull Request
                                                    </a>
                                                </Button>
                                            ) : (
                                                <div className={cn("text-[10px] font-mono break-all bg-white/50 p-2 rounded border-teal-100", theme.status.successSubtext)}>
                                                    Commit: {deliveryResult.commit_sha}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>

                                <div className={cn("p-8 border-t", theme.surface.footer)}>
                                    <Button
                                        className={cn("w-full h-12 gap-3 group", theme.interactive.ctaLarge)}
                                        disabled={!syncSettings.targetRepo || deliveryApply.isPending}
                                        onClick={() => {
                                            if (!syncSettings.targetRepo) return;
                                            const req = {
                                                source_repo_id: repoId || backendBlueprint?.repository_id || '',
                                                target_repo: syncSettings.targetRepo,
                                                strategy: syncSettings.strategy,
                                                outputs: syncSettings.outputs
                                            };

                                            // Only send token if it's a real user token, not the server sentinel
                                            const authToken = token && token !== SERVER_TOKEN ? token : undefined;

                                            deliveryApply.mutate({ req, token: authToken }, {
                                                onSuccess: (data) => {
                                                    setDeliveryResult(data);
                                                    setNeedsSync(false);
                                                },
                                                onError: (err: any) => {
                                                    alert("Sync failed: " + (err.response?.data?.detail || err.message));
                                                }
                                            });
                                        }}
                                    >
                                        {deliveryApply.isPending ? (
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                        ) : (
                                            <>
                                                <Rocket className="w-5 h-5 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
                                                {syncSettings.strategy === 'pr' ? 'Create Delivery Pull Request' : 'Execute Direct Sync'}
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Debug Tab */}
                    {activeTab === 'debug' && (
                        <div className="p-8 animate-in fade-in slide-in-from-top-4 duration-500">
                            <DebugView data={
                                (debugData?.phases?.length > 0 || Object.keys(debugData?.gathered || {}).length > 0)
                                    ? debugData
                                    : null
                            } />
                        </div>
                    )}
                </div>
            </div>

            {/* Source File Modal */}
            {sourceFilePath && currentRepoId && (
                <SourceFileModal
                    filePath={sourceFilePath}
                    repoId={currentRepoId}
                    isOpen={!!sourceFilePath}
                    onClose={() => setSourceFilePath(null)}
                />
            )}
        </div>
    )
}

function TabButton({ active, onClick, children, icon, className }: any) {
    return (
        <button
            onClick={onClick}
            data-active={active}
            className={cn(
                "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-muted-foreground hover:text-foreground transition-all whitespace-nowrap",
                "data-[active=true]:border-primary data-[active=true]:text-primary data-[active=true]:bg-accent/50 rounded-t-lg",
                className
            )}
        >
            {icon}
            {children}
        </button>
    )
}
