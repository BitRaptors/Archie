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
    Layers,
    Zap,
    ChevronRight,
    ChevronLeft,
    Search,
    History
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ArchieLogo } from "@/components/ui/ArchieLogo"
import { WorkspaceRepository } from "@/services/workspace"

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {
    activeView?: 'repositories' | 'analysis' | 'blueprint' | 'settings'
    onNavigate?: (view: 'repositories' | 'analysis' | 'blueprint' | 'settings') => void
    history?: WorkspaceRepository[]
    onHistoryClick?: (id: string, name: string) => void
    activeRepoId?: string
    openedRepoId?: string
    onActiveClick?: (id: string, name: string) => void
    collapsed?: boolean
    onToggleCollapse?: () => void
}

export function Sidebar({ className, activeView, onNavigate, history = [], onHistoryClick, activeRepoId, openedRepoId, onActiveClick, collapsed = false, onToggleCollapse }: SidebarProps) {
    const router = useRouter()
    const { logout } = useAuth()

    const handleLogout = () => {
        logout()
        router.push('/auth')
    }

    const activeProject = history.find(h => h.repo_id === activeRepoId)

    return (
        <div className={cn(
            "flex flex-col border-r border-papaya-400/60 bg-white/70 backdrop-blur-xl h-screen relative transition-all duration-300 group/sidebar",
            collapsed ? "w-16" : "w-64",
            className
        )}>
            {/* Expand toggle — outside overflow-hidden, vertically centered with logo */}
            {collapsed && (
                <button
                    onClick={onToggleCollapse}
                    className="absolute top-[46px] -translate-y-1/2 -right-3 z-50 flex items-center justify-center w-6 h-6 rounded-full bg-white border border-papaya-400/60 shadow-sm text-ink/40 hover:text-ink/70 hover:bg-papaya-50 transition-all opacity-0 group-hover/sidebar:opacity-100"
                    title="Expand sidebar"
                >
                    <ChevronRight className="w-3 h-3" />
                </button>
            )}

            {/* Header / Logo */}
            <div className={cn("pt-6 transition-all duration-300 overflow-hidden", collapsed ? "px-3 pb-3" : "px-6 pb-6")}>
                <div className={cn("relative flex items-center group/header transition-all duration-300", collapsed ? "mb-3 justify-center" : "mb-8")}>
                    <div className="cursor-pointer group flex items-center gap-3 shrink-0" onClick={() => onNavigate?.('repositories')}>
                        <div className="shrink-0 rounded-2xl shadow-lg shadow-teal/20 transition-transform group-hover:scale-105 overflow-hidden">
                            <ArchieLogo size={collapsed ? 44 : 40} />
                        </div>
                    </div>
                    <div className={cn(
                        "whitespace-nowrap overflow-hidden transition-all duration-300 cursor-pointer",
                        collapsed ? "opacity-0 w-0 ml-0" : "opacity-100 w-auto ml-3"
                    )} onClick={() => onNavigate?.('repositories')}>
                        <h1 className="text-xl font-black tracking-tight text-ink leading-none">Archie</h1>
                        <p className="text-[9px] uppercase font-black tracking-[0.15em] text-ink/30 mt-1.5 line-clamp-1">Warden of Architecture</p>
                    </div>
                    <button
                        onClick={onToggleCollapse}
                        className={cn(
                            "shrink-0 flex items-center justify-center h-9 rounded-lg hover:!text-ink/60 hover:bg-papaya-300/30 transition-all duration-300 text-ink/0 group-hover/header:text-ink/30 overflow-hidden",
                            collapsed ? "opacity-0 max-w-0 ml-0 w-0" : "opacity-100 max-w-[36px] ml-2 w-9"
                        )}
                        title="Collapse sidebar"
                    >
                        <ChevronLeft className="w-4 h-4 shrink-0" />
                    </button>
                </div>

                {/* Active Context Card */}
                {activeProject && (
                    <div
                        className={cn(
                            "relative overflow-hidden rounded-2xl border transition-all duration-300 cursor-pointer group",
                            collapsed ? "p-2" : "p-4 hover:shadow-md",
                            theme.active.sidebarContext
                        )}
                        onClick={() => onActiveClick?.(activeProject.repo_id, activeProject.name)}
                        title={activeProject.name}
                    >
                        <div className={cn("absolute top-0 right-0 p-2 transition-all duration-300", collapsed ? "opacity-0" : "opacity-10 group-hover:opacity-20")}>
                            <Zap className="w-12 h-12 fill-current text-teal" />
                        </div>
                        <div className="relative z-10">
                            <div className={cn("flex items-center gap-2 mb-2 whitespace-nowrap overflow-hidden transition-all duration-300", collapsed ? "opacity-0 max-h-0 mb-0" : "opacity-100 max-h-8")}>
                                <div className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse shrink-0" />
                                <span className={cn("text-[10px] font-black uppercase tracking-widest", theme.active.sidebarContextLabel)}>Active Project</span>
                            </div>
                            <div className={cn("flex items-center whitespace-nowrap overflow-hidden transition-all duration-300", collapsed ? "justify-center gap-0" : "gap-2.5")}>
                                <div className="relative shrink-0">
                                    <FileJson className={cn("shrink-0 transition-all duration-300", collapsed ? "w-5 h-5" : "w-4 h-4", theme.active.iconColor)} />
                                    <div className={cn("absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-teal animate-pulse transition-opacity duration-300", collapsed ? "opacity-100" : "opacity-0")} />
                                </div>
                                <span className={cn("text-xs font-bold text-ink truncate transition-all duration-300 overflow-hidden", collapsed ? "opacity-0 max-w-0" : "opacity-100 max-w-[200px]")}>{activeProject.name}</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Navigation Section */}
            <div className={cn("flex-1 overflow-y-auto custom-scrollbar pb-32 transition-all duration-300", collapsed ? "px-2 space-y-4" : "px-4 space-y-8")}>
                <div className="space-y-1.5">
                    <Button
                        variant="ghost"
                        className={cn(
                            "h-11 rounded-xl transition-all duration-300 font-bold text-sm whitespace-nowrap overflow-hidden",
                            collapsed ? "w-11 px-0 justify-center mx-auto gap-0" : "w-full px-4 justify-start gap-3",
                            activeView === 'repositories'
                                ? "bg-teal/5 text-teal shadow-sm border border-teal/10"
                                : "text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium"
                        )}
                        onClick={() => onNavigate?.('repositories')}
                        title="Repositories"
                    >
                        <LayoutDashboard className={cn("w-4 h-4 shrink-0", activeView === 'repositories' ? "text-teal" : "text-ink/30")} />
                        <span className={cn("transition-all duration-300 overflow-hidden", collapsed ? "opacity-0 max-w-0" : "opacity-100 max-w-[200px]")}>Repositories</span>
                    </Button>
                    <Button
                        variant="ghost"
                        className={cn(
                            "h-11 rounded-xl transition-all duration-300 font-bold text-sm whitespace-nowrap overflow-hidden",
                            collapsed ? "w-11 px-0 justify-center mx-auto gap-0" : "w-full px-4 justify-start gap-3",
                            activeView === 'settings'
                                ? "bg-teal/5 text-teal shadow-sm border border-teal/10"
                                : "text-ink/60 hover:text-ink hover:bg-papaya-300/30 font-medium"
                        )}
                        onClick={() => onNavigate?.('settings')}
                        title="Settings"
                    >
                        <Settings className={cn("w-4 h-4 shrink-0", activeView === 'settings' ? "text-teal" : "text-ink/30")} />
                        <span className={cn("transition-all duration-300 overflow-hidden", collapsed ? "opacity-0 max-w-0" : "opacity-100 max-w-[200px]")}>Settings</span>
                    </Button>
                </div>

                {/* History Section */}
                <div className={cn("transition-all duration-300", collapsed ? "space-y-2" : "space-y-4")}>
                    <div className={cn("flex items-center whitespace-nowrap overflow-hidden transition-all duration-300", collapsed ? "w-11 mx-auto justify-center" : "justify-between px-4")}>
                        <div className={cn("flex items-center transition-all duration-300", collapsed ? "gap-0" : "gap-2")}>
                            <History className="w-3.5 h-3.5 text-ink/20 shrink-0" />
                            <span className={cn("text-[10px] font-black uppercase tracking-widest text-ink/30 transition-all duration-300 overflow-hidden", collapsed ? "opacity-0 max-w-0" : "opacity-100 max-w-[200px]")}>Recent Library</span>
                        </div>
                        <Badge className={cn("bg-papaya-300/30 text-ink/30 text-[9px] border-papaya-400/40 h-4 font-bold shrink-0 transition-all duration-300 overflow-hidden", collapsed || history.length === 0 ? "opacity-0 max-w-0 px-0" : "opacity-100 max-w-[40px] px-1.5")}>{history.length}</Badge>
                    </div>

                    <div className="space-y-1">
                        {history.length > 0 ? (
                            history.map((item) => {
                                const isOpened = openedRepoId === item.repo_id
                                const isActivated = activeRepoId === item.repo_id
                                const nameParts = item.name.split('/')
                                const abbrev = nameParts.length >= 2
                                    ? `${nameParts[0].slice(0, 3)}/${nameParts[1].slice(0, 3)}`
                                    : item.name.slice(0, 3)

                                return (
                                    <button
                                        key={item.repo_id}
                                        onClick={() => onHistoryClick?.(item.repo_id, item.name)}
                                        className={cn(
                                            "group relative flex items-center rounded-xl text-left transition-all duration-300 whitespace-nowrap overflow-hidden",
                                            collapsed ? "w-11 mx-auto px-0 justify-center gap-0.5 flex-col py-1" : "w-full px-4 gap-3 py-2.5",
                                            isOpened && !collapsed
                                                ? "bg-white shadow-sm border border-papaya-400/60 ring-1 ring-black/5"
                                                : isActivated && !collapsed
                                                    ? "bg-teal/5 border border-teal/20"
                                                    : "hover:bg-papaya-300/20"
                                        )}
                                        title={item.name}
                                    >
                                        <div className={cn(
                                            "shrink-0 p-2 rounded-lg transition-colors",
                                            isOpened ? "bg-teal text-white" : isActivated ? "bg-teal/20 text-teal" : "bg-papaya-300/40 text-ink/30 group-hover:text-ink/60"
                                        )}>
                                            <GitBranch className="w-3.5 h-3.5" />
                                        </div>

                                        <span className={cn("text-[7px] font-bold text-ink/40 truncate max-w-full leading-tight transition-all duration-300 overflow-hidden", collapsed ? "opacity-100 max-h-3" : "opacity-0 max-h-0 absolute")}>{abbrev}</span>

                                        <div className={cn("flex-1 min-w-0 overflow-hidden transition-all duration-300", collapsed ? "opacity-0 max-w-0 absolute" : "opacity-100 max-w-[200px]")}>
                                            <p className={cn(
                                                "text-xs font-bold truncate transition-colors",
                                                isOpened ? "text-ink" : isActivated ? "text-ink/80" : "text-ink/60"
                                            )}>
                                                {item.name}
                                            </p>
                                            <p className="text-[9px] font-medium text-ink/30 uppercase tracking-tighter truncate">
                                                {isActivated ? 'Active Context' : 'Stored Blueprint'}
                                            </p>
                                        </div>

                                        <div className={cn("absolute left-1 top-1/2 -translate-y-1/2 w-1 h-4 bg-teal rounded-full transition-opacity duration-300", isActivated && !collapsed ? "opacity-100" : "opacity-0")} />

                                        <ChevronRight className={cn(
                                            "w-3 h-3 shrink-0 transition-all duration-300",
                                            collapsed ? "opacity-0 max-w-0" : "opacity-0 -translate-x-2 group-hover:opacity-40 group-hover:translate-x-0"
                                        )} />
                                    </button>
                                )
                            })
                        ) : (
                            <div className={cn("py-8 text-center bg-papaya-300/10 rounded-2xl border border-dashed border-papaya-400/40", collapsed ? "px-1" : "px-4")}>
                                <Layers className={cn("text-ink/10 mx-auto mb-2", collapsed ? "w-5 h-5" : "w-8 h-8")} />
                                <p className={cn("text-[10px] font-bold text-ink/20 uppercase tracking-wider whitespace-nowrap overflow-hidden transition-opacity duration-300", collapsed && "opacity-0 h-0")}>Empty Library</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Footer / Logout */}
            <div className={cn("py-4 border-t border-papaya-400/40 bg-white/50 transition-all duration-300", collapsed ? "px-2" : "px-4")}>
                <Button
                    variant="ghost"
                    className={cn(
                        "h-11 rounded-xl text-ink/40 hover:text-brandy hover:bg-brandy/5 transition-all duration-300 font-bold text-sm whitespace-nowrap overflow-hidden",
                        collapsed ? "w-11 px-0 justify-center mx-auto gap-0" : "w-full px-4 justify-start gap-3"
                    )}
                    onClick={handleLogout}
                    title="Logout"
                >
                    <LogOut className="w-4 h-4 shrink-0" />
                    <span className={cn("transition-all duration-300 overflow-hidden", collapsed ? "opacity-0 max-w-0" : "opacity-100 max-w-[200px]")}>Logout</span>
                </Button>
            </div>
        </div>
    )
}
