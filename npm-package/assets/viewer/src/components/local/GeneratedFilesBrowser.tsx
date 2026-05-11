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

  if (error)
    return (
      <div className="bg-white border border-papaya-300/40 rounded-2xl p-8 shadow-sm text-red-600">
        Failed to load generated files: {error}
      </div>
    )
  if (!files)
    return (
      <div className="bg-white border border-papaya-300/40 rounded-2xl p-8 shadow-sm text-ink/60">
        Loading…
      </div>
    )
  if (Object.keys(files).length === 0)
    return (
      <div className="bg-white border border-papaya-300/40 rounded-2xl p-8 shadow-sm text-ink/70">
        No generated files yet — run{' '}
        <code className="bg-papaya-100 text-teal-700 px-1.5 py-0.5 rounded font-semibold">
          /archie-scan
        </code>{' '}
        first.
      </div>
    )

  return (
    <div className="flex gap-6 h-[calc(100vh-6rem)]">
      <aside className="w-64 shrink-0 overflow-y-auto pr-2">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-4 px-2">
          Files
        </p>
        <TreeNav paths={Object.keys(files)} selected={selected} onSelect={setSelected} />
      </aside>
      <main className="flex-1 overflow-y-auto bg-white border border-papaya-300/40 rounded-2xl p-8 lg:p-10 shadow-sm">
        {selected && <MarkdownPane content={files[selected]} />}
      </main>
    </div>
  )
}
