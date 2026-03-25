import { useState, useCallback, useRef } from 'react';
import { useSSEStream } from './useSSEStream';
import type { NewCharacterDetection, PhotoAnalysisResult } from '@/models/memory';

interface TextAnalysisResult {
  categories: string[];
  summary: string | null;
  linked_characters: Array<{ id: string; name: string }>;
  new_characters: NewCharacterDetection[];
  suggestions: Array<{
    type: string;
    character_id?: string;
    character_name?: string;
    data: Record<string, any>;
  }>;
}

interface UseMemoryStreamReturn {
  analysisText: string;
  textAnalysis: TextAnalysisResult | null;
  photoResults: PhotoAnalysisResult[];
  isConnected: boolean;
  isComplete: boolean;
  error: string | null;
  statusMessage: string;
  startStream: () => void;
  disconnect: () => void;
}

export function useMemoryStream(memoryId: string | null): UseMemoryStreamReturn {
  const [analysisText, setAnalysisText] = useState('');
  const [textAnalysis, setTextAnalysis] = useState<TextAnalysisResult | null>(null);
  const [photoResults, setPhotoResults] = useState<PhotoAnalysisResult[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [streamEnabled, setStreamEnabled] = useState(false);

  const analysisTextRef = useRef('');

  const handleEvent = useCallback((event: { event: string; data: any }) => {
    switch (event.event) {
      case 'status':
        setStatusMessage(event.data.message || '');
        break;

      case 'analysis_chunk':
        analysisTextRef.current += event.data.token || '';
        setAnalysisText(analysisTextRef.current);
        break;

      case 'text_analysis_complete':
        setTextAnalysis(event.data as TextAnalysisResult);
        break;

      case 'photo_analyzed':
        setPhotoResults(prev => [...prev, event.data as PhotoAnalysisResult]);
        break;

      case 'done':
        setIsComplete(true);
        if (event.data.analysis && !textAnalysis) {
          setTextAnalysis(event.data.analysis as TextAnalysisResult);
        }
        break;

      case 'error':
        break;
    }
  }, [textAnalysis]);

  const handleDone = useCallback(() => {
    setIsComplete(true);
  }, []);

  const { isConnected, error, disconnect: sseDisconnect } = useSSEStream({
    url: memoryId ? `/memories/${memoryId}/stream` : '',
    enabled: streamEnabled && !!memoryId,
    onEvent: handleEvent,
    onDone: handleDone,
  });

  const startStream = useCallback(() => {
    setAnalysisText('');
    analysisTextRef.current = '';
    setTextAnalysis(null);
    setPhotoResults([]);
    setIsComplete(false);
    setStatusMessage('');
    setStreamEnabled(true);
  }, []);

  const disconnect = useCallback(() => {
    setStreamEnabled(false);
    sseDisconnect();
  }, [sseDisconnect]);

  return {
    analysisText,
    textAnalysis,
    photoResults,
    isConnected,
    isComplete,
    error,
    statusMessage,
    startStream,
    disconnect,
  };
}
