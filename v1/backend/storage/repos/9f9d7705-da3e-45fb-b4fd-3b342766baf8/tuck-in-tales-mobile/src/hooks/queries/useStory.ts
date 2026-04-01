import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { Story } from '../../models/story';

export const storyQueryKey = (id: string) => ['stories', 'detail', id] as const;

export function useStory(storyId: string): UseQueryResult<Story, Error> {
  return useQuery({
    queryKey: storyQueryKey(storyId),
    queryFn: () => api.fetchStory(storyId),
    enabled: !!storyId,
    staleTime: 1000 * 60 * 2,
  });
}
