import { useEffect, useState } from 'react'
import { fetchExposure, postExposure, type ExposureData } from '@/lib/api'

const CATEGORY_LABELS: Record<string, string> = {
  rules: 'Rules',
  folder_context: 'Per-folder context',
  blueprint: 'Blueprint',
  findings: 'Findings',
}

const CATEGORY_ORDER = ['rules', 'folder_context', 'blueprint', 'findings']

export default function ExposurePanel() {
  const [data, setData] = useState<ExposureData | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    fetchExposure().then(setData).catch((e) => setErr(e.message))
  }, [])

  if (err) return <div className="p-12 text-red-600">{err}</div>
  if (!data) return <div className="p-12 text-ink/60">Loading…</div>

  if (data.mode !== 'detached') {
    return (
      <div className="p-12 max-w-2xl">
        <h2 className="text-xl font-black tracking-tight text-ink mb-3">
          Exposure control
        </h2>
        <p className="text-ink/70 leading-relaxed">
          Exposure control is available only in <b>detached</b> mode. This
          project runs in <b>repo</b> mode — Archie's artifacts are committed
          files in the working tree, so there are no symlinks to gate. Re-install
          with <code className="text-teal-700">--detached</code> to manage what
          the coding agent can see.
        </p>
      </div>
    )
  }

  const toggleCategory = async (key: string, value: boolean) => {
    try {
      setData(await postExposure('category', key, value))
    } catch (e) {
      setErr((e as Error).message)
    }
  }
  const togglePath = async (path: string, value: boolean) => {
    try {
      setData(await postExposure('path', path, value))
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  const byCat: Record<string, ExposureData['placements']> = {}
  for (const p of data.placements) (byCat[p.category] ||= []).push(p)

  return (
    <div className="p-8 max-w-3xl space-y-5">
      <div>
        <h2 className="text-xl font-black tracking-tight text-ink mb-2">
          Exposure control
        </h2>
        <p className="text-sm text-ink/60 leading-relaxed">
          Toggle what the coding agent can see — and what gets enforced. Turning
          a category off removes the symlink from the working tree; the artifact
          stays safe in the external store and can be restored anytime.
        </p>
      </div>

      {CATEGORY_ORDER.map((cat) => {
        const overrides = (byCat[cat] || []).filter((p) =>
          p.path.endsWith('CLAUDE.md'),
        )
        return (
          <div
            key={cat}
            className="border border-papaya-300/40 rounded-2xl p-4 bg-white"
          >
            <label className="flex items-center gap-3 font-semibold text-ink cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 accent-teal-600"
                checked={data.categories[cat] ?? true}
                onChange={(e) => toggleCategory(cat, e.target.checked)}
              />
              {CATEGORY_LABELS[cat] || cat}
            </label>

            {overrides.length > 0 && (
              <details className="mt-3 ml-7">
                <summary className="cursor-pointer text-sm text-ink/60 select-none">
                  Per-file overrides ({overrides.length})
                </summary>
                <ul className="mt-2 space-y-1.5">
                  {overrides.map((p) => (
                    <li
                      key={p.path}
                      className="flex items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        className="w-3.5 h-3.5 accent-teal-600"
                        checked={p.exposed}
                        onChange={(e) => togglePath(p.path, e.target.checked)}
                      />
                      <code className="text-ink/70">{p.path}</code>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )
      })}
    </div>
  )
}
