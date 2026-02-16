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
    Layers
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { WorkspaceRepository } from "@/services/workspace"

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {
    activeView?: 'repositories' | 'analysis' | 'blueprint' | 'settings'
    onNavigate?: (view: 'repositories' | 'analysis' | 'blueprint' | 'settings') => void
    history?: WorkspaceRepository[]
    onHistoryClick?: (id: string, name: string) => void
    activeRepoId?: string
    onActiveClick?: (id: string, name: string) => void
}

export function Sidebar({ className, activeView, onNavigate, history = [], onHistoryClick, activeRepoId, onActiveClick }: SidebarProps) {
    const router = useRouter()
    const { logout } = useAuth()

    const handleLogout = () => {
        logout()
        router.push('/auth')
    }

    const activeProject = history.find(h => h.repo_id === activeRepoId)

    return (
        <div className={cn("pb-12 w-64 border-r min-h-screen bg-card relative", className)}>
            <div className="space-y-4 py-4">
                <div className="px-3 py-2 border-b mb-2">
                    <h2 className="mb-4 px-4 text-lg font-semibold tracking-tight flex items-center gap-2">
                        <Ghost className={cn("w-5 h-5", theme.brand.icon)} />
                        <span>Architecture</span>
                    </h2>

                    {activeProject && (
                        <button
                            className={cn("w-full text-left px-4 py-3 rounded-lg mb-2 transition-all group", theme.active.sidebarContext)}
                            onClick={() => onActiveClick?.(activeProject.repo_id, activeProject.name)}
                        >
                            <p className={cn("text-[10px] uppercase font-bold mb-1 tracking-wider", theme.active.sidebarContextLabel)}>Active Context</p>
                            <div className="flex items-center gap-2 text-sm font-medium truncate">
                                <FileJson className={cn("w-3.5 h-3.5 group-hover:scale-110 transition-transform", theme.active.iconColor)} />
                                <span className="truncate">{activeProject.name}</span>
                            </div>
                        </button>
                    )}
                </div>

                <div className="px-3 py-2">
                    <h2 className="mb-2 px-4 text-xs font-semibold tracking-tight text-muted-foreground uppercase flex items-center gap-2">
                        <LayoutDashboard className="w-3 h-3" />
                        Navigation
                    </h2>
                    <div className="space-y-1">
                        <Button
                            variant={activeView === 'repositories' ? "secondary" : "ghost"}
                            className="w-full justify-start"
                            onClick={() => onNavigate?.('repositories')}
                        >
                            <GitBranch className="mr-2 h-4 w-4" />
                            All Repositories
                        </Button>
                        <Button
                            variant={activeView === 'settings' ? "secondary" : "ghost"}
                            className="w-full justify-start"
                            onClick={() => onNavigate?.('settings')}
                        >
                            <Settings className="mr-2 h-4 w-4" />
                            Settings
                        </Button>
                    </div>
                </div>
                <div className="px-3 py-2">
                    <h2 className="mb-2 px-4 text-xs font-semibold tracking-tight text-muted-foreground uppercase flex items-center gap-2">
                        <Layers className="w-3 h-3" />
                        Blueprints
                    </h2>
                    <div className="space-y-1 max-h-[300px] overflow-y-auto px-1">
                        {history.length > 0 ? (
                            history.map((item) => (
                                <Button
                                    key={item.repo_id}
                                    variant={activeRepoId === item.repo_id ? "secondary" : "ghost"}
                                    className={cn(
                                        "w-full justify-start font-normal text-sm gap-2 h-9",
                                        activeRepoId === item.repo_id && theme.active.sidebarItem
                                    )}
                                    onClick={() => onHistoryClick?.(item.repo_id, item.name)}
                                >
                                    <GitBranch className={cn("h-3.5 w-3.5", activeRepoId === item.repo_id ? theme.active.iconColor : "text-muted-foreground")} />
                                    <span className="truncate">{item.name}</span>
                                </Button>
                            ))
                        ) : (
                            <div className="px-4 py-2 text-xs text-muted-foreground italic">
                                No history yet
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="absolute bottom-4 left-0 w-full px-6">
                <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start text-muted-foreground hover:text-destructive hover:border-destructive/50"
                    onClick={handleLogout}
                >
                    <LogOut className="mr-2 h-4 w-4" />
                    Logout
                </Button>
            </div>
        </div>
    )
}
