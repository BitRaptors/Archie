import { useEffect, useState, useRef } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { DebugView } from '@/components/DebugView'
import { ArrowRight, Terminal, Activity, CheckCircle2, AlertCircle, Loader2, X } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { useAuth } from '@/hooks/useAuth'
import { PageHeader } from '@/components/layout/PageHeader'

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
    const [isLoading, setIsLoading] = useState(true)
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

    useEffect(() => {
        if (!analysisId) return

        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        let eventSource: EventSource | null = null

        fetch(`${API_URL}/api/v1/analyses/${analysisId}`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {}
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
                    // Fetch historical logs if already complete
                    fetch(`${API_URL}/api/v1/analyses/${analysisId}/logs`, {
                        headers: token ? { Authorization: `Bearer ${token}` } : {}
                    })
                        .then(res => res.json())
                        .then(data => setEvents(data))
                        .catch(() => { })
                    return
                }

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
                    fetch(`${API_URL}/api/v1/analyses/${analysisId}`, { headers: { Authorization: `Bearer ${token}` } })
                        .then(r => r.json())
                        .then(a => {
                            if (a.status === 'completed' || a.status === 'failed') {
                                setStatus(a)
                                isCompleteRef.current = true
                                eventSource?.close()
                            }
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
            <div className="flex flex-col h-full bg-white/50">
                <PageHeader title="Analysis Pipeline" subtitle="Initializing discovery engine..." icon={Activity} />
                <div className="flex-1 p-8 space-y-6">
                    <Skeleton className="h-48 w-full rounded-2xl" />
                    <Skeleton className="h-64 w-full rounded-2xl" />
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                <div className="w-16 h-16 bg-brandy/10 rounded-full flex items-center justify-center mb-4">
                    <AlertCircle className="w-8 h-8 text-brandy" />
                </div>
                <h3 className="text-xl font-bold text-ink mb-2">Analysis Failed to Load</h3>
                <p className="text-ink-300 max-w-md mb-6">{error}</p>
                <Button onClick={onBack} variant="outline" className="border-papaya-400">Back to Dashboard</Button>
            </div>
        )
    }

    return (
        <div className="flex flex-col h-full overflow-hidden bg-white/50 animate-in fade-in duration-500">
            <PageHeader
                title="Analysis Pipeline"
                subtitle={`Monitoring architectural discovery for #${analysisId.slice(0, 8)}`}
                icon={Activity}
                actions={
                    <div className="flex items-center gap-6">
                        <div className="flex flex-col items-end">
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] font-black text-ink/30 uppercase tracking-widest leading-none">Status</span>
                                <Badge className={cn(
                                    "px-2 py-0.5 font-black uppercase text-[10px] tracking-widest border-0",
                                    status?.status === 'completed' ? "bg-teal text-white shadow-lg shadow-teal/20" :
                                        status?.status === 'failed' ? "bg-brandy text-white shadow-lg shadow-brandy/20" :
                                            "bg-papaya-300/30 text-ink/60 border border-papaya-400/40 shadow-sm"
                                )}>
                                    {status?.status === 'completed' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                                    {status?.status === 'failed' && <AlertCircle className="w-3 h-3 mr-1" />}
                                    {status?.status || 'Active'}
                                </Badge>
                            </div>
                        </div>
                        {status?.status === 'completed' && (
                            <Button
                                onClick={() => onViewBlueprint(analysisId)}
                                className={cn("h-10 gap-2 shadow-lg", theme.interactive.cta)}
                            >
                                View Blueprint <ArrowRight className="w-4 h-4" />
                            </Button>
                        )}
                    </div>
                }
            />

            {status?.status === 'in_progress' && (
                <div className="h-1 w-full bg-papaya-300/30 shrink-0">
                    <div
                        className="h-full bg-teal transition-all duration-1000 ease-in-out shadow-[0_0_8px_rgba(33,158,188,0.5)]"
                        style={{ width: `${status?.progress || 0}%` }}
                    />
                </div>
            )}

            <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex items-center gap-8 border-b border-papaya-300 bg-white/30 px-8 z-10 backdrop-blur-sm shrink-0">
                    <button
                        onClick={() => setActiveTab('timeline')}
                        className={cn(
                            "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px] flex items-center gap-2",
                            activeTab === 'timeline' ? "text-teal border-teal" : "text-ink/40 hover:text-ink/60 border-transparent"
                        )}
                    >
                        <Terminal className="w-4 h-4" /> Console Log
                    </button>
                    <button
                        onClick={() => setActiveTab('debug')}
                        className={cn(
                            "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px] flex items-center gap-2",
                            activeTab === 'debug' ? "text-teal border-teal" : "text-ink/40 hover:text-ink/60 border-transparent"
                        )}
                    >
                        <Activity className="w-4 h-4" /> Debug Data
                        {debugData.phases.length > 0 && (
                            <Badge className="ml-2 bg-papaya-300/30 text-ink/40 text-[10px] border-papaya-400/40">
                                {debugData.phases.length}
                            </Badge>
                        )}
                    </button>
                </div>

                <div className="flex-1 flex flex-col overflow-hidden p-8">
                    {activeTab === 'timeline' ? (
                        <Card className={cn("flex-1 flex flex-col border-papaya-400/60 bg-white/60 backdrop-blur-xl shadow-inner overflow-hidden", theme.console.bg)}>
                            <div className="flex-1 overflow-y-auto p-6 font-mono text-xs space-y-3 custom-scrollbar">
                                {events.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center py-20 text-ink/20">
                                        <Loader2 className="w-8 h-8 animate-spin mb-4" />
                                        <span className="font-bold uppercase tracking-widest text-[10px]">Awaiting engine telemetry...</span>
                                    </div>
                                ) : (
                                    events.map((e, i) => (
                                        <div key={i} className="flex gap-4 group">
                                            <span className={cn("shrink-0 tabular-nums", theme.console.timestamp)}>
                                                {new Date(e.created_at).toLocaleTimeString([], { hour12: false })}
                                            </span>
                                            <div className="flex-1 break-words">
                                                <span className={cn(
                                                    "font-black mr-3 uppercase tracking-tighter",
                                                    e.type === 'PHASE_START' && theme.consoleEvent.phaseStart,
                                                    e.type === 'PHASE_END' && theme.consoleEvent.phaseEnd,
                                                    e.type === 'ERROR' && theme.consoleEvent.error,
                                                    e.type === 'WARNING' && theme.consoleEvent.warning,
                                                    e.type === 'INFO' && theme.console.waiting
                                                )}>
                                                    [{e.type.replace('_', ' ')}]
                                                </span>
                                                <span className={cn(
                                                    "leading-relaxed",
                                                    e.type === 'WARNING' ? "text-amber-200" : theme.console.text
                                                )}>{e.message}</span>
                                            </div>
                                        </div>
                                    ))
                                )}
                                {status?.status === 'completed' && events.length > 0 && (
                                    <div className="pt-8 flex justify-center">
                                        <Button
                                            onClick={() => onViewBlueprint(analysisId)}
                                            className={cn("gap-2 shadow-xl", theme.interactive.cta)}
                                        >
                                            <CheckCircle2 className="w-4 h-4" />
                                            Exploration Complete! View Results
                                            <ArrowRight className="w-4 h-4" />
                                        </Button>
                                    </div>
                                ) || status?.status === 'completed' && (
                                    <div className="pt-8 flex justify-center">
                                        <Button
                                            onClick={() => onViewBlueprint(analysisId)}
                                            className={cn("gap-2 shadow-xl", theme.interactive.cta)}
                                        >
                                            <CheckCircle2 className="w-4 h-4" />
                                            Exploration Complete! View Results
                                            <ArrowRight className="w-4 h-4" />
                                        </Button>
                                    </div>
                                )}
                                <div ref={timelineEndRef} />
                            </div>
                        </Card>
                    ) : (
                        <div className="flex-1 overflow-y-auto rounded-3xl border border-papaya-400/60 bg-white/60 p-6 custom-scrollbar">
                            <DebugView data={debugData.phases.length > 0 ? debugData : null} />
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
