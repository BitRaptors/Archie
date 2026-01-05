---
id: frontend-pattern-mutations
title: Mutation Hooks with Optimistic Updates
category: frontend
tags: [pattern, tanstack-query, mutations, optimistic-updates]
related: [frontend-patterns-overview, frontend-pattern-query-hooks]
---

# Pattern 4: Mutation Hooks with Optimistic Updates

```typescript
// hooks/api/useUpdateAppMutation.tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { appKeys } from '@/utils/queryKeys'
import { useAuth } from '../useAuth'
import type { AppDTO } from '@/types'

export const useUpdateAppMutation = () => {
  const { getIdToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: { id: string; updates: Partial<AppDTO> }) => {
      const res = await fetch(`${API_BASE_URL}/v1/apps/${data.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await getIdToken()}`,
        },
        body: JSON.stringify(data.updates),
      })
      if (!res.ok) throw new Error('Failed to update app')
      return res.json()
    },

    // Optimistic update
    onMutate: async (data) => {
      await queryClient.cancelQueries({
        queryKey: appKeys.detail({ id: data.id }),
      })
      const previous = queryClient.getQueryData(appKeys.detail({ id: data.id }))

      queryClient.setQueryData(
        appKeys.detail({ id: data.id }),
        (old: AppDTO) => ({
          ...old,
          ...data.updates,
        }),
      )

      return { previous }
    },

    onError: (_err, data, context) => {
      // Rollback on error
      queryClient.setQueryData(
        appKeys.detail({ id: data.id }),
        context?.previous,
      )
    },

    onSettled: (_data, _error, variables) => {
      // Refetch to ensure sync
      queryClient.invalidateQueries({
        queryKey: appKeys.detail({ id: variables.id }),
      })
    },
  })
}
```


