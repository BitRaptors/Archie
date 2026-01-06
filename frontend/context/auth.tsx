'use client'
import { createContext, useContext, useState, ReactNode } from 'react'
import { authService } from '@/services/auth'

interface AuthContextType {
  isAuthenticated: boolean
  token: string | null
  isLoading: boolean
  error: string | null
  authenticate: (token: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthContextProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    typeof window !== 'undefined' ? localStorage.getItem('github_token') : null
  )
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const authenticate = async (newToken: string) => {
    setIsLoading(true)
    setError(null)
    
    try {
      // Validate token with backend
      await authService.authenticate(newToken)
      
      // Store token locally if validation succeeds
      localStorage.setItem('github_token', newToken)
      setToken(newToken)
      
      // Redirect to home page
      if (typeof window !== 'undefined') {
        window.location.href = '/'
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Authentication failed'
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
    } catch (err) {
      // Continue with logout even if API call fails
      console.error('Logout API call failed:', err)
    } finally {
      localStorage.removeItem('github_token')
      setToken(null)
      setIsLoading(false)
      if (typeof window !== 'undefined') {
        window.location.href = '/auth'
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

