---
description: Architecture rules: components, file placement, naming conventions
alwaysApply: true
---

## Components

### API Route Handlers
- **Location:** `src/app/api/`
- **Responsibility:** Handle HTTP requests, parse bodies, call service layer, return responses
- **Depends on:** Application Service Layer, Infrastructure Layer

### Application Service Layer
- **Location:** `src/lib/`
- **Responsibility:** Orchestrate AI generation, GitHub fetching, prompt construction
- **Depends on:** Infrastructure Layer, External AI APIs, GitHub API

### Infrastructure Layer
- **Location:** `src/lib/db.ts`
- **Responsibility:** SQLite singleton, schema init, preset seeding
- **Depends on:** better-sqlite3

### Feature Components
- **Location:** `src/components/`
- **Responsibility:** Stateful feature containers managing distinct UI domains
- **Depends on:** API Route Handlers via fetch

### Pages/Views Layer
- **Location:** `src/app/`
- **Responsibility:** Root layout, metadata, global styles, main page composition
- **Depends on:** Feature Components

## File Placement

| Component Type | Location | Naming | Example |
|---------------|----------|--------|---------|
| API route handler | `src/app/api/[feature]/` | `route.ts` | `src/app/api/pins/route.ts` |
| Dynamic API route | `src/app/api/[feature]/[id]/` | `route.ts inside [param] or [...param]` | `src/app/api/pins/[id]/route.ts` |
| React component | `src/components/` | `PascalCase.tsx` | `src/components/GeneratePanel.tsx` |
| Business logic / service | `src/lib/` | `camelCase.ts` | `src/lib/generate.ts` |
| Unit/integration test | `src/lib/` | `*.test.ts` | `src/lib/generate.test.ts` |
| Next.js page | `src/app/` | `page.tsx or layout.tsx` | `src/app/page.tsx` |

## Where to Put Code

- **new_api_endpoint** -> `src/app/api/[feature]/route.ts`
- **new_react_component** -> `src/components/[Name].tsx`
- **shared_business_logic** -> `src/lib/[module].ts`
- **database_schema_change** -> `src/lib/db.ts getDb() initialization block`
- **prompt_templates** -> `src/lib/prompts.json`
- **unit_tests** -> `src/lib/[module].test.ts`

## Naming Conventions

- **API route files**: route.ts (fixed filename) (e.g. `src/app/api/health/route.ts`, `src/app/api/generate/stream/route.ts`)
- **React components**: PascalCase with feature suffix (e.g. `GeneratePanel.tsx`, `RefinementChat.tsx`, `PinBoard.tsx`)
- **Library functions**: camelCase verb+noun (e.g. `streamClaudeGeneration`, `getRepoContent`, `getDb`)
- **Test files**: [module].test.ts or [module].integration.test.ts (e.g. `generate.test.ts`, `generate.integration.test.ts`, `stream-parsing.test.ts`)