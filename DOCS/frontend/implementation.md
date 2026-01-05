---
id: frontend-implementation
title: Implementation Guide
category: frontend
tags: [implementation, nextjs, typescript, setup]
related: [frontend-structure, frontend-patterns-overview]
---

# Implementation Guide

## Technology Stack

| Category               | Technology                      | Purpose                 |
| ---------------------- | ------------------------------- | ----------------------- |
| **Framework**          | Next.js 14+ (Pages Router)      | React framework         |
| **Language**           | TypeScript 5+ (strict)          | Type safety             |
| **Server State**       | TanStack Query v5               | Caching, mutations      |
| **Client State**       | React Context                   | Global state            |
| **Styling**            | Tailwind CSS + shadcn/ui        | Component library       |
| **Component Variants** | class-variance-authority (CVA)  | Type-safe variants      |
| **Forms**              | React Hook Form + Zod           | Form handling           |
| **Docs**               | Storybook                       | Component documentation |
| **Backend**            | Firebase / Supabase (swappable) | Auth, DB, Storage       |

## Project Setup

See the original blueprint document for complete setup instructions, directory structure, and code templates.

## Quick Reference

```
components/atoms/     → shadcn/ui primitives
components/molecules/ → composed components
components/[feature]/ → feature UI
hooks/api/            → TanStack Query hooks
hooks/[domain]/       → domain-specific hooks
context/              → React Context providers
services/             → external integrations
types/                → TypeScript definitions
utils/                → utilities + query keys
```

## Remember

- **Hooks are the architecture** — not layers
- **Colocation over separation** — feature code stays together
- **Context for global, Query for server** — different tools for different state
- **Services for abstraction** — swap backends without touching UI
- **Stories for documentation** — living docs next to code


