import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { Character } from '../../models/character';

// Query key for React Query caching
export const charactersQueryKey = ['characters', 'list'] as const;

/**
 * Hook to fetch all characters in the family
 * Returns empty array if no characters exist
 * Requires user to have a family
 */
export function useCharacters(): UseQueryResult<Character[], Error> {
  return useQuery({
    queryKey: charactersQueryKey,
    queryFn: async () => {
      const data = await api.fetchCharacters();
      return data || [];
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}
