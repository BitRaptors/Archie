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
  const [activeTab, setActiveTab] = useState<'backend' | 'frontend' | 'mcp'>('backend')
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

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

  const fetchProjectPath = useCallback(async () => {
    if (!token || !isAuthenticated) return

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    
    try {
      const res = await fetch(`${API_URL}/api/v1/system/path`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      
      if (res.ok) {
        const data = await res.json()
        setProjectPath(data.path)
      }
    } catch (err) {
      // Silently fail - we'll just show the template
      console.error('Failed to fetch project path:', err)
    }
  }, [token, isAuthenticated])

  useEffect(() => {
    fetchBlueprints()
    fetchProjectPath()
  }, [fetchBlueprints, fetchProjectPath])

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

  // Generate MCP config JSON
  const getMcpConfig = useCallback(() => {
    if (!projectPath) {
      return JSON.stringify({
        mcpServers: {
          "architecture-mcp": {
            command: "YOUR_PROJECT_PATH/backend/.venv/bin/python",
            args: ["YOUR_PROJECT_PATH/run_mcp.py"],
            cwd: "YOUR_PROJECT_PATH",
            env: {
              PYTHONPATH: "YOUR_PROJECT_PATH"
            }
          }
        }
      }, null, 2)
    }

    return JSON.stringify({
      mcpServers: {
        "architecture-mcp": {
          command: `${projectPath}/backend/.venv/bin/python`,
          args: [`${projectPath}/run_mcp.py`],
          cwd: projectPath,
          env: {
            PYTHONPATH: projectPath
          }
        }
      }
    }, null, 2)
  }, [projectPath])

  // Copy MCP config to clipboard
  const handleCopyConfig = useCallback(() => {
    const config = getMcpConfig()
    navigator.clipboard.writeText(config).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(err => {
      console.error('Failed to copy:', err)
    })
  }, [getMcpConfig])

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

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        <button
          onClick={() => setActiveTab('backend')}
          className={`px-6 py-3 font-medium text-sm transition-colors relative ${
            activeTab === 'backend' 
              ? 'text-blue-600 border-b-2 border-blue-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Backend Architecture
        </button>
        <button
          onClick={() => setActiveTab('frontend')}
          className={`px-6 py-3 font-medium text-sm transition-colors relative ${
            activeTab === 'frontend' 
              ? 'text-blue-600 border-b-2 border-blue-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Frontend Architecture
        </button>
        <button
          onClick={() => setActiveTab('mcp')}
          className={`px-6 py-3 font-medium text-sm transition-colors relative ${
            activeTab === 'mcp' 
              ? 'text-blue-600 border-b-2 border-blue-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          MCP Server Setup
        </button>
      </div>

      <div className="min-h-[400px]">
        {/* Backend Tab */}
        {activeTab === 'backend' && (
          <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
            <div className="bg-gray-50 border-b px-6 py-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-gray-700">Backend Architecture Blueprint</span>
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
        )}

        {/* Frontend Tab */}
        {activeTab === 'frontend' && (
          <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
            <div className="bg-gray-50 border-b px-6 py-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-gray-700">Frontend Architecture Blueprint</span>
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
                <div className="text-center py-12">
                  <h3 className="text-xl font-semibold text-gray-800 mb-2">Frontend Analysis Engine</h3>
                  <p className="text-gray-600">The specialized frontend analysis engine is currently under development.</p>
                  <div className="mt-6 inline-block bg-blue-50 text-blue-700 px-4 py-2 rounded-full text-sm font-medium">
                    Coming Soon
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* MCP Tab */}
        {activeTab === 'mcp' && (
          <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
            <div className="bg-gray-50 border-b px-6 py-3">
              <span className="font-semibold text-gray-700">MCP Server Setup Guide</span>
            </div>
            <div className="p-8">
              <div className="prose prose-blue max-w-none">
                <p>
                  You can add this architectural blueprint directly to your AI assistant (like Cursor or Claude Desktop) 
                  using the Model Context Protocol (MCP). This allows the AI to query specific sections of your 
                  architecture while you code.
                </p>
                
                <h3>1. Copy MCP Configuration</h3>
                <p>Click the button below to copy the ready-to-use configuration. Then paste it directly into Cursor's MCP settings.</p>
                
                <div className="relative bg-gray-900 rounded-lg p-4 my-4 overflow-x-auto">
                  <pre className="text-gray-300 text-sm whitespace-pre-wrap break-words">
{getMcpConfig()}
                  </pre>
                  <button
                    onClick={handleCopyConfig}
                    className="absolute top-4 right-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded flex items-center gap-2 transition-colors"
                  >
                    {copied ? (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Copied!
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        Copy Config
                      </>
                    )}
                  </button>
                </div>

                {!projectPath && (
                  <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 my-4">
                    <p className="text-sm text-yellow-700">
                      <strong>Note:</strong> Could not automatically detect project path. Please replace <code>YOUR_PROJECT_PATH</code> with your actual project path.
                    </p>
                  </div>
                )}

                <h3>2. How to use in Cursor</h3>
                <ol>
                  <li>Open <strong>Cursor Settings</strong> &gt; <strong>General</strong> &gt; <strong>Model Context Protocol</strong>.</li>
                  <li>Click <strong>+ Add New MCP Server</strong>.</li>
                  <li>Name it <code>Architecture</code>.</li>
                  <li>Set Type to <code>command</code>.</li>
                  <li>Paste the copied configuration above.</li>
                </ol>

                <div className="bg-blue-50 border-l-4 border-blue-400 p-4 my-6">
                  <div className="flex">
                    <div className="flex-shrink-0">
                      <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-blue-700">
                        <strong>Pro Tip:</strong> Once connected, you can ask Cursor: 
                        <br />
                        <em>"Show me the layer architecture for repository {id}"</em> 
                        <br />
                        and it will use the MCP tool to fetch only that specific section.
                      </p>
                    </div>
                  </div>
                </div>

                <hr className="my-8" />

                <h2 className="text-xl font-bold mb-4">Option B: Cloud / Remote Setup (SSE)</h2>
                <p className="mb-4">
                  For remote environments or when the project is hosted in the cloud, you can connect via HTTP using Server-Sent Events (SSE).
                </p>
                
                <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 my-4">
                  <p className="text-sm text-yellow-700">
                    <strong>Note:</strong> SSE transport is currently being implemented. For now, please use Option A (local setup) above.
                  </p>
                </div>
                
                <div className="bg-gray-900 rounded-lg p-4 my-4 overflow-x-auto">
                  <pre className="text-gray-300 text-sm">
{`{
  "mcpServers": {
    "architecture-cloud": {
      "transport": {
        "type": "sse",
        "url": "${typeof window !== 'undefined' ? window.location.origin.replace('3000', '8000') : 'http://localhost:8000'}/api/v1/mcp/sse"
      }
    }
  }
}`}
                  </pre>
                </div>

                <ol className="list-decimal pl-6 space-y-2 text-gray-700">
                  <li>In Cursor Settings, click <strong>+ Add New MCP Server</strong>.</li>
                  <li>Name it <code>Architecture Cloud</code>.</li>
                  <li>Set Type to <code>SSE</code> or use the transport configuration above.</li>
                  <li>Paste the configuration with the URL: <code>{typeof window !== 'undefined' ? window.location.origin.replace('3000', '8000') : 'http://localhost:8000'}/api/v1/mcp/sse</code></li>
                </ol>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-8 text-center">
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

