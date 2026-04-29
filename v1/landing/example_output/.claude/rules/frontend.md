---
paths:
  - **/*.jsx
  - **/*.tsx
---

## Frontend Architecture

**Framework:** Next.js 16.1.6 (dashboard: pages router; landing: app router)

**Rendering:** Dashboard: CSR with Next.js pages router; Landing: SSG with app router

**Styling:** Tailwind CSS utility classes + shadcn/ui primitives in frontend/components/ui/; cn() helper from frontend/lib/utils.ts for conditional class merging

**State management:** React Context for auth + custom hooks for server state + useState for local UI state
  - Server state: Custom hooks in frontend/hooks/api/ wrap frontend/services/*.ts (Axios); likely React Query for caching in useRepositoriesQuery
  - Local state: useState in view components for modals, form inputs, selected items

**Conventions:**
- All components are functional with hooks — no class components
- Service layer (frontend/services/) handles all HTTP; hooks consume services
- View components in frontend/components/views/ are page-level containers
- UI primitives in frontend/components/ui/ are never modified directly (shadcn pattern)
- Auth token injected via useAuth() hook from frontend/context/auth.tsx