import Link from "next/link"
import { useRouter } from "next/router"
import { useAuth } from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import { theme } from "@/lib/theme"
import {
    LayoutDashboard,
    GitBranch,
    FileJson,
    Settings,
    LogOut,
    Ghost,
    Layers,
    Zap,
    ChevronRight,
    Search,
    History
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { WorkspaceRepository } from "@/services/workspace"

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {
    activeView?: 'repositories' | 'analysis' | 'blueprint' | 'settings'
    onNavigate?: (view: 'repositories' | 'analysis' | 'blueprint' | 'settings') => void
    history?: WorkspaceRepository[]
    onHistoryClick?: (id: string, name: string) => void
    activeRepoId?: string
    openedRepoId?: string
    onActiveClick?: (id: string, name: string) => void
}

export function Sidebar({ className, activeView, onNavigate, history = [], onHistoryClick, activeRepoId, openedRepoId, onActiveClick }: SidebarProps) {
    const router = useRouter()
    const { logout } = useAuth()

    const handleLogout = () => {
        logout()
        router.push('/auth')
    }

    const activeProject = history.find(h => h.repo_id === activeRepoId)

    return (
        <div className={cn("flex flex-col w-64 border-r border-papaya-400/60 bg-white/70 backdrop-blur-xl h-screen relative", className)}>
            {/* Header / Logo */}
            <div className="p-6">
                <div className="flex items-center gap-3 mb-8 cursor-pointer group" onClick={() => onNavigate?.('repositories')}>
                    <div className="p-2.5 rounded-2xl bg-teal shadow-lg shadow-teal/20 text-white transition-transform group-hover:scale-105">
                        <Ghost className="w-5 h-5 fill-current" />
                    </div>
                    <div>
                        <h1 className="text-xl font-black tracking-tight text-ink leading-none">Archie</h1>
                        <p className="text-[9px] uppercase font-black tracking-[0.15em] text-ink/30 mt-1.5 line-clamp-1">Warden of Architecture</p>
                    </div>
                </div>

                {/* Active Context Card */}
                {activeProject && (
                    <div
                        className={cn(
                            "relative overflow-hidden p-4 rounded-2xl border transition-all cursor-pointer hover:shadow-md group",
                            theme.active.sidebarContext
                        )}
                        onClick={() => onActiveClick?.(activeProject.repo_id, activeProject.name)}
                    >
                        <div className="absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity">
                            <Zap className="w-12 h-12 fill-current text-teal" />
                        </div>
                        <div className="relative z-10">
                            <div className="flex items-center gap-2 mb-2">
                                <div className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse" />
                                <span className={cn("text-[10px] font-black uppercase tracking-widest", theme.active.sidebarContextLabel)}>Active Project</span>
                            </div>
                            <div className="flex items-center gap-2.5">
                                <FileJson className={cn("w-4 h-4", theme.active.iconColor)} />
                                <span className="text-xs font-bold text-ink truncate">{activeProject.name}</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Navigation Section */}
            <div className="flex-1 px-4 space-y-8 overflow-y-auto custom-scrollbar pb-32">
                <div className="space-y-1.5">
                    <Button
                        variant="ghost"
                        className={cn(
                            "w-full justify-start h-11 px-4 rounded-xl gap-3 transition-all font-bold text-sm",
                            activeView === 'repositories'
                                ? "bg-teal/5 text-teal shadow-sm border border-teal/10"
                                : "text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium"
                        )}
                        onClick={() => onNavigate?.('repositories')}
                    >
                        <LayoutDashboard className={cn("w-4 h-4", activeView === 'repositories' ? "text-teal" : "text-ink/30")} />
                        Repositories
                    </Button>
                    <Button
                        variant="ghost"
                        className={cn(
                            "w-full justify-start h-11 px-4 rounded-xl gap-3 transition-all font-bold text-sm",
                            activeView === 'settings'
                                ? "bg-teal/5 text-teal shadow-sm border border-teal/10"
                                : "text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium"
                        )}
                        onClick={() => onNavigate?.('settings')}
                    >
                        <Settings className={cn("w-4 h-4", activeView === 'settings' ? "text-teal" : "text-ink/30")} />
                        Settings
                    </Button>
                </div>

                {/* History Section */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between px-4">
                        <div className="flex items-center gap-2">
                            <History className="w-3.5 h-3.5 text-ink/20" />
                            <span className="text-[10px] font-black uppercase tracking-widest text-ink/30">Recent Library</span>
                        </div>
                        {history.length > 0 && (
                            <Badge className="bg-papaya-300/30 text-ink/30 text-[9px] border-papaya-400/40 h-4 px-1.5 font-bold">{history.length}</Badge>
                        )}
                    </div>

                    <div className="space-y-1">
                        {history.length > 0 ? (
                            history.map((item) => {
                                const isOpened = openedRepoId === item.repo_id
                                const isActivated = activeRepoId === item.repo_id

                                return (
                                    <button
                                        key={item.repo_id}
                                        onClick={() => onHistoryClick?.(item.repo_id, item.name)}
                                        className={cn(
                                            "w-full group relative flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all",
                                            isOpened
                                                ? "bg-white shadow-sm border border-papaya-400/60 ring-1 ring-black/5"
                                                : "hover:bg-papaya-300/20"
                                        )}
                                    >
                                        <div className={cn(
                                            "shrink-0 p-2 rounded-lg transition-colors",
                                            isOpened ? "bg-teal text-white" : "bg-papaya-300/40 text-ink/30 group-hover:text-ink/60"
                                        )}>
                                            <GitBranch className="w-3.5 h-3.5" />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <p className={cn(
                                                "text-xs font-bold truncate transition-colors",
                                                isOpened ? "text-ink" : "text-ink/60"
                                            )}>
                                                {item.name}
                                            </p>
                                            <p className="text-[9px] font-medium text-ink/30 uppercase tracking-tighter truncate">
                                                {isActivated ? 'Active Context' : 'Stored Blueprint'}
                                            </p>
                                        </div>

                                        {isActivated && (
                                            <div className="absolute left-1 top-1/2 -translate-y-1/2 w-1 h-4 bg-teal rounded-full" />
                                        )}

                                        <ChevronRight className={cn(
                                            "w-3 h-3 transition-all opacity-0 -translate-x-2",
                                            "group-hover:opacity-40 group-hover:translate-x-0"
                                        )} />
                                    </button>
                                )
                            })
                        ) : (
                            <div className="px-4 py-8 text-center bg-papaya-300/10 rounded-2xl border border-dashed border-papaya-400/40">
                                <Layers className="w-8 h-8 text-ink/10 mx-auto mb-2" />
                                <p className="text-[10px] font-bold text-ink/20 uppercase tracking-wider">Empty Library</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Footer / Logout */}
            <div className="p-4 border-t border-papaya-400/40 bg-white/50">
                <Button
                    variant="ghost"
                    className="w-full justify-start h-11 px-4 rounded-xl gap-3 text-ink/40 hover:text-brandy hover:bg-brandy/5 transition-all font-bold text-sm"
                    onClick={handleLogout}
                >
                    <LogOut className="w-4 h-4" />
                    Logout
                </Button>
            </div>
        </div>
    )
}
