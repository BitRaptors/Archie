import { useEffect, useState, lazy, Suspense } from 'react'
import ReportPage from './ReportPage'
import type { Bundle } from '@/lib/api'
import { LocalEditContext } from '@/components/local/context/LocalEditContext'

const GeneratedFilesBrowser = lazy(() => import('@/components/local/GeneratedFilesBrowser'))
const FolderClaudeMdsBrowser = lazy(() => import('@/components/local/FolderClaudeMdsBrowser'))

type Tab = 'report' | 'generated' | 'folders'

export default function LocalPage() {
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('report')

  useEffect(() => {
    fetch('/api/bundle')
      .then((r) => {
        if (!r.ok) throw new Error(`Local bundle fetch failed (HTTP ${r.status}). Is /archie-scan run?`)
        return r.json()
      })
      .then((j) => setBundle(j.bundle))
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <h1 className="text-2xl font-semibold mb-2">Local viewer</h1>
        <p className="text-red-600">{error}</p>
      </div>
    )
  }
  if (!bundle) return <div className="p-8">Loading local bundle…</div>

  return (
    <div className="min-h-screen flex flex-col">
      <TabBar tab={tab} onChange={setTab} />
      <div className="flex-1 min-h-0">
        {tab === 'report' && (
          <LocalEditContext.Provider value={null}>
            <ReportPage bundle={bundle} />
          </LocalEditContext.Provider>
        )}
        {tab === 'generated' && (
          <Suspense fallback={<div className="p-8">Loading…</div>}>
            <GeneratedFilesBrowser />
          </Suspense>
        )}
        {tab === 'folders' && (
          <Suspense fallback={<div className="p-8">Loading…</div>}>
            <FolderClaudeMdsBrowser />
          </Suspense>
        )}
      </div>
    </div>
  )
}

function TabBar({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: 'report', label: 'Report' },
    { id: 'generated', label: 'Generated Files' },
    { id: 'folders', label: 'Folder CLAUDE.mds' },
  ]
  return (
    <nav className="flex gap-6 px-6 py-3 border-b border-ink-800 bg-ink-950/30">
      {tabs.map((t) => {
        const active = t.id === tab
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={
              active
                ? 'text-papaya-100 border-b-2 border-tangerine-500 pb-1 text-sm font-semibold'
                : 'text-papaya-300 hover:text-papaya-100 pb-1 text-sm font-semibold'
            }
          >
            {t.label}
          </button>
        )
      })}
    </nav>
  )
}
