---
id: frontend-principles
title: Guiding Principles
category: frontend
tags: [principles, colocation, composition, hooks]
related: [frontend-structure]
---

# Guiding Principles

## Core Values

| Principle                      | Meaning                                                      |
| ------------------------------ | ------------------------------------------------------------ |
| **Colocation**                 | Keep related code together. Feature code lives with feature. |
| **Composition over Config**    | Build from small, composable pieces.                         |
| **Explicit Dependencies**      | Import what you need. Avoid magic globals.                   |
| **Type Safety**                | TypeScript strict mode. No `any`.                            |
| **Hooks Are The Architecture** | React hooks are the primary abstraction for logic.           |

## Trade-offs Accepted

| We Accept                  | In Exchange For               |
| -------------------------- | ----------------------------- |
| More files                 | Clear organization            |
| Service interfaces         | Swappable backends            |
| Context nesting            | Isolated concerns             |
| Feature folder duplication | Independent feature evolution |

## What This Document Does NOT Cover

- Performance optimization strategies
- Visual design system decisions
- SEO/SSR strategies
- Backend architecture


