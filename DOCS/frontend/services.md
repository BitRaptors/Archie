---
id: frontend-services
title: Service Abstraction
category: frontend
tags: [services, abstraction, interfaces, firebase, supabase]
related: [frontend-structure]
---

# Service Abstraction

For swappable backend implementations (Firebase ↔ Supabase ↔ Mock).

## Service Interface Pattern

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

## Service Provider Context

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


