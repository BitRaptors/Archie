'use client'
import { useRouter } from 'next/router'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/hooks/useAuth'
import Link from 'next/link'

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
  const [events, setEvents] = useState<AnalysisEvent[]>([])
  const [status, setStatus] = useState<AnalysisStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const eventSourceRef = useRef<EventSource | null>(null)
  const timelineEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    timelineEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    if (!id || !token || !isAuthenticated) return

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    
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
        setStatus({
          status: analysis.status,
          progress: analysis.progress_percentage,
        })
      })
      .catch(err => {
        setIsLoading(false)
        setError(err.message)
      })

    // Connect to SSE stream
    const eventSource = new EventSource(`${API_URL}/api/v1/analyses/${id}/stream`)
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

    eventSource.addEventListener('error', (e) => {
      console.error('SSE Error:', e)
      // Don't set error for SSE connection issues, just log
    })

    return () => {
      eventSource.close()
    }
  }, [id, token, isAuthenticated])

  useEffect(() => {
    scrollToBottom()
  }, [events])

  if (!isAuthenticated) return <div className="p-8">Please authenticate first.</div>
  if (!id) return <div className="p-8">Loading...</div>

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
