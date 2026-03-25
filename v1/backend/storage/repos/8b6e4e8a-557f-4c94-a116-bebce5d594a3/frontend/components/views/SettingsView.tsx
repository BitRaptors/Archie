import { useState, useEffect } from 'react'
import { usePrompts, usePromptRevisions, useUpdatePrompt, useRevertPrompt } from '@/hooks/api/usePrompts'
import { Prompt } from '@/services/prompts'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'
import { Loader2, Settings, Save, RotateCcw, ChevronRight, FolderX, Zap, FileCode, History, Box, Trash2, Database } from 'lucide-react'
import { IgnoredDirsSettingsView } from './IgnoredDirsSettingsView'
import { CapabilitiesSettingsView } from './CapabilitiesSettingsView'
import { ConfirmationDialog } from '@/components/ConfirmationDialog'
import { useResetAllData } from '@/hooks/api/useSettings'
import { PageHeader } from '@/components/layout/PageHeader'

type SettingsTab = 'prompts' | 'ignored_dirs' | 'capabilities' | 'database'

export function SettingsView() {
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('prompts')
  const [showResetDialog, setShowResetDialog] = useState(false)
  const resetAllData = useResetAllData()

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white/50 animate-in fade-in duration-500">
      <PageHeader
        title="System Settings"
        subtitle="Configure Core Engine & Analysis Parameters"
        icon={Settings}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Tab Switcher */}
        <div className="flex items-center gap-8 border-b border-papaya-300 bg-white/30 px-8 z-10 backdrop-blur-sm shrink-0">
          <button
            onClick={() => setSettingsTab('prompts')}
            className={cn(
              "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]",
              settingsTab === 'prompts'
                ? "text-teal border-teal"
                : "text-ink/40 hover:text-ink/60 border-transparent"
            )}
          >
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4" />
              Prompt Templates
            </div>
          </button>
          <button
            onClick={() => setSettingsTab('ignored_dirs')}
            className={cn(
              "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]",
              settingsTab === 'ignored_dirs'
                ? "text-teal border-teal"
                : "text-ink/40 hover:text-ink/60 border-transparent"
            )}
          >
            <div className="flex items-center gap-2">
              <FolderX className="w-4 h-4" />
              Ignored Directories
            </div>
          </button>
          <button
            onClick={() => setSettingsTab('capabilities')}
            className={cn(
              "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]",
              settingsTab === 'capabilities'
                ? "text-teal border-teal"
                : "text-ink/40 hover:text-ink/60 border-transparent"
            )}
          >
            <div className="flex items-center gap-2">
              <Box className="w-4 h-4" />
              Library Mappings
            </div>
          </button>
          <button
            onClick={() => setSettingsTab('database')}
            className={cn(
              "py-4 text-sm font-bold transition-all relative border-b-2 -mb-[2px]",
              settingsTab === 'database'
                ? "text-teal border-teal"
                : "text-ink/40 hover:text-ink/60 border-transparent"
            )}
          >
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              Database handling
            </div>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-7xl mx-auto w-full">
            {settingsTab === 'prompts' && <PromptsSettings />}
            {settingsTab === 'ignored_dirs' && <IgnoredDirsSettingsView />}
            {settingsTab === 'capabilities' && <CapabilitiesSettingsView />}
            {settingsTab === 'database' && (
              <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
                <div className="p-8 border border-destructive/20 rounded-2xl bg-destructive/5">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-destructive/10">
                      <Trash2 className="w-5 h-5 text-destructive" />
                    </div>
                    <h3 className="text-lg font-bold text-destructive uppercase tracking-widest">Danger Zone</h3>
                  </div>

                  <p className="text-sm text-ink-400 mb-8 max-w-2xl leading-relaxed">
                    Permanently delete all repositories, analyses, embeddings, and local storage. This action will completely reset the system state to its original configuration. Defaults will be re-seeded, but all user data will be lost forever.
                  </p>

                  <div className="flex flex-col items-start gap-4">
                    <div className="bg-white/50 border border-destructive/10 p-4 rounded-xl text-xs text-destructive/80 font-medium">
                      ⚠️ Caution: There is no undo for this operation.
                    </div>
                    <Button
                      variant="outline"
                      className="border-destructive/50 text-destructive hover:bg-destructive shadow-sm hover:text-white transition-all h-12 px-8 gap-3 font-bold"
                      onClick={() => setShowResetDialog(true)}
                      disabled={resetAllData.isPending}
                    >
                      {resetAllData.isPending ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <Trash2 className="w-5 h-5" />
                      )}
                      {resetAllData.isPending ? 'Resetting System...' : 'Reset All Data and Purge Database'}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <ConfirmationDialog
          isOpen={showResetDialog}
          onClose={() => setShowResetDialog(false)}
          onConfirm={() => {
            resetAllData.mutate(undefined, {
              onSuccess: () => setShowResetDialog(false),
            })
          }}
          title="Reset All Data"
          message="This will permanently delete all repositories, analyses, blueprints, and local storage files. Settings will be re-seeded to defaults. This action cannot be undone."
          confirmText="Reset Everything"
          destructive
          isLoading={resetAllData.isPending}
        />
      </div>
    </div>
  )
}

