import { useState } from 'react'

const SEVERITIES = ['decision_violation', 'pitfall_triggered', 'tradeoff_undermined', 'pattern_divergence', 'mechanical_violation']

interface Props {
  rule: { description?: string; why?: string; example?: string; severity_class?: string }
  onSave: (patch: Record<string, string>) => Promise<void>
  onCancel: () => void
}

export default function RuleEditModal({ rule, onSave, onCancel }: Props) {
  const [description, setDescription] = useState(rule.description || '')
  const [why, setWhy] = useState(rule.why || '')
  const [example, setExample] = useState(rule.example || '')
  const [severity, setSeverity] = useState(rule.severity_class || 'pattern_divergence')

  return (
    <div className="fixed inset-0 bg-ink-950/80 flex items-center justify-center z-50">
      <div className="bg-ink-900 border border-ink-700 rounded-lg p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
        <h3 className="text-lg font-semibold mb-4">Edit rule</h3>
        <label className="block mb-2 text-sm text-papaya-300">Description</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full bg-ink-800 border border-ink-700 rounded px-3 py-2 mb-3 text-papaya-100" rows={2} />
        <label className="block mb-2 text-sm text-papaya-300">Why</label>
        <textarea value={why} onChange={(e) => setWhy(e.target.value)} className="w-full bg-ink-800 border border-ink-700 rounded px-3 py-2 mb-3 text-papaya-100" rows={4} />
        <label className="block mb-2 text-sm text-papaya-300">Example</label>
        <textarea value={example} onChange={(e) => setExample(e.target.value)} className="w-full bg-ink-800 border border-ink-700 rounded px-3 py-2 mb-3 text-papaya-100 font-mono text-sm" rows={4} />
        <label className="block mb-2 text-sm text-papaya-300">Severity class</label>
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="w-full bg-ink-800 border border-ink-700 rounded px-3 py-2 mb-4 text-papaya-100">
          {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="px-4 py-2 text-papaya-300 hover:text-papaya-100">Cancel</button>
          <button onClick={() => onSave({ description, why, example, severity_class: severity })} className="px-4 py-2 bg-tangerine-600 text-ink-900 rounded hover:bg-tangerine-500">Save</button>
        </div>
      </div>
    </div>
  )
}
