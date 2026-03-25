import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceService } from '@/services/workspace'

const KEYS = {
  repositories: ['workspace', 'repositories'] as const,
  active: ['workspace', 'active'] as const,
  agentFiles: (repoId: string) => ['workspace', 'agent-files', repoId] as const,
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

/** Clear the active repository. */
export function useClearActiveRepository() {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: () => workspaceService.clearActive(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.active })
    },
  })
}

/** Fetch agent files for a specific repo (only when requested). */
export function useAgentFiles(repoId: string | null) {
  return useQuery({
    queryKey: KEYS.agentFiles(repoId ?? ''),
    queryFn: () => workspaceService.getAgentFiles(repoId!),
    enabled: !!repoId,
    staleTime: 60_000, // 1 min
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
