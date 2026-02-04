'use client'
import { useRouter } from 'next/router'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/hooks/useAuth'
import Link from 'next/link'
import { DebugView } from '@/components/DebugView'

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

export default function AnalysisDetail() {
  const router = useRouter()
  const { id } = router.query
  const { token, isAuthenticated } = useAuth()
  const [mounted, setMounted] = useState(false)
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

  // Fix hydration error by only checking auth after mount
  useEffect(() => {
    setMounted(true)
  }, [])

  const scrollToBottom = () => {
    timelineEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    if (!id || !token || !isAuthenticated || !mounted) return

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    let eventSource: EventSource | null = null
    
    // First, verify the analysis exists and get initial status
    fetch(`${API_URL}/api/v1/analyses/${id}`)
      .then(res => {
        if (!res.ok) {
          throw new Error('Analysis not found')
        }
        return res.json()
      })
      .then(analysis => {
        setIsLoading(false)
        const currentStatus = {
          status: analysis.status,
          progress: analysis.progress_percentage,
        }
        setStatus(currentStatus)
        
        // If analysis is already complete, don't open SSE connection
        if (analysis.status === 'completed' || analysis.status === 'failed') {
          isCompleteRef.current = true
          return
        }

        // Connect to SSE stream only if analysis is in progress
        if (isCompleteRef.current) return // Don't connect if already complete
        
        eventSource = new EventSource(`${API_URL}/api/v1/analyses/${id}/stream`)
        eventSourceRef.current = eventSource

        eventSource.addEventListener('status', (e) => {
          const data = JSON.parse(e.data)
          setStatus(data)
          setIsLoading(false)
        })

        eventSource.addEventListener('log', (e) => {
          const event = JSON.parse(e.data)
          setEvents((prev) => {
            // Avoid duplicates
            if (prev.some(p => p.id === event.id)) return prev
            return [...prev, event]
          })
          scrollToBottom()
        })

        eventSource.addEventListener('debug_gathered', (e) => {
          const data = JSON.parse(e.data)
          setDebugData((prev: any) => ({
            ...prev,
            gathered: data
          }))
        })

        eventSource.addEventListener('debug_phase', (e) => {
          const data = JSON.parse(e.data)
          setDebugData((prev: any) => ({
            ...prev,
            phases: [...prev.phases.filter((p: any) => p.phase !== data.phase), data]
          }))
        })

        eventSource.addEventListener('debug_complete', (e) => {
          const data = JSON.parse(e.data)
          setDebugData(data)
        })

        eventSource.addEventListener('complete', (e) => {
          const data = JSON.parse(e.data)
          setStatus(data)
          setIsLoading(false)
          isCompleteRef.current = true
          // Close connection immediately when analysis completes
          if (eventSource) {
            eventSource.close()
            eventSourceRef.current = null
          }
        })

        eventSource.addEventListener('error', async (e) => {
          // If already complete, close connection and don't reconnect
          if (isCompleteRef.current) {
            if (eventSource) {
              eventSource.close()
              eventSourceRef.current = null
            }
            return
          }
          
          // Check if analysis is complete before reconnecting
          try {
            const res = await fetch(`${API_URL}/api/v1/analyses/${id}`)
            if (res.ok) {
              const analysis = await res.json()
              if (analysis.status === 'completed' || analysis.status === 'failed') {
                isCompleteRef.current = true
                if (eventSource) {
                  eventSource.close()
                  eventSourceRef.current = null
                }
                setStatus({
                  status: analysis.status,
                  progress: analysis.progress_percentage,
                })
                return
              }
            }
          } catch (err) {
            // If we can't check status, let it reconnect (only if not already complete)
            if (!isCompleteRef.current) {
              console.error('Error checking analysis status:', err)
            }
          }
        })
      })
      .catch(err => {
        setIsLoading(false)
        setError(err.message)
      })

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [id, token, isAuthenticated, mounted])

  useEffect(() => {
    scrollToBottom()
  }, [events])

  // Show loading state during SSR/hydration
  if (!mounted) {
    return (
      <div className="container mx-auto p-8 max-w-4xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Loading...</h1>
        </div>
        <div className="bg-white border rounded-lg p-8 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Loading analysis...</p>
        </div>
      </div>
    )
  }

  // Check authentication only after mount
  if (!isAuthenticated) {
    return (
      <div className="container mx-auto p-8 max-w-4xl">
        <div className="mb-8">
          <Link href="/" className="text-blue-500 hover:underline mb-2 inline-block">← Back to Repositories</Link>
          <h1 className="text-3xl font-bold">Authentication Required</h1>
        </div>
        <div className="bg-white border rounded-lg p-8 text-center">
          <p className="text-gray-600 mb-4">Please authenticate first.</p>
          <Link 
            href="/auth" 
            className="inline-block bg-blue-500 text-white px-6 py-2 rounded hover:bg-blue-600"
          >
            Go to Authentication
          </Link>
        </div>
      </div>
    )
  }

  if (!id) {
    return (
      <div className="container mx-auto p-8 max-w-4xl">
        <div className="mb-8">
          <Link href="/" className="text-blue-500 hover:underline mb-2 inline-block">← Back to Repositories</Link>
          <h1 className="text-3xl font-bold">Loading...</h1>
        </div>
        <div className="bg-white border rounded-lg p-8 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Loading analysis ID...</p>
        </div>
      </div>
    )
  }

  // Show loading state while initializing
  if (isLoading && !status) {
    return (
      <div className="container mx-auto p-8 max-w-4xl">
        <div className="mb-8">
          <Link href="/" className="text-blue-500 hover:underline mb-2 inline-block">← Back to Repositories</Link>
          <h1 className="text-3xl font-bold">Starting Analysis...</h1>
        </div>
        <div className="bg-white border rounded-lg p-8 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Initializing analysis. Please wait...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-8 max-w-4xl">
      <div className="mb-8 flex justify-between items-center">
        <div>
          <Link href="/" className="text-blue-500 hover:underline mb-2 inline-block">← Back to Repositories</Link>
          <h1 className="text-3xl font-bold">Analysis Timeline</h1>
          <p className="text-gray-500 text-sm">ID: {id}</p>
        </div>
        <div className="text-right">
          <div className="text-sm font-medium uppercase tracking-wider text-gray-500 mb-1">Status</div>
          <div className={`px-3 py-1 rounded-full text-sm font-bold inline-block ${
            status?.status === 'completed' ? 'bg-green-100 text-green-800' :
            status?.status === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-blue-100 text-blue-800'
          }`}>
            {status?.status || 'Initializing...'}
          </div>
        </div>
      </div>

      {status && (
        <div className="mb-8">
          <div className="flex justify-between mb-2">
            <span className="text-sm font-medium">Overall Progress</span>
            <span className="text-sm font-medium">{status.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div 
              className="bg-blue-600 h-4 rounded-full transition-all duration-500 ease-out" 
              style={{ width: `${status.progress}%` }}
            ></div>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}
      
      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        <button
          onClick={() => setActiveTab('timeline')}
          className={`px-6 py-3 text-sm font-bold transition-all border-b-2 ${
            activeTab === 'timeline' 
              ? 'border-blue-600 text-blue-600' 
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          ANALYSIS TIMELINE
        </button>
        <button
          onClick={() => setActiveTab('debug')}
          className={`px-6 py-3 text-sm font-bold transition-all border-b-2 flex items-center ${
            activeTab === 'debug' 
              ? 'border-blue-600 text-blue-600' 
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          DEBUG: DATA & PROMPTS
          {debugData.phases.length > 0 && (
            <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-600 rounded-full text-[10px]">
              {debugData.phases.length}
            </span>
          )}
        </button>
      </div>

      {activeTab === 'timeline' ? (
        <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
          <div className="bg-gray-50 border-b px-6 py-3 font-semibold text-gray-700">
            Process Logs
          </div>
          <div className="p-6 max-h-[500px] overflow-y-auto space-y-4 bg-slate-900 text-slate-100 font-mono text-sm">
            {events.length === 0 ? (
              <p className="text-slate-500 italic">Waiting for events...</p>
            ) : (
              events.map((event, index) => (
                <div key={event.id} className="flex gap-4 animate-in fade-in slide-in-from-left-2 duration-300">
                  <span className="text-slate-500 whitespace-nowrap">
                    [{new Date(event.created_at).toLocaleTimeString()}]
                  </span>
                  <span className={`font-bold whitespace-nowrap ${
                    event.type === 'PHASE_START' ? 'text-blue-400' :
                    event.type === 'PHASE_END' ? 'text-green-400' :
                    event.type === 'ERROR' ? 'text-red-400' :
                    'text-slate-300'
                  }`}>
                    {event.type}
                  </span>
                  <span className="text-slate-100">{event.message}</span>
                </div>
              ))
            )}
            <div ref={timelineEndRef} />
          </div>
        </div>
      ) : (
        <DebugView data={debugData.phases.length > 0 ? debugData : null} />
      )}

      {status?.status === 'completed' && (
        <div className="mt-8 text-center">
          <Link 
            href={`/blueprint/${id}`}
            className="bg-green-600 hover:bg-green-700 text-white px-8 py-3 rounded-lg font-bold shadow-md transition-all"
          >
            View Generated Blueprint
          </Link>
        </div>
      )}
    </div>
  )
}
