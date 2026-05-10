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

  if (error) return <div className="p-8 text-red-400">Failed to load: {error}</div>
  if (!status) return <div className="p-8">Loading…</div>
  if (!status.exists) return <IntentLayerEmptyState count={status.count} />
  if (!files) return <div className="p-8">Loading folders…</div>

  return (
    <div className="flex h-full">
      <aside className="w-72 border-r border-ink-800 overflow-y-auto p-4">
        <TreeNav paths={Object.keys(files)} selected={selected} onSelect={setSelected} />
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        {selected && <MarkdownPane content={files[selected]} />}
      </main>
    </div>
  )
}
