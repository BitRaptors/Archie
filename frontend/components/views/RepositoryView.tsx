import { useState, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { repositoriesService } from '@/services/repositories'
import { useRepositoriesQuery } from '@/hooks/api/useRepositoriesQuery'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Search, GitBranch, ArrowRight, Github, Star, CheckCircle2, Globe, Loader2, RotateCw, Eye, LayoutDashboard, Zap, Activity, X } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { useSetActiveRepository, useWorkspaceRepositories } from '@/hooks/api/useWorkspace'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { PageHeader } from '@/components/layout/PageHeader'

function parseGitHubUrl(input: string): { owner: string; repo: string } | null {
    const trimmed = input.trim()
    const short = trimmed.match(/^([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)$/)
    if (short) return { owner: short[1], repo: short[2] }
    const url = trimmed.match(/github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)/)
    if (url) return { owner: url[1], repo: url[2].replace(/\.git$/, '') }
    return null
}

interface RepositoryViewProps {
    onAnalyze: (id: string, name: string) => void
    onViewBlueprint: (repoId: string) => void
    activeRepoId?: string
}

export function RepositoryView({ onAnalyze, onViewBlueprint, activeRepoId }: RepositoryViewProps) {
    const { token } = useAuth()
    const queryClient = useQueryClient()
    const { data: repos, isLoading, refetch: refetchRepos } = useRepositoriesQuery()
    const { data: workspaceRepos } = useWorkspaceRepositories()
    const { mutate: setActiveRepo, isPending: isSettingActive } = useSetActiveRepository()
    const [analyzing, setAnalyzing] = useState<Set<string>>(new Set())
    const [search, setSearch] = useState('')
    const [publicUrl, setPublicUrl] = useState('')
    const [isAnalyzingPublic, setIsAnalyzingPublic] = useState(false)
    const [confirmDialog, setConfirmDialog] = useState<{owner: string, name: string} | null>(null)

    // Map GitHub full_name to workspace repo data (for blueprint status)
    const workspaceByName = new Map(workspaceRepos?.map(r => [r.name, r]) || [])

    const filteredRepos = useMemo(() => {
        if (!repos) return []
        return repos.filter(repo =>
            repo.full_name.toLowerCase().includes(search.toLowerCase()) ||
            (repo.description && repo.description.toLowerCase().includes(search.toLowerCase()))
        )
    }, [repos, search])

    const groupedRepos = useMemo(() => {
        if (!repos || !filteredRepos) return []
        const groups: Record<string, any[]> = {}
        filteredRepos.forEach(repo => {
            const owner = repo.owner || (repo.full_name.split('/')[0]) || 'Other'
            if (!groups[owner]) groups[owner] = []
            groups[owner].push(repo)
        })
        return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
    }, [filteredRepos, repos])

    const handleAnalyze = async (owner: string, name: string, mode: string = 'full') => {
        if (!token) return
        const key = `${owner}/${name}`
        setAnalyzing(prev => new Set(prev).add(key))
        try {
            const analysis = await repositoriesService.analyze(owner, name, token, mode)
            queryClient.invalidateQueries({ queryKey: ['workspace', 'repositories'] })
            onAnalyze(analysis.id, key)
        } catch (err: any) {
            const detail = err?.response?.data?.detail
            toast.error(typeof detail === 'string' ? detail : err.message || 'Failed to start analysis')
        } finally {
            setAnalyzing(prev => {
                const next = new Set(prev)
                next.delete(key)
                return next
            })
        }
    }

    const handleReAnalyze = (owner: string, name: string, hasBlueprint: boolean) => {
        if (hasBlueprint) {
            setConfirmDialog({ owner, name })
        } else {
            handleAnalyze(owner, name, 'full')
        }
    }

    const handlePublicAnalyze = async () => {
        const parsed = parseGitHubUrl(publicUrl)
        if (!parsed) {
            toast.error('Invalid GitHub URL. Use https://github.com/owner/repo or owner/repo')
            return
        }
        if (!token) return
        setIsAnalyzingPublic(true)
        try {
            const analysis = await repositoriesService.analyze(parsed.owner, parsed.repo, token)
            queryClient.invalidateQueries({ queryKey: ['workspace', 'repositories'] })
            onAnalyze(analysis.id, `${parsed.owner}/${parsed.repo}`)
            setPublicUrl('')
            refetchRepos()
        } catch (err: any) {
            const detail = err?.response?.data?.detail
            toast.error(typeof detail === 'string' ? detail : err.message || 'Failed to start analysis')
        } finally {
            setIsAnalyzingPublic(false)
        }
    }

    const handleSetActive = (repoId: string) => {
        setActiveRepo(repoId)
    }

    if (isLoading) {
        return (
            <div className="flex flex-col h-full bg-white/50">
                <PageHeader title="Repositories" subtitle="Loading your workspace..." icon={LayoutDashboard} />
                <div className="flex-1 p-8 space-y-6">
                    <Skeleton className="h-48 w-full rounded-2xl" />
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {[1, 2, 3].map(i => <Skeleton key={i} className="h-64 rounded-2xl" />)}
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="flex flex-col h-full overflow-hidden bg-white/50 animate-in fade-in duration-500">
            <PageHeader
                title="Repositories"
                subtitle="Select a project to analyze or set as your active context."
                icon={LayoutDashboard}
                actions={
                    <div className="relative w-64 md:w-80">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-300" />
                        <Input
                            placeholder="Search your library..."
                            className="pl-10 h-10 bg-white/50 border-papaya-400/60 focus:ring-teal/20 transition-all rounded-xl shadow-sm"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                }
            />

            <div className="flex-1 overflow-y-auto px-8 py-8">
                <div className="max-w-7xl mx-auto space-y-12">
                    {/* Analyze Public Repo Section */}
                    <div className="bg-white/60 border border-papaya-400/60 backdrop-blur-sm rounded-3xl p-6 shadow-sm">
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                            <div className="flex items-center gap-4">
                                <div className="p-3 rounded-2xl bg-tangerine/10 text-tangerine">
                                    <Globe className="w-6 h-6" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-bold text-ink">Analyze Public Repository</h2>
                                    <p className="text-sm text-ink-300">Architecture discovery for any public GitHub project.</p>
                                </div>
                            </div>
                            <div className="flex gap-2 flex-1 max-w-xl">
                                <div className="relative flex-1">
                                    <Github className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-300" />
                                    <Input
                                        placeholder="https://github.com/owner/repo"
                                        className="pl-10 h-11 bg-white/40 border-papaya-400/40 rounded-xl"
                                        value={publicUrl}
                                        onChange={(e) => setPublicUrl(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handlePublicAnalyze()}
                                    />
                                </div>
                                <Button
                                    className={cn("h-11 px-6 shadow-lg", theme.interactive.cta)}
                                    disabled={!publicUrl || isAnalyzingPublic}
                                    onClick={handlePublicAnalyze}
                                >
                                    {isAnalyzingPublic ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Zap className="w-4 h-4 mr-2" /> Analyze</>}
                                </Button>
                            </div>
                        </div>
                    </div>

                    {/* Repository Groups */}
                    <div className="space-y-12">
                        {groupedRepos.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-20 bg-white/20 border border-dashed border-papaya-400/60 rounded-3xl">
                                <Github className="w-16 h-16 text-ink-100 mb-4" />
                                <h3 className="text-xl font-bold text-ink">No Repositories Found</h3>
                                <p className="text-ink-300 mt-2">Adjust your search or add a new public repository.</p>
                            </div>
                        ) : (
                            groupedRepos.map(([owner, repos]) => (
                                <div key={owner} className="space-y-6">
                                    <div className="flex items-center gap-3">
                                        <img
                                            src={`https://github.com/${owner}.png?size=32`}
                                            alt={owner}
                                            className="w-8 h-8 rounded-lg border border-papaya-400 shadow-sm"
                                            onError={(e) => (e.target as any).src = 'https://github.com/github.png'}
                                        />
                                        <h3 className="text-sm font-black uppercase tracking-[0.2em] text-ink/40">{owner}</h3>
                                        <Badge className="bg-papaya-300/30 text-ink/40 border-papaya-400/40 font-bold">{repos.length}</Badge>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                        {repos.map(repo => {
                                            const isAnalyzing = analyzing.has(`${repo.owner}/${repo.name}`)
                                            const wsRepo = workspaceByName.get(repo.full_name)
                                            const hasBlueprint = wsRepo?.has_structured ?? false
                                            const isActive = wsRepo ? activeRepoId === wsRepo.repo_id : false

                                            return (
                                                <Card key={repo.id} className={cn(
                                                    "transition-all duration-300 hover:shadow-xl hover:-translate-y-1 border-papaya-400/60 bg-white group flex flex-col",
                                                    isActive && "border-teal ring-1 ring-teal/30 bg-teal-50/5 shadow-md shadow-teal/5"
                                                )}>
                                                    <CardHeader className="flex-1">
                                                        <div className="flex items-start justify-between">
                                                            <div className="space-y-1">
                                                                <h4 className="font-bold text-lg text-ink truncate group-hover:text-teal transition-colors" title={repo.full_name}>{repo.name}</h4>
                                                                <CardDescription className="line-clamp-2 text-xs leading-relaxed min-h-[2.5rem]">
                                                                    {repo.description || "No description provided."}
                                                                </CardDescription>
                                                            </div>
                                                            {isActive && (
                                                                <Badge className="bg-teal text-white border-0 shadow-lg shadow-teal/20 px-2 py-0.5 font-black uppercase text-[8px] tracking-widest shrink-0">
                                                                    Active
                                                                </Badge>
                                                            )}
                                                        </div>
                                                    </CardHeader>
                                                    <CardContent>
                                                        <div className="flex flex-wrap gap-2 mb-2">
                                                            {repo.language && (
                                                                <div className="px-2 py-0.5 rounded-full bg-papaya-300/30 border border-papaya-400/40 text-[10px] font-bold text-ink/60 uppercase tracking-wider flex items-center gap-1.5">
                                                                    <div className="w-1.5 h-1.5 rounded-full bg-tangerine" />
                                                                    {repo.language}
                                                                </div>
                                                            )}
                                                            <div className="px-2 py-0.5 rounded-full border border-papaya-300 text-[10px] font-bold text-ink/40 uppercase tracking-wider flex items-center gap-1.5">
                                                                <GitBranch className="w-3 h-3" />
                                                                {repo.default_branch || "main"}
                                                            </div>
                                                        </div>
                                                    </CardContent>
                                                    <CardFooter className="pt-4 border-t border-papaya-400/30 gap-2">
                                                        {hasBlueprint && wsRepo ? (
                                                            <>
                                                                <Button
                                                                    variant="outline"
                                                                    className="flex-1 h-9 gap-2 border-teal-200 text-teal hover:bg-teal-50 hover:border-teal font-bold"
                                                                    onClick={() => onViewBlueprint(wsRepo.repo_id)}
                                                                >
                                                                    <Eye className="w-4 h-4" /> Review
                                                                </Button>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    className="h-9 w-9 border border-papaya-400/40 text-ink/40 hover:bg-papaya-300/20"
                                                                    onClick={() => handleReAnalyze(repo.owner, repo.name, hasBlueprint)}
                                                                    disabled={isAnalyzing}
                                                                >
                                                                    <RotateCw className={cn("w-4 h-4", isAnalyzing && "animate-spin")} />
                                                                </Button>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    className={cn("h-9 w-9 transition-all", isActive ? "bg-teal text-white shadow-teal/20 shadow-lg" : "text-ink/20 hover:text-teal hover:bg-teal-50")}
                                                                    disabled={isActive || isSettingActive}
                                                                    onClick={() => handleSetActive(wsRepo.repo_id)}
                                                                >
                                                                    {isSettingActive && isActive ? <Loader2 className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
                                                                </Button>
                                                            </>
                                                        ) : (
                                                            <Button
                                                                className={cn("w-full h-9 gap-2 shadow-lg", theme.interactive.cta)}
                                                                onClick={() => handleAnalyze(repo.owner, repo.name)}
                                                                disabled={isAnalyzing}
                                                            >
                                                                {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Zap className="w-4 h-4" /> Start Discovery</>}
                                                            </Button>
                                                        )}
                                                    </CardFooter>
                                                </Card>
                                            )
                                        })}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Re-analyze confirmation dialog */}
            {confirmDialog && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white rounded-2xl shadow-2xl border border-papaya-400/60 p-6 w-full max-w-md mx-4">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-bold text-ink">Re-analyze Repository</h3>
                            <button
                                className="p-1 rounded-lg hover:bg-papaya-300/20 text-ink/40"
                                onClick={() => setConfirmDialog(null)}
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <p className="text-sm text-ink-300 mb-6">
                            <strong>{confirmDialog.owner}/{confirmDialog.name}</strong> already has a blueprint. How would you like to re-analyze?
                        </p>
                        <div className="flex gap-3">
                            <Button
                                className="flex-1 h-10 gap-2 bg-tangerine hover:bg-tangerine/90 text-white font-bold"
                                onClick={() => {
                                    const { owner, name } = confirmDialog
                                    setConfirmDialog(null)
                                    handleAnalyze(owner, name, 'incremental')
                                }}
                            >
                                <Zap className="w-4 h-4" /> Incremental
                            </Button>
                            <Button
                                variant="outline"
                                className="flex-1 h-10 gap-2 border-papaya-400 text-ink font-bold hover:bg-papaya-300/20"
                                onClick={() => {
                                    const { owner, name } = confirmDialog
                                    setConfirmDialog(null)
                                    handleAnalyze(owner, name, 'full')
                                }}
                            >
                                <RotateCw className="w-4 h-4" /> Full
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
