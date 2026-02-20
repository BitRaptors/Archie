import { useState } from 'react'
import { repositoriesService } from '@/services/repositories'
import { useRepositoriesQuery } from '@/hooks/api/useRepositoriesQuery'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Search, GitBranch, ArrowRight, Github, Star, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { useSetActiveRepository } from '@/hooks/api/useWorkspace'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'

interface RepositoryViewProps {
    onAnalyze: (id: string, name: string) => void
    activeRepoId?: string
}

export function RepositoryView({ onAnalyze, activeRepoId }: RepositoryViewProps) {
    const { token } = useAuth()
    const { data: repos, isLoading } = useRepositoriesQuery()
    const { mutate: setActiveRepo, isPending: isSettingActive } = useSetActiveRepository()
    const [analyzing, setAnalyzing] = useState<Set<string>>(new Set())
    const [search, setSearch] = useState('')

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

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredRepos?.map((repo) => {
                    const isAnalyzing = analyzing.has(`${repo.owner}/${repo.name}`)
                    const isActive = activeRepoId === repo.id

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
                                    ) : (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className={cn("h-8 w-8 text-muted-foreground", theme.interactive.ghostBrand)}
                                            onClick={() => handleSetActive(repo.id)}
                                            disabled={isSettingActive}
                                        >
                                            <Star className="w-4 h-4" />
                                        </Button>
                                    )}
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
                                <Button
                                    variant={isActive ? "default" : "outline"}
                                    className="flex-1"
                                    disabled={isAnalyzing}
                                    onClick={() => handleAnalyze(repo.owner, repo.name, repo.id)}
                                >
                                    {isAnalyzing ? "Analyzing..." : "Analyze"}
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
