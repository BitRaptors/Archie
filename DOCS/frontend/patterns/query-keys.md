---
id: frontend-pattern-query-keys
title: Query Key Factories
category: frontend
tags: [pattern, tanstack-query, cache, query-keys]
related: [frontend-patterns-overview, frontend-pattern-query-hooks]
---

# Pattern 3: Query Key Factories

Hierarchical keys for cache management.

```typescript
// utils/queryKeys.ts
export const appKeys = {
  all: ['apps'] as const,

  configs: () => [...appKeys.all, 'config'] as const,
  config: ({ id, draft }: { id: string; draft: boolean }) =>
    [...appKeys.configs(), id, draft] as const,

  details: () => [...appKeys.all, 'detail'] as const,
  detail: ({ id }: { id: string }) => [...appKeys.details(), id] as const,
}

export const userKeys = {
  all: ['user'] as const,
  content: () => [...userKeys.all, 'content'] as const,
  serviceCredentials: () => [...userKeys.all, 'serviceCredentials'] as const,
}

export const editorKeys = {
  all: ['editor'] as const,
  appConfigs: () => [...editorKeys.all, 'appConfig'] as const,
  appConfig: ({ id }: { id: string }) =>
    [...editorKeys.appConfigs(), id] as const,
}
```

**Why this pattern:**

- Granular cache invalidation
- Type-safe key generation
- Predictable cache structure


