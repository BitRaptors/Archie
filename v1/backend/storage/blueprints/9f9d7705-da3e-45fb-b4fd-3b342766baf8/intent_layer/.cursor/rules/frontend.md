---
description: Frontend architecture rules
globs: ["**/*.jsx", "**/*.tsx"]
alwaysApply: false
---

## Frontend Architecture

**Framework:** React 18.x (web) + React Native/Expo (mobile)

**Rendering:** CSR (web SPA via Vite) + Native compilation (mobile via Expo)

**Styling:** Tailwind CSS utility-first + Radix UI unstyled primitives + shadcn/ui component patterns (CVA variants, clsx merging) — web only; mobile uses React Native native styles

**State management:** React Context for auth; TanStack Query for server state; local useState for form/UI state
  - Server state: TanStack Query @tanstack/react-query v5 for mobile; direct axios calls + useState for web
  - Local state: React useState/useReducer in page components for forms and UI state

**Conventions:**
- Web UI components in components/ui/ follow shadcn/ui pattern with class-variance-authority
- All page components go in src/pages/{Domain}Page.tsx
- SSE hooks composed from useSSEStream.ts base with domain-specific wrappers
- Mobile routes defined by file structure under app/ following Expo Router conventions
- Auth token injected automatically by api/client.ts; never manually add Authorization headers