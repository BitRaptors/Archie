---
id: frontend-pattern-query-hooks
title: Query Hooks (Server State)
category: frontend
tags: [pattern, tanstack-query, hooks, server-state]
related: [frontend-patterns-overview, frontend-pattern-query-keys]
---

# Pattern 2: Query Hooks (Server State)

Using TanStack Query for all server data.

```typescript
// hooks/api/useAppConfigQuery.tsx
import { useQuery } from '@tanstack/react-query'
import { appKeys } from '@/utils/queryKeys'
import { useAuth } from '../useAuth'
import type { AppConfigDTO } from '@/types'
import { API_BASE_URL } from '@/config/env'

export const useAppConfigQuery = ({
  appId,
  draft,
}: {
  appId: string
  draft: boolean
}) => {
  const { getIdToken } = useAuth()

  return useQuery({
    queryKey: appKeys.config({ id: appId, draft }),
    queryFn: async (): Promise<AppConfigDTO> => {
      const res = await fetch(
        `${API_BASE_URL}/v1/apps/${appId}/config${draft ? '/?draft=true' : ''}`,
        {
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            Authorization: `Bearer ${await getIdToken()}`,
          },
        },
      )
      if (!res.ok) throw new Error(`Error getting config for app:${appId}`)
      return (await res.json()).data as AppConfigDTO
    },
    enabled: Boolean(appId),
    retry: false,
    gcTime: 0,
    refetchOnWindowFocus: false,
  })
}
```


