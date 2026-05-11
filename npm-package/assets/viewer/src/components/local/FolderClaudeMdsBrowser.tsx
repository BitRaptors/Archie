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
      .then((r) => r.json())
      .then((s: { exists: boolean; count: number }) => {
        setStatus(s)
        if (s.exists) {
          return fetch('/api/folder-claude-mds')
            .then((r) => r.json())
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
    <div className="flex gap-6 h-[calc(100vh-6rem)]">
      <aside className="w-64 shrink-0 overflow-y-auto pr-2">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-4 px-2">
          Folders
        </p>
        <TreeNav paths={Object.keys(files)} selected={selected} onSelect={setSelected} />
      </aside>
      <main className="flex-1 overflow-y-auto bg-white border border-papaya-300/40 rounded-2xl p-8 lg:p-10 shadow-sm">
        {selected && <MarkdownPane content={files[selected]} />}
      </main>
    </div>
  )
}