/* ── Prompts Settings ────────────────────────────────────────────── */

function PromptsSettings() {
  const { data: prompts, isLoading } = usePrompts()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    if (prompts && prompts.length > 0 && !selectedId) {
      setSelectedId(prompts[0].id)
    }
  }, [prompts, selectedId])

  const selectedPrompt = prompts?.find((p) => p.id === selectedId) ?? null

  if (isLoading) {
    return (
      <div className="grid grid-cols-[280px_1fr] gap-6">
        <Skeleton className="h-[600px] rounded-xl" />
        <Skeleton className="h-[600px] rounded-xl" />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-[280px_1fr] gap-6 items-start h-full">
      <PromptList
        prompts={prompts ?? []}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
      {selectedPrompt ? (
        <PromptEditor prompt={selectedPrompt} />
      ) : (
        <div className={cn("flex flex-col items-center justify-center p-12 h-[600px] border border-dashed border-papaya-400/50 rounded-3xl bg-white/30")}>
          <div className="p-6 rounded-full bg-white border border-papaya-400/50 mb-6 text-ink/10 shadow-sm">
            <FileCode className="w-12 h-12" />
          </div>
          <h3 className="text-xl font-bold text-ink">No Template Selected</h3>
          <p className="text-sm text-ink-400 text-center max-w-[320px] mt-2 leading-relaxed">
            Select a prompt from the library on the left to view and edit its content.
          </p>
        </div>
      )}
    </div>
  )
}

