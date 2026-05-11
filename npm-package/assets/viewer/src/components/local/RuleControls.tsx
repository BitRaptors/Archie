import { useState } from 'react'
import RuleEditModal from './RuleEditModal'

interface Props {
  rule: { id: string; description?: string; why?: string; example?: string; severity_class?: string }
  state: 'active' | 'proposed' | 'ignored'
  onAction: (action: 'adopt' | 'reject' | 'disable' | 'enable') => Promise<void>
  onEdit: (patch: Record<string, string>) => Promise<void>
}

// Compact pill-shaped buttons so the controls feel native to the light blueprint
// surface. Adopt/enable lean teal (positive accent); reject/disable stay muted
// ink (destructive without being loud); edit is neutral ink/70.
const BTN_BASE =
  'inline-flex items-center justify-center w-7 h-7 rounded-lg text-sm font-bold transition-colors ring-1 ring-inset'

export default function RuleControls({ rule, state, onAction, onEdit }: Props) {
  const [editing, setEditing] = useState(false)
  return (
    <div className="flex gap-1.5 ml-auto">
      {state === 'proposed' && (
        <>
          <button
            onClick={() => onAction('adopt')}
            className={`${BTN_BASE} text-teal-700 ring-teal-500/30 hover:bg-teal-500/10`}
            title="Adopt"
          >
            ✓
          </button>
          <button
            onClick={() => onAction('reject')}
            className={`${BTN_BASE} text-ink/50 ring-ink/15 hover:bg-ink/5 hover:text-ink/70`}
            title="Reject"
          >
            ✕
          </button>
        </>
      )}
      {state === 'active' && (
        <>
          <button
            onClick={() => setEditing(true)}
            className={`${BTN_BASE} text-ink/70 ring-ink/15 hover:bg-ink/5 hover:text-ink`}
            title="Edit"
          >
            ✎
          </button>
          <button
            onClick={() => onAction('disable')}
            className={`${BTN_BASE} text-ink/50 ring-ink/15 hover:bg-ink/5 hover:text-ink/70`}
            title="Disable"
          >
            🔒
          </button>
        </>
      )}
      {state === 'ignored' && (
        <button
          onClick={() => onAction('enable')}
          className={`${BTN_BASE} text-teal-700 ring-teal-500/30 hover:bg-teal-500/10`}
          title="Enable"
        >
          🔓
        </button>
      )}
      {editing && (
        <RuleEditModal
          rule={rule}
          onSave={(patch) => onEdit(patch).finally(() => setEditing(false))}
          onCancel={() => setEditing(false)}
        />
      )}
    </div>
  )
}
