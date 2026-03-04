import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Download, Copy, Check, FileText, Code, Database, Terminal, Server, Star, Rocket, Zap, Shield, GitPullRequest, Trash2, ChevronLeft, Github, ChevronRight, Loader2, CheckCircle2, X, Layers, Eye, Activity, Folder, DownloadCloud } from 'lucide-react'
import dynamic from 'next/dynamic'
import { MermaidDiagram } from '@/components/MermaidDiagram'
import { ConfirmationDialog } from '@/components/ConfirmationDialog'

const SourceFileModal = dynamic(
    () => import('@/components/SourceFileModal').then(mod => mod.SourceFileModal),
    { ssr: false }
)
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { SERVER_TOKEN } from '@/context/auth'
import { useActiveRepository, useSetActiveRepository, useDeleteRepository, useWorkspaceRepositories } from '@/hooks/api/useWorkspace'
import { useDeliveryApply } from '@/hooks/api/useDelivery'
import { useRepositoriesQuery } from '@/hooks/api/useRepositoriesQuery'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { generateId, parseNavigation } from '@/lib/blueprint-toc'
import { DebugView } from '@/components/DebugView'
import { Progress } from '@/components/ui/progress'
import { PageHeader } from '@/components/layout/PageHeader'

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
        outputs: ['claude_md', 'cursor_rules', 'agents_md', 'mcp_claude', 'mcp_cursor', 'intent_layer', 'codebase_map']
    })
    const [deliveryResult, setDeliveryResult] = useState<any>(null)
    const [needsSync, setNeedsSync] = useState(false)
    const [projectPath, setProjectPath] = useState<string | null>(null)
    const [copied, setCopied] = useState(false)
    const [sourceFilePath, setSourceFilePath] = useState<string | null>(null)
    const [showDeleteDialog, setShowDeleteDialog] = useState(false)
    const [agentFiles, setAgentFiles] = useState<{
        claude_md: string
        cursor_rules: string
        agents_md: string
        files?: Record<string, string>
    } | null>(null)
    const [selectedFile, setSelectedFile] = useState<string | null>(null)
    const [debugData, setDebugData] = useState<any>({
        gathered: {},
        phases: [],
        summary: {}
    })
    const [activeSection, setActiveSection] = useState('')

    const markdownComponents = useMemo(() => ({
        code({ className, children, ...props }: any) {
            if (className === 'language-mermaid') {
                return <MermaidDiagram chart={String(children).trim()} />
            }
            return <code className={className} {...props}>{children}</code>
        },
        pre({ children, node, ...props }: any) {
            const child = node?.children?.[0] as any
            if (child?.tagName === 'code' && child?.properties?.className?.[0] === 'language-mermaid') {
                return <>{children}</>
            }
            return <pre {...props}>{children}</pre>
        },
        a({ href, children, ...props }: any) {
            const isSourceLink = href?.startsWith('source://')
            const isRelativeFile = !!(href && !href.startsWith('http') && !href.startsWith('https') && !href.startsWith('#') && (href.includes('.') || href.includes('/')))

            if (isSourceLink || isRelativeFile) {
                const filePath = isSourceLink ? href?.replace('source://', '') : href
                if (filePath) {
                    return (
                        <span
                            onClick={() => setSourceFilePath(filePath)}
                            className="text-teal font-bold underline cursor-pointer hover:text-teal-600 transition-colors"
                        >
                            {children}
                        </span>
                    )
                }
            }
            return <a {...props} href={href || ''} target="_blank" rel="noopener noreferrer" className="text-teal underline font-medium">{children}</a>
        },
    }), []) // setSourceFilePath is a stable useState setter

    const toc = useMemo(
        () => (activeTab === 'backend' && backendBlueprint?.content)
            ? parseNavigation(backendBlueprint.content)
            : [],
        [backendBlueprint?.content, activeTab]
    )

    const effectiveId = repoId || analysisId

    const fetchBlueprints = useCallback(async () => {
        if (!effectiveId || !token) return
        setIsLoading(true)
        setError(null)
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        try {
            const backendUrl = repoId
                ? `${API_URL}/api/v1/workspace/repositories/${repoId}/blueprint`
                : `${API_URL}/api/v1/analyses/${analysisId}/blueprint?type=backend`

            const backendRes = await fetch(backendUrl, {
                headers: { Authorization: `Bearer ${token}` }
            })
            if (!backendRes.ok) throw new Error('Failed to load blueprint')
            const backendData = await backendRes.json()
            setBackendBlueprint(backendData)

            const agentUrl = repoId
                ? `${API_URL}/api/v1/workspace/repositories/${repoId}/agent-files`
                : `${API_URL}/api/v1/analyses/${analysisId}/agent-files`
            const agentRes = await fetch(agentUrl, { headers: { Authorization: `Bearer ${token}` } })
            if (agentRes.ok) setAgentFiles(await agentRes.json())

            const targetAnalysisId = analysisId || backendData.analysis_id
            if (targetAnalysisId) {
                try {
                    const adRes = await fetch(`${API_URL}/api/v1/analyses/${targetAnalysisId}/analysis-data`, {
                        headers: { Authorization: `Bearer ${token}` }
                    })
                    if (adRes.ok) setDebugData(await adRes.json())
                } catch (e) { }
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
        } catch (err: any) { }
    }, [token])

    useEffect(() => {
        fetchBlueprints()
        fetchProjectPath()
    }, [fetchBlueprints, fetchProjectPath])

    const scrollingToRef = useRef(false)

    useEffect(() => {
        if (activeTab !== 'backend' || toc.length === 0 || isLoading) return
        const container = document.getElementById('blueprint-content-area')
        if (!container) return
        const headings = container.querySelectorAll<HTMLElement>('h2, h3')
        headings.forEach((h) => {
            h.id = generateId(h.textContent || '')
            h.style.scrollMarginTop = '1.5rem'
        })
        const handleScroll = () => {
            if (scrollingToRef.current) return
            const containerTop = container.getBoundingClientRect().top
            let current = ''
            for (const h of headings) {
                const rect = h.getBoundingClientRect()
                if (rect.top - containerTop < 100) {
                    current = h.id
                } else {
                    break
                }
            }
            if (current) setActiveSection(current)
        }
        container.addEventListener('scroll', handleScroll, { passive: true })
        handleScroll()
        return () => container.removeEventListener('scroll', handleScroll)
    }, [toc, activeTab, isLoading])

    const scrollToSection = (id: string) => {
        const container = document.getElementById('blueprint-content-area')
        const element = document.getElementById(id)
        if (!container || !element) return
        scrollingToRef.current = true
        setActiveSection(id)
        const y = element.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop - 24
        container.scrollTo({ top: y, behavior: 'smooth' })
        setTimeout(() => { scrollingToRef.current = false }, 800)
    }

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
        return JSON.stringify({
            mcpServers: { "architecture-blueprints": { url: `${API_URL}/mcp/sse` } }
        }, null, 2)
    }

    if (isLoading) {
        return (
            <div className="flex flex-col h-screen bg-white/50">
                <PageHeader title="Blueprints" subtitle="Mapping architecture..." icon={Layers} />
                <div className="flex-1 p-8 space-y-6">
                    <Skeleton className="h-10 w-48" />
                    <div className="flex gap-6">
                        <Skeleton className="w-64 h-[600px] rounded-2xl" />
                        <Skeleton className="flex-1 h-[600px] rounded-2xl" />
                    </div>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-screen p-8 text-center bg-white/50">
                <div className="w-16 h-16 bg-brandy/10 rounded-full flex items-center justify-center mb-6">
                    <FileText className="w-8 h-8 text-brandy" />
                </div>
                <h3 className="text-xl font-bold text-ink mb-2">Failed to Load Blueprint</h3>
                <p className="text-ink-300 max-w-sm mb-8">{error}</p>
                <div className="flex gap-3">
                    <Button onClick={onBack} variant="outline" className="border-papaya-400">Back</Button>
                    <Button onClick={fetchBlueprints} className={theme.interactive.cta}>Try Again</Button>
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
        <div className="flex flex-col h-screen overflow-hidden bg-white/50 animate-in fade-in duration-500">
            <PageHeader
                title="Architecture Blueprint"
                subtitle={repoId ? `Repository: ${repoId}` : `Analysis: ${analysisId?.slice(0, 8)}`}
                icon={Layers}
                actions={
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            className="text-ink-300 hover:text-brandy hover:bg-brandy/10 h-9 border-papaya-400/60"
                            onClick={() => setShowDeleteDialog(true)}
                            disabled={isDeleting}
                        >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                        </Button>

                        <div className="w-px h-6 bg-papaya-300 mx-1" />

                        {repoFullName && (
                            <Button variant="outline" size="sm" className="h-9 gap-2 border-papaya-400/60 text-ink-300" asChild>
                                <a href={`https://github.com/${repoFullName}`} target="_blank" rel="noopener noreferrer">
                                    <Github className="w-4 h-4" />
                                    Repo
                                </a>
                            </Button>
                        )}

                        <Button
                            size="sm"
                            className={cn(
                                "h-9 gap-2 shadow-lg transition-all",
                                needsSync ? "bg-brandy hover:bg-brandy-600 text-white" : theme.interactive.cta
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
                                className={cn("h-9", isActive ? "bg-teal/10 text-teal border-teal/20" : "bg-teal hover:bg-teal-600 text-white shadow-lg shadow-teal/20")}
                            >
                                {isActive ? (
                                    <><Check className="w-4 h-4 mr-2" /> Active</>
                                ) : (
                                    <><Star className="w-4 h-4 mr-2" /> Activate</>
                                )}
                            </Button>
                        )}
                    </div>
                }
            />

            <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex items-center gap-8 border-b border-papaya-300 bg-white/30 px-8 z-10 backdrop-blur-sm shrink-0">
                    <button
                        onClick={() => setActiveTab('backend')}
                        className={cn(
                            "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px] flex items-center gap-2",
                            activeTab === 'backend' ? "text-teal border-teal" : "text-ink/40 hover:text-ink/60 border-transparent"
                        )}
                    >
                        <Database className="w-4 h-4" /> Blueprint
                    </button>
                    <button
                        onClick={() => { setActiveTab('claude'); setSelectedFile(null) }}
                        className={cn(
                            "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px] flex items-center gap-2",
                            activeTab === 'claude' ? "text-teal border-teal" : "text-ink/40 hover:text-ink/60 border-transparent"
                        )}
                    >
                        <FileText className="w-4 h-4" /> CLAUDE.md
                    </button>
                    <button
                        onClick={() => { setActiveTab('cursor'); setSelectedFile(null) }}
                        className={cn(
                            "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px] flex items-center gap-2",
                            activeTab === 'cursor' ? "text-teal border-teal" : "text-ink/40 hover:text-ink/60 border-transparent"
                        )}
                    >
                        <Terminal className="w-4 h-4" /> Cursor Rules
                    </button>
                    <button
                        onClick={() => setActiveTab('mcp')}
                        className={cn(
                            "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px] flex items-center gap-2",
                            activeTab === 'mcp' ? "text-teal border-teal" : "text-ink/40 hover:text-ink/60 border-transparent"
                        )}
                    >
                        <Server className="w-4 h-4" /> MCP Setup
                    </button>
                    {(analysisId || backendBlueprint?.analysis_id) && (
                        <button
                            onClick={() => setActiveTab('debug')}
                            className={cn(
                                "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px] flex items-center gap-2",
                                activeTab === 'debug' ? "text-teal border-teal" : "text-ink/40 hover:text-ink/60 border-transparent"
                            )}
                        >
                            <Code className="w-4 h-4" /> Analysis Data
                            {debugData?.phases?.length > 0 && (
                                <Badge className="ml-2 bg-papaya-300/30 text-ink/40 text-[10px] border-papaya-400/40">
                                    {debugData.phases.length}
                                </Badge>
                            )}
                        </button>
                    )}
                </div>

                <div className="flex-1 flex gap-6 overflow-hidden p-8">
                    {activeTab === 'backend' && toc.length > 0 && (
                        <aside className="w-64 flex-shrink-0 hidden lg:block overflow-y-auto pr-4 custom-scrollbar">
                            <div className="flex items-center gap-2 mb-6 px-1">
                                <div className="p-1.5 rounded-md bg-papaya-300/30">
                                    <Layers className="w-3.5 h-3.5 text-teal" />
                                </div>
                                <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em]">Overview</p>
                            </div>
                            <nav className="space-y-1">
                                {toc.map((section) => {
                                    const isMainActive = activeSection === section.id
                                    const hasActiveChild = section.items.some(item => activeSection === item.id)
                                    return (
                                        <div key={section.id} className="space-y-1">
                                            <button
                                                id={`toc-${section.id}`}
                                                onClick={() => scrollToSection(section.id)}
                                                className={cn(
                                                    "group flex items-center w-full text-left px-3 py-2 rounded-lg transition-all duration-200",
                                                    isMainActive ? "bg-teal/5 text-teal font-bold" : "text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium"
                                                )}
                                            >
                                                <span className="text-xs truncate flex-1">{section.title}</span>
                                                {isMainActive && <div className="w-1.5 h-1.5 rounded-full bg-teal" />}
                                            </button>
                                            {section.items.length > 0 && (
                                                <div className="ml-3 pl-2 border-l border-teal/20 space-y-1 my-1">
                                                    {section.items.map((item) => (
                                                        <button
                                                            key={item.id}
                                                            id={`toc-${item.id}`}
                                                            onClick={() => scrollToSection(item.id)}
                                                            className={cn(
                                                                "group flex items-center w-full text-left px-3 py-1.5 rounded-md text-[11px] transition-all",
                                                                activeSection === item.id ? "text-teal font-bold" : "text-ink/40 hover:text-ink/60 font-medium"
                                                            )}
                                                        >
                                                            <span className="truncate flex-1">{item.title}</span>
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )
                                })}
                            </nav>
                        </aside>
                    )}

                    <div className="flex-1 overflow-y-auto overflow-x-hidden bg-white/60 border border-papaya-400/60 rounded-3xl shadow-inner relative" id="blueprint-content-area">
                        {activeTab === 'backend' && backendBlueprint && (
                            <div className="p-10 relative">
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => handleDownload(backendBlueprint.content, 'blueprint.md')}
                                    className="absolute top-8 right-8 z-10 bg-white/80 backdrop-blur-sm border-papaya-400/60"
                                >
                                    <Download className="w-4 h-4 mr-2" /> Download
                                </Button>
                                <div className="prose prose-slate max-w-none prose-headings:text-ink prose-a:text-teal">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        urlTransform={(url) => {
                                            if (url.startsWith('source://')) return url
                                            return url
                                        }}
                                        components={markdownComponents}
                                    >
                                        {backendBlueprint.content}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        )}

                        {(activeTab === 'claude' || activeTab === 'cursor') && agentFiles?.files && (() => {
                            const isClaude = activeTab === 'claude'
                            const prefix = isClaude ? '.claude/' : '.cursor/'

                            // Build file entries: root files + per-folder CLAUDE.md + platform-specific rules
                            const rootFiles = isClaude
                                ? ['CLAUDE.md', 'AGENTS.md']
                                : []
                            const ruleFiles = Object.keys(agentFiles.files)
                                .filter(p => p.startsWith(prefix))
                                .sort()
                            // Include per-folder CLAUDE.md files and CODEBASE_MAP.md in Claude tab
                            const intentLayerFiles = isClaude
                                ? Object.keys(agentFiles.files)
                                    .filter(p => (p.endsWith('/CLAUDE.md') || p === 'CODEBASE_MAP.md') && !rootFiles.includes(p))
                                    .sort()
                                : []
                            const allPaths = [...rootFiles, ...intentLayerFiles, ...ruleFiles].filter(p => agentFiles.files![p])

                            // Build tree structure
                            type TreeNode = { name: string; path?: string; children: TreeNode[] }
                            const treeRoot: TreeNode = { name: '/', children: [] }

                            for (const filePath of allPaths) {
                                const parts = filePath.split('/')
                                let current = treeRoot
                                for (let i = 0; i < parts.length; i++) {
                                    const part = parts[i]
                                    const isFile = i === parts.length - 1
                                    let child = current.children.find(c => c.name === part)
                                    if (!child) {
                                        child = { name: part, children: [], ...(isFile ? { path: filePath } : {}) }
                                        current.children.push(child)
                                    }
                                    current = child
                                }
                            }

                            const currentFile = selectedFile && agentFiles.files[selectedFile] ? selectedFile : allPaths[0]
                            const currentContent = currentFile ? agentFiles.files[currentFile] : ''
                            const currentFileName = currentFile?.split('/').pop() || ''

                            const handleDownloadAll = () => {
                                for (const p of allPaths) {
                                    handleDownload(agentFiles.files![p], p.replace(/\//g, '_'))
                                }
                            }

                            const renderTree = (nodes: TreeNode[], depth: number = 0) => (
                                <div className={depth > 0 ? 'ml-3' : ''}>
                                    {nodes.map(node => (
                                        <div key={node.path || node.name}>
                                            {node.path ? (
                                                <button
                                                    onClick={() => setSelectedFile(node.path!)}
                                                    className={cn(
                                                        'flex items-center gap-1.5 w-full text-left px-2 py-1.5 rounded-lg text-xs transition-all duration-200',
                                                        currentFile === node.path
                                                            ? 'bg-teal/5 text-teal font-bold'
                                                            : 'text-ink/40 hover:text-ink/60 hover:bg-papaya-300/30 font-medium'
                                                    )}
                                                >
                                                    <FileText className="w-3.5 h-3.5 shrink-0" />
                                                    <span className="truncate">{node.name}</span>
                                                    {currentFile === node.path && <div className="w-1.5 h-1.5 rounded-full bg-teal ml-auto shrink-0" />}
                                                </button>
                                            ) : (
                                                <div className="flex items-center gap-1.5 px-2 py-1.5 text-xs font-bold text-ink/60">
                                                    <Folder className="w-3.5 h-3.5 shrink-0 text-tangerine" />
                                                    <span>{node.name}</span>
                                                </div>
                                            )}
                                            {node.children.length > 0 && renderTree(node.children, depth + 1)}
                                        </div>
                                    ))}
                                </div>
                            )

                            return (
                                <div className="flex h-full">
                                    {/* File tree sidebar */}
                                    <div className="w-56 shrink-0 border-r border-papaya-400/40 p-4 overflow-y-auto">
                                        <div className="flex items-center gap-2 mb-4 px-1">
                                            <div className="p-1.5 rounded-md bg-papaya-300/30">
                                                <Layers className="w-3.5 h-3.5 text-teal" />
                                            </div>
                                            <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em]">Files</p>
                                            <Badge className="ml-auto bg-papaya-300/30 text-ink/40 text-[10px] border-papaya-400/40">
                                                {allPaths.length}
                                            </Badge>
                                        </div>
                                        {renderTree(treeRoot.children)}
                                    </div>

                                    {/* File content */}
                                    <div className="flex-1 overflow-y-auto p-10">
                                        <div className={cn(
                                            'p-4 rounded-2xl mb-8 flex items-center justify-between',
                                            isClaude ? 'bg-teal-50 border border-teal-200' : 'bg-tangerine/5 border border-tangerine/20'
                                        )}>
                                            <code className={cn('text-xs font-mono font-medium', isClaude ? 'text-teal-800' : 'text-ink/80')}>{currentFile}</code>
                                            <div className="flex items-center gap-2">
                                                <Button variant="outline" size="sm" className={cn(isClaude ? 'border-teal-200 text-teal' : 'border-tangerine/20 text-tangerine')}
                                                    onClick={() => handleDownload(currentContent, currentFileName)}>
                                                    <Download className="w-3.5 h-3.5 mr-1.5" />Download
                                                </Button>
                                                <Button variant="outline" size="sm" className={cn(isClaude ? 'border-teal-200 text-teal' : 'border-tangerine/20 text-tangerine')}
                                                    onClick={handleDownloadAll}>
                                                    <DownloadCloud className="w-3.5 h-3.5 mr-1.5" />All
                                                </Button>
                                            </div>
                                        </div>
                                        <div className="prose prose-slate max-w-none prose-headings:text-ink prose-a:text-teal">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{currentContent}</ReactMarkdown>
                                        </div>
                                    </div>
                                </div>
                            )
                        })()}

                        {/* Fallback when files map not available */}
                        {activeTab === 'claude' && agentFiles?.claude_md && !agentFiles?.files && (
                            <div className="p-10">
                                <div className="bg-teal-50 border border-teal-200 p-4 rounded-2xl mb-8 flex justify-between items-center">
                                    <p className="text-sm text-teal-800 font-medium"><strong>CLAUDE.md</strong>: Place in root for AI context.</p>
                                    <Button variant="outline" size="sm" className="border-teal-200 text-teal" onClick={() => handleDownload(agentFiles.claude_md, 'CLAUDE.md')}>Download</Button>
                                </div>
                                <div className="prose max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{agentFiles.claude_md}</ReactMarkdown></div>
                            </div>
                        )}

                        {activeTab === 'cursor' && agentFiles?.cursor_rules && !agentFiles?.files && (
                            <div className="p-10">
                                <div className="bg-tangerine/5 border border-tangerine/20 p-4 rounded-2xl mb-8 flex justify-between items-center">
                                    <p className="text-sm text-ink/80 font-medium"><strong>.cursor/rules/architecture.md</strong>: Place in rules folder.</p>
                                    <Button variant="outline" size="sm" className="border-tangerine/20 text-tangerine" onClick={() => handleDownload(agentFiles.cursor_rules, 'architecture.md')}>Download</Button>
                                </div>
                                <div className="prose max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{agentFiles.cursor_rules}</ReactMarkdown></div>
                            </div>
                        )}

                        {activeTab === 'mcp' && (
                            <div className="p-10 max-w-3xl">
                                <h3 className="text-lg font-bold text-ink mb-4">MCP Configuration</h3>
                                <p className="text-sm text-ink-300 mb-6">Connect your workspace to the blueprint server for real-time architectural awareness.</p>
                                <div className="relative group">
                                    <pre className="p-6 bg-ink text-white rounded-2xl overflow-x-auto text-xs font-mono shadow-xl border-t border-white/10">
                                        {getMcpConfig()}
                                    </pre>
                                    <Button
                                        size="sm"
                                        className="absolute top-4 right-4 bg-white/10 hover:bg-white/20 text-white border-0"
                                        onClick={() => { navigator.clipboard.writeText(getMcpConfig()); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
                                    >
                                        {copied ? <Check className="w-3 h-3 mr-2" /> : <Copy className="w-3 h-3 mr-2" />} {copied ? "Copied" : "Copy"}
                                    </Button>
                                </div>
                            </div>
                        )}

                        {activeTab === 'debug' && (
                            <div className="p-10">
                                <DebugView data={(debugData?.phases?.length > 0 || Object.keys(debugData?.gathered || {}).length > 0) ? debugData : null} />
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Sync Overlay */}
            {isSyncPanelOpen && (
                <div className="fixed inset-0 z-[100] flex justify-end">
                    <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm animate-in fade-in duration-300" onClick={() => setIsSyncPanelOpen(false)} />
                    <div className="relative w-full max-w-xl bg-white shadow-2xl flex flex-col animate-in slide-in-from-right duration-500">
                        <div className="p-8 border-b border-papaya-300 flex items-center justify-between bg-white/80 backdrop-blur-md">
                            <div className="flex items-center gap-4">
                                <div className="p-3 rounded-2xl bg-tangerine shadow-lg shadow-tangerine/20 text-white"><Zap className="w-6 h-6 fill-current" /></div>
                                <div><h3 className="text-xl font-black text-ink">Sync with Agent</h3><p className="text-[10px] font-black uppercase tracking-widest text-ink/30">Provision Knowledge to AI</p></div>
                            </div>
                            <Button variant="ghost" size="icon" onClick={() => setIsSyncPanelOpen(false)}><X className="w-5 h-5 text-ink/40" /></Button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-10 space-y-10">
                            <div className="grid grid-cols-2 gap-4">
                                <Card className="p-5 border-teal/20 bg-teal-50/30">
                                    <div className="text-[10px] font-black uppercase text-teal mb-3 tracking-widest">Pipeline Health</div>
                                    <div className="text-2xl font-black text-ink">Verified</div>
                                </Card>
                                <Card className="p-5 border-papaya-400 bg-white">
                                    <div className="text-[10px] font-black uppercase text-ink/30 mb-3 tracking-widest">Target</div>
                                    <div className="text-2xl font-black text-ink truncate">{syncSettings.targetRepo.split('/')[1] || "—"}</div>
                                </Card>
                            </div>
                            <div className="space-y-6">
                                <label className="text-[10px] font-black uppercase text-ink/40 tracking-widest">Target Repository</label>
                                <select
                                    className="w-full h-12 px-4 rounded-xl border border-papaya-400 bg-white text-sm font-bold text-ink"
                                    value={syncSettings.targetRepo}
                                    onChange={(e) => setSyncSettings(p => ({ ...p, targetRepo: e.target.value }))}
                                >
                                    <option value="">Select a repository...</option>
                                    {repos?.map(r => <option key={r.full_name} value={r.full_name}>{r.full_name}</option>)}
                                </select>
                            </div>

                            <div className="space-y-6">
                                <label className="text-[10px] font-black uppercase text-ink/40 tracking-widest">Sync Strategy</label>
                                <div className="grid grid-cols-2 gap-3">
                                    <button
                                        onClick={() => setSyncSettings(p => ({ ...p, strategy: 'pr' }))}
                                        className={cn(
                                            "flex flex-col items-center justify-center p-4 rounded-2xl border transition-all gap-2",
                                            syncSettings.strategy === 'pr'
                                                ? "bg-teal/5 border-teal text-teal shadow-sm ring-1 ring-teal/20"
                                                : "bg-white border-papaya-400 text-ink/40 hover:border-teal/40"
                                        )}
                                    >
                                        <GitPullRequest className="w-5 h-5" />
                                        <span className="text-xs font-bold">Create Pull Request</span>
                                    </button>
                                    <button
                                        onClick={() => setSyncSettings(p => ({ ...p, strategy: 'commit' }))}
                                        className={cn(
                                            "flex flex-col items-center justify-center p-4 rounded-2xl border transition-all gap-2",
                                            syncSettings.strategy === 'commit'
                                                ? "bg-tangerine/5 border-tangerine text-tangerine shadow-sm ring-1 ring-tangerine/20"
                                                : "bg-white border-papaya-400 text-ink/40 hover:border-tangerine/40"
                                        )}
                                    >
                                        <Zap className="w-5 h-5" />
                                        <span className="text-xs font-bold">Direct Commit</span>
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-6 pt-4 border-t border-papaya-300">
                                <div className="space-y-4">
                                    <div className="flex items-center gap-3">
                                        <div className="w-1.5 h-1.5 rounded-full bg-teal shadow-[0_0_8px_rgba(45,161,176,0.5)]" />
                                        <h4 className="text-xs font-black uppercase tracking-wider text-ink">How it works</h4>
                                    </div>
                                    <p className="text-[11px] text-ink-300 leading-relaxed px-1">
                                        Archie establishes a live link between your repository and our engine. By provisioning a <strong>dynamic MCP bridge</strong>, AI agents gain real-time awareness of project patterns, transforming static files into an active, always-current source of truth.
                                    </p>
                                </div>

                                <div className="space-y-4 pt-4 border-t border-papaya-300">
                                    <div className="flex items-center gap-3">
                                        <div className="w-1.5 h-1.5 rounded-full bg-tangerine shadow-[0_0_8px_rgba(242,133,0,0.5)]" />
                                        <h4 className="text-xs font-black uppercase tracking-wider text-ink">Provisioned Files</h4>
                                    </div>
                                    <div className="grid gap-3">
                                        <div className="flex items-start gap-4 p-4 rounded-2xl bg-papaya-300/10 border border-papaya-400/40">
                                            <div className="bg-white p-2 rounded-lg border border-papaya-400 shadow-sm shrink-0">
                                                <Terminal className="w-4 h-4 text-teal" />
                                            </div>
                                            <div>
                                                <p className="text-xs font-bold text-ink">Architecture Rules</p>
                                                <p className="text-[10px] text-ink-300 mt-1 leading-relaxed">`.cursor/rules/architecture.md` — Enforces structural patterns directly in your IDE.</p>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-4 p-4 rounded-2xl bg-papaya-300/10 border border-papaya-400/40">
                                            <div className="bg-white p-2 rounded-lg border border-papaya-400 shadow-sm shrink-0">
                                                <Server className="w-4 h-4 text-purple-600" />
                                            </div>
                                            <div>
                                                <p className="text-xs font-bold text-ink">MCP Bridge</p>
                                                <p className="text-[10px] text-ink-300 mt-1 leading-relaxed">`mcp.json` — Injects a live connection to Archie for <strong>real-time, dynamic</strong> architectural awareness.</p>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-4 p-4 rounded-2xl bg-papaya-300/10 border border-papaya-400/40">
                                            <div className="bg-white p-2 rounded-lg border border-papaya-400 shadow-sm shrink-0">
                                                <Database className="w-4 h-4 text-blue-500" />
                                            </div>
                                            <div>
                                                <p className="text-xs font-bold text-ink">Static Arch Data</p>
                                                <p className="text-[10px] text-ink-300 mt-1 leading-relaxed">`ARCHIE.json` — Deep architectural primitives for advanced agent reasoning.</p>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-4 p-4 rounded-2xl bg-papaya-300/10 border border-papaya-400/40">
                                            <div className="bg-white p-2 rounded-lg border border-papaya-400 shadow-sm shrink-0">
                                                <FileText className="w-4 h-4 text-tangerine" />
                                            </div>
                                            <div>
                                                <p className="text-xs font-bold text-ink">AI Knowledge</p>
                                                <p className="text-[10px] text-ink-300 mt-1 leading-relaxed">`CLAUDE.md`, `agents.md` — Essential context for AI agents to operate on this codebase.</p>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-4 p-4 rounded-2xl bg-papaya-300/10 border border-papaya-400/40">
                                            <div className="bg-white p-2 rounded-lg border border-papaya-400 shadow-sm shrink-0">
                                                <Layers className="w-4 h-4 text-emerald-600" />
                                            </div>
                                            <div>
                                                <p className="text-xs font-bold text-ink">Per-Folder Context</p>
                                                <p className="text-[10px] text-ink-300 mt-1 leading-relaxed">`CLAUDE.md` per folder — Granular, code-aware context for every directory in your project.</p>
                                            </div>
                                        </div>
                                        <div className="flex items-start gap-4 p-4 rounded-2xl bg-papaya-300/10 border border-papaya-400/40">
                                            <div className="bg-white p-2 rounded-lg border border-papaya-400 shadow-sm shrink-0">
                                                <Layers className="w-4 h-4 text-indigo-500" />
                                            </div>
                                            <div>
                                                <p className="text-xs font-bold text-ink">Codebase Map</p>
                                                <p className="text-[10px] text-ink-300 mt-1 leading-relaxed">`CODEBASE_MAP.md` — Complete architecture map with module guide, navigation, and gotchas in a single file.</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="p-10 border-t border-papaya-300 bg-papaya-300/10">
                            <Button
                                className={cn("w-full h-14 gap-3 text-lg transition-all", theme.interactive.cta)}
                                disabled={!syncSettings.targetRepo || deliveryApply.isPending}
                                onClick={() => {
                                    const authToken = token && token !== SERVER_TOKEN ? token : undefined
                                    deliveryApply.mutate({
                                        req: { source_repo_id: repoId || backendBlueprint?.repository_id || '', target_repo: syncSettings.targetRepo, strategy: syncSettings.strategy, outputs: syncSettings.outputs },
                                        token: authToken
                                    }, {
                                        onSuccess: (data) => { setDeliveryResult(data); setNeedsSync(false); toast.success('Sync successful') },
                                        onError: (err: any) => toast.error(err.response?.data?.detail || err.message)
                                    })
                                }}
                            >
                                {deliveryApply.isPending ? <Loader2 className="w-6 h-6 animate-spin" /> : <><Rocket className="w-6 h-6" /> Deploy Blueprint</>}
                            </Button>
                        </div>
                    </div>
                </div>
            )}

            {showDeleteDialog && <ConfirmationDialog isOpen={showDeleteDialog} onClose={() => setShowDeleteDialog(false)} onConfirm={() => deleteAnalysis(repoId || backendBlueprint?.repository_id || '', { onSuccess: () => { setShowDeleteDialog(false); onBack() } })} title="Delete Blueprint" message="Are you sure? This action is permanent." confirmText="Delete" destructive isLoading={isDeleting} />}
            {sourceFilePath && currentRepoId && <SourceFileModal filePath={sourceFilePath} repoId={currentRepoId} isOpen={!!sourceFilePath} onClose={() => setSourceFilePath(null)} />}
        </div>
    )
}
