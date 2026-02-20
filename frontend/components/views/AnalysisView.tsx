
import { useEffect, useState, useRef } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { DebugView } from '@/components/DebugView' // Assumes this exists and works
import { ArrowRight, Terminal, Activity, CheckCircle2, AlertCircle } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { useAuth } from '@/hooks/useAuth'

interface AnalysisEvent {
    id: string
    type: string
    message: string
    created_at: string
}

interface AnalysisStatus {
    status: string
    progress: number
}

interface AnalysisViewProps {
    analysisId: string
    onViewBlueprint: (id: string) => void
    onBack: () => void
}

export function AnalysisView({ analysisId, onViewBlueprint, onBack }: AnalysisViewProps) {
    const { token } = useAuth()
    const [events, setEvents] = useState<AnalysisEvent[]>([])
    const [status, setStatus] = useState<AnalysisStatus | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true) // Initial fetch loading
    const [activeTab, setActiveTab] = useState<'timeline' | 'debug'>('timeline')
    const [debugData, setDebugData] = useState<any>({
        gathered: {},
        phases: [],
        summary: {}
    })

    const eventSourceRef = useRef<EventSource | null>(null)
    const timelineEndRef = useRef<HTMLDivElement>(null)
    const isCompleteRef = useRef<boolean>(false)

    const scrollToBottom = () => {
        timelineEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    // Effect for SSE and interactions
    useEffect(() => {
        if (!analysisId || !token) return

        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        let eventSource: EventSource | null = null

        // 1. Fetch initial status
        fetch(`${API_URL}/api/v1/analyses/${analysisId}`, {
            headers: { Authorization: `Bearer ${token}` }
        })
            .then(res => {
                if (!res.ok) throw new Error('Analysis not found')
                return res.json()
            })
            .then(analysis => {
                setIsLoading(false)
                setStatus({
                    status: analysis.status,
                    progress: analysis.progress_percentage
                })

                if (analysis.status === 'completed' || analysis.status === 'failed') {
                    isCompleteRef.current = true
                    return
                }

                // 2. Connect SSE
                if (isCompleteRef.current) return

                eventSource = new EventSource(`${API_URL}/api/v1/analyses/${analysisId}/stream`)
                eventSourceRef.current = eventSource

                eventSource.addEventListener('status', (e) => {
                    const data = JSON.parse(e.data)
                    setStatus(data)
                })

                eventSource.addEventListener('log', (e) => {
                    const event = JSON.parse(e.data)
                    setEvents((prev) => {
                        if (prev.some(p => p.id === event.id)) return prev
                        return [...prev, event]
                    })
                    scrollToBottom()
                })

                // Debug events
                eventSource.addEventListener('debug_gathered', (e) => {
                    const data = JSON.parse(e.data)
                    setDebugData((prev: any) => ({ ...prev, gathered: data }))
                })
                eventSource.addEventListener('debug_phase', (e) => {
                    const data = JSON.parse(e.data)
                    setDebugData((prev: any) => ({
                        ...prev,
                        phases: [...prev.phases.filter((p: any) => p.phase !== data.phase), data]
                    }))
                })
                eventSource.addEventListener('debug_complete', (e) => {
                    setDebugData(JSON.parse(e.data))
                })

                eventSource.addEventListener('complete', (e) => {
                    const data = JSON.parse(e.data)
                    setStatus(data)
                    isCompleteRef.current = true
                    eventSource?.close()
                })

                eventSource.addEventListener('error', (e) => {
                    // Check if analysis finished while SSE was disconnected
                    fetch(`${API_URL}/api/v1/analyses/${analysisId}`, { headers: { Authorization: `Bearer ${token}` } })
                        .then(r => r.json())
                        .then(a => {
                            if (a.status === 'completed' || a.status === 'failed') {
                                setStatus(a)
                                isCompleteRef.current = true
                                eventSource?.close()
                            } else {
                                toast.error('Lost connection to analysis stream')
                            }
                        })
                        .catch(() => {
                            toast.error('Lost connection to analysis stream')
                        })
                })

            })
            .catch(err => {
                setIsLoading(false)
                setError(err.message)
            })

        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
            }
        }
    }, [analysisId, token])


    if (isLoading) {
        return (
            <div className="p-8 space-y-4">
                <Skeleton className="h-8 w-1/3" />
                <Skeleton className="h-64 w-full" />
            </div>
        )
    }

    return (
        <div className="flex flex-col h-full overflow-hidden animate-in fade-in duration-500">
            {/* Header */}
            <div className="border-b bg-card/50 px-6 py-4 flex items-center justify-between backdrop-blur-sm">
                <div className="flex items-center gap-4">
                    <div>
                        <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
                            Analysis
                            <span className="text-muted-foreground font-mono text-sm font-normal">#{analysisId.slice(0, 8)}</span>
                        </h2>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex flex-col items-end">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-medium text-muted-foreground uppercase">Status</span>
                            <Badge variant={
                                status?.status === 'completed' ? 'default' :
                                    status?.status === 'failed' ? 'destructive' : 'secondary'
                            }>
                                {status?.status === 'completed' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                                {status?.status === 'failed' && <AlertCircle className="w-3 h-3 mr-1" />}
                                {status?.status}
                            </Badge>
                        </div>
                    </div>
                    {status?.status === 'completed' && (
                        <Button onClick={() => onViewBlueprint(analysisId)}>
                            View Blueprint <ArrowRight className="ml-2 w-4 h-4" />
                        </Button>
                    )}
                </div>
            </div>

            {/* Progress Bar (if active) */}
            {status?.status === 'in_progress' && (
                <div className="h-1 w-full bg-secondary overflow-hidden">
                    <div
                        className="h-full bg-primary/80 transition-all duration-500 ease-out"
                        style={{ width: `${status?.progress || 0}%` }}
                    />
                </div>
            )}

            {/* Main Content */}
            <div className="flex-1 overflow-hidden flex flex-col p-6 gap-6">
                <div className="flex items-center gap-2 border-b pb-0">
                    <Button
                        variant={activeTab === 'timeline' ? "default" : "ghost"}
                        size="sm"
                        className="rounded-b-none rounded-t-lg"
                        onClick={() => setActiveTab('timeline')}
                    >
                        <Terminal className="w-4 h-4 mr-2" />
                        Console Log
                    </Button>
                    <Button
                        variant={activeTab === 'debug' ? "default" : "ghost"}
                        size="sm"
                        className="rounded-b-none rounded-t-lg"
                        onClick={() => setActiveTab('debug')}
                    >
                        <Activity className="w-4 h-4 mr-2" />
                        Debug Data
                        {debugData.phases.length > 0 && <Badge variant="secondary" className="ml-2 px-1 py-0">{debugData.phases.length}</Badge>}
                    </Button>
                </div>

                {activeTab === 'timeline' ? (
                    <Card className={cn("flex-1 overflow-hidden flex flex-col", theme.console.bg)}>
                        <div className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-2">
                            {events.length === 0 ? (
                                <div className={cn("flex items-center justify-center h-full", theme.console.waiting)}>
                                    <span className="animate-pulse">Waiting for analysis stream...</span>
                                </div>
                            ) : (
                                events.map((e, i) => (
                                    <div key={i} className={cn("flex gap-3", theme.console.text)}>
                                        <span className={cn("shrink-0 select-none", theme.console.timestamp)}>
                                            {new Date(e.created_at).toLocaleTimeString()}
                                        </span>
                                        <div className="flex-1 break-words">
                                            <span className={cn(
                                                "font-bold mr-2",
                                                e.type === 'PHASE_START' && theme.consoleEvent.phaseStart,
                                                e.type === 'PHASE_END' && theme.consoleEvent.phaseEnd,
                                                e.type === 'ERROR' && theme.consoleEvent.error,
                                            )}>
                                                [{e.type}]
                                            </span>
                                            {e.message}
                                        </div>
                                    </div>
                                ))
                            )}
                            {status?.status === 'completed' && events.length > 0 && (
                                <div className={cn("pt-4 pb-2 border-t mt-4 flex justify-center", theme.console.separator)}>
                                    <Button
                                        onClick={() => onViewBlueprint(analysisId)}
                                        className={cn("gap-2", theme.status.successBtn)}
                                    >
                                        <CheckCircle2 className="w-4 h-4" />
                                        View Blueprint
                                        <ArrowRight className="w-4 h-4" />
                                    </Button>
                                </div>
                            )}
                            <div ref={timelineEndRef} />
                        </div>
                    </Card>
                ) : (
                    <div className="flex-1 overflow-auto">
                        <DebugView data={debugData.phases.length > 0 ? debugData : null} />
                    </div>
                )}
            </div>
        </div>
    )
}
