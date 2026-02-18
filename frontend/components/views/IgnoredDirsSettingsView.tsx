import { useState, useEffect } from 'react'
import { useIgnoredDirs, useUpdateIgnoredDirs, useResetIgnoredDirs } from '@/hooks/api/useSettings'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Save, RotateCcw, Plus, X, FolderX, AlertCircle, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'

export function IgnoredDirsSettingsView() {
  const { data: rows, isLoading } = useIgnoredDirs()
  const updateMutation = useUpdateIgnoredDirs()
  const resetMutation = useResetIgnoredDirs()

  const [dirs, setDirs] = useState<string[]>([])
  const [newDir, setNewDir] = useState('')
  const [initialized, setInitialized] = useState(false)

  // Derive the server-side list of names for dirty comparison
  const serverDirs = (rows ?? []).map((r) => r.directory_name).sort()

  useEffect(() => {
    if (rows && !initialized) {
      setDirs(rows.map((r) => r.directory_name))
      setInitialized(true)
    }
  }, [rows, initialized])

  // Sync from server after save/reset completes
  useEffect(() => {
    if (rows && initialized && !updateMutation.isPending && !resetMutation.isPending) {
      setDirs(rows.map((r) => r.directory_name))
    }
  }, [rows])

  const isDirty = JSON.stringify([...dirs].sort()) !== JSON.stringify(serverDirs)

  const handleAdd = () => {
    const trimmed = newDir.trim()
    if (trimmed && !dirs.includes(trimmed)) {
      setDirs([...dirs, trimmed])
      setNewDir('')
    }
  }

  const handleRemove = (dir: string) => {
    setDirs(dirs.filter((d) => d !== dir))
  }

  const handleSave = () => {
    updateMutation.mutate(dirs)
  }

  const handleReset = () => {
    if (window.confirm("Are you sure you want to reset ignored directories to defaults?")) {
      resetMutation.mutate(undefined, {
        onSuccess: () => setInitialized(false),
      })
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAdd()
    }
  }

  if (isLoading) {
    return (
      <Card className="border shadow-sm">
        <CardContent className="py-12 flex flex-col items-center">
          <Skeleton className="h-12 w-12 rounded-full mb-4" />
          <Skeleton className="h-4 w-64 mb-2" />
          <Skeleton className="h-4 w-48" />
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500">
      <Card className={cn("border-none shadow-none bg-transparent")}>
        <div className="pb-6 border-b border-papaya-400/50">
          <h3 className="text-2xl font-bold tracking-tight text-ink">Ignored Directories</h3>
          <p className="text-sm text-ink-400 mt-1">
            Configure which folders should be skipped during architecture discovery.
          </p>
        </div>

        <div className="mt-8 space-y-8">
          <div className={cn("p-5 rounded-2xl border flex gap-4 bg-white/40 border-papaya-400/50")}>
            <div className="w-10 h-10 rounded-full bg-white border border-papaya-400/50 flex items-center justify-center shrink-0">
              <Info className="w-5 h-5 text-ink/40" />
            </div>
            <div className="text-[13px] text-ink-400 leading-relaxed">
              <p className="font-bold uppercase tracking-wider mb-0.5 text-ink">Discovery logic</p>
              Directories listed here are excluded from code analysis. Manifest files (package.json, etc.)
              will still be scanned to identify project dependencies.
            </div>
          </div>

          <div className="space-y-4">
            <label className="text-[11px] font-black text-ink/30 uppercase tracking-widest block">
              Configured Filters
            </label>
            <div className="flex flex-wrap gap-2 min-h-[120px] p-6 rounded-2xl bg-papaya-300/20 border-2 border-dashed border-papaya-400/50 relative">
              {dirs.length === 0 && (
                <div className="absolute inset-0 flex items-center justify-center text-ink/20 text-sm">
                  No directories currently ignored
                </div>
              )}
              {dirs.map((dir) => (
                <div
                  key={dir}
                  className="flex items-center gap-2 pl-4 pr-2 py-2 bg-white border border-papaya-400/50 rounded-xl shadow-sm group hover:border-teal/30 hover:shadow-md transition-all animate-in zoom-in-95 duration-200"
                >
                  <span className="text-sm font-mono font-bold text-ink">{dir}</span>
                  <button
                    className="p-1.5 rounded-lg text-ink/30 hover:text-white hover:bg-brandy transition-all"
                    onClick={() => handleRemove(dir)}
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <label className="text-[11px] font-black text-ink/30 uppercase tracking-widest block">
              Add New Filter
            </label>
            <div className="flex gap-3">
              <div className="relative flex-1 group">
                <FolderX className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-300 group-focus-within:text-teal transition-colors" />
                <Input
                  placeholder="e.g. build, artifacts, coverage..."
                  value={newDir}
                  onChange={(e) => setNewDir(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className={cn(
                    "h-12 pl-12 px-6 font-mono text-lg transition-all bg-white",
                    theme.surface.inputBorder,
                    theme.interactive.focusRing
                  )}
                />
              </div>
              <Button
                onClick={handleAdd}
                disabled={!newDir.trim()}
                className={cn("h-12 px-8 shadow-lg", theme.active.checkBtn)}
              >
                <Plus className="w-5 h-5 mr-2" />
                Add Entry
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between pt-8 border-t border-papaya-400/50 gap-4">
            <div className="flex items-center gap-2">
              {isDirty && (
                <div className="flex items-center gap-1.5 text-xs text-tangerine font-black bg-tangerine/10 px-3 py-1.5 rounded-full border border-tangerine/20">
                  <AlertCircle className="w-4 h-4" />
                  UNSAVED CHANGES
                </div>
              )}
            </div>
            <div className="flex items-center gap-4">
              <Button
                variant="outline"
                size="lg"
                onClick={handleReset}
                disabled={resetMutation.isPending}
                className="h-12 px-8 border-dashed border-papaya-400 hover:bg-papaya-300/50"
              >
                <RotateCcw className="w-4 h-4 mr-2" />
                Reset Defaults
              </Button>
              <Button
                onClick={handleSave}
                disabled={!isDirty || updateMutation.isPending}
                className={cn("h-12 px-10 min-w-[180px] shadow-xl", isDirty ? theme.interactive.cta : "")}
              >
                {updateMutation.isPending ? (
                  <RotateCcw className="w-5 h-5 mr-2 animate-spin" />
                ) : (
                  <Save className="w-5 h-5 mr-2" />
                )}
                {updateMutation.isPending ? 'Syncing...' : 'Apply Filters'}
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
