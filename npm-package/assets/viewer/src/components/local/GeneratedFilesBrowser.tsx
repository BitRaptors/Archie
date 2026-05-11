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
        if (!r.ok) {
          throw new Error(
            r.status === 404
              ? 'This Archie viewer is out of date — /api/generated-files missing. Stop the viewer.py process and relaunch it to pick up the new endpoints.'
              : `HTTP ${r.status}`,
          )
        }
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
    <div className="flex flex-col lg:flex-row gap-8 lg:gap-12 h-[calc(100vh-6rem)]">
      <aside className="lg:w-72 shrink-0 overflow-y-auto pr-2 custom-scrollbar">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/30 mb-4 px-2">
          Files
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
