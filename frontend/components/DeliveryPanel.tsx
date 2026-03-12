'use client'

import { useState, useCallback } from 'react'
import { useRepositoriesQuery } from '@/hooks/api/useRepositoriesQuery'
import { useDeliveryApply } from '@/hooks/api/useDelivery'
import { useAuth } from '@/hooks/useAuth'
import { SERVER_TOKEN } from '@/context/auth'
import type { DeliveryRequest } from '@/services/delivery'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'

const OUTPUT_OPTIONS = [
  { key: 'claude_md', label: 'CLAUDE.md' },
  { key: 'claude_rules', label: 'Claude Rules' },
  { key: 'cursor_rules', label: 'Cursor Rules' },
  { key: 'agents_md', label: 'AGENTS.md' },
  { key: 'mcp_claude', label: '.mcp.json' },
  { key: 'mcp_cursor', label: '.cursor/mcp.json' },
] as const

export default function DeliveryPanel({ repoId }: { repoId: string }) {
  const { token } = useAuth()
  const { data: repos } = useRepositoriesQuery()
  const applyMutation = useDeliveryApply()

  const [targetRepo, setTargetRepo] = useState('')
  const [strategy, setStrategy] = useState<'pr' | 'commit'>('pr')
  const [outputs, setOutputs] = useState<string[]>(['claude_md', 'claude_rules', 'cursor_rules', 'agents_md', 'mcp_claude', 'mcp_cursor'])

  const toggleOutput = useCallback((key: string) => {
    setOutputs((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    )
  }, [])

  const handleDeliver = useCallback(() => {
    if (!targetRepo || outputs.length === 0) return

    const req: DeliveryRequest = {
      source_repo_id: repoId,
      target_repo: targetRepo,
      strategy,
      outputs,
    }

    // Don't send SERVER_TOKEN as a Bearer token — the backend uses its own env token
    const authToken = token && token !== SERVER_TOKEN ? token : undefined

    applyMutation.mutate({ req, token: authToken })
  }, [targetRepo, outputs, strategy, repoId, token, applyMutation])

  const canDeliver = !!targetRepo && outputs.length > 0 && !applyMutation.isPending

  return (
    <div className="border rounded-lg mt-6 p-5">
      <h3 className="font-semibold mb-1">Deliver to Repository</h3>
      <p className="text-sm text-muted-foreground mb-4">
        Push architecture outputs to a GitHub repository via PR or direct commit.
      </p>

      {/* Target repo */}
      <label className="block text-sm font-medium text-foreground/80 mb-1">
        Target repository
      </label>
      <select
        value={targetRepo}
        onChange={(e) => {
          setTargetRepo(e.target.value)
          applyMutation.reset()
        }}
        className="w-full border rounded px-3 py-2 text-sm mb-4 bg-white"
      >
        <option value="">Select a repository...</option>
        {repos?.map((r: any) => (
          <option key={r.full_name || r.id} value={r.full_name}>
            {r.full_name}
          </option>
        ))}
      </select>

      {/* Output checkboxes */}
      <label className="block text-sm font-medium text-foreground/80 mb-1">
        Outputs
      </label>
      <div className="flex gap-4 mb-4">
        {OUTPUT_OPTIONS.map((opt) => (
          <label key={opt.key} className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={outputs.includes(opt.key)}
              onChange={() => toggleOutput(opt.key)}
              className={cn("rounded", theme.surface.inputBorder)}
            />
            {opt.label}
          </label>
        ))}
      </div>

      {/* Strategy toggle */}
      <label className="block text-sm font-medium text-foreground/80 mb-1">
        Strategy
      </label>
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setStrategy('pr')}
          className={cn(
            "text-sm px-3 py-1.5 rounded border transition-colors",
            strategy === 'pr' ? theme.interactive.strategyActive : theme.interactive.strategyInactive
          )}
        >
          Pull Request
        </button>
        <button
          onClick={() => setStrategy('commit')}
          className={cn(
            "text-sm px-3 py-1.5 rounded border transition-colors",
            strategy === 'commit' ? theme.interactive.strategyActive : theme.interactive.strategyInactive
          )}
        >
          Direct Commit
        </button>
      </div>

      {/* Action button */}
      <button
        onClick={handleDeliver}
        disabled={!canDeliver}
        className={cn("text-sm px-5 py-2 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed", theme.interactive.cta)}
      >
        {applyMutation.isPending ? (
          <span className="flex items-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle
                className="opacity-25"
                cx="12" cy="12" r="10"
                stroke="currentColor" strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>
            Delivering...
          </span>
        ) : (
          strategy === 'pr' ? 'Create Pull Request' : 'Commit to Default Branch'
        )}
      </button>

      {/* Success feedback */}
      {applyMutation.isSuccess && (
        <div className={cn("mt-4 p-3 rounded text-sm", theme.status.successPanel)}>
          <p className={theme.status.successText}>Delivered successfully!</p>
          {applyMutation.data.pr_url && (
            <a
              href={applyMutation.data.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className={cn("mt-1 inline-block", theme.brand.link)}
            >
              View Pull Request
            </a>
          )}
          {applyMutation.data.commit_sha && (
            <p className={cn("mt-1", theme.status.successSubtext)}>
              Commit: <code className="text-xs">{applyMutation.data.commit_sha}</code>
            </p>
          )}
          <p className="text-muted-foreground mt-1">
            Files: {applyMutation.data.files_delivered.join(', ')}
          </p>
        </div>
      )}

      {/* Error feedback */}
      {applyMutation.isError && (
        <div className={cn("mt-4 p-3 rounded text-sm", theme.status.errorPanel)}>
          <p className={theme.status.errorTitle}>Delivery failed</p>
          <p className={cn("mt-1", theme.status.errorText)}>
            {(applyMutation.error as any)?.response?.data?.detail ??
              (applyMutation.error as Error).message}
          </p>
        </div>
      )}
    </div>
  )
}
