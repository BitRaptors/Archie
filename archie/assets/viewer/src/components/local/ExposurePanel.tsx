import { useEffect, useState } from 'react'
import { fetchExposure, postExposure, type ExposureData } from '@/lib/api'

// The two groups of generated markdown the agent reads. This is purely about
// VISIBILITY (which files the agent can see) — it is NOT rule-curation /
// enforcement (rules.json), which is a separate feature. Detached mode only.
const GROUPS: { key: string; label: string; hint: string }[] = [
  {
    key: 'intent_layer',
    label: 'Intent-layer files',
    hint: 'Per-folder CLAUDE.md — Claude Code auto-loads these as it works in each directory.',
  },
  {
    key: 'blueprint',
    label: 'Blueprint docs',
    hint: '.claude/rules/*.md — the topic docs rendered from the blueprint.',
  },
]

export default function ExposurePanel() {
  const [data, setData] = useState<ExposureData | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    fetchExposure().then(setData).catch((e) => setErr(e.message))
  }, [])

  if (err) return <div className="p-12 text-red-600">{err}</div>
  if (!data) return <div className="p-12 text-ink/60">Loading…</div>

  // Defensive: this tab should not render at all in repo mode (LocalPage hides
  // it), but guard anyway.
  if (data.mode !== 'detached') return null

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

  const byGroup: Record<string, ExposureData['placements']> = {}
  for (const p of data.placements) (byGroup[p.category] ||= []).push(p)

  return (
    <div className="p-8 max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-black tracking-tight text-ink mb-2">
          Agent file visibility
        </h2>
        <p className="text-sm text-ink/60 leading-relaxed">
          Choose which generated markdown files the coding agent can see. Turning
          one off removes just that file from the working tree — the content
          stays safe in the external store and can be restored anytime. This does
          not touch rule enforcement.
        </p>
      </div>

      {GROUPS.map((group) => {
        const files = (byGroup[group.key] || []).slice().sort((a, b) =>
          a.path.localeCompare(b.path),
        )
        return (
          <div
            key={group.key}
            className="border border-papaya-300/40 rounded-2xl p-4 bg-white"
          >
            <label className="flex items-center gap-3 font-semibold text-ink cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 accent-teal-600"
                checked={data.categories[group.key] ?? true}
                onChange={(e) => toggleCategory(group.key, e.target.checked)}
              />
              {group.label}
              <span className="text-xs font-normal text-ink/40">
                ({files.length})
              </span>
            </label>
            <p className="text-xs text-ink/50 mt-1 ml-7">{group.hint}</p>

            {files.length > 0 && (
              <ul className="mt-3 ml-7 space-y-1.5">
                {files.map((p) => (
                  <li key={p.path} className="flex items-center gap-2 text-sm">
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
            )}
            {files.length === 0 && (
              <p className="text-xs text-ink/40 mt-3 ml-7 italic">
                None yet — run a scan to generate these.
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
