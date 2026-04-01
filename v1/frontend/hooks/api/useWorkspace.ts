import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceService } from '@/services/workspace'

const KEYS = {
  repositories: ['workspace', 'repositories'] as const,
  active: ['workspace', 'active'] as const,
}

/** Fetch all analyzed repositories. */
export function useWorkspaceRepositories() {
  return useQuery({
    queryKey: KEYS.repositories,
    queryFn: () => workspaceService.listRepositories(),
    staleTime: 30_000, // 30 s
  })
}

/** Fetch the currently active repository. */
export function useActiveRepository() {
  return useQuery({
    queryKey: KEYS.active,
    queryFn: () => workspaceService.getActive(),
    staleTime: 10_000, // 10 s
  })
}

/** Set the active repository (optimistic). */
export function useSetActiveRepository() {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: (repoId: string) => workspaceService.setActive(repoId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.active })
    },
  })
}

/** Delete a repository analysis. */
export function useDeleteRepository() {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: (repoId: string) => workspaceService.deleteRepository(repoId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.repositories })
      qc.invalidateQueries({ queryKey: KEYS.active })
    },
  })
}
