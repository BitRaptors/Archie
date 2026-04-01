---
paths:
  - **/*.jsx
  - **/*.tsx
---

## Frontend Architecture

**Framework:** React 19 + Next.js 15 App Router

**Rendering:** Hybrid: SSR for root layout/metadata, CSR ('use client') for all interactive feature components

**Styling:** Tailwind CSS v4 utility classes with CSS custom properties (--surface, --text, --text-secondary, --text-muted, --bg-elevated, --radius-lg) for theming. Dark theme applied at html element level in layout.tsx.

**State management:** React hooks (useState, useEffect, useRef) + sessionStorage for cross-refresh persistence
  - Server state: Direct fetch() calls per component; no caching library (no SWR/React Query)
  - Local state: Each feature component owns its loading/error/data state; root page.tsx owns siteDir/sessionId/provider

**Conventions:**
- All interactive components use 'use client' directive
- CSS variables referenced as bg-[var(--surface)] Tailwind arbitrary values
- sessionStorage key: pinlaunch_session for state persistence
- SSE events parsed with line-split buffer strategy in ClaudeTerminal