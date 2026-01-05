---
id: frontend-pattern-sse-hook
title: SSE Hook for Streaming
category: frontend
tags: [pattern, sse, streaming, hooks]
related: [frontend-patterns-overview]
---

# Pattern 5: SSE Hook for Streaming

For consuming Server-Sent Events from Python backend.

```typescript
// hooks/useSSE.ts
import { useState, useCallback, useRef, useEffect } from 'react'
import { useAuth } from './useAuth'

type SSEStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'done'

type SSEOptions<T> = {
  onMessage?: (data: T) => void
  onComplete?: () => void
  onError?: (error: Error) => void
}

export function useSSE<T = string>(options: SSEOptions<T> = {}) {
  const [messages, setMessages] = useState<T[]>([])
  const [status, setStatus] = useState<SSEStatus>('idle')
  const [error, setError] = useState<Error | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const { getIdToken } = useAuth()

  const connect = useCallback(
    async (url: string, body?: unknown) => {
      setStatus('connecting')
      setMessages([])
      setError(null)

      abortRef.current = new AbortController()

      try {
        const token = await getIdToken()
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            Accept: 'text/event-stream',
          },
          body: body ? JSON.stringify(body) : undefined,
          signal: abortRef.current.signal,
        })

        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        if (!response.body) throw new Error('No response body')

        setStatus('connected')
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data:')) {
              try {
                const data = JSON.parse(line.slice(5).trim()) as T
                setMessages((prev) => [...prev, data])
                options.onMessage?.(data)
              } catch {
                // Handle non-JSON data
                setMessages((prev) => [...prev, line.slice(5).trim() as T])
              }
            }
          }
        }

        setStatus('done')
        options.onComplete?.()
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setStatus('error')
          setError(err as Error)
          options.onError?.(err as Error)
        }
      }
    },
    [getIdToken, options],
  )

  const close = useCallback(() => {
    abortRef.current?.abort()
    setStatus('done')
  }, [])

  const reset = useCallback(() => {
    close()
    setMessages([])
    setError(null)
    setStatus('idle')
  }, [close])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  return {
    messages,
    status,
    error,
    isConnecting: status === 'connecting',
    isConnected: status === 'connected',
    isDone: status === 'done',
    isError: status === 'error',
    connect,
    close,
    reset,
  }
}
```


