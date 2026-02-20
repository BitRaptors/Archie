import { useState } from 'react'
import { repositoriesService } from '@/services/repositories'
import { useRepositoriesQuery } from '@/hooks/api/useRepositoriesQuery'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Search, GitBranch, ArrowRight, Github, Star, CheckCircle2, Globe, Loader2, RotateCw, Eye } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { useSetActiveRepository, useWorkspaceRepositories } from '@/hooks/api/useWorkspace'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'

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
    const { data: repos, isLoading } = useRepositoriesQuery()
    const { data: workspaceRepos } = useWorkspaceRepositories()
    const { mutate: setActiveRepo, isPending: isSettingActive } = useSetActiveRepository()
    const [analyzing, setAnalyzing] = useState<Set<string>>(new Set())
    const [search, setSearch] = useState('')
    const [publicUrl, setPublicUrl] = useState('')
    const [isAnalyzingPublic, setIsAnalyzingPublic] = useState(false)

    const githubFullNames = new Set(repos?.map(r => r.full_name) || [])
    const externalRepos = workspaceRepos?.filter(r => !githubFullNames.has(r.name)) || []

    // Map GitHub full_name to workspace repo data (for blueprint status)
    const workspaceByName = new Map(workspaceRepos?.map(r => [r.name, r]) || [])

    const handleAnalyze = async (owner: string, name: string, repoId: string) => {
        if (!token) return
        const key = `${owner}/${name}`
        setAnalyzing(prev => new Set(prev).add(key))
        try {
            const analysis = await repositoriesService.analyze(owner, name, token)
            onAnalyze(analysis.id, `${owner}/${name}`)
        } catch (err: any) {
            const detail = err?.response?.data?.detail
            toast.error(typeof detail === 'string' ? detail : err.message || 'Failed to start analysis')
            setAnalyzing(prev => {
                const next = new Set(prev)
                next.delete(key)
                return next
            })
        }
    }

    const handleSetActive = (repoId: string) => {
        setActiveRepo(repoId)
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
            onAnalyze(analysis.id, `${parsed.owner}/${parsed.repo}`)
            setPublicUrl('')
        } catch (err: any) {
            const detail = err?.response?.data?.detail
            toast.error(typeof detail === 'string' ? detail : err.message || 'Failed to start analysis')
        } finally {
            setIsAnalyzingPublic(false)
        }
    }

    const filteredRepos = repos?.filter(r =>
        r.full_name.toLowerCase().includes(search.toLowerCase())
    )

    if (isLoading) {
        return (
            <div className="p-8 space-y-6">
                <div className="flex items-center justify-between">
                    <Skeleton className="h-8 w-48" />
                    <Skeleton className="h-10 w-64" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[1, 2, 3, 4, 5, 6].map(i => (
                        <Skeleton key={i} className="h-48 w-full" />
                    ))}
                </div>
            </div>
        )
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Repositories</h1>
                    <p className="text-muted-foreground mt-1">Select a project to analyze or set as your active context.</p>
                </div>
                <div className="relative w-full md:w-72">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search repositories..."
                        className="pl-8"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
            </div>

            {/* Public Repo URL Input */}
            <Card>
                <CardHeader>
                    <div className="flex items-center gap-2">
                        <Globe className="w-5 h-5 text-primary" />
                        <CardTitle className="text-lg">Analyze Public Repository</CardTitle>
                    </div>
                    <CardDescription>
                        Paste any public GitHub repository URL to analyze its architecture.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex gap-2">
                        <Input
                            placeholder="https://github.com/owner/repo"
                            value={publicUrl}
                            onChange={(e) => setPublicUrl(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') handlePublicAnalyze() }}
                            disabled={isAnalyzingPublic}
                        />
                        <Button
                            onClick={handlePublicAnalyze}
                            disabled={isAnalyzingPublic || !publicUrl.trim()}
                        >
                            {isAnalyzingPublic ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Analyzing...
                                </>
                            ) : (
                                'Analyze'
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* External Repositories */}
            {externalRepos.length > 0 && (
                <div className="space-y-4">
                    <div className="flex items-center gap-2">
                        <Globe className="w-5 h-5 text-muted-foreground" />
                        <h2 className="text-xl font-semibold tracking-tight">External Repositories</h2>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {externalRepos.map((repo) => {
                            const parsed = parseGitHubUrl(repo.name)
                            const isReanalyzing = parsed ? analyzing.has(`${parsed.owner}/${parsed.repo}`) : false

                            return (
                                <Card key={repo.repo_id} className="group transition-all flex flex-col hover:border-primary/50">
                                    <CardHeader className="flex-1">
                                        <div className="flex items-center gap-2 text-lg font-bold">
                                            <Globe className="w-5 h-5" />
                                            <span className="truncate max-w-[180px]" title={repo.name}>{repo.name}</span>
                                        </div>
                                        <CardDescription className="mt-2">
                                            {repo.analyzed_at
                                                ? `Analyzed ${new Date(repo.analyzed_at).toLocaleDateString()}`
                                                : 'Not yet analyzed'}
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <div className={cn("w-2 h-2 rounded-full", theme.brand.languageDot)} />
                                            {repo.language || "Unknown"}
                                        </div>
                                    </CardContent>
                                    <CardFooter className="gap-2">
                                        {repo.has_structured && (
                                            <Button
                                                variant="default"
                                                className="flex-1"
                                                onClick={() => onViewBlueprint(repo.repo_id)}
                                            >
                                                <Eye className="w-4 h-4 mr-2" />
                                                View Blueprint
                                            </Button>
                                        )}
                                        {parsed && (
                                            <Button
                                                variant="outline"
                                                className={repo.has_structured ? '' : 'flex-1'}
                                                disabled={isReanalyzing}
                                                onClick={() => handleAnalyze(parsed.owner, parsed.repo, repo.repo_id)}
                                            >
                                                {isReanalyzing ? (
                                                    <>
                                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                                        Analyzing...
                                                    </>
                                                ) : (
                                                    <>
                                                        <RotateCw className="w-4 h-4 mr-2" />
                                                        Re-analyze
                                                    </>
                                                )}
                                            </Button>
                                        )}
                                    </CardFooter>
                                </Card>
                            )
                        })}
                    </div>
                </div>
            )}

            {/* GitHub Repositories */}
            {externalRepos.length > 0 && (
                <div className="flex items-center gap-2">
                    <Github className="w-5 h-5 text-muted-foreground" />
                    <h2 className="text-xl font-semibold tracking-tight">Your Repositories</h2>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredRepos?.map((repo) => {
                    const isAnalyzing = analyzing.has(`${repo.owner}/${repo.name}`)
                    const wsRepo = workspaceByName.get(repo.full_name)
                    const hasBlueprint = wsRepo?.has_structured ?? false
                    const isActive = wsRepo ? activeRepoId === wsRepo.repo_id : false

                    return (
                        <Card key={repo.id} className={cn(
                            "group transition-all flex flex-col",
                            isActive ? theme.active.card : "hover:border-primary/50"
                        )}>
                            <CardHeader className="flex-1">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-2 text-lg font-bold">
                                        <Github className="w-5 h-5" />
                                        <span className="truncate max-w-[180px]" title={repo.full_name}>{repo.name}</span>
                                    </div>
                                    {isActive ? (
                                        <Badge variant="secondary" className={theme.active.badge}>
                                            Active
                                        </Badge>
                                    ) : wsRepo ? (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className={cn("h-8 w-8 text-muted-foreground", theme.interactive.ghostBrand)}
                                            onClick={() => handleSetActive(wsRepo.repo_id)}
                                            disabled={isSettingActive}
                                        >
                                            <Star className="w-4 h-4" />
                                        </Button>
                                    ) : null}
                                </div>
                                <CardDescription className="line-clamp-2 mt-2">
                                    {repo.description || "No description provided."}
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <div className={cn("w-2 h-2 rounded-full", theme.brand.languageDot)} />
                                    {repo.language || "Unknown"}
                                    <span className="mx-1">•</span>
                                    <GitBranch className="w-3 h-3" />
                                    {repo.default_branch || "main"}
                                </div>
                            </CardContent>
                            <CardFooter className="gap-2">
                                {hasBlueprint && wsRepo && (
                                    <Button
                                        variant="default"
                                        className="flex-1"
                                        onClick={() => onViewBlueprint(wsRepo.repo_id)}
                                    >
                                        <Eye className="w-4 h-4 mr-2" />
                                        View Blueprint
                                    </Button>
                                )}
                                <Button
                                    variant="outline"
                                    className={hasBlueprint ? '' : 'flex-1'}
                                    disabled={isAnalyzing}
                                    onClick={() => handleAnalyze(repo.owner, repo.name, repo.id)}
                                >
                                    {isAnalyzing ? (
                                        <>
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                            Analyzing...
                                        </>
                                    ) : hasBlueprint ? (
                                        <>
                                            <RotateCw className="w-4 h-4 mr-2" />
                                            Re-analyze
                                        </>
                                    ) : (
                                        'Analyze'
                                    )}
                                </Button>
                                {isActive && (
                                    <Button
                                        variant="secondary"
                                        size="icon"
                                        disabled
                                        className={theme.active.checkBtn}
                                    >
                                        <CheckCircle2 className="w-4 h-4" />
                                    </Button>
                                )}
                            </CardFooter>
                        </Card>
                    )
                })}
            </div>
        </div>
    )
}
