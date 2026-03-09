import { useEffect, useState, useRef, useMemo } from 'react'
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

const ANALYSIS_PHASES = [
    { id: 'structure', label: 'Structure' },
    { id: 'data', label: 'Data Prep' },
    { id: 'observation', label: 'Observation' },
    { id: 'discovery', label: 'Discovery' },
    { id: 'layers', label: 'Layers' },
    { id: 'patterns', label: 'Patterns' },
    { id: 'communication', label: 'Comms' },
    { id: 'technology', label: 'Tech' },
    { id: 'frontend', label: 'Frontend' },
    { id: 'implementation', label: 'Impl' },
    { id: 'synthesis', label: 'Synthesis' },
    { id: 'save', label: 'Save' },
    { id: 'intent', label: 'Intent Layer' },
]

interface PhaseGroup {
    phaseStart: AnalysisEvent
    events: AnalysisEvent[]
    phaseEnd?: AnalysisEvent
    duration?: number
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

    const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set())

    const eventSourceRef = useRef<EventSource | null>(null)
    const timelineEndRef = useRef<HTMLDivElement>(null)
    const isCompleteRef = useRef<boolean>(false)

    const currentPhaseIndex = useMemo(() => {
        const phaseMarkers: [string, number][] = [
            ['Phase 1', 0],
            ['Phase 2', 1],
            ['Observation', 2],
            ['Discovery', 3],
            ['Layers', 4],
            ['Patterns', 5],
            ['Communication', 6],
            ['Technology', 7],
            ['Frontend', 8],
            ['Implementation', 9],
            ['Synthesis', 10],
            ['Phase 4', 11],
            ['Intent layer', 12],
        ]
        let lastIndex = -1
        for (const e of events) {
            for (const [marker, idx] of phaseMarkers) {
                if (e.message.includes(marker) && (e.type === 'PHASE_START' || e.type === 'STEP')) {
                    lastIndex = Math.max(lastIndex, idx)
                }
            }
        }
        if (status?.status === 'completed') return ANALYSIS_PHASES.length
        return lastIndex
    }, [events, status?.status])

    const groupedEvents = useMemo(() => {
        const groups: PhaseGroup[] = []
        let currentGroup: PhaseGroup | null = null
        const ungrouped: AnalysisEvent[] = []

        for (const e of events) {
            if (e.type === 'PHASE_START') {
                if (currentGroup) groups.push(currentGroup)
                currentGroup = { phaseStart: e, events: [] }
            } else if (e.type === 'PHASE_END' && currentGroup) {
                currentGroup.phaseEnd = e
                const startTime = new Date(currentGroup.phaseStart.created_at).getTime()
                const endTime = new Date(e.created_at).getTime()
                currentGroup.duration = endTime - startTime
                groups.push(currentGroup)
                currentGroup = null
            } else if (currentGroup) {
                currentGroup.events.push(e)
            } else {
                ungrouped.push(e)
            }
        }
        if (currentGroup) groups.push(currentGroup)
        return { groups, ungrouped }
    }, [events])

    const scrollToBottom = () => {
        timelineEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    useEffect(() => {
        if (!analysisId || !token) return

        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        let eventSource: EventSource | null = null

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
                    // Fetch historical logs if already complete
                    fetch(`${API_URL}/api/v1/analyses/${analysisId}/logs`, {
                        headers: { Authorization: `Bearer ${token}` }
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

            {status?.status === 'in_progress' && (
                <div className="px-8 py-3 border-b border-papaya-300 bg-white/30 overflow-x-auto shrink-0">
                    <div className="flex items-center gap-1 min-w-max">
                        {ANALYSIS_PHASES.map((phase, i) => (
                            <div key={phase.id} className="flex items-center">
                                {i > 0 && <div className={cn("w-4 h-px mx-0.5", i <= currentPhaseIndex ? "bg-teal" : "bg-papaya-400/40")} />}
                                <div className={cn(
                                    "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all whitespace-nowrap",
                                    i < currentPhaseIndex
                                        ? "bg-teal/10 text-teal"
                                        : i === currentPhaseIndex
                                            ? "bg-teal text-white shadow-sm shadow-teal/20"
                                            : "text-ink/20"
                                )}>
                                    {i < currentPhaseIndex && <CheckCircle2 className="w-3 h-3" />}
                                    {i === currentPhaseIndex && <Loader2 className="w-3 h-3 animate-spin" />}
                                    {phase.label}
                                </div>
                            </div>
                        ))}
                    </div>
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
                                    <>
                                        {/* Ungrouped events (before first phase) */}
                                        {groupedEvents.ungrouped.map((e, i) => (
                                            <div key={`u-${i}`} className="flex gap-4 group">
                                                <span className={cn("shrink-0 tabular-nums", theme.console.timestamp)}>
                                                    {new Date(e.created_at).toLocaleTimeString([], { hour12: false })}
                                                </span>
                                                <div className="flex-1 break-words">
                                                    <span className={cn(
                                                        "font-black mr-3 uppercase tracking-tighter",
                                                        e.type === 'ERROR' && theme.consoleEvent.error,
                                                        e.type === 'WARNING' && theme.consoleEvent.warning,
                                                        e.type === 'INFO' && theme.console.waiting
                                                    )}>
                                                        [{e.type}]
                                                    </span>
                                                    <span className={cn("leading-relaxed", theme.console.text)}>{e.message}</span>
                                                </div>
                                            </div>
                                        ))}

                                        {/* Grouped events by phase */}
                                        {groupedEvents.groups.map((group, gi) => {
                                            const stepEvents = group.events.filter(e => e.type === 'STEP' || e.type === 'WARNING' || e.type === 'ERROR')
                                            const infoEvents = group.events.filter(e => e.type === 'INFO')
                                            const isExpanded = expandedGroups.has(gi)
                                            const isActive = !group.phaseEnd && status?.status === 'in_progress'
                                            const durationStr = group.duration ? `${(group.duration / 1000).toFixed(1)}s` : null

                                            return (
                                                <div key={`g-${gi}`} className="space-y-1.5">
                                                    {/* Phase header */}
                                                    <div className="flex items-center gap-3 pt-3 first:pt-0">
                                                        <span className={cn("shrink-0 tabular-nums", theme.console.timestamp)}>
                                                            {new Date(group.phaseStart.created_at).toLocaleTimeString([], { hour12: false })}
                                                        </span>
                                                        <div className="flex-1 flex items-center gap-2">
                                                            {group.phaseEnd ? (
                                                                <CheckCircle2 className="w-3.5 h-3.5 text-green-400 shrink-0" />
                                                            ) : isActive ? (
                                                                <Loader2 className="w-3.5 h-3.5 text-teal animate-spin shrink-0" />
                                                            ) : null}
                                                            <span className={cn("font-black uppercase tracking-tighter", theme.consoleEvent.phaseStart)}>
                                                                {group.phaseStart.message}
                                                            </span>
                                                            {durationStr && (
                                                                <span className="text-ink-400 ml-auto font-mono">{durationStr}</span>
                                                            )}
                                                        </div>
                                                    </div>

                                                    {/* STEP events (always visible) */}
                                                    {stepEvents.map((e, si) => (
                                                        <div key={`s-${gi}-${si}`} className="flex gap-4 pl-8">
                                                            <span className={cn("shrink-0 tabular-nums", theme.console.timestamp)}>
                                                                {new Date(e.created_at).toLocaleTimeString([], { hour12: false })}
                                                            </span>
                                                            <div className="flex-1 break-words">
                                                                {e.type === 'STEP' && <span className={cn("font-bold mr-2", theme.consoleEvent.step || "text-papaya-200")}>{'>'}</span>}
                                                                {e.type === 'WARNING' && <span className={cn("font-black mr-3 uppercase tracking-tighter", theme.consoleEvent.warning)}>[WARNING]</span>}
                                                                {e.type === 'ERROR' && <span className={cn("font-black mr-3 uppercase tracking-tighter", theme.consoleEvent.error)}>[ERROR]</span>}
                                                                <span className={cn(
                                                                    "leading-relaxed",
                                                                    e.type === 'WARNING' ? "text-amber-200" : theme.console.text
                                                                )}>{e.message}</span>
                                                            </div>
                                                        </div>
                                                    ))}

                                                    {/* Collapsed INFO events */}
                                                    {infoEvents.length > 0 && (
                                                        <div className="pl-8">
                                                            <button
                                                                onClick={() => setExpandedGroups(prev => {
                                                                    const next = new Set(prev)
                                                                    if (next.has(gi)) next.delete(gi)
                                                                    else next.add(gi)
                                                                    return next
                                                                })}
                                                                className="text-[10px] text-ink-400 hover:text-ink-200 font-mono transition-colors flex items-center gap-1"
                                                            >
                                                                <span className="text-ink-400">{isExpanded ? '\u25BC' : '\u25B6'}</span>
                                                                {infoEvents.length} detail{infoEvents.length > 1 ? 's' : ''}
                                                            </button>
                                                            {isExpanded && (
                                                                <div className="mt-1 space-y-1 border-l border-ink-400/30 pl-3">
                                                                    {infoEvents.map((e, ii) => (
                                                                        <div key={`i-${gi}-${ii}`} className="flex gap-4 opacity-60">
                                                                            <span className={cn("shrink-0 tabular-nums text-[10px]", theme.console.timestamp)}>
                                                                                {new Date(e.created_at).toLocaleTimeString([], { hour12: false })}
                                                                            </span>
                                                                            <span className={cn("text-[10px] leading-relaxed break-words", theme.console.text)}>{e.message}</span>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            )
                                        })}
                                    </>
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
