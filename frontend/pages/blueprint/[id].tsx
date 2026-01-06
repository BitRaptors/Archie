'use client'
import { useRouter } from 'next/router'
import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/hooks/useAuth'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface BlueprintData {
  analysis_id: string
  repository_id: string
  type?: string
  content: string
  path: string
}

// Download icon component
function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg 
      className={className} 
      fill="none" 
      stroke="currentColor" 
      viewBox="0 0 24 24"
    >
      <path 
        strokeLinecap="round" 
        strokeLinejoin="round" 
        strokeWidth={2} 
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" 
      />
    </svg>
  )
}

export default function BlueprintView() {
  const router = useRouter()
  const { id } = router.query
  const { token, isAuthenticated } = useAuth()
  const [backendBlueprint, setBackendBlueprint] = useState<BlueprintData | null>(null)
  const [frontendBlueprint, setFrontendBlueprint] = useState<BlueprintData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchBlueprints = useCallback(async () => {
    if (!id || !token || !isAuthenticated) return

    setIsLoading(true)
    setError(null)

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    
    try {
      // Fetch backend blueprint
      const backendRes = await fetch(`${API_URL}/api/v1/analyses/${id}/blueprint?type=backend`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      
      if (!backendRes.ok) {
        if (backendRes.status === 400) {
          const data = await backendRes.json()
          throw new Error(data.detail || 'Analysis is not completed')
        }
        throw new Error(`Failed to load backend blueprint: ${backendRes.statusText}`)
      }
      const backendData = await backendRes.json()
      setBackendBlueprint(backendData)

      // Fetch frontend blueprint
      const frontendRes = await fetch(`${API_URL}/api/v1/analyses/${id}/blueprint?type=frontend`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      
      if (frontendRes.ok) {
        const frontendData = await frontendRes.json()
        setFrontendBlueprint(frontendData)
      }

      setIsLoading(false)
    } catch (err: any) {
      setIsLoading(false)
      setError(err.message)
    }
  }, [id, token, isAuthenticated])

  useEffect(() => {
    fetchBlueprints()
  }, [fetchBlueprints])

  // Download blueprint as markdown file
  const handleDownload = useCallback((blueprint: BlueprintData | null) => {
    if (!blueprint?.content) return

    // Create blob with markdown content
    const blob = new Blob([blueprint.content], { type: 'text/markdown;charset=utf-8' })
    
    // Generate filename from path or use default
    const filename = blueprint.path 
      ? blueprint.path.split('/').pop() || `${blueprint.type}_blueprint.md`
      : `${blueprint.type}_blueprint.md`
    
    // Create download link and trigger download
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    
    // Cleanup
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, [])

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

  if (!backendBlueprint && !isLoading && !error) {
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
        <div className="flex gap-3">
          <Link 
            href={`/analysis/${id}`}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded text-gray-700"
          >
            View Timeline
          </Link>
        </div>
      </div>

      <div className="space-y-8">
        {/* Backend Blueprint Section */}
        <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
          <div className="bg-gray-50 border-b px-6 py-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-gray-700">Backend Architecture</span>
              {backendBlueprint && (
                <button
                  onClick={() => handleDownload(backendBlueprint)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                >
                  <DownloadIcon className="w-4 h-4" />
                  Download MD
                </button>
              )}
            </div>
          </div>
          <div className="p-8">
            {backendBlueprint ? (
              <div className="prose prose-blue max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {backendBlueprint.content}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="text-gray-500 italic text-center">Backend blueprint not available.</p>
            )}
          </div>
        </div>

        {/* Frontend Blueprint Section */}
        <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
          <div className="bg-gray-50 border-b px-6 py-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-gray-700">Frontend Architecture</span>
              {frontendBlueprint && !frontendBlueprint.content.includes("Coming Soon") && (
                <button
                  onClick={() => handleDownload(frontendBlueprint)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                >
                  <DownloadIcon className="w-4 h-4" />
                  Download MD
                </button>
              )}
            </div>
          </div>
          <div className="p-8">
            {frontendBlueprint ? (
              <div className="prose prose-blue max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {frontendBlueprint.content}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
                <p className="text-gray-600">Loading frontend blueprint...</p>
              </div>
            )}
          </div>
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

