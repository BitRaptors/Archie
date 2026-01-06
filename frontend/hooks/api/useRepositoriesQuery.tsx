import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { repositoriesService } from '@/services/repositories'

export function useRepositoriesQuery() {
  const { token } = useAuth()
  
  return useQuery({
    queryKey: ['repositories'],
    queryFn: () => repositoriesService.list(token!),
    enabled: !!token,
  })
}


