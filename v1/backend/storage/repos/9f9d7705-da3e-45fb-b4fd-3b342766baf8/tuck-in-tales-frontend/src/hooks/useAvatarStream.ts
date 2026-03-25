import { useState, useCallback } from 'react';
import { useSSEStream } from './useSSEStream';

interface AvatarStreamState {
  status: string;
  statusMessage: string;
  avatarUrl: string | null;
  visualDescription: string | null;
  imagePrompt: string | null;
  isComplete: boolean;
  error: string | null;
}

export function useAvatarStream(characterId: string | undefined, enabled: boolean = false) {
  const [state, setState] = useState<AvatarStreamState>({
    status: 'idle',
    statusMessage: '',
    avatarUrl: null,
    visualDescription: null,
    imagePrompt: null,
    isComplete: false,
    error: null,
  });

  const handleEvent = useCallback((event: { event: string; data: any }) => {
    const { event: eventType, data } = event;
    switch (eventType) {
      case 'status':
        setState(prev => {
          const update: Partial<AvatarStreamState> = {
            status: data.step || prev.status,
            statusMessage: data.message || prev.statusMessage,
          };
          if (data.visual_description) update.visualDescription = data.visual_description;
          if (data.image_prompt) update.imagePrompt = data.image_prompt;
          return { ...prev, ...update };
        });
        break;
      case 'complete':
        setState(prev => ({
          ...prev,
          isComplete: true,
          avatarUrl: data.avatar_url || null,
          statusMessage: 'Avatar generation complete!',
        }));
        break;
      case 'error':
        setState(prev => ({
          ...prev,
          error: data.message || 'Avatar generation failed',
          statusMessage: data.message || 'Failed',
        }));
        break;
    }
  }, []);

  const { isConnected } = useSSEStream({
    url: characterId ? `/characters/${characterId}/avatar/stream` : '',
    enabled: enabled && !!characterId,
    onEvent: handleEvent,
  });

  return { ...state, isConnected };
}
