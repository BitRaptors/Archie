import { useEffect, useState } from 'react'
import MarkdownPane from './MarkdownPane'
import TreeNav from './TreeNav'

export default function GeneratedFilesBrowser() {
  const [files, setFiles] = useState<Record<string, string> | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/generated-files')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => {
        setFiles(data)
        const first = Object.keys(data)[0]
        if (first) setSelected(first)
      })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="p-8 text-red-400">Failed to load generated files: {error}</div>
  if (!files) return <div className="p-8">Loading…</div>
  if (Object.keys(files).length === 0)
    return <div className="p-8 text-papaya-300">No generated files yet — run /archie-scan first.</div>

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
