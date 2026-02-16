import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { repositoriesService } from '@/services/repositories'


export interface Repository {
  id: string
  name: string
  full_name: string
  owner: string
  description?: string
  language?: string
  default_branch?: string
  [key: string]: any
}

export function useRepositoriesQuery() {
  const { token } = useAuth()

  return useQuery<Repository[]>({
    queryKey: ['repositories'],
    queryFn: async () => {
      if (!token) return []
      return repositoriesService.list(token)
    },
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

