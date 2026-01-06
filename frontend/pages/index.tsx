'use client'
import { useRepositoriesQuery } from '@/hooks/api/useRepositoriesQuery'
import { useAuth } from '@/hooks/useAuth'
import { repositoriesService } from '@/services/repositories'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'

export default function Home() {
  const [mounted, setMounted] = useState(false)
  const [analyzing, setAnalyzing] = useState<Set<string>>(new Set())
  const { isAuthenticated, token } = useAuth()
  const { data: repos, isLoading } = useRepositoriesQuery()
  const router = useRouter()

  // Fix hydration error by only rendering after mount
  useEffect(() => {
    setMounted(true)
  }, [])

  // Show loading state during SSR/hydration
  if (!mounted) {
    return (
      <div className="container mx-auto p-8">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-3xl font-bold mb-4">Repository Analysis System</h1>
          <p className="text-gray-600 mb-6">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="container mx-auto p-8">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-3xl font-bold mb-4">Repository Analysis System</h1>
          <p className="text-gray-600 mb-6">
            Analyze GitHub repositories and generate architecture blueprints.
          </p>
          <Link 
            href="/auth" 
            className="inline-block bg-blue-500 text-white px-6 py-2 rounded hover:bg-blue-600"
          >
            Get Started - Authenticate with GitHub
          </Link>
        </div>
      </div>
    )
  }

  const handleAnalyze = async (owner: string, name: string, repoId: string) => {
    if (!token) return
    
    const repoKey = `${owner}/${name}`
    
    // Mark as analyzing immediately (optimistic UI)
    setAnalyzing(prev => new Set(prev).add(repoKey))
    
    try {
      // Start analysis - this should be fast (just creates DB record)
      const analysis = await repositoriesService.analyze(owner, name, token)
      
      // Navigate immediately once we have the ID
      router.push(`/analysis/${analysis.id}`)
    } catch (err: any) {
      // Remove analyzing state on error
      setAnalyzing(prev => {
        const next = new Set(prev)
        next.delete(repoKey)
        return next
      })
      alert(`Failed to start analysis: ${err.message}`)
    }
  }

  return (
    <div className="container mx-auto p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Your Repositories</h1>
        {isLoading ? (
          <p className="text-gray-600">Loading repositories...</p>
        ) : repos && repos.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {repos.map((repo) => {
              const repoKey = `${repo.owner}/${repo.name}`
              const isAnalyzing = analyzing.has(repoKey)
              
              return (
                <div key={repo.id} className="border rounded p-4 hover:bg-gray-50 flex flex-col justify-between">
                  <div>
                    <h2 className="text-xl font-semibold">{repo.full_name}</h2>
                    {repo.description && (
                      <p className="text-gray-600 mt-1 line-clamp-2">{repo.description}</p>
                    )}
                    {repo.language && (
                      <span className="inline-block mt-2 text-sm text-gray-500">
                        {repo.language}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => handleAnalyze(repo.owner, repo.name, repo.id)}
                    disabled={isAnalyzing}
                    className={`mt-4 px-4 py-2 rounded transition-all w-full ${
                      isAnalyzing
                        ? 'bg-gray-400 cursor-not-allowed text-white'
                        : 'bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700'
                    }`}
                  >
                    {isAnalyzing ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Starting...
                      </span>
                    ) : (
                      'Analyze Repository'
                    )}
                  </button>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-gray-600">No repositories found. Start by analyzing a repository.</p>
        )}
      </div>
    </div>
  )
}
