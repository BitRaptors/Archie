---
id: frontend-structure
title: Project Structure
category: frontend
tags: [structure, organization, directories]
related: [frontend-principles]
---

# Project Structure

## Overview

```
src/
├── pages/                    # Next.js Pages Router
├── components/               # UI Components
├── hooks/                    # Custom Hooks
├── context/                  # React Context Providers
├── services/                 # External Service Implementations
├── types/                    # TypeScript Types
├── utils/                    # Utility Functions
├── config/                   # App Configuration
└── styles/                   # Global Styles
```

## Directory Breakdown

### `pages/` — Route Definitions

```
pages/
├── _app.tsx                  # App wrapper with providers
├── _document.tsx             # HTML document
├── index.tsx                 # Home page
├── api/                      # API routes (if any)
├── [slug]/                   # Dynamic routes
│   ├── index.tsx
│   └── editor.tsx
└── admin/
    └── index.tsx
```

**Conventions:**

- Pages are thin — they compose components
- Complex pages get their own folder: `pages/admin/`
- Page-specific logic lives in hooks, not in pages

### `components/` — UI Components

```
components/
├── atoms/                    # Base UI (shadcn/ui)
│   ├── button.tsx
│   ├── button.stories.tsx    # Storybook story
│   ├── input.tsx
│   └── ...
│
├── molecules/                # Composed primitives
│   ├── Loading.tsx
│   ├── Loading.stories.tsx
│   └── FileUpload.tsx
│
├── layout/                   # App shell
│   ├── Layout.tsx
│   ├── Sidebar.tsx
│   ├── Sidebar.stories.tsx
│   └── navbars/
│
└── [feature]/                # Feature-specific components
    ├── detail/               # App detail feature
    │   ├── AppDetailHeader.tsx
    │   ├── AppDetailTabs.tsx
    │   ├── components/       # Sub-components
    │   └── sections/
    │
    ├── editor/               # Editor feature
    │   ├── Editor.tsx
    │   ├── EditorSidebar/
    │   │   ├── EditorSidebar.tsx
    │   │   ├── EditorSidebar.stories.tsx
    │   │   └── index.ts
    │   └── elements/
    │
    └── settings/
        └── SettingsPage.tsx
```

**Conventions:**

- `atoms/` = shadcn/ui components (primitives)
- `molecules/` = composed primitives (Loading, FileUpload)
- `layout/` = app shell components
- Feature folders = domain-specific UI
- Stories live next to components: `Button.tsx` + `Button.stories.tsx`

### `hooks/` — Custom Hooks

```
hooks/
├── api/                      # Server state (queries/mutations)
│   ├── useAppConfigQuery.tsx
│   ├── useAppQuery.tsx
│   ├── useCreateAppMutation.tsx
│   └── admin/                # Admin-specific API hooks
│
├── apps/                     # App-specific business logic
│   ├── useAction.tsx
│   ├── useAppInputs.tsx
│   └── useAppUIState.tsx
│
├── db/                       # Database/Firestore hooks
│   ├── useFeaturesConfig.tsx
│   └── useDBAppConfigQuery.tsx
│
└── [generic hooks]           # Reusable utility hooks
    ├── useAuth.tsx           # Auth context consumer
    ├── useBalance.tsx
    ├── useConfig.tsx
    ├── useScrollPosition.tsx
    ├── useAutoResizeTextArea.tsx
    └── ...
```

**Conventions:**

- `api/` = TanStack Query hooks (server state)
- Feature folders for domain-specific hooks
- Root level for generic, reusable hooks
- Consumer hooks for contexts: `useAuth.tsx` wraps `AuthContext`

### `context/` — Global State

```
context/
├── auth.tsx                  # Authentication state
├── balance.tsx               # User balance/credits
├── config.tsx                # App configuration
├── translations.tsx          # i18n
├── analytics.tsx             # Analytics context
├── queryClient.ts            # TanStack Query setup
└── [feature]/                # Feature-specific contexts
    ├── editorContext.tsx
    └── appContext.tsx
```

**Conventions:**

- Each context = one concern
- Export both `Provider` and consumer hook
- Context file includes all related logic

### `services/` — External Integrations

```
services/
├── auth.ts                   # Firebase Auth operations
├── balance.ts                # Balance streaming
├── storage.ts                # File storage
├── apps.ts                   # App-related API calls
└── cms/
    └── translations.ts
```

**Conventions:**

- Services are plain functions, not classes
- Each file = one external system
- Services handle data transformation

### `types/` — Type Definitions

```
types/
└── index.ts                  # All types in one file (or split by domain)
```

**Conventions:**

- Centralized types for shared definitions
- Export interfaces for external contracts
- Use discriminated unions for variants

### `utils/` — Utilities

```
utils/
├── queryKeys.ts              # TanStack Query key factories
├── cn.ts                     # Class name utility
├── format.ts                 # Formatters
├── analytics.ts              # Analytics event names
└── [domain].ts               # Domain-specific utilities
```


