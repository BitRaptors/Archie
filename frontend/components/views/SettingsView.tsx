import { useState } from 'react'
import { usePrompts, usePromptRevisions, useUpdatePrompt, useRevertPrompt } from '@/hooks/api/usePrompts'
import { Prompt } from '@/services/prompts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { Settings, Save, RotateCcw, ChevronRight, Clock } from 'lucide-react'

export function SettingsView() {
  const { data: prompts, isLoading } = usePrompts()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selectedPrompt = prompts?.find((p) => p.id === selectedId) ?? null

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-6">
          <Skeleton className="h-[600px] w-64" />
          <Skeleton className="h-[600px] flex-1" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Settings className="w-6 h-6" />
        Settings
      </h1>
      <div className="flex gap-6 items-start">
        <PromptList
          prompts={prompts ?? []}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        {selectedPrompt ? (
          <PromptEditor prompt={selectedPrompt} />
        ) : (
          <Card className="flex-1">
            <CardContent className="flex items-center justify-center h-96 text-muted-foreground">
              Select a prompt to edit
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

/* ── Prompt List ──────────────────────────────────────────────────── */

function PromptList({
  prompts,
  selectedId,
  onSelect,
}: {
  prompts: Prompt[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <Card className="w-64 shrink-0">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Prompts</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="space-y-0.5 max-h-[600px] overflow-y-auto">
          {prompts.map((p) => (
            <button
              key={p.id}
              className={cn(
                'w-full text-left px-4 py-2.5 text-sm transition-colors hover:bg-muted/50',
                selectedId === p.id && 'bg-muted font-medium'
              )}
              onClick={() => onSelect(p.id)}
            >
              <div className="flex items-center gap-2">
                <ChevronRight
                  className={cn(
                    'w-3 h-3 shrink-0 transition-transform',
                    selectedId === p.id && 'rotate-90'
                  )}
                />
                <span className="truncate">{p.name}</span>
              </div>
              {p.key && (
                <span className="text-[10px] text-muted-foreground ml-5">{p.key}</span>
              )}
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

/* ── Prompt Editor ────────────────────────────────────────────────── */

function PromptEditor({ prompt }: { prompt: Prompt }) {
  const [name, setName] = useState(prompt.name)
  const [template, setTemplate] = useState(prompt.prompt_template)
  const [changeSummary, setChangeSummary] = useState('')
  const [showRevisions, setShowRevisions] = useState(false)

  const updateMutation = useUpdatePrompt()

  // Reset form when selected prompt changes
  const [prevId, setPrevId] = useState(prompt.id)
  if (prompt.id !== prevId) {
    setPrevId(prompt.id)
    setName(prompt.name)
    setTemplate(prompt.prompt_template)
    setChangeSummary('')
    setShowRevisions(false)
  }

  const isDirty = name !== prompt.name || template !== prompt.prompt_template

  const handleSave = () => {
    updateMutation.mutate(
      {
        id: prompt.id,
        data: {
          name,
          prompt_template: template,
          change_summary: changeSummary || undefined,
        },
      },
      {
        onSuccess: () => setChangeSummary(''),
      }
    )
  }

  return (
    <div className="flex-1 space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">{prompt.name}</CardTitle>
            <div className="flex items-center gap-2">
              {prompt.key && <Badge variant="outline">{prompt.key}</Badge>}
              <Badge variant="secondary">{prompt.category}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">
              Name
            </label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">
              Prompt Template
            </label>
            <textarea
              className="w-full min-h-[300px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
            />
          </div>

          {prompt.variables.length > 0 && (
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Variables
              </label>
              <div className="flex flex-wrap gap-1.5">
                {prompt.variables.map((v) => (
                  <Badge key={v} variant="outline" className="font-mono text-xs">
                    {`{${v}}`}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-end gap-3 pt-2 border-t">
            <div className="flex-1">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Change summary (optional)
              </label>
              <Input
                placeholder="What did you change?"
                value={changeSummary}
                onChange={(e) => setChangeSummary(e.target.value)}
              />
            </div>
            <Button
              onClick={handleSave}
              disabled={!isDirty || updateMutation.isPending}
            >
              <Save className="w-4 h-4 mr-2" />
              {updateMutation.isPending ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div>
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          onClick={() => setShowRevisions(!showRevisions)}
        >
          <Clock className="w-4 h-4 mr-2" />
          {showRevisions ? 'Hide' : 'Show'} Revision History
        </Button>
        {showRevisions && <RevisionHistory promptId={prompt.id} />}
      </div>
    </div>
  )
}

/* ── Revision History ─────────────────────────────────────────────── */

function RevisionHistory({ promptId }: { promptId: string }) {
  const { data: revisions, isLoading } = usePromptRevisions(promptId)
  const revertMutation = useRevertPrompt()

  if (isLoading) {
    return (
      <Card className="mt-2">
        <CardContent className="py-4">
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (!revisions?.length) {
    return (
      <Card className="mt-2">
        <CardContent className="py-4 text-sm text-muted-foreground">
          No revisions yet
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="mt-2">
      <CardContent className="py-3 space-y-2">
        {revisions.map((rev) => (
          <div
            key={rev.id}
            className="flex items-center justify-between py-2 px-3 rounded-md border text-sm"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="shrink-0">
                  #{rev.revision_number}
                </Badge>
                <span className="text-muted-foreground text-xs truncate">
                  {new Date(rev.created_at).toLocaleString()}
                </span>
              </div>
              {rev.change_summary && (
                <p className="text-xs text-muted-foreground mt-1 truncate">
                  {rev.change_summary}
                </p>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              disabled={revertMutation.isPending}
              onClick={() =>
                revertMutation.mutate({ promptId, revisionId: rev.id })
              }
            >
              <RotateCcw className="w-3 h-3 mr-1" />
              Revert
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
