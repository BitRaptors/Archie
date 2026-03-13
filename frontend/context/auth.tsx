'use client'
import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { authService } from '@/services/auth'

/**
 * Special sentinel value indicating the backend has a server-side GITHUB_TOKEN.
 * When this is the token value, the frontend does NOT send an Authorization header
 * — the backend uses its own env token instead.
 */
export const SERVER_TOKEN = '__server__'

interface AuthContextType {
  /** True when we have a usable token (user-provided OR server-side). */
  isAuthenticated: boolean
  /** The token string, or SERVER_TOKEN sentinel, or null. */
  token: string | null
  /** True while we're checking the backend config on first load. */
  isLoading: boolean
  error: string | null
  /** True when the backend has GITHUB_TOKEN set in env (no user token needed). */
  serverTokenMode: boolean
  authenticate: (token: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthContextProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true) // start true: checking config
  const [error, setError] = useState<string | null>(null)
  const [serverTokenMode, setServerTokenMode] = useState(false)

  // On mount: check backend config, then resolve auth state
  useEffect(() => {
    let cancelled = false

    async function init() {
      try {
        const config = await authService.getConfig()

        if (cancelled) return

        if (config.server_token_configured) {
          // Backend has its own token — skip user auth entirely
          setServerTokenMode(true)
          setToken(SERVER_TOKEN)
        } else {
          // No server token — check localStorage for user-provided token
          const stored = localStorage.getItem('github_token')
          if (stored) {
            setToken(stored)
          }
        }
      } catch {
        // If backend is unreachable, fall back to stored token
        const stored =
          typeof window !== 'undefined'
            ? localStorage.getItem('github_token')
            : null
        if (stored) setToken(stored)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    init()
    return () => { cancelled = true }
  }, [])

  const authenticate = async (newToken: string) => {
    setIsLoading(true)
    setError(null)

    try {
      await authService.authenticate(newToken)

      localStorage.setItem('github_token', newToken)
      setToken(newToken)

      if (typeof window !== 'undefined') {
        window.location.href = '/'
      }
    } catch (err: any) {
      const errorMessage =
        err.response?.data?.detail || err.message || 'Authentication failed'
      setError(errorMessage)
      throw err
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    setIsLoading(true)
    try {
      await authService.logout()
    } catch {
      // Continue with logout even if API call fails
    } finally {
      localStorage.removeItem('github_token')
      setToken(null)
      setServerTokenMode(false)
      setIsLoading(false)
      if (typeof window !== 'undefined') {
        window.location.href = '/'
      }
    }
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!token,
        token,
        isLoading,
        error,
        serverTokenMode,
        authenticate,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthContextProvider')
  }
  return context
}
