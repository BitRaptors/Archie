import { useState, useCallback, useRef } from 'react';
import { useSSEStream } from './useSSEStream';
import type { DebugPromptEntry } from '@/models/story';

export interface StoryPage {
  page: number;
  description?: string;
  text: string;
  imageUrl?: string;
  charactersOnPage?: string[];
  imagePrompt?: string;
  debugPrompts?: Record<string, DebugPromptEntry>;
  avatarUrls?: Record<string, string>;
}

export interface StoryStreamState {
  status: string;
  statusMessage: string;
  pages: StoryPage[];
  outlineDebug?: DebugPromptEntry | null;
  outlineRawResponse?: string | null;
  isComplete: boolean;
  isFailed: boolean;
  error: string | null;
}

export function useStoryStream(storyId: string | undefined) {
  const [state, setState] = useState<StoryStreamState>({
    status: 'connecting',
    statusMessage: 'Connecting to story stream...',
    pages: [],
    outlineDebug: null,
    outlineRawResponse: null,
    isComplete: false,
    isFailed: false,
    error: null,
  });

  const pagesRef = useRef<StoryPage[]>([]);

  const handleEvent = useCallback((event: { event: string; data: any }) => {
    const { event: eventType, data } = event;

    switch (eventType) {
      case 'status':
        setState(prev => ({
          ...prev,
          status: data.step || prev.status,
          statusMessage: data.message || prev.statusMessage,
        }));
        break;

      case 'outline': {
        if (data.outline_pages) {
          const outlinePages: StoryPage[] = data.outline_pages.map((p: any) => ({
            page: p.page,
            description: p.description,
            text: '',
          }));
          pagesRef.current = outlinePages;
          setState(prev => ({
            ...prev,
            pages: [...outlinePages],
            outlineDebug: data.debug_prompts || null,
            outlineRawResponse: data.raw_response || null,
            statusMessage: `Outline ready (${data.total_pages} pages)`,
          }));
        }
        break;
      }

      case 'page_start': {
        // Reset page text if retrying (page already has text from previous attempt)
        const startPageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (startPageIdx >= 0 && pagesRef.current[startPageIdx].text) {
          pagesRef.current[startPageIdx] = {
            ...pagesRef.current[startPageIdx],
            text: '',
          };
        }
        setState(prev => ({
          ...prev,
          pages: [...pagesRef.current],
          statusMessage: `Writing page ${data.page}...`,
        }));
        break;
      }

      case 'page_retry':
        setState(prev => ({
          ...prev,
          statusMessage: `Revising page ${data.page} (attempt ${data.retry + 1})...`,
        }));
        break;

      case 'consistency_result': {
        const crPageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (crPageIdx >= 0 && data.debug_prompts) {
          const debugKey = data.debug_key || `consistency_check_${data.attempt || 1}`;
          pagesRef.current[crPageIdx] = {
            ...pagesRef.current[crPageIdx],
            debugPrompts: {
              ...pagesRef.current[crPageIdx].debugPrompts,
              [debugKey]: data.debug_prompts,
            },
          };
          setState(prev => ({
            ...prev,
            pages: [...pagesRef.current],
            statusMessage: data.passed
              ? `Page ${data.page} consistency check passed.`
              : `Page ${data.page} has issues, revising...`,
          }));
        }
        break;
      }

      case 'text_chunk': {
        const pageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (pageIdx >= 0) {
          pagesRef.current[pageIdx] = {
            ...pagesRef.current[pageIdx],
            text: pagesRef.current[pageIdx].text + data.chunk,
          };
          setState(prev => ({
            ...prev,
            pages: [...pagesRef.current],
          }));
        }
        break;
      }

      case 'page_text': {
        const pageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (pageIdx >= 0) {
          pagesRef.current[pageIdx] = {
            ...pagesRef.current[pageIdx],
            text: data.text,
            charactersOnPage: data.characters_on_page,
            debugPrompts: {
              ...pagesRef.current[pageIdx].debugPrompts,
              ...(data.debug_prompts ? { page_text: data.debug_prompts } : {}),
            },
          };
          setState(prev => ({
            ...prev,
            pages: [...pagesRef.current],
          }));
        }
        break;
      }

      case 'image_prompt': {
        const pageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (pageIdx >= 0) {
          pagesRef.current[pageIdx] = {
            ...pagesRef.current[pageIdx],
            imagePrompt: data.prompt,
            charactersOnPage: data.characters_on_page,
            avatarUrls: data.avatar_urls || undefined,
            debugPrompts: {
              ...pagesRef.current[pageIdx].debugPrompts,
              ...(data.debug_prompts ? { image_prompt: data.debug_prompts } : {}),
            },
          };
          setState(prev => ({
            ...prev,
            pages: [...pagesRef.current],
            statusMessage: `Image prompt for page ${data.page} ready`,
          }));
        }
        break;
      }

      case 'page_image': {
        const pageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (pageIdx >= 0) {
          pagesRef.current[pageIdx] = {
            ...pagesRef.current[pageIdx],
            imageUrl: data.image_url,
          };
          setState(prev => ({
            ...prev,
            pages: [...pagesRef.current],
            statusMessage: `Page ${data.page} image ready`,
          }));
        }
        break;
      }

      case 'done':
        setState(prev => ({
          ...prev,
          isComplete: true,
          status: 'completed',
          statusMessage: 'Story generation complete!',
        }));
        break;

      case 'error':
        setState(prev => ({
          ...prev,
          isFailed: true,
          error: data.message || 'Generation failed',
          statusMessage: data.message || 'Generation failed',
        }));
        break;
    }
  }, []);

  const handleDone = useCallback(() => {
    setState(prev => ({ ...prev, isComplete: true }));
  }, []);

  const handleError = useCallback((msg: string) => {
    setState(prev => ({ ...prev, error: msg, isFailed: true }));
  }, []);

  const { isConnected } = useSSEStream({
    url: storyId ? `/stories/${storyId}/stream` : '',
    enabled: !!storyId,
    onEvent: handleEvent,
    onDone: handleDone,
    onError: handleError,
  });

  return {
    ...state,
    isConnected,
  };
}
