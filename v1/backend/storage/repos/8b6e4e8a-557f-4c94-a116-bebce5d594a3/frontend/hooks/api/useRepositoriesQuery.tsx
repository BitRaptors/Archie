import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

export function useAnalyzeRepository() {
  const { token } = useAuth()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async ({ owner, repo, mode = 'full', promptConfig }: { owner: string, repo: string, mode?: string, promptConfig?: Record<string, string> }) => {
      if (!token) throw new Error('No auth token')
      return repositoriesService.analyze(owner, repo, token, mode, promptConfig)
    },
    onSuccess: () => {
      // Refresh analyses and workspace repos
      qc.invalidateQueries({ queryKey: ['workspace', 'repositories'] })
    }
  })
}

export function useLatestCommitSha(owner: string, repo: string, enabled: boolean = true) {
  const { token } = useAuth()

  return useQuery({
    queryKey: ['repositories', owner, repo, 'latest-commit'],
    queryFn: async () => {
      if (!token) return null
      return repositoriesService.getLatestCommitSha(owner, repo, token)
    },
    enabled: !!token && !!owner && !!repo && enabled,
    staleTime: 60 * 1000, // 1 minute
  })
}

