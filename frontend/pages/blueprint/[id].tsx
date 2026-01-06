'use client'
import { useRouter } from 'next/router'
import { useEffect, useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import Link from 'next/link'

interface BlueprintData {
  analysis_id: string
  repository_id: string
  content: string
  path: string
}

export default function BlueprintView() {
  const router = useRouter()
  const { id } = router.query
  const { token, isAuthenticated } = useAuth()
  const [blueprint, setBlueprint] = useState<BlueprintData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!id || !token || !isAuthenticated) return

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    
    fetch(`${API_URL}/api/v1/analyses/${id}/blueprint`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(res => {
        if (!res.ok) {
          if (res.status === 404) {
            throw new Error('Blueprint not found. The analysis may not be completed yet.')
          }
          if (res.status === 400) {
            return res.json().then(data => {
              throw new Error(data.detail || 'Analysis is not completed')
            })
          }
          throw new Error(`Failed to load blueprint: ${res.statusText}`)
        }
        return res.json()
      })
      .then(data => {
        setBlueprint(data)
        setIsLoading(false)
      })
      .catch(err => {
        setIsLoading(false)
        setError(err.message)
      })
  }, [id, token, isAuthenticated])

  if (!isAuthenticated) return <div className="p-8">Please authenticate first.</div>
  if (!id) return <div className="p-8">Loading...</div>

  if (isLoading) {
    return (
      <div className="container mx-auto p-8 max-w-6xl">
        <div className="mb-8">
          <Link href="/" className="text-blue-500 hover:underline mb-2 inline-block">← Back to Repositories</Link>
          <h1 className="text-3xl font-bold">Loading Blueprint...</h1>
        </div>
        <div className="bg-white border rounded-lg p-8 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Loading blueprint content...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto p-8 max-w-6xl">
        <div className="mb-8">
          <Link href="/" className="text-blue-500 hover:underline mb-2 inline-block">← Back to Repositories</Link>
          <h1 className="text-3xl font-bold">Blueprint Error</h1>
        </div>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
        <div className="mt-4">
          <Link 
            href={`/analysis/${id}`}
            className="text-blue-500 hover:underline"
          >
            ← Back to Analysis Timeline
          </Link>
        </div>
      </div>
    )
  }

  if (!blueprint) {
    return (
      <div className="container mx-auto p-8 max-w-6xl">
        <div className="mb-8">
          <Link href="/" className="text-blue-500 hover:underline mb-2 inline-block">← Back to Repositories</Link>
          <h1 className="text-3xl font-bold">Blueprint Not Found</h1>
        </div>
        <p className="text-gray-600">The blueprint could not be loaded.</p>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-8 max-w-6xl">
      <div className="mb-8 flex justify-between items-center">
        <div>
          <Link href="/" className="text-blue-500 hover:underline mb-2 inline-block">← Back to Repositories</Link>
          <h1 className="text-3xl font-bold">Architecture Blueprint</h1>
          <p className="text-gray-500 text-sm mt-1">Analysis ID: {id}</p>
        </div>
        <div className="flex gap-4">
          <Link 
            href={`/analysis/${id}`}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded text-gray-700"
          >
            View Timeline
          </Link>
        </div>
      </div>

      <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
        <div className="bg-gray-50 border-b px-6 py-3 font-semibold text-gray-700">
          Blueprint Document
        </div>
        <div className="p-8">
          <pre className="whitespace-pre-wrap font-mono text-sm bg-gray-50 p-6 rounded border overflow-x-auto">
            {blueprint.content}
          </pre>
        </div>
      </div>

      <div className="mt-6 text-center">
        <Link 
          href={`/analysis/${id}`}
          className="text-blue-500 hover:underline"
        >
          ← Back to Analysis Timeline
        </Link>
      </div>
    </div>
  )
}

