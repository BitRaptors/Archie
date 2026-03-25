import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { StoryBasic } from '../../models/story';

// Query key for React Query caching
export const storiesQueryKey = ['stories', 'list'] as const;

/**
 * Hook to fetch all stories in the family
 * Returns empty array if no stories exist
 * Requires user to have a family
 */
export function useStories(): UseQueryResult<StoryBasic[], Error> {
  return useQuery({
    queryKey: storiesQueryKey,
    queryFn: async () => {
      const data = await api.listStories();
      return data || [];
    },
    staleTime: 1000 * 60 * 2, // 2 minutes (stories update more frequently)
  });
}
