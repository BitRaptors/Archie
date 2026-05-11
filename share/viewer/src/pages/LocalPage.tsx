import { useEffect, useState, lazy, Suspense } from 'react'
import ReportPage from './ReportPage'
import type { Bundle } from '@/lib/api'
import { LocalEditContext, type LocalEditCtx } from '@/components/local/context/LocalEditContext'
import Toast from '@/components/local/Toast'

const GeneratedFilesBrowser = lazy(() => import('@/components/local/GeneratedFilesBrowser'))
const FolderClaudeMdsBrowser = lazy(() => import('@/components/local/FolderClaudeMdsBrowser'))

type Tab = 'report' | 'generated' | 'folders'

export default function LocalPage() {
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('report')
  const [toast, setToast] = useState<string | null>(null)
  const [bundleVersion, setBundleVersion] = useState(0)

  const ctx: LocalEditCtx = {
    toggleRule: async (id, action) => {
      const res = await fetch('/api/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, rule_id: id }),
      })
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
        setToast(`Failed: ${errBody.error || `HTTP ${res.status}`}`)
        return
      }
      setToast(`Rule ${id} ${action}d.`)
      setBundleVersion((v) => v + 1)
    },
    editRule: async (id, patch) => {
      const res = await fetch('/api/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'edit', rule_id: id, patch }),
      })
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
        setToast(`Failed: ${errBody.error || `HTTP ${res.status}`}`)
        return
      }
      setToast(`Rule ${id} updated.`)
      setBundleVersion((v) => v + 1)
    },
  }

  useEffect(() => {
    fetch('/api/bundle')
      .then((r) => {
        if (!r.ok) throw new Error(`Local bundle fetch failed (HTTP ${r.status}). Is /archie-scan run?`)
        return r.json()
      })
      .then((j) => setBundle(j.bundle))
      .catch((e) => setError(e.message))
  }, [bundleVersion])

  if (error) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <h1 className="text-2xl font-semibold mb-2">Local viewer</h1>
        <p className="text-red-600">{error}</p>
      </div>
    )
  }
  if (!bundle) return <div className="p-8 text-ink/60">Loading local bundle…</div>

  // Non-report tabs render inside ReportPage's chrome via mainContent. The
  // sidebar's blueprint sections collapse to just the VIEW switcher (handled
  // in ReportPage). Share-mode never sets localView/mainContent so the share
  // viewer renders identically to before.
  const tabContent =
    tab === 'generated' ? (
      <Suspense fallback={<div className="p-12 text-ink/60">Loading…</div>}>
        <GeneratedFilesBrowser />
      </Suspense>
    ) : tab === 'folders' ? (
      <Suspense fallback={<div className="p-12 text-ink/60">Loading…</div>}>
        <FolderClaudeMdsBrowser />
      </Suspense>
    ) : null

  return (
    <LocalEditContext.Provider value={ctx}>
      <ReportPage
        bundle={bundle}
        localView={{ active: tab, setActive: setTab }}
        mainContent={tabContent}
      />
      <Toast message={toast} onDismiss={() => setToast(null)} />
    </LocalEditContext.Provider>
  )
}