/* ── Prompt List Sidebar ───────────────────────────────────────────── */

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
    <div className="shrink-0 w-72 flex flex-col border border-papaya-400/50 rounded-2xl overflow-hidden bg-white/40 h-[700px]">
      <div className="px-5 py-5 border-b border-papaya-400/50 bg-papaya-300/20">
        <h3 className="text-[10px] font-black uppercase tracking-widest text-ink/40 flex items-center gap-2">
          <FileCode className="w-4 h-4" />
          Prompt Library
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto">
        {prompts.map((p) => (
          <button
            key={p.id}
            className={cn(
              'w-full text-left px-5 py-4 text-sm transition-all group relative border-b border-papaya-400/30 last:border-0',
              selectedId === p.id
                ? "bg-white/60 text-ink"
                : "bg-transparent text-ink/40 hover:bg-white/30 hover:text-ink/60"
            )}
            onClick={() => onSelect(p.id)}
          >
            {selectedId === p.id && (
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-teal shadow-[2px_0_8px_rgba(45,212,191,0.3)]" />
            )}
            <div className="flex items-center gap-4">
              <ChevronRight
                className={cn(
                  'w-4 h-4 shrink-0 transition-transform duration-200 text-teal',
                  selectedId === p.id ? 'rotate-90 opacity-100' : 'opacity-0 group-hover:opacity-100'
                )}
              />
              <div className="min-w-0">
                <div className="font-semibold truncate text-[13px] leading-tight mb-0.5">
                  {p.name}
                </div>
                {p.key && (
                  <div className="text-[10px] font-mono opacity-60 truncate">
                    {p.key}
                  </div>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── Prompt Editor ────────────────────────────────────────────────── */

function PromptEditor({ prompt }: { prompt: Prompt }) {
  const [name, setName] = useState(prompt.name)
  const [template, setTemplate] = useState(prompt.prompt_template)
  const [changeSummary, setChangeSummary] = useState('')
  const [showRevisions, setShowRevisions] = useState(false)

  const updateMutation = useUpdatePrompt()

  useEffect(() => {
    setName(prompt.name)
    setTemplate(prompt.prompt_template)
    setChangeSummary('')
    setShowRevisions(false)
  }, [prompt.id])

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
    <div className="flex-1 space-y-6 animate-in slide-in-from-right-4 duration-500">
      <div className={cn("border border-papaya-400/60 rounded-2xl shadow-md overflow-hidden bg-white/60", theme.surface.panelStrong)}>
        <div className="px-8 py-6 border-b border-papaya-400/60 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-white flex items-center justify-center border border-papaya-400/60 shadow-sm shrink-0">
              <Zap className="w-5 h-5 text-ink-300" />
            </div>
            <div>
              <h3 className="font-bold text-xl tracking-tight text-ink leading-none">{prompt.name}</h3>
              <div className="flex items-center gap-2 mt-1.5">
                {prompt.key && (
                  <code className="text-[10px] px-1.5 py-0.5 bg-background rounded font-mono border border-papaya-400/60 text-ink/60">
                    {prompt.key}
                  </code>
                )}
                <Badge className="bg-white text-[10px] font-black uppercase tracking-widest border border-papaya-400/60 text-ink/40">{prompt.category}</Badge>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-9 gap-2 border-papaya-400/60 text-ink/60 hover:bg-papaya-300/20"
              onClick={() => setShowRevisions(!showRevisions)}
            >
              <History className="w-4 h-4" />
              {showRevisions ? 'Hide History' : 'View History'}
            </Button>
            <Button
              size="sm"
              className={cn("h-9 gap-2", isDirty ? theme.interactive.cta : "")}
              onClick={handleSave}
              disabled={!isDirty || updateMutation.isPending}
            >
              <Save className="w-4 h-4" />
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </div>

        <div className="p-8 space-y-8">
          <div className="space-y-2.5">
            <label className="text-[11px] font-black text-ink/30 uppercase tracking-widest block">
              Display Name
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={cn("h-11 px-4 text-base font-semibold transition-all bg-white/50", theme.surface.inputBorder, theme.interactive.focusRing)}
            />
          </div>

          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-black text-ink/30 uppercase tracking-widest block">
                Prompt Template
              </label>
              {prompt.variables.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-ink/20 mr-1 uppercase font-bold">Injectables:</span>
                  {prompt.variables.map((v) => (
                    <code key={v} className="text-[10px] px-1.5 py-0.5 bg-background rounded font-mono border border-papaya-400/40 text-ink/60">
                      {`{${v}}`}
                    </code>
                  ))}
                </div>
              )}
            </div>
            <textarea
              className={cn(
                "w-full min-h-[400px] rounded-xl border bg-white/80 px-4 py-3 text-[13px] font-mono leading-relaxed transition-all focus:outline-none focus:ring-2 focus:ring-teal/30 shadow-inner resize-y",
                theme.surface.inputBorder
              )}
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              placeholder="Enter AI prompt template here..."
            />
          </div>

          <div className="space-y-2.5 pt-6 border-t border-papaya-400/40">
            <label className="text-[11px] font-black text-ink/30 uppercase tracking-widest block">
              Revision Note (Required for Save)
            </label>
            <Input
              placeholder="e.g. Optimized security context, updated formatting rules..."
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
              className={cn("h-11 px-4 transition-all italic bg-white/50", theme.surface.inputBorder)}
            />
          </div>
        </div>
      </div>

      {showRevisions && (
        <div className="animate-in slide-in-from-top-4 duration-500">
          <RevisionHistory promptId={prompt.id} />
        </div>
      )}
    </div>
  )
}

/* ── Revision History ─────────────────────────────────────────────── */

function RevisionHistory({ promptId }: { promptId: string }) {
  const { data: revisions, isLoading } = usePromptRevisions(promptId)
  const revertMutation = useRevertPrompt()

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center h-48 border border-dashed border-papaya-400/60 rounded-2xl">
        <Loader2 className="w-6 h-6 animate-spin text-ink/20" />
      </div>
    )
  }

  if (!revisions?.length) {
    return (
      <div className="p-12 flex flex-col items-center justify-center border border-dashed border-papaya-400/60 rounded-2xl bg-white/20">
        <History className="w-8 h-8 text-ink/20 mb-3" />
        <p className="text-sm font-medium text-ink-300">No revision history found.</p>
      </div>
    )
  }

  return (
    <div className="border border-papaya-400/60 rounded-2xl shadow-lg overflow-hidden bg-white/40">
      <div className="bg-papaya-300/30 px-6 py-4 border-b border-papaya-400/60">
        <h4 className="text-[11px] font-black uppercase tracking-widest text-ink/40 flex items-center gap-2">
          <History className="w-3.5 h-3.5" /> Revision History
        </h4>
      </div>
      <div className="max-h-[400px] overflow-y-auto divide-y divide-papaya-400/30">
        {revisions.map((rev) => (
          <div
            key={rev.id}
            className="flex items-center justify-between p-5 hover:bg-white/40 transition-colors group"
          >
            <div className="flex-1 min-w-0 flex items-start gap-4">
              <div className="w-9 h-9 rounded-full bg-white text-ink-400 border border-papaya-400/50 shadow-sm flex items-center justify-center text-xs font-bold shrink-0">
                {rev.revision_number}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-ink flex items-center gap-2">
                  <span>Update #{rev.revision_number}</span>
                  <span className="w-1 h-1 rounded-full bg-ink/20" />
                  <span className="text-xs text-ink/40 font-normal">
                    {new Date(rev.created_at).toLocaleString()}
                  </span>
                </div>
                {rev.change_summary ? (
                  <p className="text-xs text-ink-400 mt-1 leading-relaxed italic">
                    "{rev.change_summary}"
                  </p>
                ) : (
                  <p className="text-xs text-ink/20 mt-1 italic">
                    No summary provided
                  </p>
                )}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="opacity-0 group-hover:opacity-100 transition-all h-8 border-papaya-400 shadow-sm"
              disabled={revertMutation.isPending}
              onClick={() => revertMutation.mutate({ promptId, revisionId: rev.id })}
            >
              <RotateCcw className="w-3 h-3 mr-2" />
              Revert
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}
