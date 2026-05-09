import { useEffect, useState } from 'react'
import ReportPage from './ReportPage'
import type { Bundle } from '@/lib/api'

export default function LocalPage() {
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const [error, setError] = useState<string | null>(null)

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
  return <ReportPage bundle={bundle} />
}
