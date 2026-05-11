import { useEffect, useState } from 'react'
import MarkdownPane from './MarkdownPane'
import TreeNav from './TreeNav'
import IntentLayerEmptyState from './IntentLayerEmptyState'

export default function FolderClaudeMdsBrowser() {
  const [status, setStatus] = useState<{ exists: boolean; count: number } | null>(null)
  const [files, setFiles] = useState<Record<string, string> | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/intent-layer-status')
      .then((r) => {
        if (!r.ok) {
          throw new Error(
            r.status === 404
              ? 'This Archie viewer is out of date — /api/intent-layer-status missing. Stop the viewer.py process and relaunch it to pick up the new endpoints.'
              : `intent-layer-status HTTP ${r.status}`,
          )
        }
        return r.json()
      })
      .then((s: { exists: boolean; count: number }) => {
        setStatus(s)
        if (s.exists) {
          return fetch('/api/folder-claude-mds')
            .then((r) => {
              if (!r.ok) throw new Error(`folder-claude-mds HTTP ${r.status}`)
              return r.json()
            })
            .then((data: Record<string, string>) => {
              setFiles(data)
              const first = Object.keys(data)[0]
              if (first) setSelected(first)
            })
        }
      })
      .catch((e) => setError(e.message))
  }, [])

  if (error)
    return (
      <div className="bg-white border border-papaya-300/40 rounded-2xl p-8 shadow-sm text-red-600">
        Failed to load: {error}
      </div>
    )
  if (!status)
    return (
      <div className="bg-white border border-papaya-300/40 rounded-2xl p-8 shadow-sm text-ink/60">
        Loading…
      </div>
    )
  if (!status.exists) return <IntentLayerEmptyState count={status.count} />
  if (!files)
    return (
      <div className="bg-white border border-papaya-300/40 rounded-2xl p-8 shadow-sm text-ink/60">
        Loading folders…
      </div>
    )

  return (
    <div className="flex flex-col lg:flex-row gap-8 lg:gap-12 h-[calc(100vh-6rem)]">
      <aside className="lg:w-72 shrink-0 overflow-y-auto pr-2 custom-scrollbar">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-4 px-2">
          Folders
        </p>
        <TreeNav paths={Object.keys(files)} selected={selected} onSelect={setSelected} />
      </aside>
      <main className="flex-1 overflow-y-auto bg-white/60 backdrop-blur-xl border border-white/80 rounded-[32px] p-8 lg:p-16 shadow-2xl shadow-ink/5 custom-scrollbar relative">
        <div className="absolute inset-0 bg-gradient-to-br from-white/40 to-transparent rounded-[32px] pointer-events-none" />
        <div className="relative">
          {selected && <MarkdownPane content={files[selected]} />}
        </div>
      </main>
    </div>
  )
}
