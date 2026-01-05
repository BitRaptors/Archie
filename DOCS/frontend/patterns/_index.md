---
id: frontend-patterns-overview
title: Core Patterns
category: frontend
tags: [patterns, react, hooks, context]
related: [frontend-structure]
---

# Core Patterns

## Available Patterns

1. [Context + Consumer Hook](./context-hook.md) - Primary pattern for global state
2. [Query Hooks](./query-hooks.md) - TanStack Query for server state
3. [Query Key Factories](./query-keys.md) - Hierarchical keys for cache management
4. [Mutation Hooks](./mutations.md) - Mutations with optimistic updates
5. [SSE Hook](./sse-hook.md) - Server-Sent Events for streaming
6. [Component with CVA Variants](./cva-components.md) - Styled components with variants

## Pattern Summary

| Pattern           | Purpose             | Location               |
| ----------------- | ------------------- | ---------------------- |
| Context + Hook    | Global state        | `context/` + `hooks/`  |
| Query Hook        | Server state        | `hooks/api/`           |
| Query Keys        | Cache management    | `utils/queryKeys.ts`   |
| Service Interface | Backend abstraction | `types/` + `services/` |
| CVA Components    | Styled variants     | `components/atoms/`    |
| Storybook Stories | Documentation       | `*.stories.tsx`        |


