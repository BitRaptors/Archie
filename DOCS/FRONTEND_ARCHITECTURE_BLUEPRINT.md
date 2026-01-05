# Frontend Architecture Blueprint

## Purpose

This document defines the **architectural patterns and conventions** for building maintainable React applications. It reflects real-world React idioms rather than backend-derived concepts.

The document is structured in two parts:

1. **Architecture** (Sections 1-5): Core patterns and conventions
2. **Implementation Guide** (Section 6): Complete project setup with code templates

---

## Table of Contents

### Part 1: Architecture

1. [Guiding Principles](#guiding-principles)
2. [Project Structure](#project-structure)
3. [Core Patterns](#core-patterns)
4. [Service Abstraction](#service-abstraction)
5. [Cross-Cutting Concerns](#cross-cutting-concerns)

### Part 2: Implementation

6. [Implementation Guide](#implementation-guide) — Complete setup with templates

---

## Guiding Principles

### Core Values

| Principle                      | Meaning                                                      |
| ------------------------------ | ------------------------------------------------------------ |
| **Colocation**                 | Keep related code together. Feature code lives with feature. |
| **Composition over Config**    | Build from small, composable pieces.                         |
| **Explicit Dependencies**      | Import what you need. Avoid magic globals.                   |
| **Type Safety**                | TypeScript strict mode. No `any`.                            |
| **Hooks Are The Architecture** | React hooks are the primary abstraction for logic.           |

### Trade-offs Accepted

| We Accept                  | In Exchange For               |
| -------------------------- | ----------------------------- |
| More files                 | Clear organization            |
| Service interfaces         | Swappable backends            |
| Context nesting            | Isolated concerns             |
| Feature folder duplication | Independent feature evolution |

### What This Document Does NOT Cover

- Performance optimization strategies
- Visual design system decisions
- SEO/SSR strategies
- Backend architecture

---

## Project Structure

### Overview

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

### Directory Breakdown

#### `pages/` — Route Definitions

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

#### `components/` — UI Components

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

#### `hooks/` — Custom Hooks

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

#### `context/` — Global State

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

#### `services/` — External Integrations

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

#### `types/` — Type Definitions

```
types/
└── index.ts                  # All types in one file (or split by domain)
```

**Conventions:**

- Centralized types for shared definitions
- Export interfaces for external contracts
- Use discriminated unions for variants

#### `utils/` — Utilities

```
utils/
├── queryKeys.ts              # TanStack Query key factories
├── cn.ts                     # Class name utility
├── format.ts                 # Formatters
├── analytics.ts              # Analytics event names
└── [domain].ts               # Domain-specific utilities
```

---

## Core Patterns

### Pattern 1: Context + Consumer Hook

The primary pattern for global state.

```typescript
// context/auth.tsx
import { createContext, useContext, useState, useEffect, FC, PropsWithChildren, useCallback } from 'react'
import { streamUser } from '@/services/auth'
import type { User } from '@/types'

// 1. Define context shape
type AuthContextValue = {
  user: User | null
  isLoading: boolean
  isAdmin: boolean
  getIdToken: () => Promise<string>
}

// 2. Create context with defaults
const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoading: true,
  isAdmin: false,
  getIdToken: async () => '',
})

// 3. Provider component with all logic
export const AuthContextProvider: FC<PropsWithChildren> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [idToken, setIdToken] = useState<string>()
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    // Subscribe to auth state changes
    const unsubscribe = auth.onAuthStateChanged(async (firebaseUser) => {
      if (firebaseUser) {
        const token = await firebaseUser.getIdToken()
        setIdToken(token)

        // Stream user data from Firestore
        const unsubUser = streamUser(firebaseUser.uid, setUser)
        return () => unsubUser()
      } else {
        setUser(null)
      }
      setIsLoading(false)
    })
    return unsubscribe
  }, [])

  const getIdToken = useCallback(async () => idToken || '', [idToken])

  return (
    <AuthContext.Provider value={{ user, isLoading, isAdmin, getIdToken }}>
      {children}
    </AuthContext.Provider>
  )
}

// 4. Consumer hook (in hooks/useAuth.tsx or same file)
export const useAuth = () => useContext(AuthContext)
```

**Usage:**

```typescript
// In any component
const { user, isLoading, getIdToken } = useAuth()
```

### Pattern 2: Query Hooks (Server State)

Using TanStack Query for all server data.

```typescript
// hooks/api/useAppConfigQuery.tsx
import { useQuery } from '@tanstack/react-query'
import { appKeys } from '@/utils/queryKeys'
import { useAuth } from '../useAuth'
import type { AppConfigDTO } from '@/types'
import { API_BASE_URL } from '@/config/env'

export const useAppConfigQuery = ({
  appId,
  draft,
}: {
  appId: string
  draft: boolean
}) => {
  const { getIdToken } = useAuth()

  return useQuery({
    queryKey: appKeys.config({ id: appId, draft }),
    queryFn: async (): Promise<AppConfigDTO> => {
      const res = await fetch(
        `${API_BASE_URL}/v1/apps/${appId}/config${draft ? '/?draft=true' : ''}`,
        {
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            Authorization: `Bearer ${await getIdToken()}`,
          },
        },
      )
      if (!res.ok) throw new Error(`Error getting config for app:${appId}`)
      return (await res.json()).data as AppConfigDTO
    },
    enabled: Boolean(appId),
    retry: false,
    gcTime: 0,
    refetchOnWindowFocus: false,
  })
}
```

### Pattern 3: Query Key Factories

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

### Pattern 4: Mutation Hooks with Optimistic Updates

```typescript
// hooks/api/useUpdateAppMutation.tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { appKeys } from '@/utils/queryKeys'
import { useAuth } from '../useAuth'
import type { AppDTO } from '@/types'

export const useUpdateAppMutation = () => {
  const { getIdToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: { id: string; updates: Partial<AppDTO> }) => {
      const res = await fetch(`${API_BASE_URL}/v1/apps/${data.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await getIdToken()}`,
        },
        body: JSON.stringify(data.updates),
      })
      if (!res.ok) throw new Error('Failed to update app')
      return res.json()
    },

    // Optimistic update
    onMutate: async (data) => {
      await queryClient.cancelQueries({
        queryKey: appKeys.detail({ id: data.id }),
      })
      const previous = queryClient.getQueryData(appKeys.detail({ id: data.id }))

      queryClient.setQueryData(
        appKeys.detail({ id: data.id }),
        (old: AppDTO) => ({
          ...old,
          ...data.updates,
        }),
      )

      return { previous }
    },

    onError: (_err, data, context) => {
      // Rollback on error
      queryClient.setQueryData(
        appKeys.detail({ id: data.id }),
        context?.previous,
      )
    },

    onSettled: (_data, _error, variables) => {
      // Refetch to ensure sync
      queryClient.invalidateQueries({
        queryKey: appKeys.detail({ id: variables.id }),
      })
    },
  })
}
```

### Pattern 5: SSE Hook for Streaming

For consuming Server-Sent Events from Python backend.

```typescript
// hooks/useSSE.ts
import { useState, useCallback, useRef, useEffect } from 'react'
import { useAuth } from './useAuth'

type SSEStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'done'

type SSEOptions<T> = {
  onMessage?: (data: T) => void
  onComplete?: () => void
  onError?: (error: Error) => void
}

export function useSSE<T = string>(options: SSEOptions<T> = {}) {
  const [messages, setMessages] = useState<T[]>([])
  const [status, setStatus] = useState<SSEStatus>('idle')
  const [error, setError] = useState<Error | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const { getIdToken } = useAuth()

  const connect = useCallback(
    async (url: string, body?: unknown) => {
      setStatus('connecting')
      setMessages([])
      setError(null)

      abortRef.current = new AbortController()

      try {
        const token = await getIdToken()
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            Accept: 'text/event-stream',
          },
          body: body ? JSON.stringify(body) : undefined,
          signal: abortRef.current.signal,
        })

        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        if (!response.body) throw new Error('No response body')

        setStatus('connected')
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data:')) {
              try {
                const data = JSON.parse(line.slice(5).trim()) as T
                setMessages((prev) => [...prev, data])
                options.onMessage?.(data)
              } catch {
                // Handle non-JSON data
                setMessages((prev) => [...prev, line.slice(5).trim() as T])
              }
            }
          }
        }

        setStatus('done')
        options.onComplete?.()
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setStatus('error')
          setError(err as Error)
          options.onError?.(err as Error)
        }
      }
    },
    [getIdToken, options],
  )

  const close = useCallback(() => {
    abortRef.current?.abort()
    setStatus('done')
  }, [])

  const reset = useCallback(() => {
    close()
    setMessages([])
    setError(null)
    setStatus('idle')
  }, [close])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  return {
    messages,
    status,
    error,
    isConnecting: status === 'connecting',
    isConnected: status === 'connected',
    isDone: status === 'done',
    isError: status === 'error',
    connect,
    close,
    reset,
  }
}
```

### Pattern 6: Component with CVA Variants

Using shadcn/ui patterns with analytics integration.

```typescript
// components/atoms/button.tsx
import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/utils/cn'
import mixpanel from 'mixpanel-browser'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap text-center font-sans font-bold transition-all duration-200',
  {
    variants: {
      variant: {
        primary: cn(
          'bg-background-1 text-text-color',
          'hover:bg-container-light-1-hover',
          'active:bg-background-2',
        ),
        secondary: cn(
          'border-2 border-border-color-inv text-text-color-inv',
          'hover:border-background-2',
        ),
        tertiary: cn(
          'text-text-color bg-container-light-2',
          'hover:bg-container-light-1-hover',
        ),
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        destructive: 'text-text-error hover:bg-container-light-1-hover',
      },
      size: {
        xs: 'rounded-lg p-1 text-button-3',
        sm: 'rounded-lg px-2 py-3 text-button-2',
        md: 'rounded-2xl p-3 text-button-1',
        lg: 'rounded-2xl p-4 text-button-1',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  eventData?: {
    eventId: string
  } & Record<string, unknown>
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, onClick, eventData, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      if (eventData) {
        const { eventId, ...data } = eventData
        mixpanel.track(eventId, data)
      }
      onClick?.(e)
    }

    return (
      <Comp
        className={cn(
          'outline-none disabled:pointer-events-none disabled:opacity-30',
          buttonVariants({ variant, size }),
          className,
        )}
        ref={ref}
        onClick={handleClick}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }
```

---

## Service Abstraction

For swappable backend implementations (Firebase ↔ Supabase ↔ Mock).

### Service Interface Pattern

```typescript
// types/services.ts (or types/index.ts)
export type User = {
  id: string
  email: string | null
  displayName: string | null
  userGroup: 'free' | 'pro' | 'dev' | null
}

// Service interface - what operations are available
export interface IAuthService {
  signIn(email: string, password: string): Promise<void>
  signInWithGoogle(): Promise<void>
  signInWithApple(): Promise<void>
  sendLoginEmail(email: string, redirectUrl: string): Promise<void>
  completeEmailLogin(): Promise<void>
  signOut(): Promise<void>
  onAuthStateChange(callback: (user: User | null) => void): () => void
  getIdToken(): Promise<string>
}

export interface IDataService {
  get<T>(collection: string, id: string): Promise<T | null>
  query<T>(collection: string, filters?: QueryFilter[]): Promise<T[]>
  create<T>(collection: string, data: Omit<T, 'id'>): Promise<T>
  update<T>(collection: string, id: string, data: Partial<T>): Promise<T>
  delete(collection: string, id: string): Promise<void>
  subscribe<T>(
    collection: string,
    id: string,
    callback: (data: T) => void,
  ): () => void
}

export interface IStorageService {
  upload(path: string, file: File): Promise<string>
  getUrl(path: string): Promise<string>
  delete(path: string): Promise<void>
}
```

### Firebase Implementation

```typescript
// services/firebase/auth.ts
import { auth, db } from '@/firebase'
import {
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  OAuthProvider,
  sendSignInLinkToEmail,
  signInWithEmailLink,
  isSignInWithEmailLink,
  signOut,
  onAuthStateChanged,
} from 'firebase/auth'
import { doc, onSnapshot } from 'firebase/firestore'
import type { IAuthService, User } from '@/types'

const googleProvider = new GoogleAuthProvider()
const appleProvider = new OAuthProvider('apple.com')
appleProvider.addScope('email')
appleProvider.addScope('name')

export const firebaseAuthService: IAuthService = {
  async signIn(email, password) {
    await signInWithEmailAndPassword(auth, email, password)
  },

  async signInWithGoogle() {
    await signInWithPopup(auth, googleProvider)
  },

  async signInWithApple() {
    await signInWithPopup(auth, appleProvider)
  },

  async sendLoginEmail(email, redirectUrl) {
    await sendSignInLinkToEmail(auth, email, {
      url: redirectUrl,
      handleCodeInApp: true,
    })
    window.localStorage.setItem('emailForSignIn', email)
  },

  async completeEmailLogin() {
    if (!isSignInWithEmailLink(auth, window.location.href)) return
    const email = window.localStorage.getItem('emailForSignIn')
    if (!email) throw new Error('No email found')
    await signInWithEmailLink(auth, email, window.location.href)
    window.localStorage.removeItem('emailForSignIn')
  },

  async signOut() {
    await signOut(auth)
  },

  onAuthStateChange(callback) {
    return onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        // Stream user data from Firestore
        const unsub = onSnapshot(doc(db, 'users', firebaseUser.uid), (doc) => {
          callback(doc.data() as User)
        })
        return unsub
      }
      callback(null)
    })
  },

  async getIdToken() {
    const user = auth.currentUser
    if (!user) throw new Error('No authenticated user')
    return user.getIdToken()
  },
}
```

### Mock Implementation (for testing/Storybook)

```typescript
// services/mock/auth.ts
import type { IAuthService, User } from '@/types'

const mockUser: User = {
  id: 'mock-user-1',
  email: 'test@example.com',
  displayName: 'Test User',
  userGroup: 'pro',
}

export const mockAuthService: IAuthService = {
  async signIn() {
    /* no-op */
  },
  async signInWithGoogle() {
    /* no-op */
  },
  async signInWithApple() {
    /* no-op */
  },
  async sendLoginEmail() {
    /* no-op */
  },
  async completeEmailLogin() {
    /* no-op */
  },
  async signOut() {
    /* no-op */
  },
  onAuthStateChange(callback) {
    callback(mockUser)
    return () => {}
  },
  async getIdToken() {
    return 'mock-token'
  },
}
```

### Service Provider Context

```typescript
// context/services.tsx
import { createContext, useContext, useMemo, type ReactNode } from 'react'
import type { IAuthService, IDataService, IStorageService } from '@/types'
import { firebaseAuthService } from '@/services/firebase/auth'
import { firebaseDataService } from '@/services/firebase/data'
import { firebaseStorageService } from '@/services/firebase/storage'
import { mockAuthService } from '@/services/mock/auth'
import { mockDataService } from '@/services/mock/data'
import { mockStorageService } from '@/services/mock/storage'

type Services = {
  auth: IAuthService
  data: IDataService
  storage: IStorageService
}

const ServiceContext = createContext<Services | null>(null)

export function ServiceProvider({
  children,
  useMock = false,
}: {
  children: ReactNode
  useMock?: boolean
}) {
  const services = useMemo<Services>(
    () =>
      useMock
        ? {
            auth: mockAuthService,
            data: mockDataService,
            storage: mockStorageService,
          }
        : {
            auth: firebaseAuthService,
            data: firebaseDataService,
            storage: firebaseStorageService,
          },
    [useMock],
  )

  return <ServiceContext.Provider value={services}>{children}</ServiceContext.Provider>
}

export function useServices(): Services {
  const ctx = useContext(ServiceContext)
  if (!ctx) throw new Error('useServices must be used within ServiceProvider')
  return ctx
}

// Convenience hooks
export const useAuthService = () => useServices().auth
export const useDataService = () => useServices().data
export const useStorageService = () => useServices().storage
```

---

## Cross-Cutting Concerns

### Provider Composition

```typescript
// pages/_app.tsx
import '@/styles/globals.css'
import type { AppProps } from 'next/app'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { queryClient, persistOptions } from '@/context/queryClient'
import { ServiceProvider } from '@/context/services'
import { AuthContextProvider } from '@/context/auth'
import { ConfigContextProvider } from '@/context/config'
import { TranslationsProvider } from '@/context/translations'
import { TooltipProvider } from '@/components/atoms/tooltip'
import { Toaster } from '@/components/atoms/toaster'
import Layout from '@/components/layout/Layout'
import type { ReactElement, ReactNode } from 'react'
import type { NextPage } from 'next'

export type NextPageWithLayout<P = unknown> = NextPage<P> & {
  getLayout?: (page: ReactElement) => ReactNode
}

type AppPropsWithLayout = AppProps & {
  Component: NextPageWithLayout
}

export default function App({ Component, pageProps }: AppPropsWithLayout) {
  const getLayout = Component.getLayout ?? ((page) => <Layout>{page}</Layout>)

  return (
    <PersistQueryClientProvider client={queryClient} persistOptions={persistOptions}>
      <ServiceProvider useMock={process.env.NEXT_PUBLIC_USE_MOCK === 'true'}>
        <TranslationsProvider>
          <AuthContextProvider>
            <ConfigContextProvider>
              <TooltipProvider>
                {getLayout(<Component {...pageProps} />)}
                <Toaster />
              </TooltipProvider>
            </ConfigContextProvider>
          </AuthContextProvider>
        </TranslationsProvider>
      </ServiceProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </PersistQueryClientProvider>
  )
}
```

### Error Boundaries

```typescript
// components/ErrorBoundary.tsx
import { Component, type ReactNode } from 'react'

type Props = {
  children: ReactNode
  fallback?: ReactNode
}

type State = {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error) {
    // Log to error reporting service
    console.error('ErrorBoundary caught:', error)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <div>Something went wrong</div>
    }
    return this.props.children
  }
}
```

---

## Implementation Guide

### Technology Stack

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

### Project Setup

```bash
# Create project
npx create-next-app@latest my-app --typescript --tailwind --eslint --src-dir
# Select NO for App Router

cd my-app

# Install dependencies
npm install @tanstack/react-query @tanstack/react-query-devtools
npm install @tanstack/react-query-persist-client idb-keyval
npm install react-hook-form @hookform/resolvers zod
npm install class-variance-authority clsx tailwind-merge
npm install lucide-react sonner usehooks-ts

# shadcn/ui
npx shadcn@latest init
npx shadcn@latest add button input card dialog tooltip

# Storybook
npx storybook@latest init

# Firebase (or Supabase)
npm install firebase
# OR npm install @supabase/supabase-js
```

### Key Configuration Files

#### `components.json` (shadcn)

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/styles/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/utils",
    "ui": "@/components/atoms"
  }
}
```

#### `context/queryClient.ts`

```typescript
import { QueryClient } from '@tanstack/react-query'
import { PersistQueryClientOptions } from '@tanstack/react-query-persist-client'
import { get, set, del } from 'idb-keyval'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      gcTime: 1000 * 60 * 30,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const idbPersister = {
  persistClient: async (client: unknown) => {
    try {
      await set('reactQuery', client)
    } catch {}
  },
  restoreClient: async () => await get('reactQuery'),
  removeClient: async () => await del('reactQuery'),
}

export const persistOptions: Omit<PersistQueryClientOptions, 'queryClient'> = {
  persister: idbPersister,
  dehydrateOptions: {
    shouldDehydrateQuery: ({ meta }) => Boolean(meta?.persist),
  },
}
```

#### `utils/cn.ts`

```typescript
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

#### `config/env.ts`

```typescript
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || ''
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === 'true'
```

### Storybook Configuration

#### `.storybook/main.ts`

```typescript
import type { StorybookConfig } from '@storybook/nextjs'

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
  addons: [
    '@storybook/addon-links',
    '@storybook/addon-essentials',
    '@storybook/addon-interactions',
  ],
  framework: {
    name: '@storybook/nextjs',
    options: {},
  },
  staticDirs: ['../public'],
}

export default config
```

#### `.storybook/preview.ts`

```typescript
import type { Preview } from '@storybook/react'
import '../src/styles/globals.css'

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
}

export default preview
```

#### Example Story

```typescript
// components/atoms/button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './button'

const meta: Meta<typeof Button> = {
  title: 'Atoms/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['primary', 'secondary', 'tertiary', 'ghost', 'destructive'],
    },
    size: {
      control: 'select',
      options: ['xs', 'sm', 'md', 'lg'],
    },
  },
}

export default meta
type Story = StoryObj<typeof Button>

export const Primary: Story = {
  args: {
    children: 'Button',
    variant: 'primary',
  },
}

export const Secondary: Story = {
  args: {
    children: 'Button',
    variant: 'secondary',
  },
}

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="tertiary">Tertiary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="destructive">Destructive</Button>
    </div>
  ),
}
```

---

## Summary

### Key Patterns

| Pattern           | Purpose             | Location               |
| ----------------- | ------------------- | ---------------------- |
| Context + Hook    | Global state        | `context/` + `hooks/`  |
| Query Hook        | Server state        | `hooks/api/`           |
| Query Keys        | Cache management    | `utils/queryKeys.ts`   |
| Service Interface | Backend abstraction | `types/` + `services/` |
| CVA Components    | Styled variants     | `components/atoms/`    |
| Storybook Stories | Documentation       | `*.stories.tsx`        |

### Quick Reference

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

### Remember

- **Hooks are the architecture** — not layers
- **Colocation over separation** — feature code stays together
- **Context for global, Query for server** — different tools for different state
- **Services for abstraction** — swap backends without touching UI
- **Stories for documentation** — living docs next to code
