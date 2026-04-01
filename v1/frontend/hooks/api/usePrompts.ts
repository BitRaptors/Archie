import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { promptsService, UpdatePromptPayload } from '@/services/prompts'

const KEYS = {
  list: ['prompts'] as const,
  detail: (id: string) => ['prompts', id] as const,
  revisions: (id: string) => ['prompts', id, 'revisions'] as const,
}

/** Fetch all prompts. */
export function usePrompts() {
  return useQuery({
    queryKey: KEYS.list,
    queryFn: () => promptsService.list(),
    staleTime: 60_000,
  })
}

/** Fetch revisions for a specific prompt. */
export function usePromptRevisions(promptId: string | null) {
  return useQuery({
    queryKey: KEYS.revisions(promptId ?? ''),
    queryFn: () => promptsService.getRevisions(promptId!),
    enabled: !!promptId,
    staleTime: 30_000,
  })
}

/** Update a prompt (creates a revision). */
export function useUpdatePrompt() {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdatePromptPayload }) =>
      promptsService.update(id, data),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: KEYS.list })
      qc.invalidateQueries({ queryKey: KEYS.detail(variables.id) })
      qc.invalidateQueries({ queryKey: KEYS.revisions(variables.id) })
    },
  })
}

/** Revert a prompt to a previous revision. */
export function useRevertPrompt() {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: ({ promptId, revisionId }: { promptId: string; revisionId: string }) =>
      promptsService.revert(promptId, revisionId),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: KEYS.list })
      qc.invalidateQueries({ queryKey: KEYS.detail(variables.promptId) })
      qc.invalidateQueries({ queryKey: KEYS.revisions(variables.promptId) })
    },
  })
}
