import { useState, useEffect, useRef, useCallback } from 'react';
import { auth } from '@/firebaseConfig';

interface SSEEvent {
  event: string;
  data: any;
}

interface UseSSEStreamOptions {
  url: string;
  enabled?: boolean;
  onEvent?: (event: SSEEvent) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

interface UseSSEStreamReturn {
  isConnected: boolean;
  error: string | null;
  disconnect: () => void;
}

export function useSSEStream({
  url,
  enabled = true,
  onEvent,
  onDone,
  onError,
}: UseSSEStreamOptions): UseSSEStreamReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const onEventRef = useRef(onEvent);
  const onDoneRef = useRef(onDone);
  const onErrorRef = useRef(onError);

  // Keep callback refs up to date without causing re-renders
  onEventRef.current = onEvent;
  onDoneRef.current = onDone;
  onErrorRef.current = onError;

  const disconnect = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (!enabled || !url) return;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const connect = async () => {
      try {
        const user = auth.currentUser;
        if (!user) {
          setError('Not authenticated');
          return;
        }

        const token = await user.getIdToken();
        const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
        const fullUrl = `${baseURL}${url}`;

        const response = await fetch(fullUrl, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'text/event-stream',
          },
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        setIsConnected(true);
        setError(null);

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || ''; // Keep incomplete event in buffer

          for (const part of parts) {
            if (!part.trim()) continue;

            let currentEvent = '';
            let currentData = '';

            for (const line of part.split('\n')) {
              if (line.startsWith('event: ')) {
                currentEvent = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                currentData = line.slice(6).trim();
              }
            }

            if (currentEvent && currentData) {
              try {
                const parsedData = JSON.parse(currentData);
                const sseEvent: SSEEvent = { event: currentEvent, data: parsedData };

                onEventRef.current?.(sseEvent);

                if (currentEvent === 'done' || currentEvent === 'complete') {
                  onDoneRef.current?.();
                  setIsConnected(false);
                  return;
                }
                if (currentEvent === 'error') {
                  onErrorRef.current?.(parsedData.message || 'Stream error');
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', currentData, e);
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name === 'AbortError') return;
        console.error('SSE stream error:', err);
        setError(err.message || 'Stream connection failed');
        onErrorRef.current?.(err.message || 'Stream connection failed');
      } finally {
        setIsConnected(false);
      }
    };

    connect();

    return () => {
      controller.abort();
      setIsConnected(false);
    };
  }, [url, enabled]);

  return { isConnected, error, disconnect };
}
