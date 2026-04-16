import { useState } from 'react'
import { Trash2, Plus, ChevronDown, Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { isLocalMode } from '@/lib/data'

interface Rule {
  id: string
  severity: string
  description: string
  rationale?: string
  confidence?: number
  applies_to?: string
  source?: string
  check_type?: string
  check_value?: string
}

interface Props {
  adopted: Rule[]
  proposed?: Rule[]
  ignored?: Rule[]
  onRulesChange?: (rules: Rule[]) => void
}

export function RulesManagementSection({ adopted, proposed, ignored, onRulesChange }: Props) {
  const [filter, setFilter] = useState<'all' | 'error' | 'warn'>('all')
  const [showIgnored, setShowIgnored] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newRule, setNewRule] = useState({ id: '', severity: 'warn', description: '', rationale: '' })
  const local = isLocalMode()

  const filtered = adopted.filter(r =>
    filter === 'all' ? true : r.severity === filter
  )

  const saveRules = async (rules: Rule[]) => {
    if (!local) return
    await fetch('/api/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    })
    onRulesChange?.(rules)
  }

  const handleDelete = (id: string) => {
    const updated = adopted.filter(r => r.id !== id)
    saveRules(updated)
  }

  const handleSeverityChange = (id: string, severity: string) => {
    const updated = adopted.map(r => r.id === id ? { ...r, severity } : r)
    saveRules(updated)
  }

  const handleAdopt = (rule: Rule) => {
    const updated = [...adopted, { ...rule, source: 'proposed' }]
    saveRules(updated)
  }

  const handleAddRule = () => {
    if (!newRule.id || !newRule.description) return
    const updated = [...adopted, { ...newRule, source: 'manual' }]
    saveRules(updated)
    setNewRule({ id: '', severity: 'warn', description: '', rationale: '' })
    setShowAddForm(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        {(['all', 'error', 'warn'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              'px-3 py-1 rounded-lg text-xs font-bold transition-colors',
              filter === f ? 'bg-teal text-white' : 'bg-papaya-50 text-ink/40 hover:text-ink'
            )}
          >
            {f === 'all' ? `All (${adopted.length})` : `${f} (${adopted.filter(r => r.severity === f).length})`}
          </button>
        ))}
        {local && (
          <button
            onClick={() => setShowAddForm(true)}
            className="ml-auto px-3 py-1 rounded-lg text-xs font-bold bg-teal/10 text-teal hover:bg-teal/20 flex items-center gap-1"
          >
            <Plus className="w-3 h-3" /> Add Rule
          </button>
        )}
      </div>

      {showAddForm && local && (
        <div className="border border-teal/30 rounded-2xl p-4 space-y-3 bg-teal/5">
          <input
            placeholder="Rule ID (e.g. no-direct-db-access)"
            value={newRule.id}
            onChange={e => setNewRule(prev => ({ ...prev, id: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-papaya-300 text-sm bg-white"
          />
          <select
            value={newRule.severity}
            onChange={e => setNewRule(prev => ({ ...prev, severity: e.target.value }))}
            className="px-3 py-2 rounded-lg border border-papaya-300 text-sm bg-white"
          >
            <option value="error">Error</option>
            <option value="warn">Warning</option>
          </select>
          <textarea
            placeholder="Description"
            value={newRule.description}
            onChange={e => setNewRule(prev => ({ ...prev, description: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-papaya-300 text-sm bg-white"
            rows={2}
          />
          <textarea
            placeholder="Rationale (optional)"
            value={newRule.rationale}
            onChange={e => setNewRule(prev => ({ ...prev, rationale: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-papaya-300 text-sm bg-white"
            rows={2}
          />
          <div className="flex gap-2">
            <button onClick={handleAddRule} className="px-3 py-1 rounded-lg text-xs bg-teal text-white font-bold flex items-center gap-1">
              <Check className="w-3 h-3" /> Save
            </button>
            <button onClick={() => setShowAddForm(false)} className="px-3 py-1 rounded-lg text-xs bg-papaya-50 text-ink/50 font-bold flex items-center gap-1">
              <X className="w-3 h-3" /> Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {filtered.map(rule => (
          <div key={rule.id} className="border border-papaya-400/60 rounded-2xl p-4 bg-white/60">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  {local ? (
                    <select
                      value={rule.severity}
                      onChange={e => handleSeverityChange(rule.id, e.target.value)}
                      className={cn(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full border-0',
                        rule.severity === 'error' ? 'bg-brandy/10 text-brandy' : 'bg-tangerine/10 text-tangerine-700'
                      )}
                    >
                      <option value="error">error</option>
                      <option value="warn">warn</option>
                    </select>
                  ) : (
                    <span className={cn(
                      'text-[10px] font-bold px-2 py-0.5 rounded-full',
                      rule.severity === 'error' ? 'bg-brandy/10 text-brandy' : 'bg-tangerine/10 text-tangerine-700'
                    )}>
                      {rule.severity}
                    </span>
                  )}
                  <code className="text-[11px] text-ink/40">{rule.id}</code>
                  {rule.source && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-papaya-50 text-ink/30">{rule.source}</span>
                  )}
                  {rule.confidence != null && rule.confidence < 100 && (
                    <span className="text-[10px] text-ink/30">{rule.confidence}%</span>
                  )}
                </div>
                <p className="text-sm text-ink">{rule.description}</p>
                {rule.rationale && <p className="text-xs text-ink/50 mt-1">{rule.rationale}</p>}
                {rule.applies_to && <code className="text-[10px] text-ink/30 mt-1 block">{rule.applies_to}</code>}
              </div>
              {local && (
                <button
                  onClick={() => handleDelete(rule.id)}
                  className="text-ink/20 hover:text-brandy transition-colors p-1"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {proposed && proposed.length > 0 && (
        <div>
          <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] mb-3">
            Proposed Rules ({proposed.length})
          </p>
          <div className="space-y-3">
            {proposed.map((rule: Rule) => (
              <div key={rule.id} className="border border-dashed border-teal/30 rounded-2xl p-4 bg-teal/5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full',
                        rule.severity === 'error' ? 'bg-brandy/10 text-brandy' : 'bg-tangerine/10 text-tangerine-700'
                      )}>
                        {rule.severity}
                      </span>
                      <code className="text-[11px] text-ink/40">{rule.id}</code>
                    </div>
                    <p className="text-sm text-ink">{rule.description}</p>
                    {rule.rationale && <p className="text-xs text-ink/50 mt-1">{rule.rationale}</p>}
                  </div>
                  {local && (
                    <button
                      onClick={() => handleAdopt(rule)}
                      className="px-3 py-1 rounded-lg text-xs bg-teal text-white font-bold"
                    >
                      Adopt
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {ignored && ignored.length > 0 && (
        <div>
          <button
            onClick={() => setShowIgnored(!showIgnored)}
            className="flex items-center gap-2 text-[11px] font-black text-ink/30 uppercase tracking-[0.15em]"
          >
            <ChevronDown className={cn('w-3 h-3 transition-transform', showIgnored && 'rotate-180')} />
            Ignored Rules ({ignored.length})
          </button>
          {showIgnored && (
            <div className="space-y-2 mt-2 opacity-50">
              {ignored.map((rule: Rule, i: number) => (
                <div key={i} className="border border-papaya-200 rounded-xl p-3 text-xs text-ink/40">
                  <code>{rule.id}</code> — {rule.description}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
