'use client'
import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import Link from 'next/link'

export default function AuthPage() {
  const [token, setToken] = useState('')
  const { authenticate, isLoading, error } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await authenticate(token)
      // Redirect will happen in the authenticate function
    } catch (err) {
      // Error is handled in the context and displayed below
      console.error('Authentication error:', err)
    }
  }

  return (
    <div className="container mx-auto p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-4">GitHub Authentication</h1>
        <p className="text-gray-600 mb-6">
          Enter your GitHub Personal Access Token to authenticate with GitHub and access your repositories.
        </p>
        
        <div className="bg-blue-50 border border-blue-200 rounded p-4 mb-6">
          <h2 className="font-semibold text-blue-900 mb-2">Need a token?</h2>
          <p className="text-sm text-blue-800 mb-2">
            Create a Personal Access Token on GitHub with <code className="bg-blue-100 px-1 rounded">repo</code> and <code className="bg-blue-100 px-1 rounded">read:user</code> permissions.
          </p>
          <Link 
            href="https://github.com/settings/tokens"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 underline text-sm"
          >
            Create token on GitHub →
          </Link>
          <span className="text-sm text-gray-600 mx-2">|</span>
          <Link 
            href="https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 underline text-sm"
          >
            Documentation →
          </Link>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="token" className="block text-sm font-medium text-gray-700 mb-2">
              GitHub Personal Access Token
            </label>
            <input
              id="token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              className="border border-gray-300 rounded p-3 w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Your token will be encrypted and stored securely. It starts with <code>ghp_</code> or <code>github_pat_</code>.
            </p>
          </div>
          {error && (
            <div className="bg-red-50 border border-red-200 rounded p-4">
              <p className="text-red-800 text-sm">
                <strong>Error:</strong> {error}
              </p>
            </div>
          )}
          
          <button 
            type="submit" 
            disabled={isLoading || !token.trim()}
            className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed text-white px-6 py-2 rounded font-medium"
          >
            {isLoading ? 'Authenticating...' : 'Authenticate'}
          </button>
        </form>
      </div>
    </div>
  )
}

