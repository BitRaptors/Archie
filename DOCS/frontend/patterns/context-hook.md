---
id: frontend-pattern-context-hook
title: Context + Consumer Hook
category: frontend
tags: [pattern, context, hooks, global-state]
related: [frontend-patterns-overview]
---

# Pattern 1: Context + Consumer Hook

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


