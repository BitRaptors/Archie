import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { FamilyDetailResponse } from '../../models/family';

// Query key for React Query caching
export const familyQueryKey = ['family', 'details'] as const;

/**
 * Hook to fetch the current user's family details
 * Returns family info including members and main characters
 * Handles 404 when user has no family (returns null data)
 */
export function useFamilyDetails(): UseQueryResult<FamilyDetailResponse | null, Error> {
  return useQuery({
    queryKey: familyQueryKey,
    queryFn: async () => {
      try {
        const data = await api.fetchFamilyDetails();
        return data;
      } catch (error: any) {
        // If user has no family, return null instead of throwing
        if (error?.response?.status === 404) {
          return null;
        }
        throw error;
      }
    },
    // Retry only on server errors, not on 404
    retry: (failureCount, error: any) => {
      if (error?.response?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}
