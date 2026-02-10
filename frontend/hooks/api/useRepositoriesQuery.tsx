import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { repositoriesService } from '@/services/repositories'

export function useRepositoriesQuery() {
  const { token } = useAuth()
  
  return useQuery({
    queryKey: ['repositories'],
    queryFn: () => repositoriesService.list(token!),
    enabled: !!token,
    retry: (failureCount, error: any) => {
      // Don't retry on 401 (unauthorized) - token is invalid
      if (error?.response?.status === 401) {
        return false
      }
      // Retry up to 2 times for other errors
      return failureCount < 2
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}


