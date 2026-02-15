'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import {
  useWorkspaceRepositories,
  useActiveRepository,
  useSetActiveRepository,
  useClearActiveRepository,
  useAgentFiles,
  useDeleteRepository,
} from '@/hooks/api/useWorkspace'
import type { WorkspaceRepository } from '@/services/workspace'
import DeliveryPanel from '@/components/DeliveryPanel'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text)
}

function downloadFile(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// Repo Card
// ---------------------------------------------------------------------------

function RepoCard({
  repo,
  isActive,
  onActivate,
  onDeactivate,
  onDelete,
}: {
  repo: WorkspaceRepository
  isActive: boolean
  onActivate: () => void
  onDeactivate: () => void
  onDelete: () => void
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <div
      className={`border rounded-lg p-5 flex flex-col justify-between transition-all ${
        isActive ? 'border-blue-500 ring-2 ring-blue-200 bg-blue-50/30' : 'hover:border-gray-300'
      }`}
    >
      <div>
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-lg truncate">{repo.name}</h3>
          {isActive && (
            <span className="shrink-0 text-xs font-medium bg-blue-500 text-white px-2 py-0.5 rounded-full">
              Active
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
          {repo.language && (
            <span className="inline-flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-gray-400 inline-block" />
              {repo.language}
            </span>
          )}
          {repo.analyzed_at && (
            <span>
              {new Date(repo.analyzed_at).toLocaleDateString()}
            </span>
          )}
          {repo.has_structured && (
            <span className="text-green-600 font-medium" title="Structured blueprint available">
              JSON
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 mt-4">
        {isActive ? (
          <button
            onClick={onDeactivate}
            className="flex-1 text-sm px-3 py-1.5 border border-gray-300 rounded hover:bg-gray-100 transition-colors"
          >
            Deactivate
          </button>
        ) : (
          <button
            onClick={onActivate}
            className="flex-1 text-sm px-3 py-1.5 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
          >
            Activate
          </button>
        )}
        <Link
          href={`/blueprint/${repo.repo_id}?source=workspace`}
          className="text-sm px-3 py-1.5 border border-gray-300 rounded hover:bg-gray-100 transition-colors text-center"
        >
          Blueprint
        </Link>
        {confirmDelete ? (
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                onDelete()
                setConfirmDelete(false)
              }}
              className="text-sm px-3 py-1.5 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
            >
              Confirm
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="text-sm px-2 py-1.5 text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="text-sm px-3 py-1.5 border border-red-200 text-red-500 rounded hover:bg-red-50 transition-colors"
            title="Delete analysis"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent File Panel
// ---------------------------------------------------------------------------

function AgentFilePanel({ repoId }: { repoId: string }) {
  const { data: files, isLoading, isError } = useAgentFiles(repoId)
  const [activeTab, setActiveTab] = useState<'claude' | 'cursor' | 'agents'>('claude')
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(
    (content: string) => {
      copyToClipboard(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    },
    []
  )

  if (isLoading) {
    return (
      <div className="border rounded-lg p-6 mt-6 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="h-24 bg-gray-100 rounded" />
      </div>
    )
  }

  if (isError || !files) {
    return (
      <div className="border rounded-lg p-6 mt-6 bg-yellow-50 border-yellow-200">
        <h3 className="font-semibold text-yellow-800 mb-1">No Structured Blueprint</h3>
        <p className="text-sm text-yellow-600">
          Agent files require a structured blueprint (blueprint.json). Re-analyze to generate one.
        </p>
      </div>
    )
  }

  const tabs = [
    { key: 'claude' as const, label: 'CLAUDE.md', content: files.claude_md, filename: 'CLAUDE.md' },
    { key: 'cursor' as const, label: 'Cursor Rules', content: files.cursor_rules, filename: 'architecture.md' },
    { key: 'agents' as const, label: 'AGENTS.md', content: files.agents_md, filename: 'AGENTS.md' },
  ]

  const currentTab = tabs.find((t) => t.key === activeTab)!

  return (
    <div className="border rounded-lg mt-6 overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b bg-gray-50">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === t.key
                ? 'bg-white border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
        <div className="flex-1" />
        <div className="flex items-center gap-1 pr-3">
          <button
            onClick={() => handleCopy(currentTab.content)}
            className="text-xs px-2.5 py-1 border rounded text-gray-500 hover:text-gray-700 hover:border-gray-400 transition-colors"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={() => downloadFile(currentTab.filename, currentTab.content)}
            className="text-xs px-2.5 py-1 border rounded text-gray-500 hover:text-gray-700 hover:border-gray-400 transition-colors"
          >
            Download
          </button>
        </div>
      </div>

      {/* Content */}
      <pre className="p-4 text-xs leading-relaxed overflow-auto max-h-96 bg-gray-900 text-gray-100">
        <code>{currentTab.content}</code>
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MCP Config Panel
// ---------------------------------------------------------------------------

function McpConfigPanel() {
  const [copied, setCopied] = useState(false)

  const config = JSON.stringify(
    {
      mcpServers: {
        'architecture-blueprints': {
          url: 'http://localhost:8000/mcp/sse',
        },
      },
    },
    null,
    2
  )

  return (
    <div className="border rounded-lg mt-6 p-5">
      <h3 className="font-semibold mb-1">MCP Configuration</h3>
      <p className="text-sm text-gray-500 mb-3">
        Add to your editor&apos;s MCP settings to connect. The MCP server
        automatically serves the active repository.
      </p>
      <div className="relative">
        <pre className="p-3 text-xs bg-gray-900 text-gray-100 rounded overflow-auto">
          <code>{config}</code>
        </pre>
        <button
          onClick={() => {
            copyToClipboard(config)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
          }}
          className="absolute top-2 right-2 text-xs px-2 py-1 bg-gray-700 text-gray-200 rounded hover:bg-gray-600 transition-colors"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function WorkspacePage() {
  const { data: repos, isLoading: reposLoading } = useWorkspaceRepositories()
  const { data: activeData, isLoading: activeLoading } = useActiveRepository()
  const setActive = useSetActiveRepository()
  const clearActive = useClearActiveRepository()
  const deleteRepo = useDeleteRepository()

  const activeRepoId = activeData?.active_repo_id ?? null

  // Combined loading
  if (reposLoading || activeLoading) {
    return (
      <div className="container mx-auto p-8 max-w-5xl">
        <h1 className="text-3xl font-bold mb-6">Workspace</h1>
        <p className="text-gray-500">Loading workspace...</p>
      </div>
    )
  }

  const hasRepos = repos && repos.length > 0

  return (
    <div className="container mx-auto p-8 max-w-5xl">
      <h1 className="text-3xl font-bold mb-2">Workspace</h1>
      <p className="text-gray-500 mb-8">
        Select an active repository. The MCP server, CLAUDE.md, and Cursor rules
        will use the active repository&apos;s architecture data.
      </p>

      {/* Repository Grid */}
      {hasRepos ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {repos.map((repo) => (
            <RepoCard
              key={repo.repo_id}
              repo={repo}
              isActive={repo.repo_id === activeRepoId}
              onActivate={() => setActive.mutate(repo.repo_id)}
              onDeactivate={() => clearActive.mutate()}
              onDelete={() => deleteRepo.mutate(repo.repo_id)}
            />
          ))}
        </div>
      ) : (
        <div className="border rounded-lg p-8 text-center bg-gray-50">
          <h3 className="font-semibold text-lg mb-2">No analyzed repositories yet</h3>
          <p className="text-gray-500 mb-4">
            Analyze a GitHub repository first, then come back here to manage it.
          </p>
          <Link
            href="/"
            className="inline-block bg-blue-500 text-white px-5 py-2 rounded hover:bg-blue-600 transition-colors"
          >
            Go to Repositories
          </Link>
        </div>
      )}

      {/* Active Repository Panel */}
      {activeRepoId && (
        <div className="mt-10">
          <h2 className="text-xl font-semibold mb-1">Active Repository</h2>
          <p className="text-sm text-gray-500 mb-4">
            Agent files generated from the structured blueprint.
          </p>

          <AgentFilePanel repoId={activeRepoId} />
          <DeliveryPanel repoId={activeRepoId} />
          <McpConfigPanel />
        </div>
      )}
    </div>
  )
}
