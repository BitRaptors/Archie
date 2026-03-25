## Development Rules

### Code Style

- Always export HTTP verb functions (GET, POST, PUT, DELETE) from route.ts files; never use default exports for API routes *(source: `src/app/api/pins/route.ts, src/app/api/settings/route.ts — named export pattern`)*
- Always add 'use client' directive to components using useState/useEffect; omit for server-only layout/page files *(source: `src/components/GeneratePanel.tsx, ClaudeTerminal.tsx — all interactive components are client components`)*

### Dependency Management

- Always use npm; no yarn or pnpm — project uses package-lock.json exclusively *(source: `package-lock.json lockfileVersion 3 present; no yarn.lock or pnpm-lock.yaml`)*

### Environment

- Always initialize SQLite with WAL pragma via getDb() singleton; never create direct Database instances in route files *(source: `src/lib/db.ts — db.pragma('journal_mode = WAL') + singleton pattern`)*

### Testing

- Always mirror ClaudeTerminal.tsx SSE event handler logic in src/lib/stream-parsing.test.ts when adding new event types *(source: `src/lib/stream-parsing.test.ts — duplicates handleEvent, handleToolUse, TOOL_ICONS from ClaudeTerminal`)*
- Always run tests with vitest run (not vitest watch) for non-interactive CI execution *(source: `package.json — 'test': 'vitest run'`)*